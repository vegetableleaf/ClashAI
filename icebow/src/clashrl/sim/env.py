"""SimMatchEnv -- a headless Gym-style match env over the sim engine, exposing the SAME interface
`train_sim` needs and `PolicyNet` expects: reset()/step() plus hand_vec / next_vec / elixir_vec /
threat_vec and an obs IMAGE, so the exact same CNN policy trains here and transfers to the real game.

The observation is a crude synthetic TOP-DOWN render (towers + unit blobs, blue = you / red = enemy)
at the real `observation.arena_size`, so the policy learns from roughly what the real arena reduces
to when downscaled. Rewards are computed from GROUND TRUTH (tower HP, crowns, unit mass, win/loss)
using the SAME config weights as the live env, plus the deck's placement doctrine (X-Bow in tower
range, Miner on the enemy tower). Medium fidelity -> a sim-trained policy is a PRIOR to fine-tune live.
"""
from __future__ import annotations

import copy
import random
from typing import Tuple

import numpy as np

from ..actions import ActionSpace
from ..cards import shared as shared_db
from .. import card_threat
from .. import detect_obs
from .. import interactions
from .. import threat_value
from ..cycle import cycle_vector
from .engine import SimEngine, build_spec, tile_dist, _ROCKET_RADIUS
from .meta_decks import load_meta_decks
from .opponents import make_opponent
from . import view

Action = Tuple[int, int, int]
_THREAT_DIM = 16
_TOWER_DIM = view.TOWER_DIM   # HP fraction of (L princess, R princess, king) x (mine, theirs)


class _BoardCfg:
    """Read-only config view that re-anchors the ActionSpace to the SIM BOARD.

    ``ActionSpace`` maps grid cells through ``action.arena_box`` into FRAME-normalised SCREEN
    coordinates -- right for live play, wrong for the sim, whose board is the full [0,1] square
    with the river at y=0.5. Feeding screen cells (and screen tower anchors) to the engine is what
    made the simulated arena vertically asymmetric. Cell IDs and ``action.grid`` are untouched, so
    a checkpoint's action head still lines up."""

    def __init__(self, cfg, over):
        self._cfg, self._over = cfg, over

    def get(self, *keys, default=None):
        return self._over[keys] if keys in self._over else self._cfg.get(*keys, default=default)


def _board_action_space(cfg) -> ActionSpace:
    b = dict(cfg.get("sim", "board", default=None) or {})
    tx, ty = float(b.get("tiles_x", 18.0)), float(b.get("tiles_y", 32.0))
    pt = list(b.get("princess_tile", [3.5, 6.5]))
    kt = list(b.get("king_tile", [9.0, 3.0]))
    py, ky = 1.0 - pt[1] / ty, 1.0 - kt[1] / ty                 # YOUR side (bottom)
    epy, eky = pt[1] / ty, kt[1] / ty                           # THEIR side (top), board-true
    return ActionSpace(_BoardCfg(cfg, {
        ("action", "arena_box"): [0.0, 0.0, 1.0, 1.0],
        ("action", "deploy_top"): float(b.get("deploy_top", 0.5)),   # the river
        ("env", "my_towers"): [[pt[0] / tx, py], [(tx - pt[0]) / tx, py], [kt[0] / tx, ky]],
        # board-true enemy anchors too, so BoardWarp's anchor pairs are identity points in the
        # sim and the warp exactly reduces to the identity mapping there
        ("env", "enemy_towers"): [[pt[0] / tx, epy], [(tx - pt[0]) / tx, epy], [kt[0] / tx, eky]],
        # ...and board-true field edges/river, so the edge anchors are identity points too
        ("env", "board_edges"): {"top": 0.0, "river": 0.5, "bottom": 1.0, "left": 0.0, "right": 1.0},
    }))


class SimMatchEnv:
    def __init__(self, cfg, seed: int = 0):
        self.cfg = cfg
        self.rng = random.Random(seed)
        self.db = shared_db(cfg)          # read-only + shared: building one per env cost ~0.4 s each
        self.actions = _board_action_space(cfg)
        self.gw, self.gh = int(self.actions.gw), int(self.actions.gh)
        self.n_cells = int(self.actions.n_cells)
        self.deck_keys = self.db.deck_identities()
        self.deck_card_levels = self.db.deck_levels()
        self.n_cards = max(1, len(self.deck_keys))
        self.specs = [build_spec(self.db, k, lvl) for k, lvl in zip(self.deck_keys, self.deck_card_levels)]
        # PHYSICAL CARD SLOTS. The cycle runs over the deck's 8 CARDS, not the 10 policy identities:
        # an Evolution is not its own card, it IS the base card shown evolved once that slot has been
        # played `cycles` times. Cycling identities instead let base and Evo sit in hand together and
        # let the Evo be replayed every lap -- neither happens in a real match.
        self.slots = self.db.deck_slots()
        self.n_slots = max(1, len(self.slots))
        self.slot_base_id = [self.deck_keys.index(s["base"]) for s in self.slots]
        self.slot_evo_id = [self.deck_keys.index(s["evo"]) if s["evo"] in self.deck_keys else -1
                            for s in self.slots]
        self.slot_cycles = [int(s["cycles"]) for s in self.slots]
        self.slot_of = {}                                # identity id -> slot index
        for si in range(self.n_slots):
            self.slot_of[self.slot_base_id[si]] = si
            if self.slot_evo_id[si] >= 0:
                self.slot_of[self.slot_evo_id[si]] = si
        self.evo_charge = [0] * self.n_slots             # base plays banked toward this slot's Evolution
        self.meta_pool = load_meta_decks(cfg, self.db)   # opponent decks (top-meta or curated fallback)
        ow, oh = cfg.get("observation", "arena_size", default=[64, 96])
        # OBS-CANVAS FLIP (observation.use_detector_canvas): the policy's IMAGE branch gains
        # detect_obs's semantic channels -- enemy/ally x ground/air/building + spell -- so "what is
        # where" arrives as a clean map instead of having to be inferred from a 64x96 blob canvas
        # that domain randomisation repaints every match. Gated on detect-eval's class-agnostic
        # PRESENCE recall because that is exactly what the canvas needs (position + team, not names).
        # Sim renders it from ground truth degraded by `sim_detector_presence_recall`; live renders
        # it from the real detector, so the two stay the same layout on the same 0..255 scale.
        self.use_canvas = bool(cfg.get("observation", "use_detector_canvas", default=False))
        self.canvas_presence_recall = float(
            cfg.get("observation", "sim_detector_presence_recall", default=1.0))
        # CANVAS STACK (observation.canvas_stack): >1 appends the canvas as it looked canvas_stack_dt_s
        # ago, so the conv trunk can read MOTION off the channel deltas instead of seeing a snapshot.
        # Shape comes from detect_obs so the sim can never drift from the live builders (the whole
        # class of bug that lets a sim-trained checkpoint fail to load live).
        self.canvas_stack_n = detect_obs.canvas_stack_len(cfg)
        self._canvas_stack = detect_obs.CanvasStack(self.canvas_stack_n, detect_obs.canvas_stack_dt(cfg))
        self.use_pred_canvas = detect_obs.predictive_enabled(cfg)
        self.pred_dt = detect_obs.predictive_dt(cfg)
        self.pred_horizon = detect_obs.eta_horizon(cfg)
        self.use_hp_canvas = detect_obs.hp_enabled(cfg)
        self.obs_shape = (int(oh), int(ow), detect_obs.obs_in_channels(cfg))
        # Stage 3: identity-grounded threat block (KB roles of RECOGNISED enemy cards). When on, the
        # threat vector grows by card_threat.IDENTITY_DIM; the sim reads it from GROUND TRUTH but only
        # for whitelisted cards, so it mimics the live detector's (partial) recognition coverage.
        self.use_detector = bool(cfg.get("observation", "use_detector", default=False))
        self.detector_cards = set(cfg.get("observation", "detector_cards", default=[]))
        self.identity_front = card_threat.identity_front(cfg)   # identity watch line (shared with live/label)
        self.predict_horizon = float(cfg.get("observation", "predict_horizon_s", default=1.0))
        # SIM-only detector realism: simulate the live YOLO detector's imperfect recall/precision on the
        # ground-truth identity block so the sim PRIOR trains on a sparse, live-like signal (1.0 = perfect).
        self.det_recall = float(cfg.get("observation", "sim_detector_recall", default=1.0))
        self.det_precision = float(cfg.get("observation", "sim_detector_precision", default=1.0))
        # optional PER-CARD recall override (reliable vs weak cards); cards absent use the scalar det_recall
        self.det_recall_by_card = dict(cfg.get("observation", "sim_detector_recall_by_card", default=None) or {})
        # Stage-3b gate: the troop-INTERACTION block (who is predicted to be moving at which tower)
        self.use_interactions = bool(cfg.get("observation", "use_interactions", default=False))
        self.sight_range = float(cfg.get("sim", "sight_tiles", default=5.5))   # tiles
        # TOWER BLOCK: 6 dims = HP FRACTION of (L princess, R princess, king) for MINE then THEIRS,
        # in the policy's own mirrored frame. Gated so an old checkpoint's schema still resolves.
        #
        # WHY IT EXISTS. Crown/tower state was observable ONLY as a 5x5 block vanishing from the 64x96
        # canvas -- in the same colour as units, under per-match domain randomisation. Nothing in the
        # 46-dim vector carried it. Consequences seen in live play: after taking a princess the policy
        # kept placing X-Bows at the spot that used to reach it (the other tower is out of range from
        # there, so they fired at nothing), and the `_defensive` turtle flag -- which silently changes
        # what _wincon_exec pays for the moment my_c >= 1 -- was being graded on a state the policy
        # could not see at all.
        # It also became outcome-critical: since the overtime tiebreak was fixed (c2fb89e) the
        # least-healthy STANDING tower decides level matches, and the policy was blind to it.
        # HP FRACTION rather than an alive flag because it is strictly more information: 0.0 IS
        # destroyed (so crowns are implied), and the non-zero values are exactly what the tiebreak
        # compares. Readable LIVE with no new perception work -- env.py already runs TowerHpTracker
        # (the hp_digits CNN) for rewards and simply never fed it to the observation.
        self.use_tower_obs = bool(cfg.get("observation", "use_tower_hp", default=True))
        self.threat_dim = (_THREAT_DIM
                           + ((card_threat.IDENTITY_DIM + card_threat.OPP_MEMORY_DIM)
                              if self.use_detector else 0)
                           + (interactions.INTERACTION_DIM if self.use_interactions else 0)
                           + (_TOWER_DIM if self.use_tower_obs else 0))

        def _base(k):
            return k[:-4] if k.endswith("_evo") else k
        self.anywhere_ids = {i for i, k in enumerate(self.deck_keys) if _base(k) in ("rocket", "miner")}
        self.miner_ids = {i for i, k in enumerate(self.deck_keys) if _base(k) == "miner"}
        self.xbow_ids = {i for i, k in enumerate(self.deck_keys) if _base(k) == "x_bow"}
        # Stage 3: your deck's KB profiles (played-card role) + the last identity block, for the
        # role-based COUNTER reward (played the right answer to a RECOGNISED threat). Off unless use_detector.
        self._deck_profiles = [card_threat.profile(self.db, _base(k)) for k in self.deck_keys]
        self._threat_id = np.zeros(card_threat.IDENTITY_DIM, np.float32)
        self._prev_ident_depth = 0.0     # deepest recognised-threat depth last step (for approach velocity)
        # REWARD-side twin of the above, built WITHOUT detector noise. The observation must stay noisy
        # (that is the perception the policy has to cope with) but GRADING must not be: with
        # sim_detector_recall 0.72, ~28% of real threats are invisible to the noisy vector, so a
        # correctly pre-placed defender was scored as a "premature defender on a quiet board" (-0.4)
        # whenever the referee happened not to see the push it answered. This file's own contract at the
        # top says rewards are computed from GROUND TRUTH; these three terms were the exception.
        self._threat_id_true = np.zeros(card_threat.IDENTITY_DIM, np.float32)
        self._prev_ident_depth_true = 0.0
        self._opp_mem = card_threat.OpponentMemory(self.db)   # per-match opponent short-term memory (Stage 3)

        r = lambda k, d: float(cfg.get("rewards", k, default=d))  # noqa: E731
        # --- CORRECTNESS-FIRST reward weights (playing correctly > winning). ONE coherent score of a
        # few bounded sub-terms replaces the old ~40 patchwork rewards; see the reward assembly in step(). ---
        self.w_threat_response = r("threat_response", 1.0)   # right KB counter, placed to intercept an assessed threat
        self.w_threat_miss = r("threat_miss", -1.0)          # wrong counter / wrong lane / ignored an ANSWERABLE threat
        self.w_elixir_trade = r("elixir_trade", 1.0)         # (enemy value eliminated - elixir spent), normalised
        self.w_wincon = r("wincon_exec", 0.8)                # deck win-condition executed correctly for the phase
        self.w_wincon_mis = r("wincon_misplace", -0.6)       # win-condition card thrown away
        # cycle_plan / cycle_waste: DELETED -- see the _cycle_plan stub below for the full record.
        # The weights are no longer read (2026-08-12: the live env's copy was deleted too).
        # PER-TICK TERMS SCALE WITH agent_dt -- see the live env's note. A shorter decision period
        # must not silently multiply the terms that are charged once per decision.
        self._tick_scale = float(cfg.get("sim", "agent_dt", default=1.0)) / 1.0
        self.w_leak = r("leak_penalty", -0.2) * self._tick_scale   # at elixir capacity, leaking
        self.correctness_cap = r("correctness_cap", 8.0)     # per-match cap on correctness shaping (anti-farm, BOTH signs)
        self._match_penalty = 0.0                            # symmetric twin of _match_bonus (see _bonus)
        # Per-term reward accounting -- which shaping term is actually driving the policy.
        from ..reward_stats import RewardTerms
        self.rw_stats = RewardTerms()
        # OUTCOME compass -- DEMOTED so correctness dominates (winning is not the objective).
        self.w_win = r("win", 2.0); self.w_loss = r("loss", -2.0)
        self.w_take = r("take_enemy_tower", 1.0); self.w_lose = r("lose_own_tower", -1.0)   # the CROWN jump on a take/loss
        self.tower_chip_scale = r("tower_chip_scale", 0.3)   # convex chip POOL per tower (small; the crown is the jump)
        self.chip_power = float(cfg.get("env", "tower_chip_power", default=2.0))   # >1 -> partial chip sub-proportional
        # --- doctrine GEOMETRY (kept: the win-condition / counter checks the correctness terms use) ---
        self.combo_mult = float(cfg.get("rewards", "rocket_combo_mult", default=3.0))   # rocket 2-for-1 = wincon_exec x this
        self.intercept_lane = float(cfg.get("env", "intercept_lane", default=0.15))     # same-lane tolerance for an intercept
        self.quiet_board_free_elixir = float(cfg.get("env", "quiet_board_free_elixir", default=8.0))
        # Wincon-bank parameters, mirrored for the threat_miss_idle waiver (see that method): the
        # trainer's bank masks cheaper cards while the bar climbs to a held win condition's cost,
        # and a penalty must not charge the agent for a hold the sampler itself mandates.
        self._bank_floor = float(cfg.get("sim", "wincon_bank_floor", default=0.0))
        _wc_ids = set(getattr(self, "xbow_ids", ())) | set(getattr(self, "rocket_ids", ()))
        self._bank_wincon_ids = _wc_ids
        self._bank_wincon_cost = min((float(self.specs[i].elixir) for i in _wc_ids), default=0.0)
        # Tower level for the triage waiver in _threat_miss_idle (clashrl.threat_value).
        self._tower_level_for_triage = int(cfg.get("env", "my_tower_level", default=15) or 15)
        self.punish_opp_elixir = float(cfg.get("env", "punish_opp_elixir", default=4.0))
        self.punish_elixir_gap = float(cfg.get("env", "punish_elixir_gap", default=4.0))
        self.punish_blocker_min_hp = float(cfg.get("env", "punish_blocker_min_hp", default=600.0))
        self.xbow_punish_mult = float(cfg.get("rewards", "xbow_punish_mult", default=1.5))
        # X-BOW LEDGER REPAIR (2026-08-14, user-directed; findings in log). The bow's value is
        # DELAYED (chip over 10-30 s at (gamma*lambda)^dt = 0.94^dt reach-back: +15 s arrives at
        # 0.40 strength) and INSTRUMENTAL (a thwarted bow that drew a 9-elixir answer did its
        # job). The old ledger paid geometry once (+0.8) and billed the death (-0.6 Phi), while
        # the convex chip pool muted the bow's whole product (20-30% chip ~ +0.01-0.03) -- so a
        # bow play netted <= 0 in essentially every line and the head RATIONALLY learned
        # never-bow (raw logit -7 within minutes of the repair). Three dense-but-capped lanes +
        # doctrine context modifiers fix the ledger. Sources: the 3.5 IceBow + 3.0 X-Bow deck
        # guides (Hunter-lineage doctrine): "never X-Bow the bridge first play", "if they invest
        # a high cost tank at the back, immediately X-Bow opposite lane" (SAME lane vs a Lava
        # Hound), "Little Prince/Evolved Bomber ... wrecks a X-Bow" -> discount when seen.
        self.w_bow_over = r("xbow_overcommit", 0.08)          # per enemy elixir drawn beyond the bow's 6
        # A FORWARD BOW PLANTED INTO A COMMITTED PUSH. See _xbow_into_push for the measurement that
        # forced this: nothing anywhere priced the bow dying to the push it was dropped on top of,
        # so the leak penalty alone made it a GOOD play at high elixir.
        self.w_bow_into_push = r("xbow_into_push", -4.0)
        self.bow_push_radius = float(cfg.get("sim", "xbow_push_radius_tiles", default=5.0))
        # How far from the river still counts as a FORWARD (win-condition) bow. 4.0 tiles
        # covers the two frontmost deployable rows; the defensive centre band starts beyond.
        self.bow_forward_tiles = float(cfg.get("sim", "xbow_forward_tiles", default=4.0))
        # A forward bow that leaves the defence unable to answer a live push. See
        # _xbow_overaggression -- it covers the window where threat_miss_idle goes silent.
        self.w_bow_overaggro = r("xbow_overaggression", -3.0)
        # Share of a push a card must be able to remove to count as a real ANSWER rather
        # than support. See _counter_contribution.
        self.counter_min_share = float(cfg.get("sim", "counter_min_share", default=0.35))
        self.bow_over_cap = float(cfg.get("rewards", "xbow_overcommit_cap", default=0.5))
        self.w_bow_lock = r("xbow_lock_tick", 0.02)           # per second the bow is TOWER-LOCKED...
        self.bow_lock_cap = float(cfg.get("rewards", "xbow_lock_cap", default=0.4))   # ...capped per bow
        self.w_bow_chip = r("xbow_chip_linear", 0.15)         # LINEAR chip lane while a bow stands
        self.bow_first_frac = float(cfg.get("rewards", "xbow_first_play_frac", default=0.25))
        self.bow_hostile_frac = float(cfg.get("rewards", "xbow_hostile_frac", default=0.6))
        self._bow_hostile_keys = {"little_prince", "bomber_evo"}
        self.value_norm = float(cfg.get("env", "value_norm", default=10.0))             # elixir-value normaliser for the trade term
        self.trade_cap = float(cfg.get("env", "trade_cap", default=1.0))
        self.trade_deadband = float(cfg.get("rewards", "sim_trade_deadband", default=0.05))  # (v3 ledger: unused)
        self.action_latency = float(cfg.get("sim", "action_latency_s", default=0.25))
        self.trade_kill_r = float(cfg.get("env", "trade_kill_radius_tiles", default=4.0))
        self.trade_grace_s = float(cfg.get("env", "trade_grace_s", default=3.0))
        self.trade_late_s = float(cfg.get("env", "trade_late_s", default=10.0))
        self.threat_min_depth = float(cfg.get("env", "threat_min_depth", default=0.12))
        self.threat_max_depth = float(cfg.get("env", "threat_max_depth", default=0.65))
        self.threat_credit_budget = int(cfg.get("env", "threat_credit_budget", default=2))
        self._ev_enemy, self._ev_own, self._ev_spells = {}, {}, []
        self._threat_credits, self._tid_unlit_t = 0, None                # per-step clip on the trade term
        # Minimum seconds between two threat_miss charges. See _threat_miss_idle: charging every
        # 1-second step made holding elixir strictly worse than dumping it, by 8x.
        self.threat_miss_period = float(cfg.get("env", "threat_miss_period_s", default=4.0))
        self._threat_miss_last = -1e9
        # --- COUNTERFACTUAL FORK (off by default; see _fork / _roll_fork for the RNG hazard) ---
        self.cf_enabled = bool(cfg.get("sim", "counterfactual", "enabled", default=False))
        self.cf_horizon = float(cfg.get("sim", "counterfactual", "horizon_s", default=8.0))
        self.cf_budget = int(cfg.get("sim", "counterfactual", "budget_per_match", default=12))
        self.cf_min_units = int(cfg.get("sim", "counterfactual", "min_units", default=1))
        self.cf_cap = float(cfg.get("sim", "counterfactual", "cap", default=1.0))
        self.cf_board_weight = float(cfg.get("sim", "counterfactual", "board_weight", default=1.0))
        self.w_counterfactual = r("counterfactual", 1.0)   # weight on (real - held-the-card) position
        self._cf_used = 0
        self._cf_watch: list = []
        # NB the sim's geometry lives under `sim.*` in TILES, not the `env.*` keys the LIVE env uses:
        # those are screen-space normalised distances on a foreshortened phone frame.
        self.xbow_range = float(cfg.get("sim", "xbow_range_tiles", default=11.5))       # siege sight
        self.xbow_front = float(cfg.get("sim", "xbow_defense_front", default=0.56))     # normalised y band
        self.xbow_back = float(cfg.get("sim", "xbow_defense_back", default=0.66))
        self.xbow_deep_frac = float(cfg.get("rewards", "xbow_deep_frac", default=0.25))
        self.xbow_lane_frac = float(cfg.get("rewards", "xbow_lane_frac", default=0.35))
        self.rocket_ids = {i for i, k in enumerate(self.deck_keys) if _base(k) == "rocket"}
        self.xbow_success_frac = float(cfg.get("env", "xbow_success_frac", default=0.30))
        self.rocket_combo_hp_frac = float(cfg.get("env", "rocket_combo_hp_frac", default=1.5))  # support ~one-shot
        self.rocket_combo_radius = float(cfg.get("sim", "rocket_combo_tiles", default=3.5))   # support near the aimed tower
        self.pump_window = float(cfg.get("env", "pump_rocket_window_s", default=12.0))  # rocket the pump within this of its deploy
        # CONDITIONAL ROCKET VALUE (see _rocket_value). A rocket is not worth a fixed amount: the
        # same cast is a game-winning tiebreak chip or six elixir thrown at three Skeletons
        # depending entirely on the board and the clock.
        self.rocket_min_worth = float(cfg.get("env", "rocket_min_worth", default=4.0))   # elixir in the blast to count as VALUE
        self.rocket_nado_mult = float(cfg.get("rewards", "rocket_nado_mult", default=3.0))   # tornado-bundled rocket = 2-for-1 class
        self.rocket_nado_s = float(cfg.get("env", "rocket_nado_window_s", default=2.5))      # combo timing window
        self.rocket_chip_behind = float(cfg.get("rewards", "rocket_chip_behind", default=1.2))  # losing/level the tiebreak race
        self.rocket_chip_ahead = float(cfg.get("rewards", "rocket_chip_ahead", default=0.35))   # already ahead on it
        self.rocket_chip_early = float(cfg.get("rewards", "rocket_chip_early", default=0.25))   # regulation, bow still the plan
        self.rocket_emergency = float(cfg.get("rewards", "rocket_emergency", default=0.8))      # only answer left in hand
        self.rocket_waste_mult = float(cfg.get("rewards", "rocket_waste_mult", default=0.5))    # x wincon_misplace for cheap bodies
        self._rocket_dmg = float(self.specs[next(iter(self.rocket_ids))].spell_dmg) if self.rocket_ids else 0.0
        self.spell_aim_radius = float(cfg.get("sim", "spell_tower_aim_tiles", default=3.8))
        # (soft) discourage a DAMAGE spell cast into emptiness (no unit in its blast + not aimed at a tower)
        self.damage_spell_ids = {i for i in range(self.n_cards)
                                 if self.specs[i].kind == "spell" and self.specs[i].spell_dmg > 0.0}
        self.w_spell_waste = r("spell_waste", -0.3)
        # A defensive BUILDING spent on a quiet board while they still hold a win condition.
        # Same shape as spell_waste but for the card that has to still BE there later.
        self.w_building_waste = r("building_waste", -0.4)
        self.spell_waste_radius = float(cfg.get("sim", "spell_waste_tiles", default=4.5))
        # TORNADO execution shaping (positive-only, soft, inside the correctness cap): the pull's value
        # is COMPOSITE + DELAYED (clump -> splash/rocket, king activation, dragging a wincon off a
        # tower), which plain outcome terms barely see -- so a WELL-EXECUTED pull is credited by its
        # MECHANICAL effect, measured from engine ground truth a couple of steps after the cast.
        # n_step >= 3 carries the delayed credit back to the cast action.
        self.w_nado_clump = r("nado_clump", 0.25)          # per extra enemy clumped at the vortex centre
        self.w_nado_combo = r("nado_combo", 0.6)           # >=2 pulled enemies dead shortly after (splash/rocket payoff)
        self.w_nado_king = r("nado_king_activate", 0.5)    # pull activated your sleeping king (once/match)
        # BAD PULL (2026-08-19, user request): a tornado whose pulled units SURVIVE the window,
        # earned no kill combo and no king activation, and ended up CLOSER to our princess towers
        # than where the pull found them -- the cast actively improved the enemy's position.
        # Ground truth from the engine, the live twin approximates via the team tracker.
        self.w_nado_bad = r("nado_bad", -0.3)
        self.w_nado_retarget = r("nado_retarget", 0.4)     # dragged a tower-locked wincon off your tower
        # SIEGE WINDOW (2026-08-15, user doctrine): the offensive phase now runs until OVERTIME
        # begins, not until double elixir does. Flipping at 2x (regulation - 60 s) surrendered
        # the siege a full minute early -- exactly the minute where DOUBLE elixir makes a
        # 6-cost bow affordable to re-place and defend, which is when a lock is most winnable.
        # A match that reaches overtime still gets its whole overtime for defence + rocket
        # cycling, which is what that phase is actually for.
        self._double_time = float(cfg.get("sim", "regulation_s", default=180.0))   # OVERTIME start
        self.split_lane_counters = set(cfg.get("env", "split_lane_counter_cards",
                                               default=["royal_recruits", "royal_hogs"]))
        self.agent_dt = float(cfg.get("sim", "agent_dt", default=1.0))
        self.sub_dt = float(cfg.get("sim", "sub_dt", default=0.1))

        self.eng = SimEngine(cfg, self.db, self.rng)
        # Per-match visual restyle (sim2real for the CNN). PRIVATE rng seeded once at construction:
        # resample() must NOT consume self.rng, or the eval benchmark's seeded deck sequences shift.
        self.domain_rand = view.DomainRand(cfg, random.Random(self.rng.randrange(2 ** 31)))
        # Optional hook: train_sim sets this to inject SELF-PLAY opponents (a frozen past policy) mixed
        # with the scripted meta bots. Called with `self` in reset(); default None = always scripted.
        self.opponent_provider = None
        # Optional hook: called with `self` after EVERY physics sub-tick inside step(). `sim-view` uses it
        # to render the engine at sub_dt resolution (the agent only decides every agent_dt, so rendering
        # per step would hide everything that happens between decisions -- projectile flight, the tornado
        # pull, aggro switches). None = no-op, so training pays nothing for it.
        self.on_tick = None
        self._reset_vectors()

    def _reset_vectors(self):
        self._last_obs = np.zeros(self.obs_shape, dtype=np.uint8)
        self.hand_vec = np.zeros(self.n_cards, np.float32)
        self.next_vec = np.zeros(self.n_cards, np.float32)
        self.elixir_vec = np.zeros(1, np.float32)
        self.threat_vec = np.zeros(self.threat_dim, np.float32)
        self.elixir = 0
        self._last_frame = self._last_obs
        self._prev_ident_depth = 0.0
        self._prev_ident_depth_true = 0.0
        self._opp_mem.reset()

    # -- hand cycle --------------------------------------------------------
    def _slot_card_id(self, slot: int) -> int:
        """The identity this slot currently presents: the Evolution once it has banked its cycles,
        otherwise the base card."""
        evo = self.slot_evo_id[slot]
        if evo >= 0 and self.evo_charge[slot] >= self.slot_cycles[slot]:
            return evo
        return self.slot_base_id[slot]

    def _queue_ids(self):
        """The whole cycle as the identities it will present, in order (hand first)."""
        return [self._slot_card_id(s) for s in self.cycle]

    def _hand_ids(self):
        return [self._slot_card_id(s) for s in self.cycle[:4]]

    def _play_slot(self, card_id: int) -> None:
        """Consume a played identity: bank/spend its slot's Evolution charge, then send the slot to
        the back of the cycle."""
        slot = self.slot_of.get(card_id)
        if slot is None:
            return
        if card_id == self.slot_evo_id[slot]:
            self.evo_charge[slot] = 0                    # the Evolution was spent -> recharge from scratch
        elif self.slot_evo_id[slot] >= 0:
            self.evo_charge[slot] += 1                   # a base play banks one cycle toward the Evolution
        self.cycle.remove(slot)
        self.cycle.append(slot)

    def _update_vectors(self):
        self.hand_vec[:] = 0.0
        for i in self._hand_ids():
            self.hand_vec[i] = 1.0
        # graded UPCOMING-order vector (Next=1.0 grading down for the hidden cards) from the true
        # ordered queue -- lets the policy plan which cards to cycle toward. Superset of a next one-hot.
        self.next_vec[:] = cycle_vector(self._queue_ids(), self.n_cards)
        self.elixir = int(self.eng.elixir[0])
        self.elixir_vec[0] = self.eng.elixir[0] / 10.0
        self.threat_vec[:] = self._threat_vector()
        self._last_obs = self._render()
        self._last_frame = self._last_obs

    # -- observation -------------------------------------------------------
    def _threat_vector(self) -> np.ndarray:
        """Compact, best-effort approximation of clashrl.threats.Threat.vector() from ground truth:
        enemy (team-1) units on YOUR half. Not a 1:1 layout -- enough to condition on in sim. When
        use_detector, append card_threat's identity block for the RECOGNISED (whitelisted) enemies."""
        base = view.threat_vector(self.eng, _THREAT_DIM, team=0)
        if not self.use_detector:
            return base
        self._threat_id = card_threat.identity_threat_vector(
            view.apply_detector_noise(view.identity_items(self.eng, 0, self.detector_cards,
                                                          self.identity_front),
                                      self.det_recall, self.det_precision, self.rng, self.detector_cards,
                                      self.det_recall_by_card),
            self.db, prev_depth=self._prev_ident_depth, dt=self.agent_dt, horizon=self.predict_horizon)
        self._prev_ident_depth = float(self._threat_id[7])
        # ...and the un-noised twin the REWARD grades against (never enters the observation).
        self._threat_id_true = card_threat.identity_threat_vector(
            view.identity_items(self.eng, 0, self.detector_cards, self.identity_front),
            self.db, prev_depth=self._prev_ident_depth_true, dt=self.agent_dt,
            horizon=self.predict_horizon)
        self._prev_ident_depth_true = float(self._threat_id_true[7])
        # THREAT-CREDIT HYSTERESIS: the budget refills only after 3 s of SUSTAINED quiet -- a
        # one-step gap between two waves of the same push must not hand out fresh credits.
        if self._threat_id_true[0] < 0.5:
            if self._tid_unlit_t is None:
                self._tid_unlit_t = self.eng.t
            elif self.eng.t - self._tid_unlit_t >= 3.0:
                self._threat_credits = 0
        else:
            self._tid_unlit_t = None
        mem = self._opp_mem.update(
            view.apply_detector_noise(view.opponent_memory_items(self.eng, 0, self.detector_cards),
                                      self.det_recall, self.det_precision, self.rng, self.detector_cards,
                                      self.det_recall_by_card), dt=self.agent_dt)
        # Slot 5 mirrors the opponent-elixir signal from team 1's perspective.
        mem[5] = self.eng.elixir[0] / 10.0
        parts = [base, self._threat_id, mem]
        if self.use_interactions:                     # who is predicted to be marching at which tower
            units, mine_t, en_t = view.interaction_state(self.eng, 0, self.detector_cards, self.rng,
                                                         self.det_recall, self.det_recall_by_card)
            parts.append(interactions.interaction_vector(units, mine_t, en_t, self.db))
        if self.use_tower_obs:
            parts.append(view.tower_vector(self.eng, 0))
        return np.concatenate(parts).astype(np.float32)

    def _render(self) -> np.ndarray:
        oh, ow, _ = self.obs_shape
        img = view.render_obs(self.eng, oh, ow, team=0, dr=self.domain_rand)
        if not self.use_canvas:
            return img
        ch = view.semantic_channels(self.eng, oh, ow, team=0, rng=self.rng,
                                    presence_recall=self.canvas_presence_recall)
        if self.use_pred_canvas:
            # PREDICTIVE slice from the SAME noised unit view the interaction vector reads --
            # sim and live both paint mover_forecast, so the feature transfers by construction.
            units, mine_t, en_t = view.interaction_state(self.eng, 0, self.detector_cards, self.rng,
                                                         self.det_recall, self.det_recall_by_card)
            pred = detect_obs.predictive_channels(units, mine_t, en_t, self.db, oh, ow,
                                                  dt_s=self.pred_dt, horizon_s=self.pred_horizon)
            ch = np.concatenate([ch, detect_obs.channels_to_uint8(pred)], axis=2)
        if self.use_hp_canvas:
            hp = detect_obs.hp_channels(view.hp_state(self.eng, 0, self.rng,
                                                      self.canvas_presence_recall), oh, ow)
            ch = np.concatenate([ch, detect_obs.channels_to_uint8(hp)], axis=2)
        # Each slice keeps its OWN independent presence dropout, which is what live does: a unit the
        # detector missed this frame is absent from this slice only.
        return np.concatenate([img, self._canvas_stack.push(ch, self.eng.t)], axis=2)

    # -- lifecycle ---------------------------------------------------------
    def reset(self) -> np.ndarray:
        self.eng.reset()
        self._canvas_stack.reset()       # motion history must never bridge two matches
        self.domain_rand.resample()      # a new 'arena look' each match (stable within the match)
        self.opponent = (self.opponent_provider(self) if self.opponent_provider is not None
                         else make_opponent(self.cfg, self.db, self.rng, self.meta_pool))
        self.cycle = list(range(self.n_slots))
        self.rng.shuffle(self.cycle)
        self.evo_charge = [0] * self.n_slots     # match starts with every Evolution UNCHARGED
        self._match_bonus = 0.0
        self._match_penalty = 0.0        # symmetric twin of _match_bonus (see _bonus)
        self.rw_stats.new_match()
        self._cf_used = 0                # counterfactual fork budget is PER MATCH
        self._cf_watch = []              # ...and no fork may outlive the match that opened it
        self._prev_trade_pot = self._trade_potential(self.eng)   # two-sided resource balance (starts level)
        self._prev_chip_prog = 0.0       # convex enemy-tower chip progress (offense)
        self._prev_chip_prog_def = 0.0   # convex own-tower chip progress (defense)
        self._prev_my_crowns = 0
        self._prev_op_crowns = 0
        self._defensive = False          # icebow phase: False = offensive X-Bow win-condition; True = defence + rocket-cycle
        self._enemy_chip_total = 0.0     # cumulative enemy-tower HP the X-Bow/rocket has chipped (X-Bow success gauge)
        self._ally_xbow_standing = False  # pre-deploy read for the wincon repeat-credit gate
        self._bow_ledger = {}             # id(bow) -> {ids, cost, lock}: overcommit + uptime ledgers
        self._enemy_seen = set()          # enemy spec.keys fielded this match (context modifiers)
        self._ev_enemy, self._ev_own, self._ev_spells = {}, {}, []   # trade event ledger
        self._threat_credits = 0          # threat-response credits paid this episode (budgeted)
        self._tid_unlit_t = None          # engine-time stamp of sustained threat quiet (hysteresis)
        self._threat_miss_last = -1e9     # engine-time of the last threat_miss charge (throttle)
        # MATCHUP-aware doctrine. The X-Bow playstyle is SIEGE FIRST, then turtle once ahead -- the
        # "turtle" half is the my_c >= 1 flip in step(), so the matchup lock here only needs to cover
        # decks that STRUCTURALLY blank a siege. A SPLIT-LANE deck (Royal Recruits / Royal Hogs) does:
        # a wide two-lane push is something one X-Bow cannot cover, whatever the elixir count.
        # Fast CYCLE and heavy BEATDOWN used to lock defensive here too, which was wrong -- those are
        # an ELIXIR-TIMING problem, not a structural one. A beatdown deck blanks a forward X-Bow only
        # while it can AFFORD a mini-tank, which is exactly what _punish_window now tests. Locking the
        # whole match defensive meant MEASURED 93.5% of steps in defensive phase and 0 of 143 X-Bow
        # plays ever placed forward: the deck's siege win condition trained into a defensive building.
        self._matchup = getattr(self.opponent, "style", "control")
        opp_cards = set(getattr(self.opponent, "cards", ()) or ())
        self._split_lane_counter = bool(opp_cards & self.split_lane_counters)
        if self._split_lane_counter:
            self._defensive = True
        # Cheapest card in the OPPONENT's deck that can actually BODY a forward X-Bow. A 3-5 elixir
        # mini-tank blanks a 6-elixir siege commitment, so the siege is only SAFE while they cannot
        # afford even this. Swarms are excluded (the rule is about tanks / mini-tanks) and so is
        # anything too flimsy to trade with a siege -- without the HP floor the "cheapest blocker" came
        # out as a 1-elixir SPIRIT in most decks (median 1e), which made the window near-unreachable.
        # Air is NOT excluded: the X-Bow cannot shoot back at it.
        self._opp_block_cost = min(
            (float(p.elixir) for p in
             (card_threat.profile(self.db, k[:-4] if k.endswith("_evo") else k) for k in opp_cards)
             if p.kind == "troop" and not p.swarm and p.elixir
             and (p.tank or float(p.hitpoints or 0.0) >= self.punish_blocker_min_hp)),
            default=self.punish_opp_elixir)
        # Exact opponent blocker identities (sim-only ground truth): used by punish logic to ask
        # whether a blocker is in hand NOW, not just whether the opponent has enough elixir in abstract.
        self._opp_block_bases = {
            p.name for p in
            (card_threat.profile(self.db, k[:-4] if k.endswith("_evo") else k) for k in opp_cards)
            if p.kind == "troop" and not p.swarm
            and (p.tank or float(p.hitpoints or 0.0) >= self.punish_blocker_min_hp)
        }
        self._nado_watch = []            # in-flight tornado casts awaiting their delayed execution credit
        self._nado_king_credited = False
        self._reset_vectors()
        self._update_vectors()
        return self._last_obs

    def _opp_hand_specs(self):
        """Best-effort opponent hand from the sim opponent's cycle state.

        ScriptedBot and SelfPlayOpponent both expose `specs` and `cycle`, where the first four cycle
        entries are the current hand. If an opponent implementation does not expose this, fall back to
        unknown (empty) so reward logic degrades to the old elixir-only behaviour.
        """
        cyc = getattr(self.opponent, "cycle", None)
        specs = getattr(self.opponent, "specs", None)
        if not cyc or not specs:
            return []
        out = []
        for idx in list(cyc)[:4]:
            if 0 <= int(idx) < len(specs):
                out.append(specs[int(idx)])
        return out

    def _opp_can_block_now(self) -> bool:
        """True when the opponent can immediately answer a forward X-Bow this decision step.

        This is deterministic in sim: a blocker must be BOTH in the current 4-card hand and affordable
        at the opponent's current elixir.
        """
        if not self._opp_block_bases:
            return False
        opp_elixir = float(self.eng.elixir[1])
        for s in self._opp_hand_specs():
            if s is None:
                continue
            base = str(getattr(s, "base", "") or "")
            if base in self._opp_block_bases and float(getattr(s, "elixir", 99.0)) <= opp_elixir:
                return True
        return False

    def _bonus(self, credit: float) -> float:
        """Cap the CUMULATIVE correctness shaping per match, SYMMETRICALLY (anti-farm both ways).

        Capping only the POSITIVE side turns the cap into a SLOPE: the bonus saturates while the
        penalty stream keeps growing, so the best available policy becomes the one that ends the match
        soonest. Bounding both signs by the same budget keeps the anti-farm intent without making
        'stop playing' the optimum. Mirrors env.py's live twin.
        """
        if credit >= 0.0:
            allowed = min(credit, max(0.0, self.correctness_cap - self._match_bonus))
            self._match_bonus += allowed
            return allowed
        allowed = min(-credit, max(0.0, self.correctness_cap - self._match_penalty))
        self._match_penalty += allowed
        return -allowed

    def _threat_pos(self):
        """(x, y) of the deepest enemy troop on YOUR half (the threat to intercept); centre if none."""
        onside = [u for u in self.eng.units if u.team == 1 and u.spec.kind != "spell" and u.y >= 0.5]
        if not onside:
            return 0.5, 0.5
        u = max(onside, key=lambda u: u.y)               # deepest = closest to your king
        return float(u.x), float(u.y)

    def _leaking_first(self, spend: float = 0.0) -> bool:
        """True when waiting costs more than committing. On a QUIET board the safe default is to hold --
        a defender dropped in one lane cannot answer a push in the other, so it can simply be played
        around. The exception is the elixir race: if you are near the cap AND hold more than the
        opponent, YOUR bar overflows first, so the elixir wasted by waiting exceeds what the lane
        commitment risks. Reward-side only (uses the opponent's true elixir, which the policy cannot
        see -- see the observability note in _threat_response).

        ``spend`` is ADDED BACK because the caller runs inside step()'s `if eng.deploy(...)` block,
        where the engine has ALREADY deducted the card. This grades the DECISION, which was taken
        before paying. Reading the engine raw asked "are you still near the cap AFTER paying?" -- for a
        3-cost card that needs 11 elixir, so it only ever fired for 1-cost cards. The opponent has not
        acted yet at this point, so eng.elixir[1] is correctly their elixir at decision time."""
        mine = self.eng.elixir[0] + spend
        return mine >= self.quiet_board_free_elixir and mine > self.eng.elixir[1]

    def _threat_response(self, card_id: int, nx: float, ny: float) -> float:
        """(1) THREAT-RESPONSE correctness: did you play the KB-correct counter to the ASSESSED threat,
        placed to intercept it? Right counter in the threat's lane -> +; the WRONG role dropped as a
        defence, or a pure defender played with no threat (premature) -> -. Offensive placements are
        judged by wincon_exec / the trade term, not here. Grades on the GROUND-TRUTH threat identity,
        not the detector-noised one the policy observes."""
        tid = self._threat_id_true
        prof = self._deck_profiles[card_id]
        if tid is None or len(tid) < card_threat.IDENTITY_DIM or tid[0] < 0.5:
            # QUIET BOARD -> NOT GRADED. This branch used to charge w_threat_miss * 0.4 for playing a
            # defender with no threat on the board ("premature"). It was the single largest remaining
            # one-sided penalty: MEASURED over 40 matches, 257 fires and ZERO bonuses (-2.57/match),
            # while the DEFENSIVE half of this same term was healthy and balanced at +63 / -66.
            #
            # It is deleted rather than narrowed because the question it asks CANNOT BE ANSWERED AT
            # PLAY TIME. Whether cycling a cheap defender on a quiet board was right depends entirely
            # on what happens next: it can rotate you back to the Tesla that stops a bridge wincon, or
            # it can leave you holding nothing when the push lands in the other lane. Same board, same
            # card, opposite verdicts. An instantaneous classifier has to guess, and a guess that can
            # only ever subtract is an action tax -- it made "play less" strictly better regardless of
            # whether playing helped, and the policy found that twice (plays/match 50.1 -> 30.9 with
            # winrate 4.4% -> 0.0% while episode reward IMPROVED -24.1 -> -18.1).
            #
            # The consequence it was guessing at is ALREADY MEASURED. agent_dt is 1.0 s and GAE runs at
            # gamma 0.99 / lambda 0.95 = a 17-SECOND credit window, which comfortably spans the few
            # seconds to a preventable tower hit or the ~5-10 s for a bridge wincon to connect. If a
            # cycle play really did cost a tower, the chip and crown terms bill it -- with the actual
            # damage, at the actual time, instead of a prior. Keeping both charged it twice, once wrong.
            return 0.0
        # DEPTH WINDOW + EPISODE BUDGET (2026-08-14, ported from live). Below min depth the push
        # is still building -- pre-committing is wrong; ABOVE max depth the threat is already on
        # our tower, and crediting the late answer teaches slow defense (same timing doctrine as
        # the trade ledger's grace window). At most threat_credit_budget positive credits pay per
        # threat episode (a real defense is 1-2 cards, not 4); the budget refills only after 3 s
        # of sustained quiet, engine-timed in _observe -- a flickering assessment cannot refill it.
        dpt = float(tid[7]) if len(tid) > 7 else 0.5
        deep_ok = self.threat_min_depth <= dpt <= self.threat_max_depth
        budget_ok = self._threat_credits < self.threat_credit_budget
        tx, ty = self._threat_pos()
        intercept = abs(nx - tx) <= self.intercept_lane and ny >= 0.5   # same lane, on your defensive half
        if prof.kind == "building":
            # A BUILDING DOES NOT INTERCEPT, IT ATTRACTS -- so the same-lane test is the wrong physics.
            # The lane rule encodes "put a body in the path", which is how a TROOP defends. A defensive
            # building works by being the nearest BUILDING to a building-targeter (see engine._acquire),
            # which pulls the wincon toward IT, and the classic answer is a CENTRAL placement precisely
            # because it drags the push off-lane into range of BOTH princess towers.
            # With intercept_lane 0.15, a central Tesla against a hog in the x=0.25 lane is 0.25 away
            # and scored ZERO, while dropping it directly on the hog scored full credit -- the reward
            # paid for the WORSE placement. That mattered from the moment buildings could actually pull
            # (5cac1bf); before then neither placement did anything, so the error was invisible.
            # Graded on the counter role alone here; WHERE it went is settled by what follows -- the
            # chip/crown terms bill the damage it failed to prevent, and the counterfactual fork
            # compares against having held it. Same reasoning that retired the quiet-board branch.
            if not (card_threat.counters(prof, tid) and 0.50 <= ny <= 0.80 and deep_ok and budget_ok):
                return 0.0                # right role but wrong geometry/timing, or budget spent
            self._threat_credits += 1
            return self.w_threat_response
        if prof.pull:
            # A PULL spell is not a role counter and must not be graded as one. Its payoff is the CLUMP --
            # ice-wizard splash landing on everything, a centre Rocket hitting the whole push, a wincon
            # dragged off a tower, your king woken early -- none of which exists at cast time. Grading it
            # here charged an UNCAPPED -1.0 the moment it was cast on any non-swarm push, while the
            # execution credit that repays it arrives 2-3.5s later and is INSIDE correctness_cap: a tornado
            # that clumped 2 enemies still netted -0.75, teaching the policy that the deck's signature
            # defensive play is a mistake. Judged solely by _nado_shaping now; an EMPTY pull is still
            # punished by spell_waste, so this is not a free pass.
            return 0.0
        if card_threat.counters(prof, tid):
            if not (intercept and deep_ok and budget_ok):
                return 0.0
            self._threat_credits += 1
            return self.w_threat_response                                # right counter, placed AND timed right
        if prof.spell:
            # DAMAGE SPELLS ARE NEVER A "MISREAD" (2026-08-15). A defensive Rocket dropped ON a
            # golem push at intercept was charged w_threat_miss (-1.0) EVERY time -- the counter
            # matrix only role-validates spells against swarms, so the deck's get-out-of-jail
            # card was punished at exactly the moment it is the right play. Same double-billing
            # the pull-spell exemption removed: a damage spell's defensive worth is already
            # priced to the elixir by the trade ledger's spell-kill attribution (blast + 3 s)
            # and the chip terms, with spell_waste still billing an EMPTY cast. MEASURED before
            # this change: rocket at 0 plays across 60 greedy eval matches (twice, a day apart)
            # while every other card saw abundant use, with a clean +-0.05 logit row -- the
            # behaviour was learned from this penalty, not from head damage.
            return 0.0
        return self.w_threat_miss if intercept else 0.0                  # wrong role dropped as a defence = a misread

    def _threat_miss_idle(self) -> float:
        """No play while an ANSWERABLE threat is present (a counter is in hand AND affordable) = a missed
        defence. Uncapped penalty (this is the 'ignored the push' case the old idle_penalty covered).
        Ground-truth threat: the objective is defined by the real board, not by what the detector saw.

        WINCON-BANK WAIVER (2026-08-14): "answerable" now means playable UNDER THE SAME RULE THE
        SAMPLER APPLIES. While the bank is active (a win condition in hand, bank_floor <= elixir <
        its cost) every cheaper card is MASKED by wincon_bank.apply_wincon_bank -- the trainer
        itself forbids the counter -- so charging the idle penalty for that hold punished mandated
        behaviour. MEASURED on the round-4 14k read: 1595 fires / 100 matches (-16/match, the
        dominant negative at 3x the next term) on a policy making 16.6 plays/match with 57% forced
        waits. The waiver applies exactly while the mask does: at elixir >= the wincon's cost the
        counter is genuinely playable again and the penalty charges as before."""
        tid = self._threat_id_true
        if tid is None or len(tid) < card_threat.IDENTITY_DIM or tid[0] < 0.5:
            return 0.0
        # TRIAGE WAIVER (2026-08-16). "Answerable" is not the same as "worth answering", and this
        # term charged the full miss penalty for the single clearest correct hold in the doctrine:
        # MEASURED, a lone Skeletons -- 0.38% of a Princess Tower if ignored outright -- cost -1.0,
        # the identical penalty as ignoring a Hog Rider at 34%. The fundamentals tier teaches that
        # hold and this term punished it, so the two were pulling the policy in opposite directions
        # on the exact board the user reported it playing badly.
        #
        # Threats ADD, so this triages the committed GROUP: three ignorable units together are a
        # real push and the penalty applies again, unchanged.
        committed = [u for u in self.eng.units
                     if u.team == 1 and u.hp > 0 and u.spec.kind != "spell" and u.y > 0.42]
        if committed and threat_value.group_ignore_frac(
                self.db, [u.spec.base for u in committed],
                tower_level=self._tower_level_for_triage) < threat_value.IGNORE_FRAC:
            return 0.0
        # ALREADY ANSWERING IT IS NOT IGNORING IT (2026-08-17). This term asked only "is a counter in
        # hand and affordable", never "is the push already being dealt with" -- so the step after a
        # Knight was dropped to intercept, and every step while he walked into the fight, was charged
        # the full miss penalty again. Defence takes seconds; the penalty charged per 1-second step.
        if any(u.team == 0 and u.hp > 0 and u.spec.kind != "spell"
               and card_threat.counters(card_threat.profile(self.db, u.spec.base), tid)
               for u in self.eng.units):
            return 0.0
        # ...AND IGNORING IT IS ONE MISTAKE, NOT ONE PER TICK. Uncapped per-step charging made this
        # the dominant term in the whole ledger and taught the policy to keep its bar empty.
        #
        # MEASURED on the Hog EQ deck, which shares this file: a hold-to-6 policy took -152.00 from
        # this term alone over 152 fires -- 86% of its total penalty -- while spend-everything took
        # none, because the term only charges on a step where nothing was played. Holding scored
        # -0.545/step against -0.065 for dumping, so ALWAYS PLAY was strictly optimal; the gate duly
        # collapsed to it (P(play) 0.611-0.698, never below the 0.25 threshold, bar never above 5,
        # 4-cost cards never played). After the fix: 24 fires, -0.106/step against -0.065.
        #
        # A push left genuinely unanswered still charges repeatedly -- that is what this term is for
        # -- just on a human timescale rather than every tick.
        if self.eng.t - self._threat_miss_last < self.threat_miss_period:
            return 0.0
        elix = float(self.eng.elixir[0])
        hand = self._hand_ids()
        banking = (self._bank_floor > 0.0 and self._bank_wincon_cost > 0.0
                   and any(c in self._bank_wincon_ids for c in hand)
                   and self._bank_floor <= elix < self._bank_wincon_cost)
        for cid in hand:
            if not card_threat.counters(self._deck_profiles[cid], tid):
                continue
            if self.specs[cid].elixir > elix:
                continue                                     # not affordable
            if banking and self.specs[cid].elixir < self._bank_wincon_cost:
                continue                                     # bank-masked -> not actually playable
            self._threat_miss_last = self.eng.t
            return self.w_threat_miss
        return 0.0

    def _punish_window(self, spend: float = 0.0) -> bool:
        """The opponent has overcommitted and cannot answer a siege before it starts firing. A forward
        X-Bow is a 6-elixir bet that is simply BLANKED by any 3-5 elixir tank or mini-tank, so the bar
        is not a flat number: it is whether they can still afford their own CHEAPEST BLOCKER
        (_opp_block_cost, from their actual deck) AND whether a blocker is actually in hand NOW. Reward-
        side only -- it reads the opponent's true sim state (elixir + cycle), which the policy cannot
        observe live. ``spend`` is added back for the same pre-spend reason: an X-Bow costs 6, so
        measured POST-spend this needed a 10-elixir lead and fired EXACTLY ZERO times in 162 X-Bow plays.
        """
        mine = self.eng.elixir[0] + spend
        opp = float(self.eng.elixir[1])
        # If they can drop a blocker immediately, this is not a punish window even with an elixir lead.
        if self._opp_can_block_now():
            return False
        return ((opp < self._opp_block_cost)
                or (mine - opp >= self.punish_elixir_gap))

    def _bow_split_punish(self, nx: float) -> bool:
        """The guide's tank-investment punish: a heavy enemy tank committed DEEP in their own
        territory means an immediate bow is answered late -- OPPOSITE lane for ground tanks
        (splits their push), SAME lane for a Lava Hound (forces the ground answer early)."""
        for u in self.eng.units:
            if (u.team == 1 and u.hp > 0 and u.spec.kind == "troop"
                    and u.spec.elixir >= 5 and u.spec.hp >= 2000 and u.y < 0.25):
                same = (u.x - 0.5) * (nx - 0.5) > 0.0
                return same if u.spec.flying else not same
        return False

    def _wincon_exec(self, card_id: int, nx: float, ny: float) -> float:
        """(3) WIN-CONDITION execution: the deck's doctrine done right for the current phase -- X-Bow
        forward-in-range (offensive) / back-centre (defensive), Miner chipping the princess (not the king),
        rocket-cycle chip or the rocket 2-for-1. + when executed correctly, - when the win condition is
        thrown away. Non-win-condition cards return 0 (they're scored by threat_response / the trade term)."""
        princesses = [t for t in self.eng.towers[1][:2] if t.alive]
        d = min((tile_dist(nx, ny, t.x, t.y) for t in princesses), default=99.0)   # tiles
        if card_id in self.xbow_ids:
            # "back-centre" = the CENTER INTERCEPT band behind the bridge (where a Tesla would sit), NOT
            # behind the princess towers. In-band = full credit; DEEPER than the towers = a small fraction
            # (soft shaping: rarely useful, but not punished like a true misplace).
            central = abs(nx - 0.5) <= 0.18
            in_band = central and self.xbow_front <= ny <= self.xbow_back
            behind = central and ny > self.xbow_back
            frac = 1.0 if in_band else (self.xbow_deep_frac if behind else 0.0)
            if frac == 0.0 and self.xbow_front <= ny <= self.xbow_back + 0.10:
                # LANE-BOW SOFTENING (2026-08-15): an off-centre bow at defensive depth is a
                # SUBOPTIMAL spot, not a thrown-away card -- but it fell off the `central`
                # cliff to frac 0 and ate the full w_wincon_mis. MEASURED: 32/32 bow plays
                # (rows 15-18, mostly lane-side) scored -1.00 in a 20-match probe -- a 100%
                # tax on the deck's win condition that xbow_lock/chip_linear (+0.07/match)
                # could never repay. Same doctrine as xbow_deep_frac: soft fraction, so the
                # gradient still points at the centre band without deleting the card. True
                # dumps (enemy half unreachable, back corners) still miss in full.
                frac = self.xbow_lane_frac
            # PUNISH OVERRIDE, checked BEFORE the phase gate. An opponent who has just overcommitted
            # cannot answer a siege before it starts firing, and that is worth breaking defensive
            # posture for -- "immediately punish" is conditional on the ELIXIR RACE, not on the matchup
            # doctrine. Without this the clause was unreachable: _defensive is set on sight of a cycle
            # or beatdown deck (most of the meta pool), so MEASURED 145 of 152 X-Bow plays took the
            # defensive branch and only 5 were ever offensive AND in a punish window.
            if d <= self.xbow_range and self._punish_window(self.specs[card_id].elixir):
                val = self.w_wincon * self.xbow_punish_mult
            elif self._defensive:                            # DEFENSIVE phase: centre-band only; forward is wrong now
                val = self.w_wincon * frac if frac > 0.0 else self.w_wincon_mis
            elif d <= self.xbow_range:                        # OFFENSIVE: forward, in tower range = win condition set
                val = self.w_wincon
                if self.eng.t < 30.0:
                    val *= self.bow_first_frac               # "never X-Bow the bridge first play"
                elif self._bow_split_punish(nx):
                    val = self.w_wincon * self.xbow_punish_mult   # back-tank invested -> split-push bow
            else:
                val = self.w_wincon * 0.4 * frac if frac > 0.0 else self.w_wincon_mis
            # REPEAT-CREDIT GATE (2026-08-12): NO placement credit while an allied X-Bow is ALREADY
            # standing. Without it the credit was renewable by re-placement: MEASURED on the 21:48
            # snapshot of the from-scratch run, wincon_exec fired 374/374 positive (~6/match,
            # saturating correctness_cap) while six cards collapsed onto one central tile -- the
            # constant-cell attractor re-formed around farming this term. The gate nulls only the
            # POSITIVE side: a misplace while one stands still costs (a wasted 6-elixir drop is not
            # made free), and a double-bow is neutral, never punished (a real play at triple elixir).
            # SEQUENTIAL re-placement -- the defensive X-Bow cadence icebow leans on at 2x/3x, one
            # bow at a time -- re-credits every time, because the previous bow is dead when it fires.
            # `_ally_xbow_standing` is read PRE-deploy in step(), so the just-placed bow never gates
            # its own credit.
            if (val > 0.0 and d <= self.xbow_range
                    and (self._bow_hostile_keys & self._enemy_seen)):
                val *= self.bow_hostile_frac                 # their deck wrecks bows (Little Prince /
                                                             # Evo Bomber seen) -> tempered credit on
                                                             # EVERY positive offensive branch
            if val > 0.0 and self._ally_xbow_standing:
                val = 0.0
            return val
        if card_id in self.rocket_ids:
            return self._rocket_value(nx, ny, d)
        if card_id in self.miner_ids:
            king = self.eng.towers[1][2]                     # [L princess, R princess, KING]
            if king.alive and tile_dist(nx, ny, king.x, king.y) <= 2.9:
                return self.w_wincon_mis                      # Miner on the enemy KING wakes it early -> bad trade
            if d <= 2.9:                                      # tiles
                return self.w_wincon                          # Miner chipping the princess
        return 0.0

    def _fresh_pump(self):
        """The enemy ELIXIR COLLECTOR while it is still WORTH rocketing: within env.pump_rocket_window_s
        of its deploy. Past that it has paid most of its value back and the rocket is better spent
        elsewhere. None when no fresh pump is on the field."""
        return next((u for u in self.eng.units
                     if u.team == 1 and u.spec.base == "elixir_collector" and u.hp > 0
                     and u.age <= self.pump_window), None)

    def _pump_rocket(self, nx: float, ny: float) -> float:
        """PUMP PUNISH: a rocket whose blast covers an enemy Elixir Collector. A FRESH pump (inside the
        window) = full win-condition credit -- an unanswered pump out-economies a control deck; the
        2-for-1 multiplier when the blast ALSO clips an alive princess tower (the ideal aim); the
        MISPLACE penalty when the blast would clip the enemy KING (activating it costs more than any
        pump). A STALE pump earns nothing (the elixir already flowed). 0.0 = no pump in the blast ->
        the ordinary rocket logic applies."""
        R = _ROCKET_RADIUS                                   # tiles
        pump = next((u for u in self.eng.units
                     if u.team == 1 and u.spec.base == "elixir_collector" and u.hp > 0
                     and tile_dist(nx, ny, u.x, u.y) <= R + 0.3), None)
        if pump is None:
            return 0.0
        king = self.eng.towers[1][2]
        if king.alive and tile_dist(nx, ny, king.x, king.y) <= R + 0.6:
            return self.w_wincon_mis                         # never wake the king for a pump
        if pump.age <= self.pump_window:
            both = any(t.alive and tile_dist(nx, ny, t.x, t.y) <= R + 0.3
                       for t in self.eng.towers[1][:2])
            return self.w_wincon * (self.combo_mult if both else 1.0)
        return 0.0

    def _rocket_blast(self, nx: float, ny: float):
        """Enemy TROOPS a rocket at (nx, ny) would cover, and the elixir they are worth."""
        hit = [u for u in self.eng.units
               if u.team == 1 and u.hp > 0 and u.spec.kind == "troop"
               and tile_dist(nx, ny, u.x, u.y) <= _ROCKET_RADIUS + 0.3]
        worth = sum(float(u.spec.elixir) / max(1, u.spec.squad_count or u.spec.count) for u in hit)
        return hit, worth

    def _tiebreak_gap(self) -> float:
        """(our lowest princess HP) - (their lowest princess HP), as a fraction of a full tower.

        NEGATIVE means we are LOSING the tiebreak -- our weakest tower is the lower one, so a draw
        at time-out hands them the win. This is the quantity an icebow match in overtime is really
        being played for, and nothing in the reward saw it before.
        """
        ours = [t for t in self.eng.towers[0][:2] if t.alive]
        theirs = [t for t in self.eng.towers[1][:2] if t.alive]
        if not ours or not theirs:
            return 0.0
        full = max(1.0, float(self.eng.towers[0][0].max_hp))
        return (min(t.hp for t in ours) - min(t.hp for t in theirs)) / full

    def _rocket_value(self, nx: float, ny: float, d: float) -> float:
        """What THIS rocket is worth, conditionally -- the card's value is entirely situational.

        The old branch was three flat cases (pump / 2-for-1 / any chip once defensive, else zero),
        which priced a rocket by WHERE it landed and never by what the match needed. Rebuilt
        2026-08-16 from the user's doctrine plus published Rocket guides, in priority order,
        because several of these can be true at once and the best reading should win:

          PUMP        an unanswered Elixir Collector out-economies a control deck (unchanged).
          TORNADO     the deck's signature combo. A rocket-sized bundle almost never forms by
                      itself -- the Tornado MAKES one, and the rocket is the second half. Guides
                      are blunt that it is a timing play ("place both cards fast or the Rocket
                      will miss"), so this only pays while a cast is still gathering.
          2-FOR-1     tower chip + a 4-6 elixir support kill in one blast (unchanged).
          TIEBREAK    the win condition an icebow match in overtime actually has. Chip is worth
                      most when our weakest tower is the lower one, because that is the game we
                      lose on a draw; it is worth much less when we are already ahead on the
                      race and the elixir is better kept for defence.
          EMERGENCY   a heavy threat is across the river and nothing else in hand answers it.
                      An inefficient answer beats taking the whole push.
          WASTE       six elixir spent on cheap bodies a 1-3 cost card would have handled.
                      Guides call out "lone tanks" and single low-value units; the user names
                      Skeletons and Goblins. Priced as a misplace, not merely as zero.
        """
        # NEVER THE KING (2026-08-20, user: "there's no reason for an icebow player to
        # intentionally rocket cycle the king tower"). This measured 0.0 -- not rewarded, but not
        # charged either, while it still dodged the leak penalty, so dumping six elixir into the
        # king was a FREE cycle and the policy duly learned it. The king has roughly twice a
        # princess's HP, the chip is worth nothing on the tiebreak (which reads princess HP), and
        # it wakes the tower. Priced as a misplace, like every other six-elixir throwaway.
        king = self.eng.towers[1][2]
        if tile_dist(nx, ny, king.x, king.y) <= self.spell_aim_radius:
            return self.w_wincon_mis
        pr = self._pump_rocket(nx, ny)                       # PUMP PUNISH: fresh elixir collector
        if pr != 0.0:
            return pr
        hit, worth = self._rocket_blast(nx, ny)
        on_tower = d <= self.spell_aim_radius

        # ROCKET + TORNADO -- the blast must land INSIDE a live pull, on the same spot.
        #
        # This used to pay any rocket cast within rocket_nado_s of a tornado, i.e. the TORNADO
        # -> ROCKET order, which is the one the mechanics forbid: a pull lasts pull_duration
        # (~1.05 s) while a rocket's cast+travel is 0.4 s + distance (~1.4 s at range), so the
        # clump is released before the blast arrives. DOCTRINE_RESEARCH.md R6 resolved the order
        # from mechanics AND from Hunter correcting a student -- "play the rocket first and then
        # tornado everything" -- and flagged this exact rule for inversion.
        #
        # Rather than encode an order, check the physical condition the order exists to produce:
        # the sim knows a vortex's remaining pull (_Vortex.left) and a rocket's remaining flight,
        # so ask whether THIS rocket will still find a pull running when it lands. The doctrinal
        # order satisfies that; the reverse order satisfies it only in the narrow case where the
        # tornado was cast so late that its pull outlives the flight, which is a correct play too.
        eta = 0.4 + tile_dist(nx, ny, 0.5, 1.0) / 32.0       # mirrors the engine's spell delay
        nado = None
        for v in (self.eng.vortices or ()):
            if v.team != 0 or v.left < eta:
                continue                                     # pull ends before the blast lands
            if tile_dist(nx, ny, v.x, v.y) <= _ROCKET_RADIUS + 1.0:
                nado = [u for u in self.eng.units
                        if u.team == 1 and u.hp > 0 and u.spec.kind == "troop"
                        and tile_dist(u.x, u.y, v.x, v.y) <= _ROCKET_RADIUS + 1.0]
                if nado:
                    break
                nado = None
        if nado is not None and worth >= self.rocket_min_worth:
            # Deliberately NOT multiplied by combo_mult as well: stacking the two multipliers
            # priced a tornado-bundled rocket at 18.0, six times an X-Bow play, which would have
            # taught the policy that the combo is worth more than winning the tower. The bundle
            # IS the engineered 2-for-1, so it is worth the same class, plus a bounded uplift when
            # the same blast also reaches a tower.
            val = self.w_wincon * self.rocket_nado_mult
            return val + (self.w_wincon * self.rocket_chip_behind * 0.5 if on_tower else 0.0)

        if self._rocket_combo(nx, ny):                       # tower + valuable support = 2-for-1
            return self.w_wincon * self.combo_mult

        if on_tower:
            # TIEBREAK RACE. Behind or level -> this chip is the win condition; ahead -> it is a
            # luxury. Scaled rather than gated so the policy learns the gradient, not a cliff.
            gap = self._tiebreak_gap()
            late = self._defensive or self.eng.t >= self._double_time
            if late:
                mult = self.rocket_chip_behind if gap <= 0.0 else self.rocket_chip_ahead
            else:
                mult = self.rocket_chip_early
            return self.w_wincon * mult + (self.w_wincon * self.rocket_chip_behind * 0.5
                                           if worth >= self.rocket_min_worth else 0.0)

        if worth >= self.rocket_min_worth:
            return self.w_wincon * min(1.0, worth / 10.0) * self.combo_mult

        threat = next((u for u in self.eng.units
                       if u.team == 1 and u.hp > 0 and u.spec.kind == "troop"
                       and u.y > 0.52 and u.spec.elixir >= 4), None)
        if threat is not None and any(tile_dist(nx, ny, u.x, u.y) <= _ROCKET_RADIUS + 0.3
                                      for u in (threat,)):
            cheaper = [i for i in self._hand_ids()
                       if i in self.rocket_ids or i < 0 or self.specs[i].kind == "spell"
                       or self.eng.elixir[0] < self.specs[i].elixir]
            if len(cheaper) >= len(self._hand_ids()):        # nothing non-spell + affordable left
                return self.w_wincon * self.rocket_emergency

        if hit and worth < self.rocket_min_worth:
            return self.w_wincon_mis * self.rocket_waste_mult   # six elixir on cheap bodies
        return 0.0

    def _rocket_combo(self, nx: float, ny: float) -> bool:
        """True when a rocket aimed at (nx, ny) hits an alive enemy PRINCESS tower AND catches a VALUABLE
        (4-6 elixir), rocket-(almost)-one-shottable enemy support troop in the same blast -- the classic
        'rocket the Musketeer behind the tower' 2-for-1 (tower chip + a card-advantage kill). The engine
        already applies the damage to both; this just REWARDS lining the two up so the policy learns it."""
        if self._rocket_dmg <= 0.0:
            return False
        tgt = next((t for t in self.eng.towers[1][:2]
                    if t.alive and tile_dist(nx, ny, t.x, t.y) <= self.spell_aim_radius), None)
        if tgt is None:
            return False
        for u in self.eng.units:
            if (u.team == 1 and u.spec.kind == "troop" and not u.spec.building_only
                    and 4 <= u.spec.elixir <= 6
                    and u.spec.hp <= self._rocket_dmg * self.rocket_combo_hp_frac
                    and tile_dist(u.x, u.y, tgt.x, tgt.y) <= self.rocket_combo_radius):
                return True
        return False

    def _defending_now(self) -> bool:
        """True when an enemy TROOP has crossed onto OUR half, i.e. there is something a defensive
        card is actually answering. Ground truth, reward-side only."""
        return any(u.team == 1 and u.spec.kind == "troop" and u.y > 0.5 for u in self.eng.units)

    # -- counterfactual fork ------------------------------------------------
    def _fork_ready(self) -> bool:
        """Guardrail gate. MEASURED end-to-end with the opponent acting inside the branch, on a
        39-unit board against a 99 ms baseline match: a fork costs a ~6.5 ms floor (deepcopy + setup)
        plus ~3.5 ms per second of horizon -- 35.0 ms at 8 s, 24.0 at 4 s, 16.1 at 2 s. So only ~3
        forks per match fit inside a 2x slowdown, and forking every play would be far worse. Bounded
        by a hard PER-MATCH BUDGET rather than a sampling probability, so the worst case is
        deterministic and a busy match cannot quietly cost ten times a quiet one."""
        return (self.cf_enabled and self._cf_used < self.cf_budget and not self.eng.done
                and len(self.eng.units) >= self.cf_min_units)

    def _fork(self):
        """An ISOLATED branch of the match: engine and opponent deep-copied, each with its OWN RNG.

        RNG ISOLATION IS THE ENTIRE POINT OF THIS FUNCTION. `make_opponent` is handed `env.rng`, so
        `ScriptedBot.act` draws from the SHARED generator (rng.random / rng.choice throughout its
        placement logic, plus the detector-noise draws inside SelfPlayOpponent). Rolling a fork with
        that same object would consume draws from the REAL match's stream: the real opponent's later
        behaviour would depend on HOW MANY forks had been run, seeded runs would stop reproducing,
        and nothing would ever flag it. deepcopy gives the clone a Random with the same state but an
        independent future, so a branch is a faithful continuation that cannot write back.
        """
        return copy.deepcopy(self.eng), copy.deepcopy(self.opponent)

    def _side_value(self, eng, team: int) -> float:
        """Effective elixir value a side has ON THE BOARD: each body's deck cost split across its
        count, scaled by remaining HP fraction. Same accounting as `_enemy_value`, but for either
        side and on ANY engine (the fork has its own)."""
        v = 0.0
        for u in eng.units:
            if u.team == team and u.spec.kind in ("troop", "building"):
                frac = max(0.0, min(1.0, u.hp / u.spec.hp)) if u.spec.hp > 0 else 1.0
                v += (u.spec.elixir / max(1, u.spec.squad_count or u.spec.count)) * frac
        return v

    def _position(self, eng) -> float:
        """'How good is my position' = TOTAL RESOURCES, not just tower HP: crown-tower differential
        plus the board-value and elixir differentials.

        WHY NOT TOWER HP ALONE. That was the first version, and MEASURED it left 2 of every 3 forks
        settling at EXACTLY zero -- over 6 s of lookahead nothing reaches a tower, so both branches
        read identical and the fork cost ~29 ms to learn nothing. Only ~1.0 of 3 forks per match
        carried any signal, which meant the weight was amplifying something present on one play in
        three.

        WHY ELIXIR HAS TO BE IN IT. Adding board value alone would have been a trap in the opposite
        direction: playing a card RAISES your own unit value against the branch that held it, so
        every play would score positive -- an action BONUS, the same asymmetry that cost two runs,
        merely inverted. Counting elixir cancels it exactly: at the moment of the play the real
        branch is -cost elixir and +cost board value while the fork is unchanged, so the difference
        is ZERO and the term only starts to move as the unit actually does something (or dies).
        That is the whole point -- it should measure the CONSEQUENCE, not the act.

        Units are elixir; tower HP is normalised by one princess tower and `cf_board_weight` sets
        how many princess-towers a full elixir bar is worth.
        """
        ref = max(1.0, float(eng.towers[0][0].max_hp))
        towers = (sum(max(0.0, float(t.hp)) for t in eng.towers[0])
                  - sum(max(0.0, float(t.hp)) for t in eng.towers[1])) / ref
        return towers + self.cf_board_weight * self._trade_potential(eng)

    def _trade_potential(self, eng) -> float:
        """RESOURCE BALANCE in elixir: (our board value + our bar) - (theirs), normalised.

        Committed value AND uncommitted elixir both count, so moving elixir from the bar onto the
        board is worth exactly zero at the moment it happens and only the CONSEQUENCE scores. Towers
        are deliberately excluded -- `_position` adds them separately, and tower damage is already
        credited by the convex chip term.
        """
        return (self._side_value(eng, 0) - self._side_value(eng, 1)
                + float(eng.elixir[0]) - float(eng.elixir[1])) / self.value_norm

    def _roll_fork(self, eng, opp, horizon_s: float) -> float:
        """Advance an isolated branch `horizon_s` seconds with the AGENT DOING NOTHING -- the
        counterfactual is "what if I had held this card" -- while the opponent keeps playing.
        Returns the position scalar at the end of the branch."""
        steps = max(1, int(round(horizon_s / self.agent_dt)))
        sub = max(1, int(round(self.agent_dt / self.sub_dt)))
        for _ in range(steps):
            if eng.done:
                break
            opp.act(eng)
            for _ in range(sub):
                eng.advance(self.sub_dt)
                if eng.done:
                    break
        return self._position(eng)

    def _cf_open(self) -> None:
        """On a play: fork the match, roll the branch where we DID NOTHING, and remember its outcome
        so the real branch can be compared against it once the same horizon has actually elapsed."""
        if not self._fork_ready():
            return
        eng, opp = self._fork()
        self._cf_watch.append((self.eng.t + self.cf_horizon,
                               self._roll_fork(eng, opp, self.cf_horizon)))
        self._cf_used += 1

    def _cf_shaping(self) -> float:
        """(6) COUNTERFACTUAL correctness: settle any fork whose horizon has now elapsed in the REAL
        match, scoring `position(real) - position(held-the-card)`.

        This is the term the hand-written per-play rules kept failing to be. It is ZERO-MEAN BY
        CONSTRUCTION -- a play that improved the tower differential over doing nothing scores +, one
        that made it worse scores -, and a play that changed nothing scores 0. Every instantaneous
        classifier written so far could only subtract (cycle_plan fired 0 bonuses against 305
        penalties; threat_response's quiet branch 0 against 257), which is an action tax and taught
        the policy to stop playing rather than to play well.

        It also answers the question the user posed, which genuinely cannot be answered at play time:
        "does cycling this card now cost me tower damage that holding it would have prevented, or does
        it rotate me back to the Tesla before their wincon reaches the bridge?" Same board, same card,
        opposite verdicts depending on what follows -- so it is measured after the fact instead of
        guessed. Settled early if the match ends inside the horizon, so a decisive play still scores.
        """
        if not self._cf_watch:
            return 0.0
        now, out, keep = self.eng.t, 0.0, []
        for due, base in self._cf_watch:
            if now < due and not self.eng.done:
                keep.append((due, base))
                continue
            out += float(np.clip(self._position(self.eng) - base, -self.cf_cap, self.cf_cap))
        self._cf_watch = keep
        return out * self.w_counterfactual

    def _cycle_plan(self, card_id: int) -> float:
        """DELETED -- kept as a stub only to document why, because this term cost two training runs.

        It graded whether a cheap play was 'deliberate cycling' or 'purposeless spam'. It failed
        THREE times, each time by being a penalty with no reachable bonus:
          1. read POST-spend elixir against a PRE-spend threshold -> 1 bonus vs 495 penalties
          2. arithmetic fixed, still fired on 99.9% of cheap plays incl. 645 correct defensive ones
          3. made discriminative (post-spend reserve + 'nothing to defend') -> STILL 0 bonuses,
             MEASURED 110 fires / 0 positive / -1.10 per match on the 4096-match checkpoint

        The bonus branch needs a recognised threat, no counter in hand, a counter in the deck AND a
        post-spend reserve at once; post-spend elixir is p50 0.29, so it is unreachable in practice.
        A term that can only subtract is not teaching correctness, it is charging rent on acting --
        and the policy twice responded exactly as it should have, by playing less: plays/match
        50.1 -> 30.9 with winrate 4.4% -> 0.0% while episode reward IMPROVED -24.1 -> -18.1.

        The user's own framing is why no instantaneous rule can work here: cycling a cheap card can
        rotate you back to the Tesla that stops a bridge wincon, or leave you empty when the push
        lands in the other lane -- same board, same card, opposite verdicts depending on what
        follows. That question is now answered after the fact by `_cf_shaping`, which forks the
        branch where the card was HELD and compares. Nothing measurable was lost: zero bonuses in
        110 fires means the behaviour this was written to reward was never once rewarded.
        """
        return 0.0

    def _trade_reward(self) -> float:
        """(2) ELIXIR-TRADE correctness, as a TRUE POTENTIAL over BOTH sides' resources.

        WHAT THIS REPLACES WAS A FLAT TAX ON PLAYING. It scored `(enemy troop value eliminated) -
        (elixir you spent)`, which mixes two incompatible things. The first half TELESCOPES -- that
        part was right, and it is why idling could not farm it -- but telescoping means that over a
        whole match it collapses to `-(enemy value still alive at the end)` NO MATTER HOW WELL YOU
        DEFEND, because killing more just means more gets deployed after. The second half does not
        telescope at all: it accumulates at -0.1 reward per elixir, uncapped, forever.

        MEASURED over 40 matches: value_eliminated summed to -8.53/match against 93.22 elixir spent
        -> -10.17/match, with **0 of 40 matches positive** and play-steps scoring 52 up vs 1459 down
        (3.4%). Against `rewards.win: 2.0` a match's spend was worth ~4.7 losses, so the only lever
        the policy had was to play less. Same action-tax shape as `_cycle_plan` (0 bonuses / 305
        penalties) and the quiet-board branch (0 / 257), but hidden inside a term whose first half
        genuinely was potential-based. It did not collapse the run this time, it PLATEAUED it:
        winrate flat from match 3000 to 9500 while the policy sat at the balance point between the
        win signal and the spend tax.

        SPENDING ELIXIR IS A TRANSFER, NOT A LOSS -- it leaves your bar and becomes value on the
        board. Scoring the change in the two-sided resource balance makes a deploy exactly zero at
        the moment it happens and lets the term move only as the unit does something, dies, or
        trades, which is what "elixir trade" actually means. It also stops billing you for the
        OPPONENT playing a card: their deploy is +board/-bar for them and nets to zero, where the
        old term read their entire push as a penalty against you.

        This is the same accounting `_position` uses for the counterfactual forks, so the two agree
        instead of contradicting each other. The cap stays as a guard against a single freak step;
        it bit 1 step in 7991 before and should be rarer now that deploys cancel.
        """
        # ---- v3-SIM (2026-08-14): ATTRIBUTED EVENT LEDGER, ported from the live env with the
        # engine's GROUND-TRUTH advantages. The potential above had the same agency hole live
        # measured: tower kills, expiries and every hp tick moved it (~123 fires/match of churn),
        # and a LATE defense collected the same credit as a prompt one. Events now:
        #   * an ENEMY TROOP dying within trade_kill_radius_tiles of one of OUR living units, OR
        #     within blast range of one of OUR damage-spell casts (<= 3 s old), is CREDITED at
        #     its per-body elixir share -- scaled by RESPONSE TIMING: full inside trade_grace_s
        #     of the troop CROSSING onto our half, decaying linearly to zero at trade_late_s
        #     (engine-exact crossing times; deaths on their half carry no timing discount);
        #   * one of OUR TROOPS dying is DEBITED unconditionally (buildings excluded: a bow or
        #     tesla expiring is card-normal, and the X-Bow ledger prices bow outcomes);
        #   * everything else (tower kills with no unit of ours near, walk-offs, expiries,
        #     enemy spells/buildings vanishing, their deploys, hp ticks) moves NOTHING.
        # Unit identity is engine-exact (id()), so there is no matching heuristic at all --
        # the live version's nearest-neighbour tracks and flicker confirmation are unnecessary.
        eng = self.eng
        now = eng.t
        credit = debit = 0.0
        cur_en, cur_own = {}, {}
        for u in eng.units:
            if u.hp <= 0 or u.spec.kind != "troop":
                continue
            share = float(u.spec.elixir) / max(1, u.spec.squad_count or u.spec.count)
            if u.team == 1:
                prev = self._ev_enemy.get(id(u))
                t_cross = prev[3] if prev else None
                if t_cross is None and u.y >= 0.5:
                    t_cross = now
                cur_en[id(u)] = (share, u.x, u.y, t_cross, u.last_unit_hit_t)
            else:
                cur_own[id(u)] = (share, u.x, u.y)
        own_pos = [(v[1], v[2]) for v in cur_own.values()]             + [(v[1], v[2]) for v in self._ev_own.values()]   # prev too: a mutual kill still attributes
        for uid, (share, x, y, t_cross, last_hit) in self._ev_enemy.items():
            if uid in cur_en:
                continue                                     # still alive
            near_own = any(tile_dist(x, y, ox, oy) <= self.trade_kill_r for ox, oy in own_pos)
            near_spell = any(tile_dist(x, y, sx, sy) <= sr + 1.0 and now - st <= 3.0
                             for (sx, sy, sr, st) in self._ev_spells)
            # COMBAT ATTRIBUTION (2026-08-15): a LONG-RANGE defender kills from far beyond the
            # 4-tile proximity radius -- a lone defensive X-Bow (reach 11.5) shredding a push
            # earned ZERO trade credit, hollowing out exactly the doctrine's defensive-bow
            # value. The engine knows who fought: any enemy that took damage from one of our
            # UNITS (never tower fire -- _TOWER_SHOT is excluded at the stamp) within its last
            # 2.5 s attributes, at any range. Tower-only kills and walk-offs still pay nothing.
            in_combat = (now - last_hit) <= 2.5
            if not (near_own or near_spell or in_combat):
                continue                                     # the towers' kill / walk-off / expiry
            scale = 1.0
            if t_cross is not None:
                late = now - t_cross
                if late > self.trade_grace_s:
                    span = max(0.1, self.trade_late_s - self.trade_grace_s)
                    scale = max(0.0, 1.0 - (late - self.trade_grace_s) / span)
            credit += share * scale
        for uid, (share, x, y) in self._ev_own.items():
            if uid not in cur_own:
                debit += share
        self._ev_enemy, self._ev_own = cur_en, cur_own
        self._ev_spells = [sp for sp in self._ev_spells if now - sp[3] <= 3.0]
        if credit == 0.0 and debit == 0.0:
            return 0.0
        d = (credit - debit) / self.value_norm
        return float(np.clip(d, -self.trade_cap, self.trade_cap)) * self.w_elixir_trade

    def _xbow_overaggression(self, card_id: int, nx: float, ny: float) -> float:
        """A forward X-Bow that spends the elixir the DEFENCE still needed.

        The opposite-lane bow is the legitimate version of the aggressive play -- it survives, it
        chips, and against an overcommitted opponent it is the punish this deck is built on. What
        it must not be is a way to trade a live push for chip damage the tower pays for.

        And the reward had a hole exactly there. MEASURED on a live Giant push with the counters
        still in hand: ``threat_miss_idle`` charges -1.0 a step at 3 elixir or more, and **goes
        silent below 3** -- the cheapest counter's cost. So spending down to 2 elixir does not
        merely fail to answer the push, it STOPS THE PENALTY FOR NOT ANSWERING IT. A 6-elixir bow
        from 8 elixir buys that silence outright. Over-aggression was an escape hatch from the
        defensive term, which is the opposite of what that term is for.

        So this charges the case the silence covers: a real committed push, and after paying for
        the bow there is no counter left in hand we can afford. Exempt when ``_punish_window``
        says they cannot answer it -- that is the counterattack, not over-aggression, and the
        deck's whole plan depends on still being allowed to make it.
        """
        if card_id not in self.xbow_ids:
            return 0.0
        if (ny - 0.5) * 32.0 > self.bow_forward_tiles:
            return 0.0                                   # defensive bow: it is part of the defence
        tid = self._threat_id_true
        if tid is None or len(tid) < card_threat.IDENTITY_DIM or tid[0] < 0.5:
            return 0.0                                   # nothing recognised to defend against
        committed = [u for u in self.eng.units
                     if u.team == 1 and u.hp > 0 and u.spec.kind != "spell" and u.y > 0.42]
        if not committed:
            return 0.0
        if threat_value.group_ignore_frac(
                self.db, [u.spec.base for u in committed],
                tower_level=self._tower_level_for_triage) < threat_value.IGNORE_FRAC:
            return 0.0                                   # the tower handles it; spending is fine
        # `spend` is added back because elixir is already deducted here -- the same correction
        # _punish_window documents, or the test needs a 10-elixir lead and never fires.
        if self._punish_window(spend=float(self.specs[card_id].elixir)):
            return 0.0                                   # they cannot punish it: the real counterattack
        # DOES AN ANSWER EVEN EXIST? The identity vector can be LIT but ROLELESS -- every role flag
        # zero -- and then card_threat.counters matches nothing, so "no affordable answer" would be
        # true no matter how much elixir was left. MEASURED on a Giant + Musketeer push: exactly
        # that, because the Giant is not in observation.detector_cards (the labelling blind spot)
        # and a lone Musketeer lights no role. Charging there would blame the model for failing to
        # cast an answer the role table cannot name, so the term abstains instead.
        answers = [cid for cid in self._hand_ids()
                   if cid != card_id
                   and card_threat.counters(self._deck_profiles[cid], tid)
                   and self._counter_contribution(cid, committed) >= self.counter_min_share]
        if not answers:
            return 0.0                                   # no real answer was in hand to spend away
        left = float(self.eng.elixir[0])                 # POST-spend: what the defence has left
        if any(self.specs[cid].elixir <= left for cid in answers):
            return 0.0                                   # a real answer is still affordable
        return self.w_bow_overaggro

    def _counter_contribution(self, cid: int, committed) -> float:
        """How much of a push can this card actually remove -- as a fraction of the push's HP.

        "Affordable and the right role" is not "enough": Skeletons alone do not defend a real
        push, though they are a fine distraction alongside something that does (user, 2026-08-17).

        A FIRST VERSION OF THIS ASKED THE WRONG QUESTION -- whether the card survives a hit from
        the threat. Giant and Hog Rider are BUILDING-TARGETING and never swing at Skeletons at
        all, so that test was measuring an attack the push does not make. Skeletons dropped on a
        Giant simply DPS it, unharassed, for as long as the support lets them (user, same day).

        So it is measured as the user framed it -- distraction time and damage contributed:

          * only the units that can actually target TROOPS harass our counter; building-targeters
            are ignored, because they walk on by,
          * survival = our total HP / their combined DPS (unbounded when nothing can touch it),
          * the window is capped by how long the push takes to REACH the tower, since damage dealt
            after that did not defend anything,
          * contribution = our DPS x that time, over the push's total HP.

        Buildings and spells return 1.0: a building's job is to survive and pull, a spell's is its
        effect, and neither is described by this model. Whether they answer THIS threat at all is
        already decided by card_threat.counters.
        """
        spec = self.specs[cid]
        if spec.kind != "troop" or not committed:
            return 1.0
        hp = float(spec.hp or 0.0) * max(1, int(spec.count or 1))
        our_dps = (float(spec.hit_dmg or 0.0) / max(0.1, float(spec.hit_speed or 1.0))) \
            * max(1, int(spec.count or 1))
        if our_dps <= 0.0:
            return 0.0
        # WHO CAN ACTUALLY SHOOT BACK. A building-targeter ignores our troop entirely.
        incoming = sum(float(u.spec.hit_dmg or 0.0) / max(0.1, float(u.spec.hit_speed or 1.0))
                       for u in committed if not u.spec.building_only)
        survive = (hp / incoming) if incoming > 0.0 else float("inf")
        # ...and the clock the defence is actually racing: the push reaching our tower.
        deepest = max(committed, key=lambda u: u.y)
        gap_tiles = max(0.0, (0.80 - deepest.y) * 32.0)          # princess line sits at y ~0.797
        pace = max(0.4, float(getattr(deepest.spec, "speed", 0.0) or 0.8))
        window = gap_tiles / pace
        push_hp = sum(float(u.hp or 0.0) for u in committed) or 1.0
        share = (our_dps * min(survive, window)) / push_hp
        # A SLOW IS NOT DAMAGE, and scoring it as damage is why the first version of this rated the
        # Ice Wizard at 0.04-0.15 against every push -- effectively "never an answer", which would
        # have fired the over-aggression penalty whenever he was the only card left. He is the
        # deck's force multiplier: slow_mult 0.7 takes 30% off the whole push's output for as long
        # as it holds, which is worth about that share of removing it. Credited once, not per body,
        # since the slow does not stack with itself.
        if getattr(spec, "slows", False) and float(spec.slow_mult or 0.0) > 0.0:
            share += max(0.0, 1.0 - float(spec.slow_mult))
        return share

    def _xbow_into_push(self, card_id: int, nx: float, ny: float) -> float:
        """A FORWARD X-Bow dropped on top of a committed push. Six elixir that never fires.

        MEASURED (2026-08-16), the same board branched three ways over ~24 steps -- a Giant,
        Musketeer and Knight committed into our left lane at 10 elixir:

            bow ON the push      -25.56      leak -1.6, wincon_exec +0.42
            hold                 -29.15      leak -4.8
            bow OPPOSITE lane    -25.34      leak -1.6, wincon_exec +0.42

        So planting into the push beat holding by +3.59, and the CORRECT lane beat the wrong one
        by 0.22. Almost the entire gap is `leak`: sitting at capacity bleeds -0.2 a step and
        playing anything stops it, so the 6-elixir bow was simply the biggest leak-stopper in
        hand. threat_miss_idle was -23.0 in all three branches -- identical -- so wasting the bow
        while the push killed us cost exactly what holding it did.

        The reward was therefore teaching "play something" at +3.2 and "play the right thing in
        the right place" at +/-0.4, about 8:1 the wrong way. That does not fade with training; it
        sharpens, because more training means more confidence in the DOMINANT signal.

        Deliberately not fixed by weakening `leak`, which exists for a good reason and would move
        every other decision at capacity. This prices the specific mistake instead.

        Not charged for a DEFENSIVE bow (behind ``xbow_front`` it IS the answer, a second pull
        building), nor when the nearby enemies are too slight to kill it -- a couple of Skeletons
        near a bow is not the failure this describes, so the same triage decides.
        """
        # FORWARD IS MEASURED FROM THE RIVER, not against xbow_front, and the difference is not
        # cosmetic: the reward sees the POST-CLAMP position, and the clamp pushes every legal
        # forward bow onto row 13 at y = 0.5625 -- already past xbow_front (0.56). Gating on that
        # threshold made this branch unreachable, so the term read 0.0 for exactly the placement
        # it exists to price. Caught because the fix did not change the measurement it was built
        # from. Rows 13-14 (2.0 and 3.3 tiles out) are the offensive lock attempt; row 15+ is the
        # defensive centre band the doctrine aims at.
        if card_id not in self.xbow_ids:
            return 0.0
        if (ny - 0.5) * 32.0 > self.bow_forward_tiles:
            return 0.0                                   # a defensive bow: it IS a pull building
        near = [u for u in self.eng.units
                if u.team == 1 and u.hp > 0 and u.spec.kind == "troop"
                and tile_dist(nx, ny, u.x, u.y) <= self.bow_push_radius]
        if not near:
            return 0.0
        cost = threat_value.group_ignore_frac(
            self.db, [u.spec.base for u in near], tower_level=self._tower_level_for_triage)
        if cost < threat_value.IGNORE_FRAC:
            return 0.0                                   # too slight to kill a bow
        return self.w_bow_into_push

    def _building_waste(self, card_id: int) -> float:
        """A defensive BUILDING spent with nothing to defend against.

        The reported failure (user, 2026-08-16): the model plants a Tesla in a good spot on an
        EMPTY board, its 30 s lifetime runs out, and the opponent's win condition then arrives
        with no building left to pull it. Nothing priced that -- spell_waste covers an empty
        cast, and there was no equivalent for a building, so an early Tesla was free.

        A building is not a spell: it keeps working for its whole lifetime, so this must not fire
        merely because the board is quiet THIS INSTANT. It fires when the board is quiet *and*
        the opponent still holds a win condition we would want the building for -- i.e. exactly
        the case where holding it is strictly better than spending it.

        The X-Bow is excluded by the siege flag: it is a building by kind, but it is our win
        condition, and planting it on a quiet board is the correct play, not a waste.
        """
        spec = self.specs[card_id]
        if spec.kind != "building" or spec.siege:
            return 0.0
        committed = [u for u in self.eng.units
                     if u.team == 1 and u.hp > 0 and u.spec.kind != "spell" and u.y > 0.42]
        if committed and threat_value.group_ignore_frac(
                self.db, [u.spec.base for u in committed],
                tower_level=self._tower_level_for_triage) >= threat_value.IGNORE_FRAC:
            return 0.0                                   # a real threat is here: this is its job
        # Quiet board. Only a waste if they still have a win condition to bring.
        if not self._opp_holds_wincon():
            return 0.0
        return self.w_building_waste

    def _opp_holds_wincon(self) -> bool:
        """Does the opponent's deck contain a win condition that is not currently on the board?

        That is the thing a defensive building is being SAVED for. If their win condition is
        already committed, the building is answering it and nothing here applies.
        """
        onboard = {u.spec.base for u in self.eng.units if u.team == 1 and u.hp > 0}
        for base in (getattr(self.opponent, "cards", None) or []):
            if base in onboard:
                continue
            if card_threat.profile(self.db, str(base)).win_condition:
                return True
        return False

    def _spell_no_target(self, nx: float, ny: float, spec) -> bool:
        """True when a DAMAGE spell is cast with NOTHING to hit -- no enemy unit within its blast radius AND
        not aimed at a live enemy princess tower (chipping a tower is a valid target). A SOFT nudge against
        casting into emptiness; env.spell_waste_radius is GENEROUS so near-miss / predictive casts aren't
        punished -- only truly empty ones. A PULL spell (Tornado) is different on both counts: a tower is
        NOT a valid target for it (crown chip ~35 -- its whole value is pulling UNITS), and its effective
        reach is the wide pull radius, so 'has a target' uses that."""
        if not spec.pulls:
            for t in self.eng.towers[1][:2]:
                if t.alive and tile_dist(nx, ny, t.x, t.y) <= self.spell_aim_radius:
                    return False                         # aimed at an enemy princess tower = a valid chip target
        rad = max(self.spell_waste_radius, spec.pull_radius) if spec.pulls else self.spell_waste_radius
        return not any(u.team == 1 and u.hp > 0 and tile_dist(nx, ny, u.x, u.y) <= rad
                       for u in self.eng.units)

    def _chip_progress(self, towers) -> float:
        """Convex chip 'progress' over a side's princess towers: sum of (damage_fraction ** chip_power) so
        PARTIAL chip is worth sub-proportionally LESS than finishing the tower. Most of a tower's value is
        the CROWN (take/lose), so the reward JUMPS when the tower is actually destroyed -- a tower at 1-2 HP
        still fully works, so it's worth far less than one at 0."""
        prog = 0.0
        for t in towers[:2]:
            if t.max_hp > 0:
                d = max(0.0, min(1.0, 1.0 - t.hp / t.max_hp))
                prog += d ** self.chip_power
        return prog

    def _register_nado(self, nx: float, ny: float, spec) -> None:
        """Record a just-cast agent tornado so its EXECUTION can be credited once the pull has
        played out: which enemies it can catch, whether the king was still asleep, and which
        enemy building-targeters were tower-locked at cast time (retarget candidates)."""
        pulled = [u for u in self.eng.units
                  if u.team == 1 and u.hp > 0
                  and tile_dist(u.x, u.y, nx, ny) <= spec.pull_radius]
        targeters = []
        for u in pulled:
            if not u.spec.building_only:
                continue
            for tw in self.eng.towers[0]:
                if tw.alive and tile_dist(u.x, u.y, tw.x, tw.y) <= u.spec.reach + 1.0:
                    targeters.append((u, tw, float(tile_dist(u.x, u.y, tw.x, tw.y))))
                    break
        self._nado_watch.append({
            "t0": self.eng.t, "cx": nx, "cy": ny,
            "pulled": pulled, "targeters": targeters,
            "pulled_at": [(u.x, u.y) for u in pulled],   # cast positions, for the bad-pull check
            "king_was_asleep": not self.eng.towers[0][2].active,
            "early_done": False,
        })

    def _nado_shaping(self) -> float:
        """Delayed tornado-execution credit, from engine ground truth. At ~2s after the cast:
        CLUMP (enemies actually gathered at the centre) + RETARGET (a tower-locked wincon dragged
        off the tower). At ~3.5s: COMBO (>=2 pulled enemies died -- the splash/rocket payoff) +
        KING ACTIVATION (a pull woke your sleeping king; once per match). Positive-only and inside
        the correctness cap, so it shapes exploration without becoming farmable."""
        credit = 0.0
        keep = []
        for w in self._nado_watch:
            age = self.eng.t - w["t0"]
            if age >= 2.0 and not w["early_done"]:
                w["early_done"] = True
                alive_close = [u for u in w["pulled"]
                               if u.hp > 0 and tile_dist(u.x, u.y, w["cx"], w["cy"]) <= 2.2]
                if len(alive_close) >= 2:
                    credit += self.w_nado_clump * (min(len(alive_close), 4) - 1)
                for u, tw, d0 in w["targeters"]:
                    if u.hp > 0 and tile_dist(u.x, u.y, tw.x, tw.y) >= d0 + 1.6:
                        credit += self.w_nado_retarget
                        break                                    # one retarget credit per cast
            if age >= 3.5:
                dead = sum(1 for u in w["pulled"] if u.hp <= 0)
                king_hit = (w["king_was_asleep"] and not self._nado_king_credited
                            and self.eng.towers[0][2].active
                            and any(tile_dist(u.x, u.y, self.eng.towers[0][2].x,
                                              self.eng.towers[0][2].y) <= self.eng.king_range + 1.0
                                    for u in w["pulled"]))
                if dead >= 2:
                    credit += self.w_nado_combo
                if king_hit:
                    credit += self.w_nado_king
                    self._nado_king_credited = True
                if dead < 2 and not king_hit:
                    # THE BAD PULL: nothing died, no activation -- did the cast leave survivors
                    # CLOSER to our princess towers than where it found them? Doctrine's good
                    # pulls all cash out inside this window (clump kill, king wake, retarget was
                    # credited at 2 s); a pull that only relocated the push toward us made the
                    # enemy's walk shorter for 3 elixir. Mean over survivors, gated at 1 tile so
                    # incidental drift is free.
                    mine = [t for t in self.eng.towers[0][:2] if getattr(t, "hp", 0) > 0]
                    gains = []
                    for u, (x0, y0) in zip(w["pulled"], w.get("pulled_at", ())):
                        if u.hp <= 0 or not mine:
                            continue
                        d_then = min(tile_dist(x0, y0, t.x, t.y) for t in mine)
                        d_now = min(tile_dist(u.x, u.y, t.x, t.y) for t in mine)
                        gains.append(d_then - d_now)
                    if gains and (sum(gains) / len(gains)) >= 1.0:
                        credit += self.rw_stats.add("nado_bad", self.w_nado_bad)
                continue                                         # fully evaluated -> drop
            keep.append(w)
        self._nado_watch = keep
        return credit

    def step(self, action: Action):
        play, card_id, cell = action
        reward = 0.0
        placed_id = -1
        if play and 0 <= card_id < self.n_cards and card_id in self._hand_ids():
            spec = self.specs[card_id]
            cell = self.actions.deploy_clamp(card_id in self.anywhere_ids, cell)
            nx, ny = self.actions.cell_center(cell % self.gw, cell // self.gw)
            # Read BEFORE deploy so a just-placed X-Bow cannot gate its own wincon credit
            # (the repeat-credit gate in _wincon_exec keys off this flag).
            self._ally_xbow_standing = any(
                u.team == 0 and u.spec.base == "x_bow" and u.hp > 0 for u in self.eng.units)
            if self.eng.deploy(0, spec, nx, ny,
                               delay_s=self.action_latency):   # affordable + placed (lands when the live tap would)
                placed_id = card_id
                reward += self.rw_stats.add("threat_response", self._bonus(self._threat_response(card_id, nx, ny)))   # (1) counter to the assessed threat
                reward += self.rw_stats.add("wincon_exec", self._bonus(self._wincon_exec(card_id, nx, ny)))           # (3) win-condition executed right
                if card_id in self.damage_spell_ids:
                    # trade ledger: enemy deaths near this cast within 3 s credit as OUR kill
                    self._ev_spells.append((nx, ny, float(spec.spell_radius or 2.0), self.eng.t))
                if card_id in self.damage_spell_ids and self._spell_no_target(nx, ny, spec):
                    reward += self.rw_stats.add("spell_waste", self.w_spell_waste)                                    # (soft) damage spell cast into emptiness
                reward += self.rw_stats.add("building_waste", self._building_waste(card_id))   # a Tesla spent on a quiet board while their wincon is still in hand
                reward += self.rw_stats.add("xbow_into_push",
                                            self._xbow_into_push(card_id, nx, ny))   # a forward bow dropped onto a committed push
                reward += self.rw_stats.add("xbow_overaggression",
                                            self._xbow_overaggression(card_id, nx, ny))
                if spec.kind == "spell" and getattr(spec, "pulls", False):
                    self._register_nado(nx, ny, spec)           # tornado: watch the pull -> delayed execution credit
                self._cf_open()             # ...and fork the alternative branch where we HELD this card
                self._play_slot(card_id)                        # bank/spend the Evo charge + cycle the slot back
        else:
            reward += self.rw_stats.add("threat_miss_idle", self._threat_miss_idle())   # (1) ignored an ANSWERABLE threat
        # opponent acts, then advance the match by agent_dt in sub-ticks
        self.opponent.act(self.eng)
        chip0 = chip1 = 0.0
        steps = max(1, int(round(self.agent_dt / self.sub_dt)))
        for _ in range(steps):
            self.eng.advance(self.sub_dt)
            chip0 += self.eng.chip[0]
            chip1 += self.eng.chip[1]
            if self.on_tick is not None:
                self.on_tick(self)
            if self.eng.done:
                break
        # (2) ELIXIR-TRADE correctness: the step's change in the two-sided RESOURCE BALANCE (both
        # boards + both elixir bars), so committing elixir is neutral and only its consequence scores.
        reward += self.rw_stats.add("elixir_trade", self._trade_reward())
        reward += self.rw_stats.add("nado", self._bonus(self._nado_shaping()))    # delayed tornado-execution credit
        reward += self.rw_stats.add("counterfactual", self._cf_shaping())   # did playing beat holding? (zero-mean)
        # X-BOW LEDGER (see __init__): uptime ticks while TOWER-LOCKED, one-shot overcommit
        # credit when a bow dies, and the enemy-cards-seen set the context modifiers read.
        bow_alive = set()
        for u in self.eng.units:
            if u.team == 1 and u.hp > 0:
                self._enemy_seen.add(u.spec.key)
                continue
            if u.team != 0 or u.spec.base != "x_bow" or u.hp <= 0:
                continue
            bid = id(u)
            bow_alive.add(bid)
            led = self._bow_ledger.setdefault(bid, {"ids": set(), "cost": 0.0, "lock": 0.0})
            for e in self.eng.units:                      # enemies the opponent SPENT to answer this bow
                # `e.age < u.age` = deployed AFTER the bow. Without it the term counted any enemy
                # whose current target happened to be the bow, which is not the same thing at all:
                # drop a bow into a push that is already committed and every body in it retargets,
                # so the whole push's elixir booked as "drawn to answer the bow", the bow died, and
                # the overcommit credit paid out. That rewarded planting bows on top of big pushes
                # -- exactly the behaviour seen in sim view (user, 2026-08-16) -- and it is the one
                # X-Bow habit no amount of further training would unlearn, because the gradient
                # pointed at it. Troops already on the board were paid for before the bow existed.
                # `<=`, not `<`: an answer deployed in the SAME tick as the bow is still an answer
                # (and the opponent model can act on the step the bow lands), so only a body that
                # is strictly OLDER than the bow -- i.e. already marching before it existed --
                # is excluded.
                if (e.team == 1 and e.hp > 0 and e.target is u and id(e) not in led["ids"]
                        and e.age <= u.age):
                    led["ids"].add(id(e))
                    led["cost"] += float(e.spec.elixir) / max(1, e.spec.squad_count or e.spec.count)
            if (u.deploy_left <= 0.0 and u.attacking and hasattr(u.target, "king")
                    and led["lock"] < self.bow_lock_cap):
                tick = min(self.w_bow_lock * self.agent_dt, self.bow_lock_cap - led["lock"])
                led["lock"] += tick
                reward += self.rw_stats.add("xbow_lock", tick)
        for bid in [b for b in self._bow_ledger if b not in bow_alive]:
            led = self._bow_ledger.pop(bid)
            over = max(0.0, led["cost"] - 6.0)            # "they paid more than the bow to stop it"
            if over > 0.0:
                reward += self.rw_stats.add("xbow_overcommit",
                                            min(self.bow_over_cap, over * self.w_bow_over))
        # (5) leak: sitting at capacity with nothing played this step wastes elixir.
        if placed_id < 0 and self.eng.elixir[0] >= 9.99:
            reward += self.rw_stats.add("leak", self.w_leak)
        self.rw_stats.step(placed_id >= 0)
        # OFFENSIVE -> DEFENSIVE phase (icebow): once you've TAKEN a tower (defend the lead), OR OVERTIME
        # arrives and the X-Bow never broke through (cumulative enemy chip < xbow_success_frac of a tower),
        # flip to defence -- rocket-cycle becomes the tower damage; the X-Bow reward moves to back-centre.
        my_c, op_c = self.eng.crowns(0), self.eng.crowns(1)
        self._enemy_chip_total += chip0
        if not self._defensive and (
                my_c >= 1
                or (self.eng.t >= self._double_time
                    and self._enemy_chip_total < self.eng.towers[1][0].max_hp * self.xbow_success_frac)):
            self._defensive = True
        # --- OUTCOME compass (DEMOTED: winning is not the objective, just a faint direction) ---
        # CONVEX tower-chip proxy: partial chip is worth sub-proportionally little; the CROWN below is the
        # big JUMP when a tower is actually destroyed (a tower at 1-2 HP still works -> worth far less).
        ep = self._chip_progress(self.eng.towers[1])
        reward += self.rw_stats.add("chip_offence", (ep - self._prev_chip_prog) * self.tower_chip_scale)
        self._prev_chip_prog = ep
        if bow_alive and chip0 > 0.0:
            # LINEAR bow-chip lane: while a bow stands, its DoT is the deck's entire plan -- the
            # convex pool above (power 2, crown-weighted) pays a bow's typical 20-30% chip
            # ~ +0.01-0.03 total, i.e. nothing. Full-tower equivalent here = w_bow_chip.
            reward += self.rw_stats.add(
                "chip_linear", self.w_bow_chip * chip0 / max(1.0, self.eng.towers[1][0].max_hp))
        mp = self._chip_progress(self.eng.towers[0])
        reward -= self.rw_stats.add("chip_defence", (mp - self._prev_chip_prog_def) * self.tower_chip_scale)
        self._prev_chip_prog_def = mp
        if my_c > self._prev_my_crowns:
            reward += self.rw_stats.add("take_enemy_tower", self.w_take * (my_c - self._prev_my_crowns))
        if op_c > self._prev_op_crowns:
            reward += self.rw_stats.add("lose_own_tower", self.w_lose * (op_c - self._prev_op_crowns))
        self._prev_my_crowns, self._prev_op_crowns = my_c, op_c
        done = self.eng.done
        outcome = self.eng.outcome
        if done:
            reward += self.rw_stats.add(
                "outcome", self.w_win if outcome == "win" else self.w_loss if outcome == "loss" else 0.0)
            self.rw_stats.matches += 1
        self._update_vectors()
        info = {"outcome": outcome, "crowns": (my_c, op_c), "defensive": self._defensive}
        return self._last_obs, float(reward), done, info
