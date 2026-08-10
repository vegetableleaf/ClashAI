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
from .. import interactions
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
    return ActionSpace(_BoardCfg(cfg, {
        ("action", "arena_box"): [0.0, 0.0, 1.0, 1.0],
        ("action", "deploy_top"): float(b.get("deploy_top", 0.5)),   # the river
        ("env", "my_towers"): [[pt[0] / tx, py], [(tx - pt[0]) / tx, py], [kt[0] / tx, ky]],
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
        self.obs_shape = (int(oh), int(ow), 3)
        # Stage 3: identity-grounded threat block (KB roles of RECOGNISED enemy cards). When on, the
        # threat vector grows by card_threat.IDENTITY_DIM; the sim reads it from GROUND TRUTH but only
        # for whitelisted cards, so it mimics the live detector's (partial) recognition coverage.
        self.use_detector = bool(cfg.get("observation", "use_detector", default=False))
        self.detector_cards = set(cfg.get("observation", "detector_cards", default=[]))
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
        self.w_cycle_plan = r("cycle_plan", 0.4)             # cheap play advancing toward a NEEDED upcoming counter
        self.w_cycle_waste = r("cycle_waste", -0.4)          # purposeless cheap spam
        self.w_leak = r("leak_penalty", -0.2)                # sitting at elixir capacity, leaking
        self.correctness_cap = r("correctness_cap", 8.0)     # per-match cap on POSITIVE shaping (anti-farm)
        # OUTCOME compass -- DEMOTED so correctness dominates (winning is not the objective).
        self.w_win = r("win", 2.0); self.w_loss = r("loss", -2.0)
        self.w_take = r("take_enemy_tower", 1.0); self.w_lose = r("lose_own_tower", -1.0)   # the CROWN jump on a take/loss
        self.tower_chip_scale = r("tower_chip_scale", 0.3)   # convex chip POOL per tower (small; the crown is the jump)
        self.chip_power = float(cfg.get("env", "tower_chip_power", default=2.0))   # >1 -> partial chip sub-proportional
        # --- doctrine GEOMETRY (kept: the win-condition / counter checks the correctness terms use) ---
        self.combo_mult = float(cfg.get("rewards", "rocket_combo_mult", default=3.0))   # rocket 2-for-1 = wincon_exec x this
        self.intercept_lane = float(cfg.get("env", "intercept_lane", default=0.15))     # same-lane tolerance for an intercept
        self.cycle_cheap_max = int(cfg.get("env", "cycle_cheap_max", default=3))        # <= this elixir counts as a 'cycle' card
        self.cycle_spare_elixir = float(cfg.get("env", "cycle_spare_elixir", default=7.0))
        self.quiet_board_free_elixir = float(cfg.get("env", "quiet_board_free_elixir", default=8.0))
        self.punish_opp_elixir = float(cfg.get("env", "punish_opp_elixir", default=4.0))
        self.punish_elixir_gap = float(cfg.get("env", "punish_elixir_gap", default=4.0))
        self.punish_blocker_min_hp = float(cfg.get("env", "punish_blocker_min_hp", default=600.0))
        self.xbow_punish_mult = float(cfg.get("rewards", "xbow_punish_mult", default=1.5))
        self.value_norm = float(cfg.get("env", "value_norm", default=10.0))             # elixir-value normaliser for the trade term
        self.trade_cap = float(cfg.get("env", "trade_cap", default=1.0))                # per-step clip on the trade term
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
        self.rocket_ids = {i for i, k in enumerate(self.deck_keys) if _base(k) == "rocket"}
        self.xbow_success_frac = float(cfg.get("env", "xbow_success_frac", default=0.30))
        self.rocket_combo_hp_frac = float(cfg.get("env", "rocket_combo_hp_frac", default=1.5))  # support ~one-shot
        self.rocket_combo_radius = float(cfg.get("sim", "rocket_combo_tiles", default=3.5))   # support near the aimed tower
        self.pump_window = float(cfg.get("env", "pump_rocket_window_s", default=12.0))  # rocket the pump within this of its deploy
        self._rocket_dmg = float(self.specs[next(iter(self.rocket_ids))].spell_dmg) if self.rocket_ids else 0.0
        self.spell_aim_radius = float(cfg.get("sim", "spell_tower_aim_tiles", default=3.8))
        # (soft) discourage a DAMAGE spell cast into emptiness (no unit in its blast + not aimed at a tower)
        self.damage_spell_ids = {i for i in range(self.n_cards)
                                 if self.specs[i].kind == "spell" and self.specs[i].spell_dmg > 0.0}
        self.w_spell_waste = r("spell_waste", -0.3)
        self.spell_waste_radius = float(cfg.get("sim", "spell_waste_tiles", default=4.5))
        # TORNADO execution shaping (positive-only, soft, inside the correctness cap): the pull's value
        # is COMPOSITE + DELAYED (clump -> splash/rocket, king activation, dragging a wincon off a
        # tower), which plain outcome terms barely see -- so a WELL-EXECUTED pull is credited by its
        # MECHANICAL effect, measured from engine ground truth a couple of steps after the cast.
        # n_step >= 3 carries the delayed credit back to the cast action.
        self.w_nado_clump = r("nado_clump", 0.25)          # per extra enemy clumped at the vortex centre
        self.w_nado_combo = r("nado_combo", 0.6)           # >=2 pulled enemies dead shortly after (splash/rocket payoff)
        self.w_nado_king = r("nado_king_activate", 0.5)    # pull activated your sleeping king (once/match)
        self.w_nado_retarget = r("nado_retarget", 0.4)     # dragged a tower-locked wincon off your tower
        self._double_time = float(cfg.get("sim", "regulation_s", default=180.0)) - 60.0  # 2x elixir start
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
            view.apply_detector_noise(view.identity_items(self.eng, 0, self.detector_cards),
                                      self.det_recall, self.det_precision, self.rng, self.detector_cards,
                                      self.det_recall_by_card),
            self.db, prev_depth=self._prev_ident_depth, dt=self.agent_dt, horizon=self.predict_horizon)
        self._prev_ident_depth = float(self._threat_id[7])
        # ...and the un-noised twin the REWARD grades against (never enters the observation).
        self._threat_id_true = card_threat.identity_threat_vector(
            view.identity_items(self.eng, 0, self.detector_cards),
            self.db, prev_depth=self._prev_ident_depth_true, dt=self.agent_dt,
            horizon=self.predict_horizon)
        self._prev_ident_depth_true = float(self._threat_id_true[7])
        mem = self._opp_mem.update(
            view.apply_detector_noise(view.opponent_memory_items(self.eng, 0, self.detector_cards),
                                      self.det_recall, self.det_precision, self.rng, self.detector_cards,
                                      self.det_recall_by_card), dt=self.agent_dt)
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
        return view.render_obs(self.eng, oh, ow, team=0, dr=self.domain_rand)

    # -- lifecycle ---------------------------------------------------------
    def reset(self) -> np.ndarray:
        self.eng.reset()
        self.domain_rand.resample()      # a new 'arena look' each match (stable within the match)
        self.opponent = (self.opponent_provider(self) if self.opponent_provider is not None
                         else make_opponent(self.cfg, self.db, self.rng, self.meta_pool))
        self.cycle = list(range(self.n_slots))
        self.rng.shuffle(self.cycle)
        self.evo_charge = [0] * self.n_slots     # match starts with every Evolution UNCHARGED
        self._match_bonus = 0.0
        self._cf_used = 0                # counterfactual fork budget is PER MATCH
        self._cf_watch = []              # ...and no fork may outlive the match that opened it
        self._prev_trade_pot = self._trade_potential(self.eng)   # two-sided resource balance (starts level)
        self._prev_chip_prog = 0.0       # convex enemy-tower chip progress (offense)
        self._prev_chip_prog_def = 0.0   # convex own-tower chip progress (defense)
        self._prev_my_crowns = 0
        self._prev_op_crowns = 0
        self._defensive = False          # icebow phase: False = offensive X-Bow win-condition; True = defence + rocket-cycle
        self._enemy_chip_total = 0.0     # cumulative enemy-tower HP the X-Bow/rocket has chipped (X-Bow success gauge)
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
        self._nado_watch = []            # in-flight tornado casts awaiting their delayed execution credit
        self._nado_king_credited = False
        self._reset_vectors()
        self._update_vectors()
        return self._last_obs

    def _bonus(self, credit: float) -> float:
        """Cap the POSITIVE correctness shaping per match (anti-farm); penalties pass through uncapped."""
        if credit <= 0.0:
            return credit
        allowed = min(credit, max(0.0, self.correctness_cap - self._match_bonus))
        self._match_bonus += allowed
        return allowed

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
            return self.w_threat_response if card_threat.counters(prof, tid) else 0.0
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
            return self.w_threat_response if intercept else 0.0          # right counter; full only if it intercepts
        return self.w_threat_miss if intercept else 0.0                  # wrong role dropped as a defence = a misread

    def _threat_miss_idle(self) -> float:
        """No play while an ANSWERABLE threat is present (a counter is in hand AND affordable) = a missed
        defence. Uncapped penalty (this is the 'ignored the push' case the old idle_penalty covered).
        Ground-truth threat: the objective is defined by the real board, not by what the detector saw."""
        tid = self._threat_id_true
        if tid is None or len(tid) < card_threat.IDENTITY_DIM or tid[0] < 0.5:
            return 0.0
        for cid in self._hand_ids():
            if (card_threat.counters(self._deck_profiles[cid], tid)
                    and self.specs[cid].elixir <= self.eng.elixir[0]):
                return self.w_threat_miss
        return 0.0

    def _punish_window(self, spend: float = 0.0) -> bool:
        """The opponent has overcommitted and cannot answer a siege before it starts firing. A forward
        X-Bow is a 6-elixir bet that is simply BLANKED by any 3-5 elixir tank or mini-tank, so the bar
        is not a flat number: it is whether they can still afford their own CHEAPEST BLOCKER
        (_opp_block_cost, from their actual deck). Reward-side only -- it reads the opponent's TRUE
        elixir, which the policy cannot observe (see the observability note on _leaking_first).
        ``spend`` is added back for the same pre-spend reason: an X-Bow costs 6, so measured POST-spend
        this needed a 10-elixir lead and fired EXACTLY ZERO times in 162 X-Bow plays."""
        mine = self.eng.elixir[0] + spend
        return (self.eng.elixir[1] < self._opp_block_cost
                and mine - self.eng.elixir[1] >= self.punish_elixir_gap)

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
            # PUNISH OVERRIDE, checked BEFORE the phase gate. An opponent who has just overcommitted
            # cannot answer a siege before it starts firing, and that is worth breaking defensive
            # posture for -- "immediately punish" is conditional on the ELIXIR RACE, not on the matchup
            # doctrine. Without this the clause was unreachable: _defensive is set on sight of a cycle
            # or beatdown deck (most of the meta pool), so MEASURED 145 of 152 X-Bow plays took the
            # defensive branch and only 5 were ever offensive AND in a punish window.
            if d <= self.xbow_range and self._punish_window(self.specs[card_id].elixir):
                return self.w_wincon * self.xbow_punish_mult
            if self._defensive:                              # DEFENSIVE phase: centre-band only; forward is wrong now
                return self.w_wincon * frac if frac > 0.0 else self.w_wincon_mis
            if d <= self.xbow_range:                          # OFFENSIVE: forward, in tower range = win condition set
                return self.w_wincon
            return self.w_wincon * 0.4 * frac if frac > 0.0 else self.w_wincon_mis
        if card_id in self.rocket_ids:
            pr = self._pump_rocket(nx, ny)                   # PUMP PUNISH: rocket the fresh elixir collector
            if pr != 0.0:
                return pr
            if self._rocket_combo(nx, ny):                   # rocket a princess tower + a valuable support = 2-for-1
                return self.w_wincon * self.combo_mult
            if self._defensive and d <= self.spell_aim_radius:
                return self.w_wincon * 0.6                   # rocket-cycle chip = sanctioned tower damage once defensive
            return 0.0
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

    def _needed_counter_coming(self, hand) -> bool:
        """True when the current hand has NO KB counter to the assessed threat but the deck DOES (an
        upcoming card) -- i.e. deliberately cycling toward that counter is worthwhile. Ground-truth
        threat (this feeds cycle_plan, a reward term)."""
        if (self._fresh_pump() is not None and not (set(hand) & self.rocket_ids)
                and any(r not in hand for r in self.rocket_ids)):
            return True                                      # a fresh enemy PUMP is a rocket job: cycle to it
        tid = self._threat_id_true
        if tid is None or len(tid) < card_threat.IDENTITY_DIM or tid[0] < 0.5:
            return False
        if any(card_threat.counters(self._deck_profiles[c], tid) for c in hand):
            return False                                     # already hold a counter -> no need to cycle
        return any(card_threat.counters(self._deck_profiles[c], tid)
                   for c in range(self.n_cards) if c not in hand)

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
        pot = self._trade_potential(self.eng)
        d = pot - self._prev_trade_pot
        self._prev_trade_pot = pot
        return float(np.clip(d, -self.trade_cap, self.trade_cap)) * self.w_elixir_trade

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
                if dead >= 2:
                    credit += self.w_nado_combo
                if (w["king_was_asleep"] and not self._nado_king_credited
                        and self.eng.towers[0][2].active
                        and any(tile_dist(u.x, u.y, self.eng.towers[0][2].x,
                                          self.eng.towers[0][2].y) <= self.eng.king_range + 1.0
                                for u in w["pulled"])):
                    credit += self.w_nado_king
                    self._nado_king_credited = True
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
            if self.eng.deploy(0, spec, nx, ny):               # affordable + placed
                placed_id = card_id
                reward += self._bonus(self._threat_response(card_id, nx, ny))   # (1) counter to the assessed threat
                reward += self._bonus(self._wincon_exec(card_id, nx, ny))       # (3) win-condition executed right
                if card_id in self.damage_spell_ids and self._spell_no_target(nx, ny, spec):
                    reward += self.w_spell_waste                                 # (soft) damage spell cast into emptiness
                if spec.kind == "spell" and getattr(spec, "pulls", False):
                    self._register_nado(nx, ny, spec)           # tornado: watch the pull -> delayed execution credit
                self._cf_open()             # ...and fork the alternative branch where we HELD this card
                self._play_slot(card_id)                        # bank/spend the Evo charge + cycle the slot back
        else:
            reward += self._threat_miss_idle()                 # (1) ignored an ANSWERABLE threat (uncapped penalty)
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
        reward += self._trade_reward()
        reward += self._bonus(self._nado_shaping())    # delayed tornado-execution credit (clump/combo/king/retarget)
        reward += self._cf_shaping()   # delayed counterfactual: did playing beat holding? (uncapped: zero-mean)
        # (5) leak: sitting at capacity with nothing played this step wastes elixir.
        if placed_id < 0 and self.eng.elixir[0] >= 9.99:
            reward += self.w_leak
        # OFFENSIVE -> DEFENSIVE phase (icebow): once you've TAKEN a tower (defend the lead), OR double elixir
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
        reward += (ep - self._prev_chip_prog) * self.tower_chip_scale
        self._prev_chip_prog = ep
        mp = self._chip_progress(self.eng.towers[0])
        reward -= (mp - self._prev_chip_prog_def) * self.tower_chip_scale
        self._prev_chip_prog_def = mp
        if my_c > self._prev_my_crowns:
            reward += self.w_take * (my_c - self._prev_my_crowns)
        if op_c > self._prev_op_crowns:
            reward += self.w_lose * (op_c - self._prev_op_crowns)
        self._prev_my_crowns, self._prev_op_crowns = my_c, op_c
        done = self.eng.done
        outcome = self.eng.outcome
        if done:
            reward += self.w_win if outcome == "win" else self.w_loss if outcome == "loss" else 0.0
        self._update_vectors()
        info = {"outcome": outcome, "crowns": (my_c, op_c), "defensive": self._defensive}
        return self._last_obs, float(reward), done, info
