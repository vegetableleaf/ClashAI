"""Live 2v2 match environment for RL fine-tuning.

Wraps the same capture / vision / controller stack the policy plays on into a
minimal RL loop:

* `reset()` drives the scripted menu navigation (HOME -> party -> quick match)
  until a match starts, then returns the first observation.
* `step(action)` plays a card (or waits), advances one action period, and returns
  `(obs, reward, done, info)`. Reward = per-step tower shaping while in a match;
  on match end it resolves the **win/loss terminal reward** off the results
  scoreboard and drives the exit tap.

Actions are `(play, slot, cell)` where `play=0` is a deliberate no-op (wait /
save elixir) and `play=1` places hand `slot` at grid `cell` (decoded exactly like
the labeler/`play`).
"""
from __future__ import annotations

import math
import time
from typing import Optional, Tuple

import numpy as np

from .actions import ActionSpace
from .capture import WindowCapture
from .controller import Controller
from .outcome import outcome_reward, read_scoreboard
from . import threat_value
from .reward import (TowerTracker, _anchors, enemy_mass, near_enemy_king, near_enemy_princess, pump_rocket_cell, spell_intercept_cell, threat_side, weaker_princess_cell, xbow_lock_cell, xbow_offense_depth_cell, xbow_target_lane_cell, tesla_pull_cell)
from .reward import spell_whiffed, nado_regressed, lead_point, lead_velocity, log_hits
# deck-dependent aim cells: hogeq's reward.py has no tornado/log-corridor helpers
try:
    from .reward import nado_king_cell
except ImportError:
    nado_king_cell = None
try:
    from .reward import log_corridor_cell
except ImportError:
    log_corridor_cell = None

from .reward import TILE as _TILE
from .clock import ElixirClock
from .states import GameState
from .nav import MenuNavigator
from .threats import ThreatTracker, Threat
from . import card_threat
# Spawn-spells DEMAND an answer (the bodies land and walk); every other enemy spell is an effect
# that nothing counters, so it must not become a "threat" the referee expects a card for.
_SPAWN_SPELLS = frozenset({"graveyard", "goblin_barrel", "royal_delivery"})
from . import interactions
from . import replay_bc
from .cycle import CycleTracker
from .opponent_elixir import OpponentElixirEstimator
from .tower_hp import TowerHpTracker
from .vision import Vision

Action = Tuple[int, int, int]  # (play 0/1, card_id, cell)

# Crown-tower HP block width -- mirrors sim/view.TOWER_DIM: (L princess, R princess, king) x (mine, theirs).
# Kept as a local constant (not imported from sim.view) so the live path never drags in the sim engine.
_TOWER_DIM = 6


class _DetHold:
    """Short-lived memory of recent detections, to smooth DETECTOR FLICKER.

    MEASURED on data/sessions/20260815_222309 (72 consecutive frames, tracks matched by card
    within 0.06): a unit that is genuinely on the board is MISSING from 31% of the frames in
    its own lifespan, with 1.71 vanish-and-return events per track (gaps of 1-7 frames). The
    user sees this as boxes blinking in the overlay; the policy sees it as units popping out of
    the semantic + predictive canvases -- while the SIM trains on a perfect canvas
    (canvas_presence_recall was 1.0), so it never learned to cope with the gaps.

    A detection therefore survives `hold_s` seconds past its last sighting, re-emitted at its
    last known position, and is dropped the moment a fresher sighting of the same card lands
    nearby. The hold is deliberately SHORT: long enough to bridge the measured 1-3 frame gaps,
    far too short to keep a dead unit alive (a killed body stays gone after hold_s, so the trade
    ledger's vanish accounting is delayed by that much and no more).
    """

    def __init__(self, hold_s: float = 0.45, radius: float = 0.06):
        self.hold_s = float(hold_s)
        self.radius = float(radius)
        self._held: list = []          # [Detection, last_seen_t]

    def reset(self) -> None:
        self._held = []

    def merge(self, dets: list, now: float) -> list:
        fresh = list(dets or [])
        keep = []
        for d, t in self._held:
            if now - t > self.hold_s:
                continue                                  # expired -- let it go
            if any(f.base == d.base
                   and abs(f.cx - d.cx) + abs(f.gy - d.gy) <= self.radius for f in fresh):
                continue                                  # seen again this frame: the fresh one wins
            keep.append((d, t))
        out = fresh + [d for d, _ in keep]
        self._held = [(d, now) for d in fresh] + keep
        return out


class _BoardDet:
    """A Detection re-expressed in BOARD coordinates for the canonical renderer (which reads
    .cx/.gy/.team). The live detector reports FRAME coords; the sim renders board-true."""

    __slots__ = ("cx", "gy", "team", "base", "cls", "w", "h", "conf")

    def __init__(self, d, bx, by):
        self.cx, self.gy, self.team = bx, by, d.team
        self.base, self.cls = d.base, getattr(d, "cls", d.base)
        self.w, self.h, self.conf = d.w, d.h, d.conf


_RIVER_BOARD_Y = 0.5            # board-true river (the canonical render is drawn in board space)


class LiveMatchEnv:
    def __init__(self, cfg):
        self.cfg = cfg
        self.capture = WindowCapture(cfg.get("window", "title_contains", default=None),
                                     cfg.get("window", "region", default=None))
        self.vision = Vision(cfg)
        self.actions = ActionSpace(cfg)
        self.controller = Controller(self.capture, cfg)
        self.tower = TowerTracker(cfg)
        self.tower_hp = TowerHpTracker(cfg)
        self.clock = ElixirClock(cfg, self.vision)   # 2x/3x elixir multiplier (feeds the phase machine)
        self.elixir_mult = 1
        self.gw, self.gh = int(self.actions.gw), int(self.actions.gh)
        self.n_slots, self.n_cells = self.actions.n_slots, self.actions.n_cells

        self.act_period = float(cfg.get("play", "act_period", default=1.5))
        self.react_min_gap = float(cfg.get("play", "react_min_gap_s", default=0.3))
        self.poll_dt = 1.0 / float(cfg.get("nav", "poll_hz", default=6))
        self.menu_delay = float(cfg.get("nav", "menu_delay", default=1.0))
        self.results_timeout = float(cfg.get("env", "results_timeout", default=30.0))

        self.battle = cfg.get("buttons", "battle_button", default=[0.5, 0.9])
        self.quick = cfg.get("buttons", "quick_match", default=[0.5, 0.55])
        self.results_ok = cfg.get("buttons", "results_ok", default=[0.5, 0.9])
        self.results_dc = cfg.get("buttons", "results_ok_dc", default=self.results_ok)
        self.play_again = cfg.get("buttons", "play_again", default=self.results_ok)
        _home = cfg.get("states", "home_menu", default={}) or {}
        self._home_tpl = _home.get("template", "home_menu.png")
        self._home_thr = float(_home.get("threshold", 0.8))
        self._nav = MenuNavigator(cfg, self.controller, self.vision, label="train-rl")

        ow, oh = cfg.get("observation", "arena_size", default=[64, 96])
        # OBS-CANVAS FLIP: the image branch gains detect_obs's semantic channels when
        # observation.use_detector_canvas is on (gated on detect-eval's PRESENCE recall).
        from .detect_obs import canvas_enabled, obs_in_channels, CanvasStack, canvas_stack_len, canvas_stack_dt
        self.use_canvas = canvas_enabled(cfg)
        # CANVAS STACK: >1 carries the canvas as it looked canvas_stack_dt_s ago so the conv trunk
        # reads MOTION off the channel deltas. Sampled by TIMESTAMP because the act loop is
        # event-driven (wakes early on a new enemy), so consecutive decisions are NOT evenly spaced.
        self._canvas_stack = CanvasStack(canvas_stack_len(cfg), canvas_stack_dt(cfg))
        self.obs_shape = (int(oh), int(ow), obs_in_channels(cfg))
        self._last_obs = np.zeros(self.obs_shape, dtype=np.uint8)
        self.last_outcome: Optional[str] = None
        self.elixir = 0                 # your current elixir (0-10), updated each step
        self.elixir_vec = np.zeros(1, np.float32)   # normalized elixir [0,1] -> policy input
        self.n_cards = max(1, len(self.vision.deck_keys))
        # CHAMPION ABILITY: a pseudo-card in the action space that is a BUTTON on screen, not a tray
        # slot. Ported from play.py, which has always done this correctly -- train-rl had no ability
        # handling at all, so `_execute`'s slot lookup discarded every selection and the model could
        # never play it once. Same three rules as play.py: one tap, only while he is on the arena,
        # one activation per body.
        self.ability_id = (self.vision.deck_keys.index(self.vision.ability_key)
                           if getattr(self.vision, "ability_key", None) in self.vision.deck_keys
                           else -1)
        self.ability_xy = tuple(cfg.get("hand", "ability_button", default=[0.963, 0.758]))
        self._champ_base = (card_threat.base_key(self.vision.ability_key)
                            if getattr(self.vision, "ability_key", None) else None)
        self._ability_spent = False
        self.hand_ids = [-1] * self.n_slots            # deck index in each tray slot
        self.hand_vec = np.zeros(self.n_cards, np.float32)   # multi-hot of cards in hand
        self.next_id = -1                              # deck index of the next (preview) card
        self.next_vec = np.zeros(self.n_cards, np.float32)   # one-hot of the next card
        self._last_frame = None                        # last full BGR frame (spell before/after)

        # spell-effect + patience rewards
        from .cards import CardDB
        db = CardDB(cfg)
        # card-role id sets the reward + deploy logic still need (rocket/miner = anywhere; spell = eval;
        # x_bow = win condition; royal_delivery = defensive area spell; defensive_kind feeds reactive_ids).
        self.spell_ids = set()
        self.rocket_ids = set()
        self.royal_delivery_ids = set()
        self.tornado_ids = set()
        self.miner_ids = set()
        self.own_half_spell_ids = set()                 # RULING 18: spells placed like TROOPS
        self.xbow_ids = set()
        self.tesla_ids = set()                          # centre-pull assist target (see _lane_wincon)
        self.defensive_kind = {}                        # id -> defender kind (Tesla / Ice Wizard) for reactive_ids
        for i, key in enumerate(self.vision.deck_keys):
            base = key[:-4] if key.endswith("_evo") else key
            c = db.get(base)
            if c and c.get("kind") == "spell":
                self.spell_ids.add(i)
            if c and "own_half_only" in set(c.get("flags") or ()):
                self.own_half_spell_ids.add(i)          # RULING 18, see anywhere_ids below
            if base == "rocket":
                self.rocket_ids.add(i)
            elif base == "royal_delivery":          # defensive area spell on your half (long fixed delay)
                self.royal_delivery_ids.add(i)
            elif base == "tornado":                 # defensive PULL spell -> reacts to a push (near-immediate)
                self.tornado_ids.add(i)
            elif base == "miner":                   # tank/chip -> deployed ANYWHERE (enemy tower, behind a tank)
                self.miner_ids.add(i)
            elif base == "x_bow":                   # siege WIN CONDITION -> forward (in range) or back-centre defence
                self.xbow_ids.add(i)
            if base == "tesla":
                self.defensive_kind[i] = "tesla"
                self.tesla_ids.add(i)
            elif base == "ice_wizard":
                self.defensive_kind[i] = "ice_wizard"
        # EVERY SPELL MAY TARGET ANYWHERE, plus the deploy-anywhere troops (Miner / Goblin Drill).
        # This used to read `self.rocket_ids | self.miner_ids`, which is not the game's rule: it
        # confined Tornado, The Log and Earthquake to our own half, so the offensive Log, the
        # Tornado sneaky-lock at the river and the whole Hog+Earthquake combo were unreachable
        # actions rather than merely unlearned ones. `spell_ids` is already computed above from the
        # card DB's own `kind`, so the rule now comes from the cards instead of a literal.
        # RULING 18 (owner, 2026-08-27) carves ONE card back out, by KB flag rather than by literal:
        # Royal Delivery is a spell that DROPS A TROOP and is own-half-only (wiki Cards revid
        # 437053 names it, The Log and Barbarian Barrel as the three exceptions). Everything the
        # fix above rescued stays rescued -- see sim/env.py for the same carve-out and the tests
        # that pin it.
        self.anywhere_ids = (self.spell_ids | self.miner_ids) - self.own_half_spell_ids
        # cards played only to REACT to a threat (defenders + Royal Delivery / Tornado); on a QUIET board they're premature.
        self.reactive_ids = set(self.defensive_kind) | self.royal_delivery_ids | self.tornado_ids
        # --- perception geometry the reward + spell-impact timing still use ---
        # (spell_effect_reward is RETIRED: the spell-impact frame sampler was deleted with the
        # trade-potential rework -- consequences settle from the ordinary frame stream.)
        self.spell_eval_time = float(cfg.get("env", "spell_eval_time", default=2.4))
        self.spell_aim_radius = float(cfg.get("env", "spell_tower_aim_radius", default=0.12))
        # rocket / spell IMPACT timing -- predict when to grab the effect frame (see _impact_time)
        self.rocket_origin = cfg.get("env", "rocket_origin", default=[0.5, 1.05])
        self.rocket_base_time = float(cfg.get("env", "rocket_base_time", default=0.3))
        self.rocket_travel_rate = float(cfg.get("env", "rocket_travel_rate", default=2.2))
        self.tornado_time = float(cfg.get("env", "tornado_time", default=1.2))
        self.royal_delivery_time = float(cfg.get("env", "royal_delivery_time", default=3.0))
        # lane read for the threat-response intercept (_same_lane)
        self.threat_min_frac = float(cfg.get("env", "defense_threat_frac", default=0.02))
        self.lane_split_x = 0.48                       # left/right split -- matches reward.threat_side
        self.wrong_lane_margin = float(cfg.get("env", "wrong_lane_margin", default=0.12))
        self._match_bonus = 0.0
        self._match_penalty = 0.0        # symmetric twin of _match_bonus (see _bonus)
        # Per-term reward accounting -- which shaping term is actually driving the policy.
        from .reward_stats import RewardTerms
        self.rw_stats = RewardTerms()
        # LIVE SPELL-IMPACT VERIFICATION (2026-08-19). The spell-impact frame sampler was retired
        # (see the note above spell_effect_reward) and with it every consequence for a whiffed
        # spell: _wincon_exec_live pays AT CAST by aim geometry, so a rocket into empty grass
        # scored like a hit and `spell_waste` never fired live (user report). Every spell cast now
        # enqueues (impact time, aim, blast radius); at impact the TEAM TRACKER -- which bridges
        # detector misses for forget_s, so one blinked frame cannot fake a whiff -- is asked
        # whether any enemy is inside the blast. Tornados additionally snapshot what they pulled
        # and are re-checked ~4 s later for the BAD-PULL case: survivors dragged closer to our
        # towers with no kill and no king activation is worse than a whiff.
        self._pending_spells: list = []
        self._last_cast_rec = None       # the whiff record for THIS step's cast (see the tick)
        self._failed_deploys = 0         # taps that never moved the elixir bar (see the tick)
        self._failed_deploys_match = 0   # ... same, reset per match, so a RATE can be reported
        self._pending_deploys: list = []  # deploy checks awaiting evidence (settled >= 1.4s later)
        self._fast_tick = False          # this decision was woken by perception: skip slow reads
        self._last_mass = None           # last colour-mass estimate; None = never measured
        # WARNING: two other readers used getattr(self, "_last_mass", <default>) and relied on
        # BEING ABSENT to get that 0.0. Setting it to None here made getattr return None and
        # `None >= float` raised on the very first reset() -- I fixed one crash into another.
        # None is still the right sentinel for the fast-tick branch (it means "never measured", so
        # go measure), so the READERS coerce instead: (getattr(...) or 0.0).
        # /!\ MUST be initialised here, not only where it is computed. The fast-tick branch reads
        # `self._last_mass is not None` DIRECTLY (the two other readers correctly use
        # getattr(..., 0.0)), while the ONLY assignment lives in that branch's `else`. So a run
        # whose FIRST decision is perception-woken raised
        #     AttributeError: 'LiveMatchEnv' object has no attribute '_last_mass'
        # before the else had ever run. None is the sentinel the code already tests for; it was
        # simply never set. Timing-dependent, which is why it survived this long.
        # THE LOG'S ROLL, shared by the aim assist and the whiff verdict so they cannot disagree
        # about what the spell can touch.
        self.log_half_w = float(cfg.get("env", "log_half_width", default=0.064))
        self.log_roll = float(cfg.get("env", "log_roll_len", default=0.28))
        # ⚠ THIS WAS `db.names() if hasattr(db, "names") else []` AND CardDB HAS NO `names()`.
        # The hasattr guard therefore yielded [] every single time and `air_bases` was PERMANENTLY
        # EMPTY -- so `log_hits(..., air=air_bases)` never skipped a flying unit and every Log cast
        # on Minions / Bats / Balloon / Baby Dragon scored as a HIT in the live reward. The owner
        # reported this repeatedly ("play log on air troops, which somehow STILL registers a hit");
        # the guard itself was written correctly, it was iterating nothing. `is_flying` was fine all
        # along (minions -> True), so only the enumeration was broken.
        self.air_bases = frozenset(b for b in db.cards if db.is_flying(b))
        # LOUD, because the failure mode above is silent by construction: an empty set makes the
        # air rule vanish while every call still succeeds. §3q's rule -- if the line is absent, the
        # feature is not running.
        if not self.air_bases:
            print("[env] ⚠ air_bases is EMPTY -- the Log's air exclusion is INERT. "
                  "log_hits() will score casts on flying units as hits.")
        else:
            print("[env] air_bases: %d flying cards (log rolls under them)" % len(self.air_bases))
        self.fast_reaction_tick = bool(cfg.get("env", "fast_reaction_tick", default=True))
        # How long to wait before judging whether a card left the bar. The tap, the deploy
        # animation and the bar redraw all have to finish first; judging in the same step read a
        # bar that had not updated yet and cried wolf on cards that were plainly played.
        self.deploy_verify_s = float(cfg.get("env", "deploy_verify_s", default=1.4))
        # TORNADO -> ROCKET: the deck's signature combo is a SAME-TILE play, so the last tornado's
        # cast point and time are remembered for the rocket that should follow it.
        self._last_nado = None           # (cx, cy, t_cast) of the most recent tornado cast
        self._last_rocket = None         # (cx, cy, t_impact) of the most recent rocket cast
        # A tornado's pull is SHORT. The combo works only when the rocket's blast lands while that
        # pull is still gathering the clump, which is why doctrine is "rocket FIRST, then tornado
        # onto the blast point" (DOCTRINE_RESEARCH.md R6): a tornado cast first has already let go
        # by the time a slow rocket arrives.
        self.nado_pull_s = float(cfg.get("env", "nado_pull_s", default=1.05))
        self.rocket_nado_window_s = float(cfg.get("env", "rocket_nado_window_s", default=2.5))
        self.rocket_nado_radius = float(cfg.get("env", "rocket_nado_radius", default=0.11))
        self.rocket_nado_mult = float(cfg.get("rewards", "rocket_nado_mult", default=3.0))
        # a combo must CATCH something: enemy elixir inside the pull, mirroring the sim's gate
        self.rocket_min_worth = float(cfg.get("rewards", "rocket_min_worth", default=4.0))
        # A spell verdict runs on FRESH sightings only: a false positive is remembered exactly as
        # long as a real unit, so 4.5 s of memory made every cast at a ghost look like a hit.
        self.spell_verify_fresh_s = float(cfg.get("env", "spell_verify_fresh_s", default=0.8))
        # SECONDS FOR THE LOG TO FINISH ROLLING: 9.6 tiles at 2.83 tiles/s (wiki projectile speed
        # 170; CR's speed unit is ~60 per tile/second). The verdict cannot be taken before this or
        # it judges a roll that has not arrived.
        self.log_impact_time = float(cfg.get("env", "log_impact_time", default=3.4))
        # Rocket flight speed in TILES per second. Replaces `rocket_travel_rate`, which was
        # seconds-per-NORMALISED-unit and therefore ranked targets by the wrong distance.
        self.rocket_speed_tiles = float(cfg.get("env", "rocket_speed_tiles", default=14.0))
        # Fixed tolerance on the blast radius for detector jitter -- NOT a lead allowance. See the
        # note where r_tiles is built: the old allowance grew with flight time and inflated a
        # rocket's 2.5-tile blast to 4.1.
        # ZERO BY DEFAULT: a spell's blast is the CARD'S blast. This started at 0.5 as "detector
        # jitter tolerance" and the owner caught what it actually does -- a rocket's 2.0-tile blast
        # became 2.5, and a near-miss on a Royal Giant scored as a hit. Jitter cuts both ways, but
        # the errors are not equally costly: a false WHIFF bills -0.3 on a good cast, while a false
        # HIT pays for a miss, which is the failure reported over and over.
        self.spell_verify_slop_tiles = float(cfg.get("env", "spell_verify_slop_tiles", default=0.0))
        # "Aimed at a tower" as a circle in TILES, replacing the normalised radius that was 2.2
        # wide and 3.8 tall. 2.2 keeps the horizontal reach the old value had.
        self.spell_aim_tiles = float(cfg.get("env", "spell_tower_aim_tiles", default=2.2))
        self.spell_verify_log = bool(cfg.get("env", "spell_verify_log", default=True))
        self._last_exec_action = None
        # The researched counter table drives WHERE a doctrine answer goes (see _where_cell).
        # Empty when the deck ships no config/counters.yaml, and the wheels then keep their
        # hand-written geometry exactly as before.
        try:
            from .counters import load as _load_counters
            self.counter_table = _load_counters(cfg)
        except Exception:  # noqa: BLE001 -- a bad table must never stop a match starting
            from .counters import CounterTable as _CT
            self.counter_table = _CT([])
        # (the two weights live in the rw() block below with every other reward weight -- they were
        # briefly read up here, before rw() exists, which cost a live match to a TypeError)
        self.training_wheels = bool(cfg.get("train", "training_wheels", default=True))
        self.rw_stats_path = cfg.path(f"data/reward_stats/live_{time.strftime('%Y%m%d_%H%M%S')}.jsonl")
        # CADENCE accounting (log 2026-08-12 item 5): where a live decision's wall time actually goes.
        # The per-match means are printed and appended to the reward-stats JSONL, so the trained-vs-
        # served cadence mismatch (act_period 1.0 vs the measured ~2.2 s/decision) stays measured
        # instead of inferred from match timestamps.
        from collections import defaultdict
        self._cad = defaultdict(float)
        self._cad_n = 0
        self._last_step_t: Optional[float] = None   # previous step() entry (decision-to-decision wall time)
        self._last_frame_t: Optional[float] = None  # previous observation grab (the paced-wait anchor)
        self._play_log: list = []                   # per-play telemetry (rebuilt per match in reset())
        self._match_t0 = time.time()
        # X-Bow win-condition geometry (offence forward-in-range / defence back-centre) + the phase gauge
        self.xbow_range = float(cfg.get("env", "xbow_range", default=0.36))
        # X-Bow lifetime (s) -- the live repeat-credit gate's "our bow may still be standing" window
        # (see _wincon_exec_live). Curated `lifetime` wins, else the imported `lifetime_s`, else the
        # 40s generic building default (mirrors sim/engine.build_spec's resolution order).
        _xb = (db.get("x_bow") or {}) if hasattr(db, "get") else {}
        self.xbow_lifetime = float(_xb.get("lifetime") or _xb.get("lifetime_s") or 40.0)
        self._xbow_play_t = None                 # when we last played an X-Bow (reset per match)
        self.deploy_top = float(cfg.get("action", "deploy_top", default=0.44))
        self.tesla_pull_front = float(cfg.get("env", "tesla_pull_front", default=0.52))
        self.tesla_pull_back = float(cfg.get("env", "tesla_pull_back", default=0.59))
        self.xbow_defense_front = float(cfg.get("env", "xbow_defense_front", default=0.52))
        self.xbow_defense_back = float(cfg.get("env", "xbow_defense_back", default=0.62))
        self.xbow_deep_frac = float(cfg.get("rewards", "xbow_deep_frac", default=0.25))
        self.xbow_success_frac = float(cfg.get("env", "xbow_success_frac", default=0.30))
        # thresholds the correctness terms use
        self.quiet_frac = float(cfg.get("env", "enemy_quiet_frac", default=0.02))       # 'quiet board' enemy-mass gate
        self.full_elixir = int(cfg.get("env", "elixir_full", default=10))               # leak / cycle threshold
        self.elixir_frac = 0.0          # last TRUE bar reading (obs + leak); self.elixir is floored
        self.elixir_margin = float(cfg.get("play", "elixir_safety_margin", default=0.25))
        self.defeat_cap = float(cfg.get("env", "defeat_cap", default=0.15))             # 'full push' mass scale for the trade term
        self._prev_mass = 0.0
        self._prev_my_hp = 0.0
        # --- reactive play: live enemy-threat vector (policy input) + foresight rewards ---
        self.threat_tracker = ThreatTracker(cfg)
        self.threat_vec = Threat.zeros()          # normalized threat features -> policy input
        self._last_threat = Threat()              # threat at action-selection time (for reward)
        # Stage 3: identity-grounded threat block from the DETECTOR (only RECOGNISED, HIGH-confidence
        # enemy cards fire). Loaded lazily so torch/ultralytics stay out of the loop when it's off.
        self.use_detector = bool(cfg.get("observation", "use_detector", default=False))
        self.detector_conf = float(cfg.get("observation", "detector_conf", default=0.75))
        self.detector_cards = set(cfg.get("observation", "detector_cards", default=[]))
        self.predict_horizon = float(cfg.get("observation", "predict_horizon_s", default=1.0))
        self.identity_front = card_threat.identity_front(cfg)   # identity watch line (shared with sim/play/label)
        self.db = db
        # your deck's KB profiles (played-card role) for the role-based COUNTER reward
        self._deck_profiles = [card_threat.profile(db, (k[:-4] if k.endswith("_evo") else k))
                               for k in self.vision.deck_keys]
        # --- CORRECTNESS-FIRST reward weights (mirror the sim; see sim/env.py). ONE coherent score of a
        # few bounded sub-terms replaces the old ~40 patchwork rewards; the assembly is in step(). ---
        rw = lambda k, d: float(cfg.get("rewards", k, default=d))  # noqa: E731
        self.w_threat_response = rw("threat_response", 1.0)   # (1) KB counter to the assessed threat, placed to intercept
        self.w_threat_miss = rw("threat_miss", -1.0)          # wrong counter / wrong lane / ignored an ANSWERABLE threat
        self.w_elixir_trade = rw("elixir_trade", 1.0)         # (2) (enemy value eliminated - elixir spent), normalised
        self.w_wincon = rw("wincon_exec", 0.8)                # (3) win-condition executed right for the phase
        self.w_wincon_mis = rw("wincon_misplace", -0.6)       # win-condition thrown away
        # A RUSH win condition (Hog Rider): bridge-only, never into a committed push, lane-aware.
        # Separate from the X-Bow's term because four elixir that WALKS is judged on timing and
        # lane, while a siege building is judged on standing geometry. Empty for decks without
        # one, in which case nothing here changes.
        _rush = set(cfg.get("sim", "wincon_cards", default=[]) or [])
        self.rush_wincon_ids = {i for i, k in enumerate(self.vision.deck_keys)
                                if card_threat.base_key(k) in _rush} - self.xbow_ids
        self.hog_bridge_y = float(cfg.get("env", "hog_bridge_y", default=0.52))
        self.hog_punish_mult = float(cfg.get("rewards", "hog_punish_mult", default=1.5))
        # (4) cycle_plan / cycle_waste: DELETED live too (2026-08-12). The sim deleted its copy after
        # 110 fires / 0 positives (see sim/env._cycle_plan's stub); live then measured the identical
        # action-tax shape -- 2 positives vs 24 negatives over 5 matches -- while being one of only
        # three terms that fired at all. Same term, same shape, same fix.
        # PER-TICK TERMS ARE SCALED BY THE DECISION PERIOD (2026-08-20). `leak` and
        # `threat_miss_idle` are charged once per DECISION, so shortening the period would bill
        # them more times per second of game time for identical play -- a silent re-weighting of
        # the two terms that already dominate the live ledger. Scaling by dt keeps their
        # per-SECOND rate fixed, and keeps it fixed through any future change of period. Terms
        # driven by EVENTS (wincon_exec, threat_response, crown, chip, spell_waste) are untouched.
        self._tick_scale = float(self.act_period) / 1.0
        self.w_leak = rw("leak_penalty", -0.2) * self._tick_scale     # (5) at capacity, leaking
        self.w_spell_waste_live = rw("spell_waste", -0.3)     # (6) spell verified at IMPACT: hit nothing
        self.w_nado_bad = rw("nado_bad", -0.3)                # tornado that improved the enemy's position
        self.correctness_cap = rw("correctness_cap", 20.0)    # per-match cap on POSITIVE shaping (anti-farm)
        self.w_take = rw("take_enemy_tower", 1.0); self.w_lose = rw("lose_own_tower", -1.0)   # the CROWN jump on a take/loss
        self.tower_chip_scale = rw("tower_chip_scale", 0.3)   # convex chip POOL per tower (small; the crown is the jump)
        self.chip_power = float(cfg.get("env", "tower_chip_power", default=2.0))   # >1 -> partial chip sub-proportional
        self.combo_mult = rw("rocket_combo_mult", 3.0)
        self.intercept_lane = float(cfg.get("env", "intercept_lane", default=0.15))
        self.value_norm = float(cfg.get("env", "value_norm", default=10.0))
        self.trade_cap = float(cfg.get("env", "trade_cap", default=1.0))
        self.card_elixir = [(db.elixir(k) or db.elixir(k[:-4] if k.endswith("_evo") else k) or 0)
                            for k in self.vision.deck_keys]   # per-card elixir cost (telemetry + waiver logic)
        self._db = db                                     # KB costs for the trade-potential board read
        self.vision.set_board_warp(self.actions.warp)     # RGB obs becomes BOARD-TRUE (sim-matched)
        self._blind_since = None                          # canvas-liveness guard state
        self._opp_est = 0.0                               # last enemy-elixir estimate (normalized [0,1])
        self._last_dets_age = 999.0                       # perception age of _last_dets_all (validity gate)
        self.phi_max_age = float(cfg.get("env", "phi_max_age_s", default=0.6))
        self.trade_deadband = float(cfg.get("env", "trade_deadband", default=0.02))  # (v3: unused)
        self.trade_kill_r = float(cfg.get("env", "trade_kill_radius_tiles", default=4.0))
        self.trade_grace_s = float(cfg.get("env", "trade_grace_s", default=3.0))
        self.trade_late_s = float(cfg.get("env", "trade_late_s", default=10.0))
        self.trade_match_r = float(cfg.get("env", "trade_match_radius_tiles", default=2.5))
        self._tr_prev_enemy = []
        self._tr_prev_mine = []
        self._tr_pend_en = []
        self._tr_pend_own = []
        self.threat_min_depth = float(cfg.get("env", "threat_min_depth", default=0.12))
        self.threat_max_depth = float(cfg.get("env", "threat_max_depth", default=0.65))
        self.threat_credit_budget = int(cfg.get("env", "threat_credit_budget", default=2))
        self._threat_credits = 0                          # positives granted this threat episode
        self._detector = None
        self._threat_id = np.zeros(card_threat.IDENTITY_DIM, np.float32)   # OBSERVATION identity block
        # REWARD-SIDE TWIN, mirroring sim/env._threat_id_true. The observation is limited to the
        # classes the detector names RELIABLY (`detector_cards`); the referee must not be, or no
        # answer to anything outside that list can ever be credited -- which is exactly what made
        # a Skeleton Army or a Battle Ram read as a quiet board. Built from every CORROBORATED
        # enemy detection instead, since the detector does see them.
        self._threat_id_true = np.zeros(card_threat.IDENTITY_DIM, np.float32)
        self._prev_ident_depth_true = 0.0
        self._prev_ident_depth = 0.0        # deepest recognised-threat depth last step (for velocity)
        self._prev_ident_t = None
        self._opp_mem = card_threat.OpponentMemory(db)   # per-match opponent short-term memory (Stage 3)
        self._opp_elixir = OpponentElixirEstimator(db)   # live estimate from mirrored spend accounting
        from .replay_mine import TeamTracker, own_card_bases
        self._team_tracker = TeamTracker(                # LIVE: evidence-fused teams (plays/motion/bars/pockets)
            own_cards=own_card_bases(db),                # + the DECK VETO: 'mine' must name a card we own
            is_building=lambda b, _db=db: _db.kind(b) == "building",   # building side prior
            spawn_radius=float(cfg.get("observation", "team_spawn_radius", default=0.10)),
            spawn_window_s=float(cfg.get("observation", "team_spawn_window_s", default=2.5)),
            enemy_window_s=float(cfg.get("observation", "team_enemy_window_s", default=4.0)),
            track_radius=float(cfg.get("observation", "team_track_radius", default=0.12)),
            forget_s=float(cfg.get("observation", "team_forget_s", default=4.5)),
            motion_min=float(cfg.get("observation", "team_motion_min", default=0.05)),
            min_hits=int(cfg.get("observation", "team_track_min_hits", default=2)),
            is_spell=lambda b, _db=db: _db.kind(b) == "spell",   # enemy spells are never targets
            phantom_stale_s=float(cfg.get("observation", "team_phantom_stale_s", default=6.0)),
            deep_mine_y=float(cfg.get("observation", "team_deep_mine_y", default=0.62)),
            deep_enemy_y=float(cfg.get("observation", "team_deep_enemy_y", default=0.38)))
        # Stage-3b gate: the troop-INTERACTION block (predicted tower pressure) -- live twin of the sim's
        self.use_interactions = bool(cfg.get("observation", "use_interactions", default=False))
        self.canonical_rgb = bool(cfg.get("observation", "canonical_rgb_live", default=True))
        # TOWER-HP block: fed to the policy exactly as the sim feeds it (sim/view.tower_vector). The sim
        # trains WITH it (threat_dim 46 -> 52) but the live env used to build the vector WITHOUT it, so a
        # sim/PPO checkpoint's threat_fc (52 wide) could not multiply the live 46-wide vector. Same
        # observation.use_tower_hp gate as the sim so the two widths always agree.
        self.use_tower_obs = bool(cfg.get("observation", "use_tower_hp", default=True))
        self.sight_range = float(cfg.get("sim", "sight_range", default=0.12))
        self._last_dets_all = []                         # every tagged detection this frame (both teams)
        self._det_hold = _DetHold(float(cfg.get("observation", "det_hold_s", default=0.45)))
        self._not_in_match = 0          # consecutive frames the board was NOT recognised
        self.match_end_confirm = int(cfg.get("env", "match_end_confirm", default=3))
        # PUMP PUNISH (elixir collector -> rocket): sighting state for the reward + the aim assist
        self.pump_window = float(cfg.get("env", "pump_rocket_window_s", default=12.0))
        self.pump_aim_radius = float(cfg.get("env", "pump_aim_radius", default=0.10))
        self.pump_pair_gap = float(cfg.get("env", "pump_pair_gap", default=0.11))
        self.pump_king_guard = float(cfg.get("env", "pump_king_guard", default=0.15))
        self.combo_mult = float(cfg.get("rewards", "rocket_combo_mult", default=3.0))
        self.spell_lead_radius = float(cfg.get("env", "spell_lead_radius", default=0.12))
        self._pump_seen_t = None                         # when a pump was FIRST sighted (window anchor)
        self._pump_last_t = 0.0                          # last read that still saw it
        self._pump_xy = None                             # its latest (cx, gy)
        self._cycle_tracker = CycleTracker(self.n_cards)   # live estimate of the upcoming-card order (graded next_vec)
        # Optional callable -> True when the caller wants to stop. reset() navigates menus in an
        # UNBOUNDED loop waiting for a match, so without this a trainer whose SIGINT handler only sets
        # a flag can never be interrupted between matches: the flag is set and nothing ever reads it.
        self.stop_requested = None
        if self.use_detector:
            self.threat_vec = np.concatenate(
                [self.threat_vec, self._threat_id,
                 np.zeros(card_threat.OPP_MEMORY_DIM, np.float32)]).astype(np.float32)
            try:
                from .replay_mine import load_detector
                det = load_detector(cfg)
                self._detector = det if det.available else None
            except Exception:
                self._detector = None
        if self.use_interactions:                        # widen by the interaction block (zeros until read)
            self.threat_vec = np.concatenate(
                [self.threat_vec, np.zeros(interactions.INTERACTION_DIM, np.float32)]).astype(np.float32)
        if self.use_tower_obs:                           # widen by the tower-HP block (zeros until first read)
            self.threat_vec = np.concatenate(
                [self.threat_vec, np.zeros(_TOWER_DIM, np.float32)]).astype(np.float32)
        # live side-window: each frame + the detector's team-coloured boxes (train-rl babysitting).
        from .detect import LivePreview, OverlayReplayRecorder
        self._preview = LivePreview(cfg)
        self._replay_rec = OverlayReplayRecorder(cfg)   # overlay_replay gate: clip each match opening
        # CONTINUOUS PERCEPTION (~10Hz): a background thread runs the detector + team tracker so the
        # act loop reads a <=1-period-old snapshot instead of being blind between decisions, tracker
        # velocities are finely sampled (rocket lead / motion team evidence), and the preview is live.
        self._ploop = None
        hz = float(cfg.get("observation", "perception_hz", default=10.0))
        if self._detector is not None and hz > 0:
            from .perception import PerceptionLoop
            self._ploop = PerceptionLoop(cfg, self._detector, self._team_tracker,
                                         self.detector_conf, hz, preview=self._preview,
                                         recorder=self._replay_rec)
            self._ploop.start()

    # -- capture helper ------------------------------------------------
    def _grab(self, retries: int = 20):
        for _ in range(retries):
            frame = self.capture.grab()
            if frame is not None:
                return frame
            self.capture.refresh_region()
            time.sleep(0.3)
        return None

    def region_ready(self) -> bool:
        return self.capture.region is not None

    def _read_hand(self, frame) -> None:
        """Recognize the hand -> deck ids per slot + multi-hot (for identity actions), and the next
        (preview) card, then fold both through the cycle tracker into a graded UPCOMING-order vector
        (Next=1.0 grading down for the hidden cards) so the policy can plan which cards to cycle to."""
        self.hand_ids = self.vision.recognize_hand(frame)
        self.hand_vec = self.vision.hand_multihot(self.hand_ids)
        if self.ability_id >= 0:
            # The button is live only while the champion is, and only once per body. Read from the
            # detector, not from what we played: he can die at any moment, and offering an action
            # the game refuses is how a policy learns that the action does nothing.
            seen = self._champion_on_board()
            if not seen:
                self._ability_spent = False        # next body brings its own activation
            self.hand_vec[self.ability_id] = 1.0 if (seen and not self._ability_spent) else 0.0
        self.next_id = self.vision.recognize_next(frame)
        self.next_vec = self._cycle_tracker.observe(self.hand_ids, self.next_id)

    def _enemy_tower_hp(self):
        """[left, right] enemy princess HP for the placement assists, or None when unread.

        The live digit read, not a fraction: xbow_target_lane_cell compares the two against each
        other and normalises by the larger, so raw HP is what it wants.
        """
        hp = getattr(self, "tower_hp", None)
        vals = list(getattr(hp, "enemy_hp", []) or [])
        if len(vals) < 2 or any(v is None for v in vals[:2]):
            return None
        return [float(vals[0]), float(vals[1])]

    def _tower_frac(self) -> np.ndarray:
        """6-dim crown-tower HP block in the SAME layout the sim trained on (sim/view.tower_vector):
        HP FRACTION of (L princess, R princess, king) for MINE then THEIRS, 0.0 == destroyed. Princess
        HP is the live digit read (TowerHpTracker) normalised by each side's full; the KING's HP is
        never printed on screen, so its alive flag is the proxy (1.0 until it falls). Destroyed towers
        are forced to 0.0 via the alive flags, matching the sim's '0.0 => crown taken' contract."""
        v = np.zeros(_TOWER_DIM, np.float32)
        hp = self.tower_hp
        mine_alive = list(getattr(self.tower, "mine_alive", []) or [])
        enemy_alive = list(getattr(self.tower, "enemy_alive", []) or [])
        my_full = hp.my_full if getattr(hp, "my_full", 0) > 0 else 1.0
        en_full = hp.full if getattr(hp, "full", 0) > 0 else 1.0
        for i in range(2):                                    # L, R princess (index 0, 1)
            if i < len(mine_alive) and mine_alive[i] and i < len(hp.my_hp):
                v[i] = min(1.0, max(0.0, float(hp.my_hp[i]) / my_full))
            if i < len(enemy_alive) and enemy_alive[i] and i < len(hp.enemy_hp):
                v[3 + i] = min(1.0, max(0.0, float(hp.enemy_hp[i]) / en_full))
        v[2] = 1.0 if (len(mine_alive) > 2 and mine_alive[2]) else 0.0    # king: alive proxy (no live HP read)
        v[5] = 1.0 if (len(enemy_alive) > 2 and enemy_alive[2]) else 0.0
        return v

    def _update_threat(self, frame) -> None:
        """Advance the live enemy-threat read from the current frame -> policy input vector. When
        use_detector, append card_threat's identity block (RECOGNISED, HIGH-confidence enemy cards on
        YOUR half) + the opponent SHORT-TERM MEMORY block (whole-match read, both halves). All-zero if
        the detector is unavailable."""
        self._last_threat = self.threat_tracker.update(frame, time.time())
        base = self._last_threat.vector()
        if not self.use_detector:
            parts = [base]
            if self.use_interactions:
                parts.append(np.zeros(interactions.INTERACTION_DIM, np.float32))
            if self.use_tower_obs:
                parts.append(self._tower_frac())
            self.threat_vec = np.concatenate(parts).astype(np.float32) if len(parts) > 1 else base
            self._preview.update(frame, [], self.capture.region)      # plain frame (no detector loaded)
            return
        dets = self._detect_enemies(frame)                                   # ONE detector pass this frame
        now = time.time()
        self._track_pump(now)                                                # pump sighting -> punish window
        dt = (now - self._prev_ident_t) if self._prev_ident_t else 0.0
        items = [(d.base, card_threat.identity_depth(d.gy, self.identity_front))
                 for d in dets if d.gy >= self.identity_front]   # identity: from the WATCH LINE (bridge)
        self._threat_id = card_threat.identity_threat_vector(
            items, self.db, prev_depth=self._prev_ident_depth, dt=dt, horizon=self.predict_horizon)
        self._prev_ident_depth = float(self._threat_id[7])
        # ...and the REWARD's twin, from every corroborated enemy rather than only the named ones.
        # `trk_hits >= 2` is the same corroboration the advisor gate and `_situation` apply, so all
        # three argue about one board; enemy SPELLS stay out because nothing counters an effect.
        true_items = []
        for d in (getattr(self, "_last_dets_all", None) or ()):
            if getattr(d, "team", "") != "enemy" or float(getattr(d, "gy", 0.0)) < self.identity_front:
                continue
            if int(getattr(d, "trk_hits", 2) or 2) < 2:
                continue
            b = str(getattr(d, "base", "") or "")
            if not b or (self.db.kind(b) == "spell" and b not in _SPAWN_SPELLS):
                continue
            true_items.append((b, card_threat.identity_depth(d.gy, self.identity_front)))
        self._threat_id_true = card_threat.identity_threat_vector(
            true_items, self.db, prev_depth=self._prev_ident_depth_true, dt=dt,
            horizon=self.predict_horizon)
        self._prev_ident_depth_true = float(self._threat_id_true[7])
        self._prev_ident_t = now
        mem = self._opp_mem.update([(d.base, d.gy) for d in dets], dt=dt)    # memory: BOTH halves (incl. staging)
        # Slot 5 carries the current opponent-elixir estimate (normalized), inferred from symmetric
        # elixir accounting + detected enemy plays; keeps model width unchanged.
        mem[5] = self._opp_elixir.update(self.elixir, dets, now)
        self._opp_est = float(mem[5])                    # the trade potential reads the same estimate
        tid_now = self._threat_id
        if tid_now is None or len(tid_now) == 0 or float(tid_now[0]) < 0.5:
            # HYSTERESIS (2026-08-14): detector gaps unlight the tid for a frame or two mid-push,
            # and an instant reset re-armed the response budget for the SAME push. Only a
            # sustained quiet (3 s) ends the episode.
            if getattr(self, "_tid_unlit_since", None) is None:
                self._tid_unlit_since = now
            elif now - self._tid_unlit_since >= 3.0:
                self._threat_credits = 0
        else:
            self._tid_unlit_since = None
        # CANVAS LIVENESS: a detector that silently yields nothing while the board is ACTIVE
        # feeds the policy an EMPTY semantic canvas -- a state that never exists in sim training
        # and a proven driver of degenerate placement. Say so loudly, once a stretch.
        if self._detector is not None:
            import time as _t
            if not dets and (getattr(self, "_last_mass", None) or 0.0) >= self.quiet_frac:
                if self._blind_since is None:
                    self._blind_since = _t.time()
                elif _t.time() - self._blind_since > 5.0:
                    print("[env] WARNING: detector returned NOTHING for >5s on an active board -- "
                          "the semantic canvas is empty and placements are untrustworthy")
                    self._blind_since = _t.time()
            else:
                self._blind_since = None
        self._replay_rec.update(self._last_dets_all)     # overlay replay: newest boxes for the clip
        parts = [base, self._threat_id, mem]
        if self.use_interactions:                        # predicted tower pressure from ALL tagged detections
            mine_a, enemy_a, _ = _anchors(self.cfg)
            my_t = [(ax, ay, bool(self.tower.mine_alive[i])) for i, (ax, ay) in enumerate(mine_a[:3])]
            en_t = [(ax, ay, bool(self.tower.enemy_alive[i])) for i, (ax, ay) in enumerate(enemy_a[:3])]
            units = [("mine" if d.team == "mine" else "enemy", d.base, d.cx, d.gy)
                     for d in self._last_dets_all
                     if d.team in ("mine", "enemy") and d.base in self.detector_cards]
            parts.append(interactions.interaction_vector(units, my_t, en_t, self.db))
        if self.use_tower_obs:                           # crown-tower HP -- appended LAST, as in sim/view
            parts.append(self._tower_frac())
        self.threat_vec = np.concatenate(parts).astype(np.float32)
        if self._ploop is None:      # side window (perception loop feeds it at 10Hz itself when active)
            self._preview.update(frame, self._last_dets_all, self.capture.region)

    def _observe(self, frame) -> np.ndarray:
        """The policy's IMAGE observation: the downscaled arena, plus detect_obs's semantic CANVAS
        when the obs-canvas gate is on.

        The canvas is rendered from ``_last_dets_all`` -- the detections ``_update_threat`` already
        produced for this frame -- so it costs NO extra detector pass. Both callers run
        ``_update_threat`` first, which is what keeps the two in sync.
        """
        if self.canonical_rgb:
            # CANONICAL RGB (2026-08-15). The image branch was the last piece of the observation
            # still fed REAL GAME PIXELS live while the policy trains on the sim's SYNTHETIC
            # top-down render -- the exact transfer failure replay_bc's design note calls out
            # ("image-BC clones pixels->action, so feeding the pro's pixels into the image branch
            # transfers badly. So we never do.") and which the BC path already avoids by
            # rebuilding the arena from detections.
            # MEASURED on the same checkpoint: in the SIM it never uses column 0 (placements
            # concentrate on the lane/centre columns 3, 9, 14); LIVE it dumped 28% of plays into
            # column 0 and 37% into columns 0-1. Same weights, so the difference is the input.
            # Rebuilt from OUR detections in the sim's own palette, board-warped so the RGB and
            # the semantic/predictive channels of a frame all agree. Shape is unchanged (3
            # channels), so checkpoints stay valid.
            w = self.actions.warp
            dets = []
            for d in (self._last_dets_all or []):
                bx, by = w.frame_to_board(d.cx, d.gy)
                dets.append(_BoardDet(d, bx, by))
            oh, ow = self.obs_shape[0], self.obs_shape[1]
            img = replay_bc.canonical_render(dets, self.cfg, int(oh), int(ow), _RIVER_BOARD_Y)
        else:
            img = self.vision.observe(frame)
        if not self.use_canvas:
            return img
        from . import detect_obs
        ch = detect_obs.detection_channels(self._last_dets_all, self.db, img.shape[0], img.shape[1],
                                           warp=self.actions.warp)
        if detect_obs.predictive_enabled(self.cfg):
            # PREDICTIVE slice, board-true like the canvas: units and tower anchors warped
            # frame -> board, then the SAME mover_forecast the sim paints.
            w = self.actions.warp
            mine_a, enemy_a, _ = _anchors(self.cfg)
            my_t = [(*w.frame_to_board(ax, ay), bool(self.tower.mine_alive[i]))
                    for i, (ax, ay) in enumerate(mine_a[:3])]
            en_t = [(*w.frame_to_board(ax, ay), bool(self.tower.enemy_alive[i]))
                    for i, (ax, ay) in enumerate(enemy_a[:3])]
            units, confs = [], []
            for d in self._last_dets_all:
                if d.team in ("mine", "enemy") and d.base in self.detector_cards:
                    bx, by = w.frame_to_board(d.cx, d.gy)
                    units.append((d.team, d.base, bx, by))
                    confs.append(min(1.0, float(d.conf)))
            pred = detect_obs.predictive_channels(units, my_t, en_t, self.db,
                                                  img.shape[0], img.shape[1], confs,
                                                  dt_s=detect_obs.predictive_dt(self.cfg),
                                                  horizon_s=detect_obs.eta_horizon(self.cfg))
            ch = np.concatenate([ch, pred], axis=2)
        if detect_obs.hp_enabled(self.cfg):
            w = self.actions.warp
            items = []
            for d in self._last_dets_all:
                if d.team in ("mine", "enemy"):
                    bx, by = w.frame_to_board(d.cx, d.gy)
                    items.append((d.team, d.base, bx, by, detect_obs.read_hp_frac(frame, d)))
            ch = np.concatenate(
                [ch, detect_obs.hp_channels(items, img.shape[0], img.shape[1])], axis=2)
        stack = self._canvas_stack.push(detect_obs.channels_to_uint8(ch), time.time())
        return np.concatenate([img, stack], axis=2)

    def _detect_enemies(self, frame):
        """Whitelisted ENEMY detections (both halves; each has .base + .gy in [0,1]). With the
        perception loop running this is the latest ~10Hz SNAPSHOT (already team-tagged in the
        thread); otherwise one synchronous detector pass. [] if the detector is off/unavailable."""
        if self._detector is None:
            return []
        if self._ploop is not None and not self._ploop.running:
            # SAY IT AND HEAL IT (2026-08-20). The old failure mode was silent: the perception
            # thread died, this method fell through to 1 Hz synchronous detection, and reaction
            # time tripled with nothing in the log -- the user's "responds to a hog 4-5 s after
            # placement" session. Rate-limited so a flapping loop doesn't spam.
            if time.time() - getattr(self, "_percep_warn_t", 0.0) > 10.0:
                self._percep_warn_t = time.time()
                print("[env] perception loop NOT RUNNING -- act loop is detecting at its own "
                      "pace (reaction degraded); attempting restart", flush=True)
            self._ploop.ensure_alive()
        if self._ploop is not None and self._ploop.running:
            self._ploop.set_towers(self.tower.mine_alive, self.tower.enemy_alive)  # pocket gating stays fresh
            dets, age = self._ploop.snapshot()
            if age <= 2.0:                                # healthy loop -> use the snapshot
                self._cad["det_age"] += float(age)        # per-match mean lands in the cadence line
                dets = self._det_hold.merge(dets, time.time())   # bridge detector flicker
                self._last_dets_all = dets
                self._last_dets_age = float(age)          # trade-potential validity gate reads this
                return [d for d in dets if d.team == "enemy" and d.base in self.detector_cards]
            if time.time() - getattr(self, "_percep_warn_t", 0.0) > 10.0:
                self._percep_warn_t = time.time()
                print("[env] perception snapshot is %.1fs STALE -- falling back to synchronous "
                      "detection this tick" % age, flush=True)
        try:
            dets = self._detector.detect(frame, conf=self.detector_conf)
        except Exception:
            return []
        # a fallen princess opens the deploy POCKET in front of it -> void the side prior for that lane
        self._team_tracker.set_towers(self.tower.mine_alive, self.tower.enemy_alive)
        self._team_tracker.tag(dets, time.time())     # evidence-fused team (plays/motion/bars/pockets)
        dets = self._det_hold.merge(dets, time.time())   # bridge detector flicker (see _DetHold)
        self._last_dets_all = dets                    # kept for the interaction block (both teams)
        self._last_dets_age = 0.0                     # synchronous pass: fresh by construction
        return [d for d in dets if d.team == "enemy" and d.base in self.detector_cards]

    # -- episode lifecycle --------------------------------------------
    def reset(self) -> Optional[np.ndarray]:
        """Navigate menus until a match starts; return the first observation.

        Returns None if the game window is lost OR ``stop_requested()`` goes True -- callers use
        ``self.stopped`` to tell the two apart.
        """
        self.stopped = False
        self.tower.reset()
        self.tower_hp.reset()
        self._canvas_stack.reset()
        self._det_hold.reset()                        # flicker memory must not bridge two matches
        self._not_in_match = 0        # motion history must never bridge two matches
        self._defensive = False           # icebow phase: False = offensive X-Bow win condition; True = defence + rocket-cycle
        self._enemy_chip_total = 0.0      # cumulative enemy-tower HP chipped (the X-Bow 'did it break through?' gauge)
        self._xbow_play_t = None          # wincon repeat-credit window must not bridge two matches
        self._match_bonus = 0.0
        self._match_penalty = 0.0
        self.rw_stats.new_match()
        # spells still in flight belong to the match that cast them: a cast in the final
        # seconds would otherwise come due during the NEXT match and be judged against its
        # (empty, by definition) opening board -- a phantom whiff billed to the wrong match.
        self._pending_spells.clear()
        self._pending_deploys.clear()   # a check from the last match cannot be settled in this one
        self._cad.clear()                 # cadence accounting is per match
        self._cad_n = 0
        self._last_step_t = None
        self._last_frame_t = None         # menu time must not count against the first paced wait
        self._play_log = []               # per-play telemetry for this match (see step's record block)
        self._failed_deploys_match = 0    # ghost plays THIS match (rate is printed at match end)
        self._match_t0 = time.time()      # re-anchored below when IN_MATCH is actually detected
        self._nav.reset_state()
        while True:
            if self.stop_requested is not None and self.stop_requested():
                self.stopped = True          # a deliberate stop, NOT a lost window
                return None
            frame = self._grab()
            if frame is None:
                return None
            state = self.vision.detect_state(frame)
            if state == GameState.IN_MATCH:
                self.clock.reset()               # zero the 2x/3x elixir clock at match start
                self._match_t0 = time.time()     # per-play records use match-relative time
                self._replay_rec.new_match()     # arm a fresh overlay-replay clip for this match
                self.elixir_mult = 1
                self.elixir = self.vision.read_elixir(frame)
                self.elixir_vec = np.asarray([self.elixir / 10.0], dtype=np.float32)
                self.threat_tracker.reset()
                self._prev_ident_depth = 0.0
                self._prev_ident_t = None
                self._opp_mem.reset()
                self._opp_elixir.reset(my_elixir=self.elixir, now=time.time())
                if self._ploop is not None and self._ploop.running:
                    self._ploop.reset_tracker()       # forget last match's tracks (thread-safe)
                else:
                    self._team_tracker.reset()
                self._pump_seen_t = None                  # forget last match's pump sighting
                self._pump_xy = None
                self._cycle_tracker.reset()
                self._read_hand(frame)
                self._update_threat(frame)
                self._last_obs = self._observe(frame)
                self._last_frame = frame
                self._prev_mass = enemy_mass(frame, self.cfg)
                self._prev_my_hp = float(sum(self.tower_hp.my_hp))
                self._prev_chip_prog = 0.0        # convex enemy-tower chip progress (offense)
                self._prev_chip_prog_def = 0.0    # convex own-tower chip progress (defense)
                return self._last_obs
            self._nav.handle(frame, state)   # robust menu nav: located buttons + MATCH_END escalation + popup watchdog + logging


    def _champion_on_board(self) -> bool:
        """Is our champion on the arena right now? The ability button is dead unless he is.

        Read from the DETECTOR (he is a tracked class, so this is a lookup) rather than from our
        own play history, which goes stale the moment he dies.
        """
        if self._champ_base is None:
            return False
        try:
            dets = getattr(self, "_last_dets_all", None) or ()
            return any(getattr(d, "base", "") == self._champ_base
                       and getattr(d, "team", "") == "mine" for d in dets)
        except Exception:  # noqa: BLE001 -- a perception hiccup must not make the button "live"
            return False

    def _execute(self, action: Action) -> None:
        play, card_id, cell = action
        if not play:
            return
        if card_id == self.ability_id and self.ability_id >= 0:
            # ONE TAP on the calibrated button. No slot to select and no placement -- the ability
            # acts on the champion wherever he stands, so the cell the policy produced is ignored,
            # exactly as it is in the sim. Deliberately does NOT touch the cycle tracker or anchor a
            # 'mine' detection: no card left the hand and no unit was deployed, and recording either
            # would desync the hand model and mis-tag whatever sits under the button.
            if not self._champion_on_board():
                return                        # he died between the decision and the tap
            self.controller.tap(*self.ability_xy)
            self._ability_spent = True        # this body's single activation is gone
            return
        slot = next((s for s, c in enumerate(self.hand_ids) if c == card_id), -1)
        if slot < 0:                          # chosen card not in hand (unrecognized) -> skip
            return
        gx, gy = cell % self.gw, cell // self.gw
        self.controller.play_card(*self.actions.decode(slot, gx, gy))
        self._cycle_tracker.record_play(card_id)      # a card left the hand -> it rotates to the queue back
        # ANY play (troop or spell) anchors its own detection 'mine' -- base-matched, so your rolling Log
        # is claimed at the cast point while an enemy answer dropped on the same spot is not.
        cx, cy = self.actions.cell_center(gx, gy)
        base = card_threat.base_key(self.vision.deck_keys[card_id])
        self._opp_elixir.record_my_play(base)
        if self._ploop is not None and self._ploop.running:
            self._ploop.record_play(cx, cy, time.time(), base=base)
        else:
            self._team_tracker.record_play(cx, cy, time.time(), base=base)
        if card_id in self.spell_ids:
            # blast radius from the KB (radius_tiles), normalized on the x axis like every live
            # radius constant in reward.py; +1.5 tiles of lead slop so a predictive cast on a
            # moving target is not billed as a whiff.
            kb = self.db.get(base) or {}
            is_rocket = card_id in self.rocket_ids
            # WAIT FOR THE SPELL TO ARRIVE. The Log's 0.8 here was the cast delay, not the ROLL:
            # at 170 projectile speed (CR's unit is ~60 per tile/second) it covers 2.83 tiles/s
            # over 9.6 tiles, so the corridor is not fully swept for ~3.4s. Judging at 0.8 scored
            # the verdict a third of the way down the lane, which is why a body that walked out of
            # the path before the roll reached it was still counted as hit.
            if base == "the_log":
                eta = self.log_impact_time
            elif is_rocket:
                eta = self._impact_time(cx, cy, is_rocket=True)
            else:
                eta = self._impact_time(cx, cy, is_rocket=False)
            # RADIUS IN TILES (2026-08-20). This used to be normalised by /18 and then compared
            # against normalised distance, which stretched every blast down the 32-tile axis --
            # tornado's 5.5-tile pull scored as a hit up to 12.4 tiles away, so a cast into the
            # river "landed on" whatever was in their half. The lead allowance is physical now
            # too: a troop covers roughly a tile per second, so a spell in flight for `eta`
            # seconds gets `eta` tiles of slop rather than a flat 1.5 that was itself mis-scaled.
            # THE REAL RADIUS, plus a small FIXED tolerance for detector jitter. The old
            # `+ eta` was a lead allowance -- necessary only for a check that fires before impact
            # and has to guess where a body will be. Judged at arrival there is nothing to guess,
            # and the allowance was large: a rocket 1.6s out was scored with a 4.1-tile blast
            # against a real 2.5, so bodies well outside it were credited as hits.
            r_tiles = float(kb.get("radius_tiles") or 2.5) + self.spell_verify_slop_tiles
            rec = {"t_eval": time.time() + eta + 0.4, "cx": cx, "cy": cy,
                   "r": r_tiles, "base": base, "kind": "whiff"}
            self._pending_spells.append(rec)
            self._last_cast_rec = rec      # the reward tick attaches what this cast was PAID
            if is_rocket:
                # WHEN this rocket goes off, so a tornado cast after it can be timed onto the
                # blast point -- the doctrinal order (R6).
                self._last_rocket = (cx, cy, time.time() + eta)
            if card_id in self.tornado_ids:
                pull_r = 5.5 / 18.0
                tracks0 = self._enemy_tracks_now()
                pulled = [(tx, ty) for (tx, ty, *_rest) in tracks0
                          if math.hypot(tx - cx, ty - cy) <= pull_r]
                self._last_nado = (cx, cy, time.time())    # pull centre, for combo timing
                if pulled:
                    # a cast aimed into the king-activation region (where nado_king_cell aims) is
                    # activation INTENT: pulling a unit deep toward our king is the play there,
                    # so that geometry is exempt from the bad-pull bill. TowerTracker carries no
                    # king-activation state live, so intent-by-aim is the honest proxy.
                    mk = _anchors(self.cfg)[0][2] if len(_anchors(self.cfg)[0]) >= 3 else (0.48, 0.72)
                    king_cast = math.hypot(cx - mk[0], cy - mk[1]) <= 0.16
                    self._pending_spells.append({"t_eval": time.time() + 4.0, "cx": cx, "cy": cy,
                                                 "kind": "nado", "pulled": pulled,
                                                 "king_cast": king_cast})

    def _lane_wincon(self):
        """The enemy WIN CONDITION currently pushing a lane, as ``(x, y, sight_radius)`` for the
        Tesla centre-pull assist -- or None when there is nothing worth pulling.

        Picks the DEEPEST recognised enemy win condition on your half (the one actually committing)
        and returns its own KB aggro radius, so how far the Tesla can be pulled toward mid-board
        scales with the card: a 9.5-tile Hog drags much further across than a 5.5-tile Ram Rider.
        Ignores anything already near mid-board -- a centre pull only makes sense against a push
        that is committed to ONE side.
        """
        best = None
        for d in self._last_dets_all:
            if d.team == "mine" or d.gy < 0.5:
                continue
            prof = card_threat.profile(self.db, card_threat.base_key(d.base))
            if not prof.win_condition or abs(d.cx - 0.5) < self.intercept_lane:
                continue
            if best is None or d.gy > best.gy:
                best = d
        if best is None:
            return None
        sight = float(self.db.sight_range_tiles(card_threat.base_key(best.base))) * _TILE
        return best.cx, best.gy, sight

    def _track_pump(self, now: float) -> None:
        """Watch the tagged detections for an enemy ELIXIR COLLECTOR on their half: the FIRST sighting
        anchors the punish window (env.pump_rocket_window_s -- a pump left alive past it has already
        paid out, especially against a control deck); the sighting expires after ~6s without one."""
        pumps = [d for d in self._last_dets_all
                 if d.base == "elixir_collector" and d.team != "mine" and d.gy < 0.5]
        if pumps:
            if self._pump_seen_t is None:
                self._pump_seen_t = now
            self._pump_last_t = now
            self._pump_xy = (pumps[0].cx, pumps[0].gy)
        elif self._pump_seen_t is not None and now - self._pump_last_t > 6.0:
            self._pump_seen_t = None
            self._pump_xy = None

    def _pump_fresh(self) -> bool:
        """A sighted enemy pump still inside the punish window (rocketing it is still worth it)."""
        return (self._pump_seen_t is not None and self._pump_xy is not None
                and time.time() - self._pump_seen_t <= self.pump_window)

    def _aim_weaker_tower(self, card_id: int, cell: int) -> int:
        """A ROCKET or an offensive MINER aimed at an enemy princess is redirected to the lower-HP
        princess so it finishes off the WEAKER tower (more efficient) instead of splitting damage --
        the same chip logic for both. The policy can't read tower HP (it isn't in the observation), so
        the env picks the weaker tower mechanically. No-op for other cards, other targets, or while a
        princess is down / both are at equal HP (then the model's own aim / lane stands)."""
        if card_id not in self.rocket_ids and card_id not in self.miner_ids:
            return cell
        gx, gy = cell % self.gw, cell // self.gw
        cx, cy = self.actions.cell_center(gx, gy)
        # PUMP PUNISH aim assist: a rocket the policy ALREADY aims near a fresh enemy pump is snapped to
        # the king-safe optimum -- midpoint with an adjacent princess tower when one blast covers both,
        # else the pump itself; never within pump_king_guard of the king (then the policy's aim stands).
        if card_id in self.rocket_ids and self._pump_fresh():
            pxy = self._pump_xy
            if pxy is not None and math.hypot(cx - pxy[0], cy - pxy[1]) <= self.pump_aim_radius * 1.5:
                tgt = pump_rocket_cell(pxy[0], pxy[1], self.tower.enemy_a, self.tower.enemy_alive,
                                       self.pump_pair_gap, self.pump_king_guard, self.actions)
                if tgt is not None:
                    return tgt
        tgt = weaker_princess_cell(cx, cy, self.spell_aim_radius, self.tower.enemy_a,
                                   self.tower_hp.enemy_hp, self.tower.enemy_alive,
                                   self.actions)
        return tgt if tgt is not None else cell

    def _aim_rocket_intercept(self, cell: int) -> int:
        """ROCKET LEAD ASSIST: the policy aims its 2-tile blast at troops it perceived ~an act period
        ago, and the flight adds 1-2s more -- a marching push walks clean out of the blast by impact.
        Snap the aim to the PREDICTED-at-impact centroid of the tracked enemies near it (TeamTracker
        positions + lifetime velocity). No tracked enemy near the aim (tower chip, pre-aimed spots) ->
        the aim stands. Tornado is deliberately NOT led: its placement is a DESTINATION (where you want
        the clump dragged), not a hit-them point."""
        gx, gy = cell % self.gw, cell // self.gw
        cx, cy = self.actions.cell_center(gx, gy)
        tracks = self._enemy_tracks_now(with_base=True)
        # KB-GROUNDED LEAD (2026-08-20). This used to rely purely on the tracker's velocity, which
        # is a LIFETIME AVERAGE and is exactly ZERO for a track under 0.5 s old -- so a hog that had
        # just crossed was "led" by nothing and the blast landed where it had been standing. The
        # lead now falls back to the card's known walking speed down the lane.
        got = lead_point(cx, cy, tracks, self._impact_time(cx, cy, is_rocket=True),
                         self.spell_lead_radius * 18.0, self.db)
        if got is None:
            return cell
        gx2, gy2 = self.actions.coords_to_grid(got[0], got[1])
        return int(gy2) * self.gw + int(gx2)

    # ============ CORRECTNESS-FIRST reward helpers (mirror the sim; from live perception) ============
    def _same_lane(self, cx: float) -> bool:
        """True when a placement at horizontal ``cx`` is in the threatened lane (or there is no clear
        lane). Reuses the coarse push-lane read from the pre-action frame."""
        frame = self._last_frame
        if frame is None:
            return True
        side = threat_side(frame, self.cfg, self.threat_min_frac)   # -1 left / 0 none / +1 right
        if side == 0:
            return True
        off = cx - self.lane_split_x
        opposite = abs(off) > self.wrong_lane_margin and (off < 0) == (side > 0)
        return not opposite

    def _threat_response_live(self, card_id: int, cx: float, cy: float) -> float:
        """(1) THREAT-RESPONSE: the KB-correct counter to the RECOGNISED threat, placed to intercept
        (its lane, your half). Wrong role dropped as a defence -> penalty. Offensive placements are
        judged by wincon_exec / trade. Mirrors sim/env._threat_response under live perception."""
        prof = self._deck_profiles[card_id] if 0 <= card_id < len(self._deck_profiles) else None
        if prof is None:
            return 0.0
        tid = self._threat_id_true
        if tid is None or len(tid) < card_threat.IDENTITY_DIM or tid[0] < 0.5:
            # NO RECOGNISED THREAT -> NOT GRADED. The quiet-board branch here used to charge
            # w_threat_miss * 0.4 for a reactive card on a quiet board. The sim retired that branch
            # after 257 fires / 0 positives (see sim/env._threat_response for the full reasoning:
            # the question cannot be answered at play time; chip/crown bill the real consequence),
            # and live measured the same one-sided shape -- threat_response paid 7 positives against
            # 43 negatives over 5 matches (2026-08-12). Live it was doubly wrong: `tid` unlit also
            # covers every frame the DETECTOR simply could not read, so it punished defending
            # exactly when perception was blind while idling scored 0 (diagnosis C4).
            return 0.0
        # DEPTH GATE (2026-08-14 rework; measured: +1.0 for a FRONT-half tesla at y 0.396 while
        # the push was still BUILDING in their back). A threat that has not advanced past the
        # watch line is not yet answerable -- pre-committing a counter is the WRONG play (the
        # doctrine says wait), so nothing positive is graded until the threat is genuinely
        # coming (identity depth beyond threat_min_depth toward our king).
        dpt = float(getattr(self, "_prev_ident_depth", 0.0))
        # DEPTH WINDOW: below min = premature (the push is still building -- wait); above max =
        # TOO LATE (the threat is already on our tower; the response should have come sooner and
        # crediting it teaches slow defense -- same timing doctrine as the trade ledger).
        deep = self.threat_min_depth <= dpt <= self.threat_max_depth
        # PER-EPISODE CREDIT BUDGET: one push used to pay every role-matching card thrown at it
        # (+1.0 x4 across 18 s, measured). A real defense is 1-2 cards; further matches add no
        # information. The budget resets when the threat episode ends (tid unlights in
        # _update_threat).
        budget_ok = self._threat_credits < self.threat_credit_budget
        if prof.kind == "building":
            # A building ATTRACTS, it does not intercept -- central pull vs an off-lane wincon is
            # right physics, so no same-lane test. But it must actually be a DEFENSIVE building:
            # our half, not shoved to the bridge (the front-half tesla is a dump, not a pull).
            if not (0.50 <= cy <= 0.80 and deep and card_threat.counters(prof, tid)):
                return 0.0
            if not budget_ok:
                return 0.0
            self._threat_credits += 1
            return self.w_threat_response
        if prof.pull:
            return 0.0        # PULL spells are graded by their delayed clump payoff, not by role match
                              # (see sim/env._threat_response; live bills an empty cast via the trade spend)
        intercept = self._same_lane(cx) and cy >= 0.5
        if card_threat.counters(prof, tid):
            if not (intercept and deep):
                return 0.0
            if not budget_ok:
                return 0.0
            self._threat_credits += 1
            return self.w_threat_response
        if prof.spell:
            # DAMAGE SPELLS ARE NEVER A "MISREAD" (2026-08-15, mirrors the sim): the matrix only
            # role-validates spells vs swarms, so a defensive Rocket on a tank push was charged
            # -1.0 at intercept. Its worth is priced by the trade/chip terms; empty casts still
            # pay spell_waste. Measured: rocket at 0 plays while its logit row sat clean.
            return 0.0
        return self.w_threat_miss if intercept else 0.0

    def _threat_miss_idle_live(self, cur_mass: float) -> float:
        """No play while an ANSWERABLE threat is recognised (a KB counter is in hand AND affordable) =
        a missed defence (uncapped penalty)."""
        tid = self._threat_id_true
        if tid is None or len(tid) < card_threat.IDENTITY_DIM or tid[0] < 0.5:
            return 0.0
        for cid in self.hand_ids:
            if (0 <= cid < len(self._deck_profiles) and card_threat.counters(self._deck_profiles[cid], tid)
                    and self.card_elixir[cid] <= self.elixir):
                # PER-TICK, so it carries the decision-period scale (2026-08-20). This is charged
                # every decision the threat goes unanswered, whereas the SAME weight used by
                # _threat_response_live is charged per PLAY -- shortening the period must not
                # quietly multiply the idle charge while leaving the play charge alone. Measured
                # at -246.0 over 144 matches, this is the largest negative term in the live
                # ledger, so an accidental 1.67x would have been a serious re-weighting.
                return self.w_threat_miss * self._tick_scale
        return 0.0

    def _enemy_tracks_now(self, max_age=None, with_base=False):
        """Bridged enemy positions (the tracker carries a unit across detector blink-outs for
        forget_s, so one missed frame cannot fake an empty board).

        `max_age` demands FRESH evidence instead: a verdict about what a spell actually hit must
        not run on memory, because a false-positive detection is remembered for exactly as long
        as a real unit (see _eval_pending_spells).
        """
        try:
            if self._ploop is not None and self._ploop.running:
                return self._ploop.enemy_tracks(time.time(), with_base, max_age)
            return self._team_tracker.enemy_tracks(time.time(), with_base, max_age)
        except Exception:  # noqa: BLE001 -- perception hiccup: no verdicts this tick
            return []

    def _eval_pending_deploys(self, cur_elixir: float) -> float:
        """Settle deploy checks whose evidence has had time to appear.

        A LIKELIHOOD test, not a threshold. Elixir regenerates while we wait, so both hypotheses
        are carried forward to now -- deployed = pre - cost + regen, not-deployed = pre + regen --
        and the reading is assigned to whichever it sits closer to. Anything inside the dead band
        (the integer bar genuinely cannot separate them) is left alone: a missed detection costs
        nothing, a false one withholds credit for a play that really happened.
        """
        if not self._pending_deploys:
            return 0.0
        now = time.time()
        due = [d for d in self._pending_deploys if d["t_eval"] <= now]
        if not due:
            return 0.0
        self._pending_deploys = [d for d in self._pending_deploys if d["t_eval"] > now]
        for d in due:
            elapsed = max(0.0, now - d["t0"])
            regen = 0.357 * float(d["mult"]) * elapsed          # 1 elixir / 2.8 s at 1x
            if_deployed = d["pre"] - d["cost"] + regen
            if_not = d["pre"] + regen
            if if_not - if_deployed < 1.5:
                continue                                        # too close to call: say nothing
            obs = float(cur_elixir)
            if abs(obs - if_not) + 0.75 < abs(obs - if_deployed):
                self._failed_deploys += 1
                self._failed_deploys_match += 1
                if self.spell_verify_log:
                    name = (self.vision.deck_keys[d["card"]]
                            if 0 <= d["card"] < self.n_cards else str(d["card"]))
                    print("[deploy] %s never left the bar: %.0f -> %.0f after %.1fs "
                          "(deployed would read ~%.1f, not-deployed ~%.1f)"
                          % (name, d["pre"], obs, elapsed, if_deployed, if_not), flush=True)
        return 0.0

    def _eval_pending_spells(self) -> float:
        """Score due spell casts against FRESHLY SEEN reality. Returns the reward sum.

        The verdict deliberately does NOT use the tracker's bridged memory (2026-08-20, user:
        "spell waste is not triggering and the model is getting rewarded for casting spells at
        nothing"). A false-positive detection produces a track that is remembered for forget_s --
        4.5 s, longer than a rocket's entire flight -- so the phantom was still "inside the blast"
        at impact, no waste was billed, and the credit _wincon_exec_live paid at cast stood. The
        model was being taught that casting at ghosts pays. A unit genuinely under a spell is
        being detected continuously; one that has not been SEEN for spell_verify_fresh_s is not
        evidence that anything was hit.
        """
        if not self._pending_spells:
            return 0.0
        now = time.time()
        due = [p for p in self._pending_spells if p["t_eval"] <= now]
        if not due:
            return 0.0
        self._pending_spells = [p for p in self._pending_spells if p["t_eval"] > now]
        fresh = self._enemy_tracks_now(max_age=self.spell_verify_fresh_s, with_base=True)
        remembered = self._enemy_tracks_now(with_base=True)   # log only: fresh vs memory
        _, enemy_a, _ = _anchors(self.cfg)
        mine_a = _anchors(self.cfg)[0]
        total = 0.0
        for p in due:
            if p["kind"] == "whiff":
                if p.get("base") == "the_log":
                    # THE USER'S RULE, geometrically: nothing in the roll's path = a miss, however
                    # close the cast landed to a body it rolled away from.
                    miss = not log_hits(p["cx"], p["cy"], fresh, self.log_half_w, self.log_roll,
                                        self.air_bases)
                else:
                    miss = spell_whiffed(p["cx"], p["cy"], p["r"], fresh,
                                         tower_anchors=enemy_a[:2],
                                         tower_alive=list(self.tower.enemy_alive)[:2],
                                         tower_aim_radius=self.spell_aim_radius,
                                         tower_aim_tiles=self.spell_aim_tiles)
                if self.spell_verify_log:
                    def _in(tracks):
                        return [t for t in tracks
                                if math.hypot((t[0] - p["cx"]) * 18.0,
                                              (t[1] - p["cy"]) * 32.0) <= p["r"]]
                    f_in, m_in = _in(fresh), _in(remembered)
                    # NAME what is in the blast. The user could not tell whether a "hit" was a
                    # real enemy, one of OUR units mis-tagged, or a phantom -- so say which cards
                    # the verdict is standing on.
                    who = ", ".join(sorted({str(t[4]) for t in f_in
                                            if len(t) > 4 and t[4]})) or "-"
                    print("[spell] %-9s at (%.2f, %.2f) r=%.1f tiles -> %s | in blast: %d fresh "
                          "(%s), %d remembered%s"
                          % (p.get("base", "?"), p["cx"], p["cy"], p["r"],
                             "WHIFF" if miss else "hit", len(f_in), who, len(m_in),
                             "  <- PHANTOM: only memory saw it" if miss and m_in else ""),
                          flush=True)
                if miss:
                    total += self.rw_stats.add("spell_waste", self.w_spell_waste_live)
                    # ...and take BACK what the cast was paid by aim geometry. Without this a
                    # whiffed spell nets "a small penalty minus the credit it already banked",
                    # which is why casting at nothing could still come out ahead.
                    paid = float(p.get("paid") or 0.0)
                    if paid > 0.0:
                        total += self.rw_stats.add("spell_waste_clawback", -paid)
            elif p["kind"] == "nado":
                if p.get("king_cast"):
                    continue                        # king-activation intent: never billed
                if nado_regressed(p["pulled"], fresh, [tuple(a) for a in mine_a[:2]]):
                    total += self.rw_stats.add("nado_bad", self.w_nado_bad)
        return total

    def _wheels_spell_aim(self, card_id: int, cell: int) -> int:
        """Doctrine aim for non-rocket spells when the model's own aim covers no enemy."""
        gx, gy = cell % self.gw, cell // self.gw
        cx, cy = self.actions.cell_center(gx, gy)
        tracks = self._enemy_tracks_now()
        base = card_threat.base_key(self.vision.deck_keys[card_id]) if 0 <= card_id < self.n_cards else ""
        kb = self.db.get(base) or {}
        if base == "the_log":
            # A ROLL, NOT A BLAST. The circular test below passes for a Log dropped just forward
            # of a troop -- the troop is a tile away, well inside the radius -- so this function
            # used to return early and the corridor correction never ran, which is precisely the
            # "log played too high, hits nothing, scores a hit" report (2026-08-20). Ask the real
            # question instead: would the roll touch anything?
            if log_hits(cx, cy, tracks, self.log_half_w, self.log_roll, self.air_bases):
                return cell
        else:
            r_tiles = float(kb.get("radius_tiles") or 2.5) + 1.0
            if any(math.hypot((t[0] - cx) * 18.0, (t[1] - cy) * 32.0) <= r_tiles for t in tracks):
                return cell                               # the model aimed at something real
        if card_id in self.tornado_ids and nado_king_cell is not None:
            got = nado_king_cell(tracks, _anchors(self.cfg)[0], self.actions)
            if got is not None:
                return got
        if base == "the_log" and log_corridor_cell is not None:
            # LEAD THE LOG TOO. Its own roll adds travel time on top of the cast delay, so a
            # corridor drawn through where the enemies stand NOW misses a marching push by the
            # time the roll arrives (user, 2026-08-20). Advance the tracks first, then draw the
            # corridor through the predicted positions.
            eta = self._impact_time(cx, cy, is_rocket=False)
            led = []
            for t in tracks:
                vx, vy = lead_velocity(t, self.db)
                led.append((t[0] + vx * eta, t[1] + vy * eta) + tuple(t[2:]))
            got = log_corridor_cell(cx, cy, led or tracks, self.actions)
            if got is not None:
                return got
        # nearest tracked enemy, if any -- better a mediocre hit than a certain whiff
        best, bd = None, 10.0
        for t in tracks:
            g = math.hypot(t[0] - cx, t[1] - cy)
            if g < bd:
                best, bd = t, g
        if best is not None:
            ngx, ngy = self.actions.coords_to_grid(best[0], best[1])
            return int(ngy) * self.gw + int(ngx)
        return cell

    def _base_of(self, card_id: int) -> str:
        """Deck key -> KB base name (evo suffix stripped), or "" for an out-of-range id."""
        if not (0 <= card_id < self.n_cards):
            return ""
        return card_threat.base_key(self.vision.deck_keys[card_id])

    def _my_xbow_live(self):
        """Our own X-Bow on the board, from the detector's MINE tags -- the anchor the deck's
        defensive doctrine is written around ("keep the bow firing"). None when it is not out."""
        for d in (getattr(self, "_last_dets_all", None) or []):
            try:
                if d.team == "mine" and card_threat.base_key(str(d.base)) == "x_bow":
                    return float(d.cx), float(d.gy)
            except Exception:  # noqa: BLE001 -- a malformed detection is not a bow
                continue
        return None

    def _enemy_massing_back(self) -> bool:
        """Are they BUILDING in their own back half (beatdown setup) with nothing committed yet?

        Read from the tracker's bridged, corroborated enemy tracks -- the same source the threat
        gate and the spell wheels use, so a single-frame phantom cannot fake a beatdown.
        """
        try:
            tracks = self._enemy_tracks_now()
            units = [(t[0], t[1], (t[4] if len(t) > 4 else "")) for t in tracks]
            return threat_value.massing_in_back(self.db, units)
        except Exception:  # noqa: BLE001 -- perception hiccup: assume no beatdown, act normally
            return False

    def _defensive_bow_cell(self, cell: int) -> int:
        """Pull an X-Bow back into the DEFENSIVE centre band (env.xbow_defense_front/back).

        Kept as a correction rather than a hard coordinate so a model that already chose a
        defensive spot keeps its own cell -- the training-wheels contract everywhere else.
        """
        gx, gy = cell % self.gw, cell // self.gw
        cx, cy = self.actions.cell_center(gx, gy)
        if self.xbow_defense_front <= cy <= self.xbow_defense_back and abs(cx - 0.48) <= 0.14:
            return cell                                   # already a defensive bow: leave it
        mid = 0.5 * (self.xbow_defense_front + self.xbow_defense_back)
        ngx, ngy = self.actions.coords_to_grid(0.48, mid)
        return int(ngy) * self.gw + int(ngx)

    def _combo_worth(self, cx: float, cy: float) -> float:
        """Enemy elixir standing inside the pull, from FRESH sightings only.

        A combo that catches nothing is not a combo. The first version of this credit tested only
        geometry and timing, so rocket-then-tornado on any tile paid the full multiplier with no
        effect on the board whatsoever -- and the wheels automated it. The sim never had that
        hole: it requires real troops worth at least rocket_min_worth. Fresh tracks, not
        remembered ones, for the same reason spell verdicts use them (a phantom is remembered
        exactly as long as a real unit).
        """
        pull_tiles = float(self.cfg.get("env", "nado_pull_tiles", default=5.5))
        worth = 0.0
        for t in self._enemy_tracks_now(max_age=self.spell_verify_fresh_s, with_base=True):
            if math.hypot((t[0] - cx) * 18.0, (t[1] - cy) * 32.0) > pull_tiles:
                continue
            base = str(t[4]) if len(t) > 4 and t[4] else ""
            if base and (self.db.kind(base) or "") == "spell":
                continue                                          # an effect is not a body
            worth += float((self.db.elixir(base) or 0.0) if base else 0.0)
        return worth

    def _combo_lands_in_pull(self, cx: float, cy: float, eta: float) -> bool:
        """Will a rocket aimed at (cx, cy), landing `eta` from now, go off inside a tornado's
        pull, on the same spot -- AND catch something worth the six elixir?"""
        nado = getattr(self, "_last_nado", None)
        if nado is None or math.hypot(cx - nado[0], cy - nado[1]) > self.rocket_nado_radius:
            return False
        start = nado[2] + self.tornado_time                      # the pull begins on activation
        impact = time.time() + float(eta)
        if not (start <= impact <= start + self.nado_pull_s):
            return False
        return self._combo_worth(cx, cy) >= self.rocket_min_worth

    def _tornado_onto_rocket(self, cx: float, cy: float) -> bool:
        """The DOCTRINAL order: a rocket is already in the air, this tornado lands on its blast
        point in time to hold a REAL clump there for it."""
        rk = getattr(self, "_last_rocket", None)
        if rk is None or math.hypot(cx - rk[0], cy - rk[1]) > self.rocket_nado_radius:
            return False
        start = time.time() + self.tornado_time                  # this pull begins on activation
        if not (start <= rk[2] <= start + self.nado_pull_s):
            return False
        return self._combo_worth(cx, cy) >= self.rocket_min_worth

    def _where_cell(self, where, tx, ty, bow=None):
        """Map one WHERE vocabulary word onto board coordinates.

        Our towers are at the HIGH-y end, so "in front of the threat" means DEEPER than it (+y):
        between the attacker and what it is walking at. Every offset clears at least one grid row,
        because the 24-row grid quantises anything smaller straight back onto the same cell (the
        lesson the sim's doctrine offsets already carry).
        """
        row = 1.0 / float(self.gh)
        mine_a = _anchors(self.cfg)[0]
        kx, ky = (mine_a[2] if len(mine_a) >= 3 else (0.495, 0.72))
        if where == "on_top" or where == "surround":
            return tx, ty
        if where == "in_front":
            return tx, ty + row
        if where == "behind_threat":
            return tx, ty - row
        if where == "center_kite":
            # centre of our half: the push has to walk a longer diagonal under fire, and BOTH
            # princess towers reach the middle.
            return kx, min(ty + 2 * row, ky - 2 * row)
        if where == "at_tower":
            # tight to the threatened princess, one row in front of it -- the tower's own dps
            # joins the defence (skeletons vs wall breakers, per the user).
            px, py = min(mine_a[:2], key=lambda a: abs(a[0] - tx)) if len(mine_a) >= 2 else (kx, ky)
            return px, py - row
        if where == "opposite_lane":
            return (2.0 * kx - tx), ty
        if where == "king_activation":
            got = nado_king_cell(self._enemy_tracks_now(), mine_a, self.actions) \
                if nado_king_cell is not None else None
            if got is not None:
                gx, gy = got % self.gw, got // self.gw
                return self.actions.cell_center(gx, gy)
            return kx, ky - row
        return None

    def _wheels_troop_aim(self, card_id: int, cell: int) -> int:
        """Doctrine placement for the DEFENDERS (DOCTRINE.md 2; mirrors sim doctrine's
        _bow_defence_cells, whose geometry is engine-verified).

            knight     -- the bodyguard. With a bow out: one row in front of it, on the threat's
                          side, so the answer walking at the bow hits him first. Without a bow:
                          between the attacker and our tower -- a body-block, not a chase.
            skeletons  -- ON the attacker. Three bodies on a distracted single-target melee kill
                          it, and even losing them buys the bow two or three more shots.
            ice_wizard -- BEHIND, deeper into our half and offset sideways: he is never the kill,
                          he is the multiplier, and he must not share a spell radius with the bow.

        Cell only, and only when the model is grossly off (a placement already within the
        tolerance is the model's to keep -- the wheels exist to stop donations, not to freeze the
        cell head). Returns the original cell whenever no rule applies.
        """
        base = self._base_of(card_id)
        table = getattr(self, "counter_table", None)
        tabled = bool(table) and len(table) > 0
        if not tabled and base not in ("knight", "skeletons", "ice_wizard"):
            return cell
        tracks = self._enemy_tracks_now()
        # the threat = the enemy that has come DEEPEST into our half (largest y is nearest our
        # towers); nothing past the river means there is nothing to body-block.
        threat = None
        for t in tracks:
            if float(t[1]) > 0.42 and (threat is None or float(t[1]) > float(threat[1])):
                threat = t     # 0.42 = the river line train_rl._needs_answer already triages on
        if threat is None:
            return cell
        tx, ty = float(threat[0]), float(threat[1])
        row = 1.0 / float(self.gh)                    # one GRID row; smaller offsets quantise away
        # THE RESEARCHED PLACEMENT WINS when the table has one for this card against this threat
        # group -- that is the whole point of recording WHERE per row ("skeletons vs wall
        # breakers go AT_TOWER, so the princess tower helps kill them"). The hand-written
        # geometry below stays as the fallback for cards and boards the table does not cover.
        if tabled:
            names = [str(t[4]) for t in tracks
                     if len(t) > 4 and t[4] and float(t[1]) > 0.42]
            for resp in table.responses(names, hand_bases=[base]):
                spot = self._where_cell(str(resp.get("where") or ""), tx, ty)
                if spot is not None:
                    ngx, ngy = self.actions.coords_to_grid(spot[0], spot[1])
                    return int(ngy) * self.gw + int(ngx)
        if base not in ("knight", "skeletons", "ice_wizard"):
            return cell                               # no table row and no hand-written rule
        # OUR KING, from the anchors rather than a guess: it is the no-deploy footprint every
        # placement below has to dodge, and the board centre the ranged defender pulls toward.
        mine_a = _anchors(self.cfg)[0]
        kx, ky = (mine_a[2] if len(mine_a) >= 3 else (0.495, 0.72))
        bow = self._my_xbow_live()
        if bow is not None:
            bx, by = bow
            toward = row if ty > by else -row         # one row from the bow, on the threat's side
            if base == "knight":
                nx, ny = bx, by + toward
            elif base == "skeletons":
                nx, ny = tx, ty
            else:                                     # ice_wizard: behind the bow, offset sideways
                nx, ny = bx + (0.06 if bx < kx else -0.06), by + 2 * row
        else:
            if base == "knight":
                nx, ny = tx, ty + row                 # between the attacker and our tower
            elif base == "skeletons":
                nx, ny = tx, ty
            else:
                nx, ny = tx + (kx - tx) * 0.5, ty + 3 * row     # back and toward the centre
        # never aim into our own king tower's footprint: the tap is a no-op there, so the card is
        # "played" and nothing is placed (the same failure defensive_cell documents).
        ny = min(ny, ky)
        if abs(nx - kx) < 0.06 and ny > ky - 0.06:
            nx = kx + (0.09 if tx >= kx else -0.09)
        gx, gy = cell % self.gw, cell // self.gw
        cx, cy = self.actions.cell_center(gx, gy)
        if math.hypot(cx - nx, cy - ny) <= 2.5 * row:
            return cell                               # already doctrinal enough -- leave it alone
        ngx, ngy = self.actions.coords_to_grid(nx, ny)
        return int(ngy) * self.gw + int(ngx)

    def _hog_wincon_live(self, card_id: int, cx: float, cy: float) -> float:
        """Live twin of the sim's rush win-condition term -- see sim/env._hog_wincon.

        Same three rules in the same order (never into a committed push, bridge only, lane bonus),
        read from perception rather than engine truth: the tracker's bridged, corroborated enemy
        positions, and the same triage gate the threat gate uses.
        """
        tracks = self._enemy_tracks_now(with_base=True)
        bases = [str(t[4]) for t in tracks if len(t) > 4 and t[4] and float(t[1]) > 0.42]
        if bases:
            try:
                if threat_value.bodies_ignore_frac(
                        self.db, bases, tower_level=15) >= threat_value.IGNORE_FRAC:
                    return self.w_wincon_mis      # a real push is on our half: not the moment
            except Exception:  # noqa: BLE001 -- a KB miss must not turn into free credit
                return 0.0
        if cy > self.hog_bridge_y:
            return self.w_wincon_mis              # sent from our own half, not the bridge
        val = self.w_wincon
        mass_l = sum(float(self.db.elixir(str(t[4])) or 0.0) for t in tracks
                     if len(t) > 4 and t[4] and float(t[0]) < 0.5)
        mass_r = sum(float(self.db.elixir(str(t[4])) or 0.0) for t in tracks
                     if len(t) > 4 and t[4] and float(t[0]) >= 0.5)
        if (mass_l or mass_r) and ((cx >= 0.5) if mass_l > mass_r else (cx < 0.5)):
            val *= self.hog_punish_mult           # opposite lane to their commitment
        return val

    def _wincon_exec_live(self, card_id: int, cx: float, cy: float) -> float:
        """(3) WIN-CONDITION execution: X-Bow forward-in-range (offence) / back-centre (defence), Miner
        chipping the princess (not the king), the defensive rocket-cycle chip. + right, - thrown away."""
        if card_id in self.xbow_ids:
            _, enemy_a, _ = _anchors(self.cfg)
            princesses = enemy_a[:2] if len(enemy_a) >= 2 else enemy_a
            d = min((math.hypot(cx - ax, cy - ay) for ax, ay in princesses), default=1.0)
            # "back-centre" = the CENTER INTERCEPT band behind the bridge (the Tesla area), NOT behind your
            # princess towers; deeper than the towers earns only a small fraction (soft shaping).
            central = abs(cx - 0.48) <= 0.18
            in_band = central and self.xbow_defense_front <= cy <= self.xbow_defense_back
            behind = central and cy > self.xbow_defense_back
            frac = 1.0 if in_band else (self.xbow_deep_frac if behind else 0.0)
            if self._defensive:
                val = self.w_wincon * frac if frac > 0.0 else self.w_wincon_mis
            elif d <= self.xbow_range:
                val = self.w_wincon
            else:
                val = self.w_wincon * 0.4 * frac if frac > 0.0 else self.w_wincon_mis
            # REPEAT-CREDIT GATE, live twin of sim/env._wincon_exec's (2026-08-12): no positive
            # credit while our previous X-Bow can still be standing. Live cannot reliably SEE its
            # own bow (detector recall), but it KNOWS when it played one -- so "standing" is the
            # KB lifetime window since our last X-Bow play. Perception-independent by design; the
            # cost is a brief over-waive when the bow died early, which only withholds a bonus.
            # Misplaces still charge, and sequential re-placement re-credits once the window lapses.
            if val > 0.0 and self._xbow_play_t is not None \
                    and (time.time() - self._xbow_play_t) < self.xbow_lifetime:
                val = 0.0
            self._xbow_play_t = time.time()      # every X-Bow play re-anchors the window
            return val
        if card_id in self.rush_wincon_ids:
            return self._hog_wincon_live(card_id, cx, cy)
        if card_id in self.tornado_ids:
            # THE DOCTRINAL HALF OF THE COMBO: the rocket went first and this tornado drags a real
            # clump onto its blast point. Credited on the TORNADO -- the card whose timing the
            # player still controls once the rocket is away -- and on that card ONLY, so the pair
            # cannot be billed twice. Guarded on BODIES: without that, this branch paid the full
            # multiplier for two casts at an empty tile, which is how it became a 9-point exploit
            # within hours of shipping (audit, 2026-08-20).
            if near_enemy_king(cx, cy, self.cfg, self.spell_aim_radius):
                return self.w_wincon_mis                          # never rescue a king cast
            if self._tornado_onto_rocket(cx, cy):
                return self.w_wincon * self.rocket_nado_mult
        if card_id in self.rocket_ids:
            # NEVER THE KING (2026-08-20, user report: the model learned to rocket-cycle it).
            # This branch used to fall through to `return 0.0` -- the existing near_enemy_king
            # guard lives in the MINER branch below and never applied to a rocket. Zero is not
            # neutral in practice: it dodges the leak penalty, so it was a free way to dump six
            # elixir. The king has ~twice a princess's HP and the tiebreak reads PRINCESS HP, so
            # this chip buys nothing at all.
            if near_enemy_king(cx, cy, self.cfg, self.spell_aim_radius):
                return self.w_wincon_mis
            # ROCKET + TORNADO, SAME TILE, and the rocket's blast must land INSIDE the pull
            # (DOCTRINE_RESEARCH.md R6: "cast the ROCKET FIRST, then Tornado onto the blast
            # point"). Paying "a rocket that follows a tornado" -- which is what this did at
            # first, and what the sim has always done -- rewards the order the mechanics forbid:
            # the pull is ~1.05 s and a rocket's cast+travel is longer, so a tornado cast first
            # has released the clump before the blast arrives.
            if self._combo_lands_in_pull(cx, cy, self._impact_time(cx, cy, is_rocket=True)):
                # The narrow legitimate reverse case: a tornado cast so late that its pull is
                # still running when the rocket lands. Paid at half, because the doctrinal order
                # is the one being taught and this must not become the cheaper way to earn it.
                return self.w_wincon * self.rocket_nado_mult * 0.5
            pxy = self._pump_xy if self._pump_fresh() else None   # PUMP PUNISH mirror (perception-gated)
            if pxy is not None and math.hypot(cx - pxy[0], cy - pxy[1]) <= self.pump_aim_radius:
                _, enemy_a, _ = _anchors(self.cfg)
                kx, ky = enemy_a[2] if len(enemy_a) >= 3 else (0.48, 0.11)
                if math.hypot(cx - kx, cy - ky) <= self.pump_king_guard:
                    return self.w_wincon_mis              # blast would wake the king -- never for a pump
                both = any(bool(self.tower.enemy_alive[i])
                           and math.hypot(cx - ax, cy - ay) <= self.spell_aim_radius
                           for i, (ax, ay) in enumerate(enemy_a[:2]))
                return self.w_wincon * (self.combo_mult if both else 1.0)
            if self._defensive and near_enemy_princess(cx, cy, self.cfg, self.spell_aim_radius):
                return self.w_wincon * 0.6
            return 0.0
        if card_id in self.miner_ids:
            if near_enemy_king(cx, cy, self.cfg, self.spell_aim_radius):
                return self.w_wincon_mis
            if near_enemy_princess(cx, cy, self.cfg, self.spell_aim_radius):
                return self.w_wincon
        return 0.0

    def _trade_events_live(self):
        """ELIXIR-TRADE v3.1 (2026-08-14): attributed event ledger WITH RESPONSE TIMING.

        v3 attributed enemy deaths to our nearby units, which fixed the tower-kill and flicker
        payouts -- but it still paid FULL credit for a LATE defense: a tesla dropped ten seconds
        after the hog crossed, after several tower hits, still collected the kill (user report).
        Timing is now a factor, exactly as the doctrine wants it: each enemy track records WHEN
        it crossed onto our half; an attributed kill pays full credit only if our engagement was
        prompt -- scale 1.0 inside trade_grace_s (3 s) of the crossing, decaying linearly to 0
        at trade_late_s (10 s). A death on THEIR half (our push trading) has no timing discount.

        Mechanics preserved from v3: 2-frame vanish confirmation (flicker cancels), kill
        attribution within trade_kill_radius_tiles of a living unit of ours, unconditional
        debit for our own losses, elixir bars excluded, blind-on-active frames hold snapshots.
        Track continuity is nearest-neighbour per base key (trade_match_radius_tiles); the
        crossing timestamp rides the match so it survives drift."""
        if self._detector is None:
            return 0.0
        dets = self._last_dets_all
        blind = (dets is None or self._last_dets_age > self.phi_max_age
                 or (not dets and (getattr(self, "_last_mass", None) or 0.0) >= self.quiet_frac))
        if blind:
            return 0.0                                   # hold the snapshots; no events this frame
        now = float(getattr(self, "_last_frame_t", None) or time.time())
        tx, ty = 18.0, 32.0                              # tile aspect for distances
        HALF = 0.48                                      # our half begins here (frame-y, warped board)

        def _fresh(team):
            out = []
            for d in dets:
                if getattr(d, "team", None) != team:
                    continue
                base = str(getattr(d, "base", "") or "")
                if base.endswith("_evo"):
                    base = base[:-4]
                cost = float(self._db.elixir(base) or 0.0)
                if cost > 0.0:
                    t_cross = now if float(d.gy) >= HALF else None
                    out.append([base, float(d.cx), float(d.gy), cost, t_cross])
            return out

        def _dist(a1, b1):
            return (((a1[1] - b1[1]) * tx) ** 2 + ((a1[2] - b1[2]) * ty) ** 2) ** 0.5

        credit = debit = 0.0
        cur_by_side = {}
        for side in ("enemy", "mine"):
            prev = getattr(self, "_tr_prev_" + side, [])
            cur = _fresh(side)
            # MATCH cur against prev (nearest neighbour per base): carry the crossing time so a
            # track keeps its history as it drifts; unmatched prev entries become vanish pendings.
            taken = set()
            for c in cur:
                best_i, best_d = -1, self.trade_match_r
                for i, t in enumerate(prev):
                    if i in taken or t[0] != c[0]:
                        continue
                    dd = _dist(c, t)
                    if dd <= best_d:
                        best_i, best_d = i, dd
                if best_i >= 0:
                    taken.add(best_i)
                    if prev[best_i][4] is not None:
                        c[4] = prev[best_i][4]           # inherited crossing time wins (earliest)
            vanished = [t for i, t in enumerate(prev) if i not in taken]
            cur_by_side[side] = cur
            setattr(self, "_tr_cur_" + side, cur)
            setattr(self, "_tr_van_" + side, vanished)
        for side, pend_key in (("enemy", "_tr_pend_en"), ("mine", "_tr_pend_own")):
            cur = cur_by_side[side]
            pend = getattr(self, pend_key, [])
            for pv in pend:                              # resolve last frame's pendings
                if any(t[0] == pv[0] and _dist(t, pv) <= self.trade_match_r for t in cur):
                    continue                             # came back: flicker, no event
                if side == "enemy":
                    near_own = any(_dist(o, pv) <= self.trade_kill_r
                                   for o in cur_by_side["mine"] + getattr(self, "_tr_prev_mine", []))
                    if not near_own:
                        continue                         # the tower's kill / walked out / expired
                    scale = 1.0
                    if pv[4] is not None:                # died on OUR half: was the answer PROMPT?
                        late = now - float(pv[4])
                        if late > self.trade_grace_s:
                            span = max(0.1, self.trade_late_s - self.trade_grace_s)
                            scale = max(0.0, 1.0 - (late - self.trade_grace_s) / span)
                    credit += pv[3] * scale
                else:
                    debit += pv[3]                       # our unit is gone, whoever did it
            setattr(self, pend_key, getattr(self, "_tr_van_" + side))
            setattr(self, "_tr_prev_" + side, cur)
        if credit == 0.0 and debit == 0.0:
            return 0.0
        d = float(np.clip((credit - debit) / self.value_norm, -self.trade_cap, self.trade_cap))
        return d * self.w_elixir_trade

    def _trade_reward(self, cur_elixir: float) -> float:
        """(2) ELIXIR-TRADE: attributed kill/loss events (see _trade_events_live)."""
        return self._trade_events_live()

    def _chip_progress(self, hp_list, full: float) -> float:
        """Convex chip 'progress' over a side's princess towers: sum of (damage_fraction ** chip_power) so
        PARTIAL chip is worth sub-proportionally LESS than finishing the tower. Most of a tower's value is
        the CROWN (take/lose), so the reward JUMPS when it is actually destroyed -- a tower at 1-2 HP still
        fully works, so it's worth far less than one at 0."""
        prog = 0.0
        for hp in list(hp_list)[:2]:
            if full > 0:
                d = max(0.0, min(1.0, 1.0 - hp / full))
                prog += d ** self.chip_power
        return prog

    def _bonus(self, credit: float) -> float:
        """Cap the CUMULATIVE correctness shaping per match, SYMMETRICALLY (anti-farm both ways).

        This used to cap only the POSITIVE side and let penalties through untouched. Over a ~180-300
        decision match that is not a cap, it is a slope: the bonus saturates at `correctness_cap` while
        the penalty stream keeps growing, so the highest-value policy becomes the one that ENDS THE
        MATCH SOONEST -- exactly the passivity/self-defeat collapse this project has now hit three
        times. Bounding both signs by the same budget keeps the original anti-farm intent without
        making 'stop playing' the optimum.
        """
        if credit >= 0.0:
            allowed = min(credit, max(0.0, self.correctness_cap - self._match_bonus))
            self._match_bonus += allowed
            return allowed
        allowed = min(-credit, max(0.0, self.correctness_cap - self._match_penalty))
        self._match_penalty += allowed
        return -allowed

    def step(self, action: Action):
        play, card_id, cell = action
        pre_elixir = float(self.elixir)           # what the DECISION saw (the post-action read
                                                  # overwrites self.elixir at the end of this step)
        raw_cell = cell                           # the model's ATTEMPTED cell, before aim + deploy-clamp
        if play:                                  # rocket / offensive miner -> aim the weaker enemy princess tower
            pre_aim = cell
            cell = self._aim_weaker_tower(card_id, cell)
            if (self.training_wheels and card_id in self.tornado_ids
                    and getattr(self, "_last_rocket", None) is not None
                    and time.time() < self._last_rocket[2]):
                # SAME TILE AS THE ROCKET, and the right way round (R6). A rocket is in the air:
                # this tornado goes onto its blast point so the clump is still being held when it
                # lands. The earlier version of this snapped the ROCKET onto an old tornado --
                # the order the mechanics forbid, since a ~1.05 s pull has expired by then.
                ngx, ngy = self.actions.coords_to_grid(self._last_rocket[0], self._last_rocket[1])
                cell = int(ngy) * self.gw + int(ngx)
            elif cell == pre_aim and card_id in self.rocket_ids:  # no tower/pump snap -> LEAD tracked troops
                cell = self._aim_rocket_intercept(cell)
            if self.training_wheels and card_id in self.spell_ids and card_id not in self.rocket_ids:
                # TRAINING WHEELS (train.training_wheels, 2026-08-19): every remaining SPELL gets
                # the same doctrine aim correction the rocket already had. The card is NEVER
                # changed and a play is NEVER converted to a wait -- the DQN's stored action keeps
                # its card axis, and cell-level correction is the already-accepted contract
                # (raw_cell keeps the model's attempt for telemetry). Log snaps to its corridor
                # over tracked enemies; a tornado with an empty aim goes to the king-activation
                # cell when one exists, else onto the densest enemy clump; any other spell aimed
                # at nothing snaps to the nearest tracked enemy. A model that has not yet learned
                # WHERE spells go stops donating elixir while it learns WHEN they go.
                cell = self._wheels_spell_aim(card_id, cell)
            elif self.training_wheels and play:
                # ...and the DEFENDERS, which is where this deck's defence actually lives. Same
                # contract: cell only, card untouched, and a placement the model already got
                # roughly right is left alone (see _wheels_troop_aim's tolerance).
                cell = self._wheels_troop_aim(card_id, cell)
            cell = self.actions.deploy_clamp(card_id in self.anywhere_ids, cell)  # rocket + miner go anywhere; rest = your half
            # DEFENSIVE BOW when they are BUILDING IN THE BACK (2026-08-20, user rule). The
            # forward snap below is what makes an offensive bow lock; running it while a beatdown
            # is assembling is precisely how six elixir gets blocked before it fires a shot. Same
            # card, opposite intent -- so the snap is skipped and the bow keeps the back-centre
            # cell the leak-guard/doctrine chose for it.
            if card_id in self.xbow_ids and self._enemy_massing_back():
                cell = self._defensive_bow_cell(cell)
            elif card_id in self.xbow_ids and not self._defensive:  # OFFENSIVE phase only: snap a forward X-Bow onto the nearer lane so it LOCKS
                gx, gy = cell % self.gw, cell // self.gw
                cx, cy = self.actions.cell_center(gx, gy)
                _, enemy_a, _ = _anchors(self.cfg)
                # WHICH TOWER FIRST, then whether it locks. Order matters: xbow_lock_cell snaps to
                # the NEARER princess, so if the bow is sitting in a lane whose tower is already
                # down, running it first cements the mistake. Live overtime showed exactly that --
                # several perfect bows, all of them in the dead lane.
                lane = xbow_target_lane_cell(cx, cy, enemy_a, self._enemy_tower_hp(),
                                             self.tower.enemy_alive, self.xbow_defense_front,
                                             self.actions)
                if lane is not None:
                    cell = lane
                    gx, gy = cell % self.gw, cell // self.gw
                    cx, cy = self.actions.cell_center(gx, gy)
                snapped = xbow_lock_cell(cx, cy, enemy_a, self.xbow_range, self.xbow_defense_front, self.actions)
                if snapped is not None:
                    cell = snapped
                # ...then fix its DEPTH from the column it ended up in: behind a bridge it can sit a
                # row back (leaving room to body-block the answer in front of it), off-lane it must
                # be on the frontmost deployable row or the diagonal puts the tower out of reach.
                gx, gy = cell % self.gw, cell // self.gw
                cx, cy = self.actions.cell_center(gx, gy)
                depth = xbow_offense_depth_cell(cx, cy, self.xbow_defense_front,
                                                self.deploy_top, self.actions)
                if depth is not None:
                    cell = depth
                # RE-CLAMP. The lane/lock/depth chain above runs AFTER deploy_clamp and can walk
                # the bow off the deployable area entirely -- MEASURED, 122 live plays landed on
                # grid row 12 with min_own_gy 13, one row past the line, where the arena tap does
                # nothing and the card never leaves the bar. Illegal-cell plays deployed 24% of
                # the time against 42% for legal ones (2026-08-20 audit).
                cell = self.actions.deploy_clamp(card_id in self.anywhere_ids, cell)
            elif card_id in self.tesla_ids:
                # CENTRE-PULL: a win condition dropped at one bridge beelines the near tower and only
                # that tower shoots it. Placing the Tesla at the far edge of the wincon's OWN aggro
                # radius drags it across the middle instead. Uses that card's KB sight range, so a
                # 9.5-tile Hog is pulled much further than a 5.5-tile Ram Rider.
                wc = self._lane_wincon()
                if wc is not None:
                    wx, wy, sight = wc
                    pull = tesla_pull_cell(wx, wy, sight, self.tesla_pull_front,
                                           self.tesla_pull_back, self.actions)
                    if pull is not None:
                        cell = pull
            action = (play, card_id, cell)
        # WHAT ACTUALLY HAPPENED (2026-08-19). Every assist above rewrites the CELL after the
        # policy chose it, so on most plays the executed action is NOT the chosen one. The replay
        # buffer must store THIS one: Q-learning is off-policy, so crediting the executed cell
        # teaches the doctrine placement (the wheels become demonstrations), while crediting the
        # model's original cell teaches it that its own bad cell earned the corrected cell's
        # reward -- which is how a crutch becomes permanent.
        self._last_exec_action = action
        now = time.time()                                     # -- cadence: decision-to-decision wall time
        if self._last_step_t is not None:
            self._cad["loop"] += now - self._last_step_t
            self._cad_n += 1
        self._last_step_t = now
        t0 = time.time()
        self._execute(action)
        self._cad["act"] += time.time() - t0
        # The spell-impact frame sampler is DELETED (ELIXIR_TRADE_DESIGN.md 5): under the
        # potential-based trade term a spell's consequence settles from the ordinary frame
        # stream (dead enemy tracks disappear over the next frames), and the sampler's blocking
        # wait -- up to ~spell_eval_time + 0.6 s -- was the single biggest cadence outlier this
        # deck had. The rocket aim/lead assists stay: they are control, not reward.
        if True:
            # PACED WAIT, anchored to the PREVIOUS OBSERVATION. The old form slept the full
            # act_period and THEN paid the whole pipeline (grab + vision + OCR + detector + tap), so
            # the served cadence was act_period + pipeline -- measured ~2.2 s/decision against the
            # trained agent_dt of 1.0 s (log 2026-08-12, C-list item 5: an unflagged train/serve
            # mismatch). Waiting only for what REMAINS of the period since the last frame grab runs
            # the pipeline inside the period, so the served cadence converges to act_period whenever
            # pipeline + learner fit within it (and to their sum, not their sum + act_period, when
            # they don't). EVENT-DRIVEN wake is unchanged: perception can still cut the wait short
            # the moment it spots a new enemy commitment (react_min_gap rate-limits, so quiet-board
            # cadence stays at the trained act_period).
            t0 = time.time()
            remaining = self.act_period if self._last_frame_t is None else \
                max(0.0, self._last_frame_t + self.act_period - t0)
            woke = False
            if self._ploop is not None and self._ploop.running:
                if remaining > 0.0:
                    # wait_event returns True when PERCEPTION cut the wait short -- this decision
                    # exists because something just happened. That answer was being discarded;
                    # it is the cleanest signal available for "be quick now".
                    woke = bool(self._ploop.wait_event(remaining, self.react_min_gap))
            elif remaining > 0.0:
                time.sleep(remaining)
            self._fast_tick = woke and self.fast_reaction_tick
            self._cad["wait"] += time.time() - t0
            t0 = time.time()
            frame = self._grab()
            self._cad["grab"] += time.time() - t0
        self._last_frame_t = time.time()
        if frame is None:
            return self._last_obs, 0.0, True, {"outcome": None, "error": "capture_lost"}

        t0 = time.time()
        state = self.vision.detect_state(frame)
        self._cad["state"] += time.time() - t0
        if state == GameState.IN_MATCH:
            t0 = time.time()
            prev_princess = list(self.tower.mine_alive[:2])
            prev_enemy = list(self.tower.enemy_alive[:2])
            # OUTCOME compass: the CROWN is the big JUMP (enemy tower taken -> +take, my king lost -> +lose);
            # tower_hp.step still READS/updates per-tower HP -- its own linear return is unused now.
            crown_r = self.tower.step(frame)
            self.tower_hp.step(frame)
            # CONVEX chip proxy: partial chip is worth sub-proportionally little (a tower at 1-2 HP still
            # works), so the reward JUMPS on the crown, not gradually with damage.
            ep = self._chip_progress(self.tower_hp.enemy_hp, self.tower_hp.full)
            reward = crown_r + (ep - self._prev_chip_prog) * self.tower_chip_scale
            self.rw_stats.add("crown", crown_r)
            self.rw_stats.add("chip_offence", (ep - self._prev_chip_prog) * self.tower_chip_scale)
            self._prev_chip_prog = ep
            mp = self._chip_progress(self.tower_hp.my_hp, self.tower_hp.my_full)
            reward -= (mp - self._prev_chip_prog_def) * self.tower_chip_scale
            self.rw_stats.add("chip_defence", -(mp - self._prev_chip_prog_def) * self.tower_chip_scale)
            self._prev_chip_prog_def = mp
            for i in range(len(prev_princess)):              # a felled princess -> the big defensive jump
                if prev_princess[i] and not self.tower.mine_alive[i]:
                    reward += self.w_lose
                    self.rw_stats.add("lose_own_tower", self.w_lose)
            # SKIPPED ON A REACTION TICK: a colour-mass estimate is a slow-moving quantity and
            # this is time sitting between seeing a push and answering it.
            if self._fast_tick and self._last_mass is not None:
                cur_mass = float(self._last_mass)
            else:
                cur_mass = enemy_mass(frame, self.cfg)
                self._last_mass = cur_mass
            my_hp = float(sum(self.tower_hp.my_hp))
            # CONSERVATIVE AFFORDABILITY (2026-08-16). The bar cannot be read finely enough to
            # tell 2.99 pips from 3.00, and the GAME requires the full amount -- so a card the
            # reader calls "exactly affordable" is often refused, the tap is spent selecting a
            # card that never places, and the referee scores a play that did not happen.
            # MEASURED over the last two live runs (110 plays with elixir_pre telemetry):
            #     slack 0 (exactly affordable): 69 plays, 61% never moved the bar
            #     slack >= 1:                   41 plays, 22%
            # and 63% of ALL plays were made at slack 0, which is why ~half of every run's taps
            # were being thrown away. `elixir` is therefore the FLOOR of the measured amount
            # minus a safety margin -- what the affordability mask can trust -- while
            # elixir_frac keeps the true reading for the observation and the leak test, which
            # both want accuracy rather than caution.
            cur_frac = self.vision.read_elixir_frac(frame)
            cur_elixir = int(max(0.0, cur_frac - self.elixir_margin))
            # The clock is TIME-driven; the badge is only a cross-check, so on a reaction tick
            # the elapsed-time reading stands on its own.
            new_mult = (self.elixir_mult if self._fast_tick
                        else self.clock.update(frame))       # 2x/3x elixir clock (time + badge)
            if new_mult != self.elixir_mult:
                print(f"[env] elixir x{new_mult}")               # 1x -> 2x (double) -> 3x (overtime)
            self.elixir_mult = new_mult
            self._cad["reads"] += time.time() - t0               # tower reads + HP OCR + mass + elixir + clock
            # OFFENSE -> DEFENSE phase (icebow): once you TAKE a tower (defend the lead), OR double elixir
            # has arrived and the X-Bow never broke through (cumulative enemy chip < xbow_success_frac of a
            # tower), give up the offensive X-Bow -> the reward moves to a back-centre X-Bow + rocket-cycle.
            # (The matchup-from-start branch -- defensive vs cycle/beatdown/split-lane decks -- and the
            # beatdown-punish need the opponent's cards, so they wait on the detector / Stage 3.)
            self._enemy_chip_total += max(0.0, self.tower_hp.last_enemy_chip)
            took_tower = any(prev_enemy[i] and not self.tower.enemy_alive[i] for i in range(len(prev_enemy)))
            # OVERTIME, not 2x elixir (2026-08-15, user doctrine -- mirrors sim/env). elixir_mult
            # hits 2 a minute before regulation ends; giving the siege up then threw away the
            # minute in which double elixir makes re-placing and defending a 6-cost bow easiest.
            # The clock reports 3x only in overtime's last minute, so overtime is detected from
            # the match clock when available and from the 3x flip as a fallback.
            in_overtime = (self.clock.overtime if hasattr(self.clock, "overtime")
                           else self.elixir_mult >= 3)
            if not self._defensive and (took_tower or (in_overtime
                    and self._enemy_chip_total < self.tower_hp.full * self.xbow_success_frac)):
                self._defensive = True
                print("[env] phase -> DEFENSIVE (X-Bow back-centre + rocket-cycle)")
            # --- CORRECTNESS score (mirrors the sim; from live perception) ---
            gx, gy = cell % self.gw, cell // self.gw
            cx, cy = self.actions.cell_center(gx, gy)
            tr = wc = tmi = lk = 0.0
            # DID THE CARD ACTUALLY DEPLOY? (2026-08-20 audit.) `_execute` sends two taps and
            # returns; nothing ever confirmed a deployment, so the correctness terms were paid
            # from the INTENDED (card, cell) whether or not anything happened. MEASURED on six-
            # elixir cards: 33% of plays showed the bar not falling at all -- impossible if six
            # elixir had been spent -- so a third of the win-condition credit was paid for
            # nothing, and the replay buffer stored those as real plays.
            #
            # Conservative on purpose: the bar is read as an INTEGER, so only an expensive card
            # whose reading did not fall AT ALL is treated as failed. Cheap cards and partial
            # drops are left alone rather than risk withholding credit for a real play.
            if play and 0 <= card_id < self.n_cards:
                # QUEUE the deploy check; do not judge it now. The paced wait is
                # event-interruptible (react_min_gap 0.15 s), so this step's elixir read can land
                # a fraction of a second after the tap -- before the game has even drawn the
                # deduction. Judging there reported "did NOT leave the bar" for cards the user
                # could watch being played (2026-08-20 report).
                self._pending_deploys.append(
                    {"t_eval": time.time() + self.deploy_verify_s, "t0": time.time(),
                     "card": card_id, "cost": float(self.card_elixir[card_id]),
                     "pre": float(pre_elixir), "mult": int(self.elixir_mult)})
            reward += self._eval_pending_deploys(cur_elixir)
            if play:
                tr = self.rw_stats.add("threat_response", self._bonus(self._threat_response_live(card_id, cx, cy)))   # (1) counter the assessed threat
                wc = self.rw_stats.add("wincon_exec", self._bonus(self._wincon_exec_live(card_id, cx, cy)))            # (3) win-condition executed right
            else:
                tmi = self.rw_stats.add("threat_miss_idle", self._threat_miss_idle_live(cur_mass))                     # (1) ignored an ANSWERABLE threat
            # (2) ELIXIR-TRADE: clipped delta of the two-sided resource potential (bar + board,
            # both sides). A deploy is a TRANSFER (zero at play time); consequences settle when
            # perception sees them. The old spend-tax + ambient-mass shape paid the policy for
            # idling under a building push -- ELIXIR_TRADE_DESIGN.md, implemented 2026-08-14.
            trd = self.rw_stats.add("elixir_trade", self._trade_reward(cur_elixir))
            if self._last_cast_rec is not None:
                # What the aim geometry paid for THIS cast, remembered so a whiff can hand it
                # back at impact (see _eval_pending_spells' clawback).
                self._last_cast_rec["paid"] = float(tr) + float(wc)
                self._last_cast_rec = None
            reward += self._eval_pending_spells()     # due spell impacts: whiffs + bad tornados
            if not play and cur_frac >= self.full_elixir:      # leak: the TRUE bar, not the floored one
                lk = self.rw_stats.add("leak", self.w_leak)                                                            # (5) leaking at capacity
            reward += tr + wc + tmi + trd + lk
            self.rw_stats.step(bool(play))
            # PER-PLAY record -> the reward-stats JSONL ("plays" array per match): every play, plus
            # every wait that drew the idle penalty. This is what turns "elixir_trade -22/match" into
            # "rocket at (0.19, 0.02) with no recognised threat, x14" -- the per-term aggregates can
            # name the guilty TERM but not the guilty HABIT. Pure telemetry: values are the exact
            # numbers already added to `reward` above, recorded after the fact.
            if play or tmi != 0.0:
                # `elixir` is the POST-action read; `elixir_pre` is what the decision saw.
                # A play that LANDED shows pre - cost (+ regen); one that was ignored by the
                # game shows no drop at all -- which is how the 24% tap-failure rate was
                # measured, and how the next run's rate can be checked in one line.
                rec = {"t": round(time.time() - self._match_t0, 1), "play": int(bool(play)),
                       "trade": round(float(trd), 3), "elixir": round(float(cur_elixir), 1),
                       "elixir_pre": round(float(pre_elixir), 1),
                       "mult": int(self.elixir_mult), "mass": round(float(cur_mass), 4)}
                if play:
                    cost = float(self.card_elixir[card_id]) if 0 <= card_id < self.n_cards else 0.0
                    rec.update(card=(self.vision.deck_keys[card_id] if 0 <= card_id < self.n_cards
                                     else str(card_id)),
                               cell=int(cell), x=round(float(cx), 3), y=round(float(cy), 3),
                               raw_cell=int(raw_cell), cost=round(cost, 1),
                               tr=round(float(tr), 3), wc=round(float(wc), 3))
                else:
                    rec["tmi"] = round(float(tmi), 2)
                tid = self._threat_id
                if tid is not None and len(tid) >= card_threat.IDENTITY_DIM and float(tid[0]) >= 0.5:
                    rec["tid"] = [round(float(v), 2) for v in tid[:card_threat.IDENTITY_DIM]]
                if len(self._play_log) < 600:                  # ~70 decisions/match; cap is a safety net
                    self._play_log.append(rec)
            self._prev_mass = cur_mass
            self._prev_my_hp = my_hp
            self.elixir = cur_elixir                          # decisions: conservative
            self.elixir_frac = float(cur_frac)                # observation/leak: accurate
            self.elixir_vec = np.asarray([cur_frac / 10.0], dtype=np.float32)
            t0 = time.time()
            self._read_hand(frame)
            self._cad["hand"] += time.time() - t0
            t0 = time.time()
            self._update_threat(frame)
            self._cad["threat"] += time.time() - t0
            t0 = time.time()
            self._last_obs = self._observe(frame)
            self._cad["obs"] += time.time() - t0
            self._last_frame = frame
            self._not_in_match = 0                  # a good frame clears the debounce
            return self._last_obs, reward, False, {"elixir": self.elixir, "elixir_mult": self.elixir_mult}

        # NOT IN_MATCH -> but ONE bad frame must not end a live match (2026-08-15, user report:
        # the bot "shut down completely when overtime hit" and the results line printed 0-0
        # while the match was still going). The branch below is terminal and there was no
        # confirmation in front of it, so any single perception hiccup -- an overtime banner
        # covering the UI element in_match keys on, a spell flash, an emote popup -- ended the
        # episode. _resolve_terminal then found no scoreboard (the match is still running),
        # which is precisely the `seen == 0 -> outcome None` path and the 0-0 print.
        # Same shape as env.tower_confirm_steps: require N CONSECUTIVE bad reads. Costs at most
        # N decisions of latency when a match really has ended (the results screen persists far
        # longer than that), and costs nothing when it has not.
        self._not_in_match += 1
        if self._not_in_match < self.match_end_confirm:
            if self._not_in_match == 1:
                print(f"[env] board not recognised ({state.name}) -- holding the match open "
                      f"({self._not_in_match}/{self.match_end_confirm})", flush=True)
            return self._last_obs, 0.0, False, {"elixir": self.elixir,
                                                "elixir_mult": self.elixir_mult,
                                                "unrecognised": int(self._not_in_match)}

        # match is over -> resolve win/loss terminal reward, then exit
        self._replay_rec.end_match()     # the clip spans the whole match: close it here
        reward, outcome, detail = self._resolve_terminal()
        self.last_outcome = outcome
        # Per-term breakdown for THIS match: the action-tax signature (a term that fires often and
        # never pays positive) is visible here in one match instead of after a whole training run.
        self.rw_stats.add("outcome", reward)
        self.rw_stats.matches += 1
        print(self.rw_stats.format_match(f"match {self.rw_stats.matches} ({outcome})"), flush=True)
        # Per-phase cadence means for THIS match. `loop` is the true decision-to-decision wall time
        # (env pipeline + the trainer's inference/learn step); the named phases are the env's share,
        # so `loop - sum(phases)` ~= what the TRAINER added. The mismatch this measures is C-list
        # item 5 (trained act_period 1.0 vs the ~2.2 s that was actually served).
        cad = {}
        if self._cad_n:
            order = ("loop", "wait", "spell", "grab", "state", "reads", "hand", "threat", "obs",
                     "act", "det_age")
            cad = {k: round(self._cad[k] / self._cad_n, 3) for k in order if self._cad.get(k)}
            print(f"[cadence] {self._cad_n} decisions | "
                  + "  ".join(f"{k} {v:.2f}s" for k, v in cad.items()), flush=True)
        # PERCEPTION HEALTH (2026-08-20): the 4-5 s reaction sessions were a DEGRADED loop nobody
        # could see. passes ~= hz * match_seconds when healthy; wakes counts event-driven early
        # decisions; det_age (cadence) is how stale each decision's snapshot was. A session with
        # passes near zero or det_age near act_period is running blind-between-decisions again.
        percep = {}
        if self._ploop is not None:
            percep = {"running": bool(self._ploop.running),
                      "passes": int(getattr(self._ploop, "passes", 0)),
                      "wakes": int(getattr(self._ploop, "wakes", 0))}
            print("[perception] running=%s passes=%d wakes=%d" %
                  (percep["running"], percep["passes"], percep["wakes"]), flush=True)
        # GHOST PLAYS -- cards the model chose, tapped, and the game refused for want of elixir.
        # The detector at _settle_deploys has existed and been careful for a while (it only counts a
        # miss when the two hypotheses are >=1.5 apart and the reading favours "not deployed" by
        # 0.75). What it did NOT do was TELL ANYONE: `_failed_deploys` was incremented and never
        # read by anything, and the per-card print was gated behind `spell_verify_log`, an unrelated
        # flag. So the bot has been measuring the exact symptom the owner is reporting and throwing
        # the measurement away. The rate goes in the per-match line and the JSONL from here.
        _nplays = sum(1 for r in self._play_log if r.get("play"))
        if _nplays:
            print("[deploy] ghost plays: %d of %d (%.0f%%) never moved the elixir bar"
                  % (self._failed_deploys_match, _nplays,
                     100.0 * self._failed_deploys_match / _nplays), flush=True)
        self.rw_stats.dump_match(self.rw_stats_path,
                                 {"outcome": outcome, "decisions": self._cad_n, "cadence": cad,
                                  "perception": percep,
                                  "ghost_plays": int(self._failed_deploys_match),
                                  "elixir_margin": round(float(self.elixir_margin), 2),
                                  # NB key must NOT be "plays": dump_match merges match_summary() LAST,
                                  # whose int "plays" count would silently clobber this array (it did,
                                  # 2026-08-13 -- the whole day's per-play detail was lost to that).
                                  "play_log": self._play_log})
        return self._last_obs, reward, True, {"outcome": outcome, **detail}

    def _impact_time(self, cx: float, cy: float, is_rocket: bool, is_rd: bool = False) -> float:
        """Seconds from cast to effect. A rocket's flight time grows ~linearly with the
        distance from its launch point to the target; a tornado activates almost immediately;
        Royal Delivery lands after a long fixed delay."""
        if is_rd:
            return self.royal_delivery_time
        if not is_rocket:
            return self.tornado_time
        ox, oy = self.rocket_origin
        # TRUE TILE DISTANCE OVER A FIXED VELOCITY. This was a normalised Euclidean distance times
        # a per-unit rate, which mixes the 18-tile and 32-tile axes: measured, a target 20.0 tiles
        # away scored a LONGER flight (1.79s) than one 20.8 tiles away (1.73s), because the second
        # was further along the cheap axis. Same anisotropy that made a Tornado's 5.5-tile pull
        # read as 12.4 tiles down-board. Speed is calibrated to preserve the far-tower flight the
        # old fit produced (27.8 tiles, 2.29s), so magnitudes are unchanged and only the RANKING
        # by distance is corrected.
        d_tiles = (((cx - ox) * 18.0) ** 2 + ((cy - oy) * 32.0) ** 2) ** 0.5
        return min(max(self.rocket_base_time + d_tiles / self.rocket_speed_tiles, 0.6),
                   self.spell_eval_time)

    def _resolve_terminal(self) -> Tuple[float, Optional[str], dict]:
        """Read the result: end-of-match scoreboard crowns cross-checked against the
        towers felled in-match (crowns == towers destroyed). Taking the max per side
        recovers crowns the scoreboard misses (which otherwise reads a loss as a
        draw); a felled king tower is decisive. Then tap to exit."""
        deadline = time.time() + self.results_timeout
        thr = float(self.cfg.get("outcome", "gold_frac", default=0.10))
        settle = int(self.cfg.get("outcome", "settle_reads", default=8))
        red = [0.0, 0.0, 0.0]
        blue = [0.0, 0.0, 0.0]
        seen = stable = 0
        last_total = -1
        while time.time() < deadline:
            frame = self._grab()
            if frame is None:
                break
            sb = read_scoreboard(frame, self.cfg)
            if sb.present:
                red = [max(a, b) for a, b in zip(red, sb.red_fracs)]
                blue = [max(a, b) for a, b in zip(blue, sb.blue_fracs)]
                seen += 1
                # Crowns animate in one-by-one, so keep reading (taking the max per
                # cushion) until the crown total holds steady -- not just until the
                # board first appears -- or the deciding crown of a 3-0 gets missed.
                total = sum(f >= thr for f in red) + sum(f >= thr for f in blue)
                stable = stable + 1 if total == last_total else 0
                last_total = total
                if seen >= 4 and stable >= settle:
                    break
            time.sleep(self.poll_dt)

        sb_blue = sum(f >= thr for f in blue)
        sb_red = sum(f >= thr for f in red)
        # crowns == towers destroyed: latched in-match, independent of the scoreboard
        t_blue, t_red, enemy_king, my_king = self.tower.crown_counts()
        blue_c, red_c = max(sb_blue, t_blue), max(sb_red, t_red)
        if enemy_king and not my_king:            # a felled king tower is decisive
            outcome: Optional[str] = "win"
        elif my_king and not enemy_king:
            outcome = "loss"
        elif seen == 0 and t_blue == 0 and t_red == 0:
            outcome = None                        # never saw the scoreboard, no towers fell
        else:
            outcome = "win" if blue_c > red_c else "loss" if red_c > blue_c else "draw"
        # A KING kill is a full 3-crown victory. The king ends the match the instant it falls, so its
        # (and the last princess's) destruction latch often can't confirm before the frame cuts to the
        # results screen -- which showed a real 3-0 as "1-0". For the WINNER only, force the count to 3
        # when a king kill is evident (latched OR trending-destroyed at the cut). Display-only:
        # outcome_reward keys off win/loss, not the crown count, so this cannot change the reward.
        ek_soft, mk_soft = self.tower.king_trending_down()
        if outcome == "win" and (enemy_king or ek_soft):
            blue_c = 3
        elif outcome == "loss" and (my_king or mk_soft):
            red_c = 3
        reward = outcome_reward(outcome, self.cfg) if outcome else 0.0
        # leave the results screen by re-queueing (1v1 "Play Again") so the next match
        # starts without a detour through HOME; reset() then picks up QUEUING/IN_MATCH.
        self.controller.tap(*self.play_again)
        time.sleep(self.menu_delay)
        detail = {"crowns": (blue_c, red_c), "scoreboard": (sb_blue, sb_red), "towers": (t_blue, t_red)}
        return reward, outcome, detail
