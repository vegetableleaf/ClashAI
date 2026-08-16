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
from .reward import (TowerTracker, _anchors, enemy_mass, near_enemy_king, near_enemy_princess,
                     pump_rocket_cell, spell_intercept_cell, threat_side, weaker_princess_cell,
                     xbow_lock_cell, xbow_offense_depth_cell, tesla_pull_cell)
from .reward import TILE as _TILE
from .clock import ElixirClock
from .states import GameState
from .nav import MenuNavigator
from .threats import ThreatTracker, Threat
from . import card_threat
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
        self.xbow_ids = set()
        self.tesla_ids = set()                          # centre-pull assist target (see _lane_wincon)
        self.defensive_kind = {}                        # id -> defender kind (Tesla / Ice Wizard) for reactive_ids
        for i, key in enumerate(self.vision.deck_keys):
            base = key[:-4] if key.endswith("_evo") else key
            c = db.get(base)
            if c and c.get("kind") == "spell":
                self.spell_ids.add(i)
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
        # ROCKET and MINER may target ANYWHERE; every other card (troops, X-Bow, royal delivery) is your-half only.
        self.anywhere_ids = self.rocket_ids | self.miner_ids
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
        # (4) cycle_plan / cycle_waste: DELETED live too (2026-08-12). The sim deleted its copy after
        # 110 fires / 0 positives (see sim/env._cycle_plan's stub); live then measured the identical
        # action-tax shape -- 2 positives vs 24 negatives over 5 matches -- while being one of only
        # three terms that fired at all. Same term, same shape, same fix.
        self.w_leak = rw("leak_penalty", -0.2)                # (5) sitting at elixir capacity, leaking
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
        self._threat_id = np.zeros(card_threat.IDENTITY_DIM, np.float32)   # last identity block (for reward)
        self._prev_ident_depth = 0.0        # deepest recognised-threat depth last step (for velocity)
        self._prev_ident_t = None
        self._opp_mem = card_threat.OpponentMemory(db)   # per-match opponent short-term memory (Stage 3)
        self._opp_elixir = OpponentElixirEstimator(db)   # live estimate from mirrored spend accounting
        from .replay_mine import TeamTracker
        self._team_tracker = TeamTracker(                # LIVE: evidence-fused teams (plays/motion/bars/pockets)
            spawn_radius=float(cfg.get("observation", "team_spawn_radius", default=0.10)),
            spawn_window_s=float(cfg.get("observation", "team_spawn_window_s", default=2.5)),
            enemy_window_s=float(cfg.get("observation", "team_enemy_window_s", default=4.0)),
            track_radius=float(cfg.get("observation", "team_track_radius", default=0.12)),
            forget_s=float(cfg.get("observation", "team_forget_s", default=4.5)),
            motion_min=float(cfg.get("observation", "team_motion_min", default=0.05)),
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
        self.next_id = self.vision.recognize_next(frame)
        self.next_vec = self._cycle_tracker.observe(self.hand_ids, self.next_id)

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
            if not dets and getattr(self, "_last_mass", 0.0) >= self.quiet_frac:
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
        if self._ploop is not None and self._ploop.running:
            self._ploop.set_towers(self.tower.mine_alive, self.tower.enemy_alive)  # pocket gating stays fresh
            dets, age = self._ploop.snapshot()
            if age <= 2.0:                                # healthy loop -> use the snapshot
                dets = self._det_hold.merge(dets, time.time())   # bridge detector flicker
                self._last_dets_all = dets
                self._last_dets_age = float(age)          # trade-potential validity gate reads this
                return [d for d in dets if d.team == "enemy" and d.base in self.detector_cards]
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
        self._det_hold.reset()                        # flicker memory must not bridge two matches        # motion history must never bridge two matches
        self._defensive = False           # icebow phase: False = offensive X-Bow win condition; True = defence + rocket-cycle
        self._enemy_chip_total = 0.0      # cumulative enemy-tower HP chipped (the X-Bow 'did it break through?' gauge)
        self._xbow_play_t = None          # wincon repeat-credit window must not bridge two matches
        self._match_bonus = 0.0
        self._match_penalty = 0.0
        self.rw_stats.new_match()
        self._cad.clear()                 # cadence accounting is per match
        self._cad_n = 0
        self._last_step_t = None
        self._last_frame_t = None         # menu time must not count against the first paced wait
        self._play_log = []               # per-play telemetry for this match (see step's record block)
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

    def _execute(self, action: Action) -> None:
        play, card_id, cell = action
        if not play:
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
        tracks = (self._ploop.enemy_tracks(time.time()) if self._ploop is not None and self._ploop.running
                  else self._team_tracker.enemy_tracks(time.time()))
        tgt = spell_intercept_cell(cx, cy, tracks, self._impact_time(cx, cy, is_rocket=True),
                                   self.spell_lead_radius, self.actions)
        return tgt if tgt is not None else cell

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
        tid = self._threat_id
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
        tid = self._threat_id
        if tid is None or len(tid) < card_threat.IDENTITY_DIM or tid[0] < 0.5:
            return 0.0
        for cid in self.hand_ids:
            if (0 <= cid < len(self._deck_profiles) and card_threat.counters(self._deck_profiles[cid], tid)
                    and self.card_elixir[cid] <= self.elixir):
                return self.w_threat_miss
        return 0.0

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
        if card_id in self.rocket_ids:
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
                 or (not dets and getattr(self, "_last_mass", 0.0) >= self.quiet_frac))
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
            if cell == pre_aim and card_id in self.rocket_ids:    # no tower/pump snap -> LEAD tracked troops
                cell = self._aim_rocket_intercept(cell)
            cell = self.actions.deploy_clamp(card_id in self.anywhere_ids, cell)  # rocket + miner go anywhere; rest = your half
            if card_id in self.xbow_ids and not self._defensive:  # OFFENSIVE phase only: snap a forward X-Bow onto the nearer lane so it LOCKS
                gx, gy = cell % self.gw, cell // self.gw
                cx, cy = self.actions.cell_center(gx, gy)
                _, enemy_a, _ = _anchors(self.cfg)
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
            if self._ploop is not None and self._ploop.running:
                if remaining > 0.0:
                    self._ploop.wait_event(remaining, self.react_min_gap)
            elif remaining > 0.0:
                time.sleep(remaining)
            self._cad["wait"] += time.time() - t0
            t0 = time.time()
            frame = self._grab()
            self._cad["grab"] += time.time() - t0
        self._last_frame_t = time.time()
        if frame is None:
            return self._last_obs, 0.0, True, {"outcome": None, "error": "capture_lost"}

        t0 = time.time()
        state = self.vision.detect_state(frame)
        self._cad["vision"] += time.time() - t0
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
            cur_mass = enemy_mass(frame, self.cfg)
            self._last_mass = cur_mass
            my_hp = float(sum(self.tower_hp.my_hp))
            cur_elixir = self.vision.read_elixir(frame)
            new_mult = self.clock.update(frame)                  # 2x/3x elixir clock (time + optional badge)
            if new_mult != self.elixir_mult:
                print(f"[env] elixir x{new_mult}")               # 1x -> 2x (double) -> 3x (overtime)
            self.elixir_mult = new_mult
            self._cad["vision"] += time.time() - t0              # tower reads + HP OCR + mass + elixir + clock
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
            if not play and cur_elixir >= self.full_elixir:
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
            self.elixir = cur_elixir
            self.elixir_vec = np.asarray([cur_elixir / 10.0], dtype=np.float32)
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
            return self._last_obs, reward, False, {"elixir": self.elixir, "elixir_mult": self.elixir_mult}

        # match is over -> resolve win/loss terminal reward, then exit
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
            order = ("loop", "wait", "spell", "grab", "vision", "hand", "threat", "obs", "act")
            cad = {k: round(self._cad[k] / self._cad_n, 3) for k in order if self._cad.get(k)}
            print(f"[cadence] {self._cad_n} decisions | "
                  + "  ".join(f"{k} {v:.2f}s" for k, v in cad.items()), flush=True)
        self.rw_stats.dump_match(self.rw_stats_path,
                                 {"outcome": outcome, "decisions": self._cad_n, "cadence": cad,
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
        d = ((cx - ox) ** 2 + (cy - oy) ** 2) ** 0.5
        return min(max(self.rocket_base_time + self.rocket_travel_rate * d, 0.6), self.spell_eval_time)

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
