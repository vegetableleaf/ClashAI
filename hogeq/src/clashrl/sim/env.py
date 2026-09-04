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
import math
import random
from dataclasses import replace
from typing import Tuple

import numpy as np

from ..actions import ActionSpace
from ..cards import shared as shared_db
from .. import card_threat
from .. import detect_obs
from .. import interactions
from .. import threat_value
from ..cycle import cycle_vector
from .engine import SimEngine, build_spec, tile_dist, _ROCKET_RADIUS, _TILES_X, _TILES_Y
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
        # ...and the three LIVE-SCREEN safety constants, which `cell_center` applies to whatever
        # space it happens to be in. `label.arena_top/arena_bottom` keep a TAP off the card tray and
        # `buttons.chat_avoid_box` keeps it off the emote icon: both are screen furniture, neither
        # exists on the board, and leaving them at their live values CLAMPED THE SIM'S OWN ACTION
        # SPACE. MEASURED 2026-08-27, both decks, 18x24 = 432 cells:
        #   * 96 cells (22.2%) deployed somewhere other than their own board centre, the worst by
        #     6.37 tiles (grid row 23, left columns);
        #   * only 372 DISTINCT deploy points existed, so 60 cells were exact duplicates of another
        #     cell -- five different grid rows all deploying to tile (0.50, 24.96);
        #   * board tile-y outside 3.20 .. 27.52 was UNREACHABLE (the arena is 0..32), which put all
        #     36 cells of grid rows 0-1 within 0.2 tiles of the ENEMY KING's row at tile-y 3.0;
        #   * the emote-icon box alone displaced 15 cells, in front of our own left princess.
        # And they were never doing their job anyway: in the LIVE ActionSpace the same three clamps
        # fire on 0 of 432 cells, because the warped grid already lands inside them. So they were
        # inert where they belong and mangling a fifth of the action space where they do not.
        # This is the mirror image of the section 4.2 trap -- not an offline tool reading live
        # coordinates, but a live-screen constant applied to the board.
        ("label", "arena_top"): 0.0,
        ("label", "arena_bottom"): 1.0,
        ("buttons", "chat_avoid_box"): None,
    }))


# How many casts of one spell count as "this tower is finishable" for the veto's endgame
# exemption. DOCTRINE_RESEARCH §3.4: "3-4 EQ casts finish a low tower in x2", and the deck
# page's own switch point is an enemy tower at <=773 HP.
_TOWER_FINISH_CASTS = 3.0


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
        # CHAMPION ABILITY AS A PSEUDO-CARD. The action space is (wait/play, card, cell) and an
        # ability is none of those: it costs elixir and it is a decision, but it has no placement --
        # it acts on the champion wherever he already stands. Giving it its own identity slot is the
        # smallest change that makes it LEARNABLE: it reuses the card head, the affordability mask
        # and the gate exactly as they are, and its cell is simply ignored.
        #
        # It is NOT in the cycle. `slot_of` has no entry for it, so _play_slot no-ops and the ability
        # neither consumes a hand slot nor rotates the deck -- which is the real behaviour, and also
        # why availability has to be computed rather than dealt (see _hand_ids).
        #
        # The `_ability` suffix is the taxonomy's existing one (card_threat._SUFFIXES), so the key
        # folds back to the champion for every threat/profile lookup without special-casing.
        self.ability_id = -1
        self.ability_champ_id = -1
        _ability_key = self.db.ability_identity()       # the SHARED definition -- live vision uses it too
        _champ = next((i for i, s in enumerate(self.specs) if s.ability_bomb_dmg > 0.0), None)
        if _ability_key is not None and _champ is not None:
            self.ability_champ_id = _champ
            self.ability_id = len(self.deck_keys)
            self.deck_keys = list(self.deck_keys) + [_ability_key]
            self.deck_card_levels = list(self.deck_card_levels) + [self.deck_card_levels[_champ]]
            # Its elixir IS the ability's cost, so every affordability check already works on it.
            self.specs = list(self.specs) + [replace(self.specs[_champ],
                                                     elixir=self.specs[_champ].ability_cost)]
            self.n_cards = len(self.deck_keys)
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
        self.lock_aware_targets = bool(cfg.get("observation", "lock_aware_targets", default=False))
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
        # EVERY SPELL GOES ANYWHERE -- that is the actual Clash Royale rule, and the old literal
        # {rocket, miner} broke it for every other spell in both decks. Measured before the fix: a
        # Tornado aimed 8.4 tiles into the enemy half landed on our own front row instead, and
        # hogeq's Earthquake could not be put on an enemy building at all, which made the deck's
        # signature Hog+EQ combo an action the policy was incapable of taking. Miner (and Goblin
        # Drill) stay in on their own merit: deploy-anywhere TROOPS, not spells.
        #
        # ...WITH ONE EXCEPTION, and it is a KB flag rather than another literal so the next one is
        # data (RULING 18, owner 2026-08-27): Royal Delivery "can only be cast on the caster's half
        # of the map (and whatever pocket presents itself)". It is a spell that DROPS A TROOP, so
        # it is placed like a troop. Cards revid 437053 says the same independently: "spells ... can
        # be cast anywhere in the battlefield (with the exception of The Log, Barbarian Barrel, and
        # Royal Delivery)".
        # THE 2026-08 FIX ABOVE IS NOT BEING UNDONE. Only cards that carry `own_half_only` leave the
        # set; every genuine anywhere-spell (rocket, tornado, the log, earthquake, fireball, ...)
        # stays in it, and a test asserts exactly that so this cannot silently regress to the old
        # "every spell was forbidden from the enemy half" bug.
        self.own_half_spell_ids = {i for i in range(len(self.deck_keys))
                                   if self.specs[i].own_half_only}
        self.anywhere_ids = {i for i, k in enumerate(self.deck_keys)
                             if (self.specs[i].kind == "spell"
                                 or _base(k) in ("miner", "goblin_drill"))} - self.own_half_spell_ids
        self.miner_ids = {i for i, k in enumerate(self.deck_keys) if _base(k) == "miner"}
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
        # GRADING SEES EVERY CARD, not just the ones the detector can name. `detector_cards` is a
        # PERCEPTION whitelist (the live model's 26 classes) and belongs on the observation; using
        # it here made the referee blind to 153 of the DB's 179 cards, so no answer to a Minion
        # Horde, a Skeleton Army or a Battle Ram could ever be credited -- the identity vector came
        # back all zeros and `_threat_response` read the board as quiet.
        self._grade_cards = frozenset(self.db.cards.keys()) or self.detector_cards
        self._prev_ident_depth_true = 0.0
        self._opp_mem = card_threat.OpponentMemory(self.db)   # per-match opponent short-term memory (Stage 3)

        r = lambda k, d: float(cfg.get("rewards", k, default=d))  # noqa: E731
        # --- CORRECTNESS-FIRST reward weights (playing correctly > winning). ONE coherent score of a
        # few bounded sub-terms replaces the old ~40 patchwork rewards; see the reward assembly in step(). ---
        self.w_threat_response = r("threat_response", 1.0)   # right KB counter, placed to intercept an assessed threat
        self.w_threat_miss = r("threat_miss", -1.0)          # wrong counter / wrong lane / ignored an ANSWERABLE threat
        self.w_elixir_trade = r("elixir_trade", 1.0)         # (enemy value eliminated - elixir spent), normalised
        self.w_wincon = r("wincon_exec", 0.8)                # deck win-condition executed correctly for the phase
        self.w_wincon_mis = r("wincon_misplace", -0.6)
        # A RUSH win condition (Hog): bridge-only, never into a push, lane-aware. See _hog_wincon.
        self.hog_bridge_y = float(cfg.get("env", "hog_bridge_y", default=0.52))
        # FLOORED AT WHAT THE ACTION GRID CAN ACTUALLY REACH. Configured at 0.52 this threshold sat
        # in FRONT of the frontmost legal own-half row (0.5625 for an 18x24 grid), so `ny > thr`
        # was true for every cell the policy could play and EVERY legal Hog send scored -1.0 --
        # while the unit test passed because it calls the term at y=0.47, a cell deploy_clamp can
        # never produce. A reward threshold read against a coordinate must be expressed in the
        # coordinates the ACTION SPACE can produce, so the grid gets the final say here: the send
        # row plus a tile of slack, which is the bridge and one row behind it.
        _front_own = float(self.actions.cell_center(0, self.actions.min_own_gy)[1])
        self.hog_bridge_y = max(self.hog_bridge_y, _front_own + 1.0 / 32.0)
        self.hog_punish_mult = float(cfg.get("rewards", "hog_punish_mult", default=1.5))
        self.hog_support_mult = float(cfg.get("rewards", "hog_support_mult", default=1.0))
        # SUPPORT TROOPS: never played alone (see _support_alone). `support_targets` are the
        # committed pushes they may legitimately escort.
        self.support_bases = frozenset(cfg.get("sim", "support_cards", default=["firecracker"]) or ())
        self.support_targets = frozenset(cfg.get("sim", "support_targets",
                                                 default=["hog_rider", "mighty_miner"]) or ())       # win-condition card thrown away
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
        self._pending_spell_checks: list = []
        # OUTCOME compass -- DEMOTED so correctness dominates (winning is not the objective).
        self.w_win = r("win", 2.0); self.w_loss = r("loss", -2.0)
        self.w_take = r("take_enemy_tower", 1.0); self.w_lose = r("lose_own_tower", -1.0)   # the CROWN jump on a take/loss
        self.tower_chip_scale = r("tower_chip_scale", 0.3)   # convex chip POOL per tower (small; the crown is the jump)
        self.chip_power = float(cfg.get("env", "tower_chip_power", default=2.0))   # >1 -> partial chip sub-proportional
        # --- doctrine GEOMETRY (kept: the win-condition / counter checks the correctness terms use) ---
        self.intercept_lane = float(cfg.get("env", "intercept_lane", default=0.15))     # same-lane tolerance for an intercept
        self.quiet_board_free_elixir = float(cfg.get("env", "quiet_board_free_elixir", default=8.0))
        # Wincon-bank parameters, mirrored for the threat_miss_idle waiver (see that method): the
        # trainer's bank masks cheaper cards while the bar climbs to a held win condition's cost,
        # and a penalty must not charge the agent for a hold the sampler itself mandates.
        self._bank_floor = float(cfg.get("sim", "wincon_bank_floor", default=0.0))
        # WHICH CARDS ARE THE WIN CONDITION -- from config, not from hardcoded card names. This was
        # `xbow_ids | rocket_ids` in three separate places (here, policy_stats, train_sim_ppo), which
        # silently evaluates to the EMPTY SET for any deck that is not IceBow: every wincon term
        # (bank, exec credit, misplace penalty, the policy_stats wincon column) then goes quiet
        # rather than failing, so a new deck trains with its win condition unpriced and nothing says so.
        _wc_keys = cfg.get("sim", "wincon_cards", default=None)
        if _wc_keys:
            _want = {str(k).strip() for k in _wc_keys}
            self.wincon_ids = {i for i, k in enumerate(self.deck_keys) if _base(k) in _want}
            _missing = _want - {_base(k) for k in self.deck_keys}
            if _missing:
                raise ValueError("sim.wincon_cards names %s, which are not in the deck (%s)"
                                 % (sorted(_missing), ", ".join(sorted({_base(k) for k in self.deck_keys}))))
        else:   # I10: this was the IceBow derivation (x_bow | rocket), which is the EMPTY SET
            # for this deck -- exactly the silent trap the comment above describes. hogeq sets
            # sim.wincon_cards, so the fallback is unreachable and is now the error it should
            # always have been.
            raise ValueError("sim.wincon_cards is not set: this deck has no declared win "
                             "condition, so every wincon term would silently price nothing")
        self._bank_wincon_ids = set(self.wincon_ids)
        self._bank_wincon_cost = min((float(self.specs[i].elixir) for i in self.wincon_ids), default=0.0)
        # Tower level for the triage waiver in _threat_miss_idle (clashrl.threat_value).
        self._tower_level_for_triage = int(cfg.get("env", "my_tower_level", default=15) or 15)
        # CHAMPION ABILITY ledger (see _ability_value). Deliberately small: the ability's real payoff
        # is already priced by the elixir_trade term when the bomb kills something, so these only
        # have to make the ACTION discoverable and discourage burning it on an empty board.
        self.w_ability_value = r("ability_value", 3.0)
        self.w_ability_waste = r("ability_waste", -0.5)
        self.ability_value_cap = float(cfg.get("rewards", "ability_value_cap", default=1.0))
        self.punish_opp_elixir = float(cfg.get("env", "punish_opp_elixir", default=4.0))
        self.punish_elixir_gap = float(cfg.get("env", "punish_elixir_gap", default=4.0))
        self.punish_blocker_min_hp = float(cfg.get("env", "punish_blocker_min_hp", default=600.0))
        # FIX 6 (2026-08-25): the CHEAP ANSWER IN THE OTHER LANE. Scaled by that lane's own danger
        # relative to the primary's, so "cheapest sufficient answer" is priced rather than ruled.
        self.w_threat_2nd = r("threat_response_secondary", 1.0)
        # Share of a push a card must be able to remove to count as a real ANSWER rather
        # than support. See _counter_contribution.
        self.counter_min_share = float(cfg.get("sim", "counter_min_share", default=0.35))
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
        # FIX 7 (2026-08-25): scale the missed-defence penalty by what the ignored group actually
        # costs, instead of charging a flat -1.0 for anything above the triage threshold.
        self.threat_miss_proportional = bool(cfg.get("env", "threat_miss_proportional", default=True))
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
        # WIN-CONDITION SUCCESS GAUGE. Deck-neutral and LIVE for this deck: the overtime phase
        # switch at the end of step() reads it against our cumulative enemy-tower chip. The
        # config key keeps its historical `env.xbow_success_frac` name so no deck's tuning
        # file has to move; only the attribute is renamed off the X-Bow.
        self.wincon_success_frac = float(cfg.get("env", "xbow_success_frac", default=0.30))
        self.spell_aim_radius = float(cfg.get("sim", "spell_tower_aim_tiles", default=3.8))
        # (soft) discourage a DAMAGE spell cast into emptiness (no unit in its blast + not aimed at a tower)
        self.damage_spell_ids = {i for i in range(self.n_cards)
                                 if self.specs[i].kind == "spell" and self.specs[i].spell_dmg > 0.0}
        self.w_spell_waste = r("spell_waste", -0.3)
        # A defensive BUILDING spent on a quiet board while they still hold a win condition.
        # Same shape as spell_waste but for the card that has to still BE there later.
        self.w_building_waste = r("building_waste", -0.4)
        self.spell_waste_radius = float(cfg.get("sim", "spell_waste_tiles", default=4.5))
        # DAMAGE PREVENTED, priced in tower fractions by the triage model (see _settle_spell_casts).
        # Measured before this existed: a Log saving 35% of a Princess Tower was paid +0.285, while
        # a good offensive rocket earns +10 -- the policy was being told defending does not matter.
        self.w_spell_defence = r("spell_defence", 1.0)
        self.spell_defence_cap = float(cfg.get("rewards", "spell_defence_cap", default=1.5))
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

    def enemy_troop_min_age(self) -> float:
        """Seconds since the YOUNGEST living enemy TROOP was deployed; 1e9 with none on the board.
        The sim side of the gate prior's PRESSURE key (tools/gate_prior.py schema 2, HANDOFF 5bx):
        the pro table's key is "the opponent played a troop within W s", and `age` starts at 0 on
        deploy (deploy time included), so `min_age < W` is the same event. Spells and buildings do
        not count on either side. The threshold W lives in the parent (sim.ppo_gate_prior_pressure_s)
        so the worker carries the raw age and no config seam can open between the two."""
        ages = [float(u.age) for u in self.eng.units
                if u.team == 1 and u.hp > 0 and u.spec.kind == "troop"]
        return min(ages) if ages else 1e9

    def _hand_ids(self):
        ids = [self._slot_card_id(s) for s in self.cycle[:4]]
        # The ability is not dealt, it becomes AVAILABLE: the champion has to be alive on the board
        # and off cooldown. Appending it here is what puts it in hand_vec and past step()'s gate, so
        # availability is expressed in exactly one place and the policy sees it the same way it sees
        # a card it may play. A hand of five is correct -- the real UI shows four cards AND the
        # ability button.
        if self.ability_id >= 0 and self._ability_ready():
            ids.append(self.ability_id)
        return ids

    def _ability_ready(self) -> bool:
        """Champion of OURS alive on the board, with an activation left and no cooldown running.

        All three conditions have to be here and not only in the engine: this is what puts the
        ability in hand_vec, so a spent or bodiless ability that stayed 'in hand' would keep being
        offered to the policy as a legal action it can never actually take -- a permanently dead
        entry in the action space, and gradient spent on it every step.

        Single use (4/8/2026 balance) is counted per BODY, so a Mighty Miner who dies and is cycled
        back brings a fresh activation with him.
        """
        # RULING 5 (I7): the button belongs to the NEWEST living champion body, so the MASK has
        # to ask the same body the engine will act on. `any(...)` over every body would light the
        # slot up because an OLDER champion still had a use, the policy would spend the action,
        # and `champion_ability` would refuse it -- a legal-looking action that can never work.
        # `ability_kind` replaces the `ability_bomb_dmg > 0` truthiness test for the same reason
        # the engine dropped it: it is one card's number standing in for "has an ability".
        bodies = [u for u in self.eng.units
                  if u.team == 0 and u.hp > 0 and u.spec.ability_kind]
        if not bodies:
            return False
        newest = max(bodies, key=lambda u: u.deploy_seq)
        return newest.ability_cd_left <= 0.0 and self.eng._ability_uses_left(newest) > 0

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
            view.identity_items(self.eng, 0, self._grade_cards, self.identity_front),
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
            units, mine_t, en_t, hs = self._interaction_state()
            parts.append(interactions.interaction_vector(units, mine_t, en_t, self.db, hints=hs))
        if self.use_tower_obs:
            parts.append(view.tower_vector(self.eng, 0))
        return np.concatenate(parts).astype(np.float32)

    def _interaction_state(self):
        """(units, my_towers, enemy_towers, hints) for the interaction vector and the predictive
        canvas. ``hints`` is None unless ``observation.lock_aware_targets`` is on (HANDOFF §5cb):
        the LIVE side has no track memory today, so a sim obs built on engine lock state is a
        sim-to-real seam until live supplies the same hint -- default off."""
        st = view.interaction_state(self.eng, 0, self.detector_cards, self.rng, self.det_recall,
                                    self.det_recall_by_card, hints=self.lock_aware_targets)
        return st if len(st) == 4 else (*st, None)

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
            units, mine_t, en_t, hs = self._interaction_state()
            pred = detect_obs.predictive_channels(units, mine_t, en_t, self.db, oh, ow,
                                                  dt_s=self.pred_dt, horizon_s=self.pred_horizon,
                                                  hints=hs)
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
        # THE OPPONENT'S TOWER TROOP IS THE DECK'S, not a roll (I8). `support:` is MEASURED per
        # deck from top-ladder battlelogs (R4) and had been inert since it was imported -- parsed,
        # carried, validated and read by nobody, while `eng.reset()` rolled one from a config
        # weight table. It has to happen HERE rather than in reset(): the towers are built before
        # the opponent exists, so the roll stands as the fallback and this overrides it for the
        # 235 decks whose battlelog actually named one. A SelfPlayOpponent carries no deck entry
        # and keeps the roll.
        _sup = getattr(self.opponent, "support", None)
        if _sup:
            self.eng.set_tower_troop(1, _sup[0] if isinstance(_sup, (list, tuple)) else _sup)
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
        self._defensive = False          # phase: False = press the win condition; True = defend the lead
        self._enemy_chip_total = 0.0     # cumulative enemy-tower HP we have chipped (win-condition success gauge)
        self._ev_enemy, self._ev_own, self._ev_spells = {}, {}, []   # trade event ledger
        self._threat_credits = 0          # threat-response credits paid this episode (budgeted)
        self._pending_spell_checks = []   # damage-spell casts awaiting their impact verdict
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
        """(x, y) of the MOST DANGEROUS enemy troop on YOUR half; centre if none.

        ⚠ THIS USED TO RETURN THE DEEPEST UNIT, AND THAT WAS THE BUG (fixed 2026-08-25).
        `_threat_response` grades the CARD against `_threat_id_true`, which ranks by DANGER, and
        the PLACEMENT against this lane. While the two disagreed, the reward asked "did you play
        the right counter to the DANGEROUS threat, in the lane of the DEEPEST one?" -- and MEASURED
        on a pekka (ignore_cost_frac 1.907) shallow beside a skeletons trickle (0.004) deeper, a
        counter placed in the pekka's lane earned NOTHING while one placed in the trickle's lane
        earned full credit. The reward PAID to defend the wrong lane, so training reinforced it.

        The ranking here is character-for-character the one `identity_threat_vector` uses for its
        primary -- `max(key=(danger, depth))` -- so the two halves of `_threat_response` now
        describe the SAME unit BY CONSTRUCTION rather than by coincidence. That is the property
        that matters; a merely "better" heuristic here would leave the same class of bug open.

        DEPTH REMAINS THE TIE-BREAK on purpose: among equally dangerous bodies the deepest is the
        most urgent, which is the one case the old rule got right.
        """
        onside = [u for u in self.eng.units if u.team == 1 and u.spec.kind != "spell" and u.y >= 0.5]
        if not onside:
            return 0.5, 0.5

        def _danger(unit):
            try:
                return float(threat_value.ignore_cost_frac(self.db, unit.spec.base))
            except Exception:  # noqa: BLE001 -- an unpriced card is not automatically harmless,
                return 0.0     # but it must not outrank a card the KB actually prices either.

        u = max(onside, key=lambda unit: (_danger(unit), unit.y))
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
        # THE BUDGET IS THE SIZE OF THE THREAT, not a constant. A flat 2 is right for a push and
        # wrong for a lone Miner: it funded a SECOND credit for a second card thrown at a one-card
        # threat, so over-answering out-earned the cheapest sufficient answer -- measured on
        # skeletons_kill_the_miner, whose pass condition is "answered for <= 1.5 elixir", episodes
        # that failed by over-spending took +1.130 from this term against +0.556 for the ones that
        # passed. The cheapest sufficient answer is the tier above every counter rule, and this was
        # paying a premium to violate it.
        #
        # Counted in CARDS via the same collapse _threat_miss_idle triages with -- bodies are not
        # cards, and one Skeletons is nine bodies. Still capped by threat_credit_budget, so a real
        # two-card push funds exactly what it funded before.
        committed = [u for u in self.eng.units
                     if u.team == 1 and u.hp > 0 and u.spec.kind != "spell" and u.y > 0.42]
        n_cards = len(threat_value.cards_from_bodies(
            self.db, [u.spec.base for u in committed])) if committed else 1
        budget_ok = self._threat_credits < max(1, min(self.threat_credit_budget, n_cards))
        # ...AND NOTHING IS PAID FOR ANSWERING A THREAT THAT DID NOT NEED ANSWERING. _threat_miss_idle
        # has carried this triage waiver since 2026-08-16 -- it will not fine you for ignoring a lone
        # Skeletons, 0.38% of a tower -- but the CREDIT side never got the mirror and paid a full
        # +1.0 for any role-valid counter at any recognised threat. That stayed hidden only because
        # the counter table happened to return False for a body against a swarm; once that hole was
        # closed, `ignore_the_ignorable` -- the drill whose whole content is NOT answering a trickle
        # -- immediately began paying more to spend (+0.09) than to hold (+0.00).
        #
        # Zero rather than a penalty: playing at a trickle is not a MISREAD, it is just not worth
        # paying for, and elixir_trade already prices the elixir. Triage is the tier above every
        # counter rule, so both halves of this term now agree about what is worth a card.
        if committed and threat_value.bodies_ignore_frac(
                self.db, [u.spec.base for u in committed],
                tower_level=self._tower_level_for_triage) < threat_value.IGNORE_FRAC:
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
        # FIX 7: the SAME number that decides the waiver also decides the PRICE. `bodies_ignore_frac`
        # is the share of a princess tower this group takes if ignored outright, so it already IS
        # "how much does ignoring this cost me" -- it was being thresholded and then thrown away.
        _miss_frac = 1.0
        if committed:
            _miss_frac = float(threat_value.bodies_ignore_frac(
                self.db, [u.spec.base for u in committed],
                tower_level=self._tower_level_for_triage))
            if _miss_frac < threat_value.IGNORE_FRAC:
                return 0.0
        # ALREADY ANSWERING IT IS NOT IGNORING IT (2026-08-17). This term asked only "is a counter in
        # hand and affordable", never "is the push already being dealt with" -- so the step after a
        # Knight was dropped to intercept, and every step while he walked into the fight, was charged
        # the full miss penalty again. Defence takes seconds; the penalty charged per 1-second step.
        if any(u.team == 0 and u.hp > 0 and u.spec.kind != "spell"
               and card_threat.counters(card_threat.profile(self.db, u.spec.base), tid)
               for u in self.eng.units):
            return 0.0
        # ...AND IGNORING IT IS ONE MISTAKE, NOT ONE PER TICK. Uncapped per-step charging is what
        # made this the dominant term in the whole ledger and taught the policy to empty its bar.
        #
        # MEASURED, before this: over 3 matches a hold-to-6 policy took -152.00 from this term alone
        # across 152 fires -- 86% of its total penalty -- while a spend-everything-immediately policy
        # took none at all, because the term only charges on a step where nothing was played. Holding
        # scored -0.545/step against -0.065 for dumping, so ALWAYS PLAY was strictly optimal and the
        # gate collapsed to it (measured P(play) 0.611-0.698, never once below the 0.25 threshold,
        # the elixir bar never above 5, and the 4-cost cards never played at all).
        #
        # A push left genuinely unanswered still charges repeatedly -- that is the behaviour this
        # term exists for -- just on a human timescale rather than every tick.
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
            # FIX 7: capped at 1.0 so a two-tower push cannot outweigh the outcome terms it is only
            # a PROXY for -- this term exists to make the delayed damage learnable, not to replace
            # it. A group with no committed bodies keeps the old full weight (`_miss_frac` 1.0):
            # the threat is lit but nothing is past the commit line, so there is nothing to price.
            if self.threat_miss_proportional:
                return self.w_threat_miss * min(1.0, _miss_frac)
            return self.w_threat_miss
        return 0.0

    def _secondary_lane_response(self, card_id: int, nx: float, ny: float) -> float:
        """A correct, proportionate answer to a committed threat in a lane OTHER than the primary.

        `_threat_response` judges the card against the PRIMARY identity in the PRIMARY lane, so a
        Skeletons dropped on the Mini Pekka while a Golem rolls the other side scores exactly zero --
        measured. The tower damage it prevents is billed only by the delayed outcome terms, which is
        the credit assignment this critic handles worst.

        Judged on the ANSWERED lane's OWN terms: its own identity vector, its own triage, and its own
        danger. The payout scales with that lane's `ignore_cost_frac` against the primary's, so a
        near-equal second threat pays near-full while a trickle pays almost nothing -- the doctrine's
        "cheapest sufficient answer" as a price rather than a rule.
        """
        if self.w_threat_2nd <= 0.0 or ny < 0.5:
            return 0.0
        tx, _ = self._threat_pos()
        if abs(nx - tx) <= self.intercept_lane:
            return 0.0                                   # primary lane -> _threat_response's job
        lane = [u for u in self.eng.units
                if u.team == 1 and u.hp > 0 and u.spec.kind != "spell"
                and u.y >= 0.5 and abs(u.x - nx) <= self.intercept_lane]
        if not lane:
            return 0.0                                   # answering nothing
        bases = [u.spec.base for u in lane]
        if threat_value.bodies_ignore_frac(
                self.db, bases, tower_level=self._tower_level_for_triage) < threat_value.IGNORE_FRAC:
            return 0.0                                   # this lane is not worth a card
        items = [(u.spec.base, card_threat.identity_depth(u.y, self.identity_front))
                 for u in lane if u.spec.base in self._grade_cards]
        if not items:
            return 0.0
        lid = card_threat.identity_threat_vector(items, self.db, horizon=self.predict_horizon)
        if lid[0] < 0.5 or not card_threat.counters(self._deck_profiles[card_id], lid):
            return 0.0                                   # wrong role for THIS lane
        n_cards = len(threat_value.cards_from_bodies(self.db, bases)) or 1
        if self._threat_credits >= max(1, min(self.threat_credit_budget, n_cards + 1)):
            return 0.0                                   # budget spent (shared with the primary)

        def _danger(base):
            try:
                return float(threat_value.ignore_cost_frac(self.db, base))
            except Exception:  # noqa: BLE001
                return 0.0

        here = max(_danger(b) for b in bases)
        prim = max([_danger(u.spec.base) for u in self.eng.units
                    if u.team == 1 and u.hp > 0 and u.spec.kind != "spell" and u.y >= 0.5] or [0.0])
        share = min(1.0, here / prim) if prim > 1e-9 else 0.0
        if share <= 0.0:
            return 0.0
        self._threat_credits += 1
        return self.w_threat_2nd * share

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


    def _support_alone(self, card_id: int, nx: float, ny: float) -> float:
        """A SUPPORT troop played with nothing to support and nothing to defend is a misplace.

        User doctrine (2026-08-20): "firecracker is a support troop... she should be played to
        support a mighty miner, help defend, or support hog rider. Never by herself." Before this
        a lone bridge firecracker returned 0.0 -- free, which is the same shape as the king-rocket
        exploit: bad in the game, costless in the reward, and it dodged the leak penalty simply by
        being a play. She is 3 elixir with 130 HP; alone at the bridge she trades with whatever
        looks at her first.

        Returns 0.0 for every legitimate use, so the ordinary terms keep scoring those.
        """
        base = self.specs[card_id].base if 0 <= card_id < len(self.specs) else ""
        if base not in self.support_bases:
            return 0.0
        # (1) supporting a committed push of ours -- Hog or Mighty Miner, same lane.
        for ally in self.eng.units:
            if (ally.team == 0 and ally.hp > 0 and ally.spec.base in self.support_targets
                    and abs(ally.x - nx) <= 0.18 and ally.y <= self.hog_bridge_y):
                return 0.0
        # (2) helping defend -- a threat worth a card is on our half. Triage decides, so she is
        # never obliged to answer a lone Skeletons, and threat_response scores the play itself.
        committed = [u for u in self.eng.units
                     if u.team == 1 and u.hp > 0 and u.spec.kind != "spell" and u.y > 0.42]
        if committed and threat_value.bodies_ignore_frac(
                self.db, [u.spec.base for u in committed],
                tower_level=self._tower_level_for_triage) >= threat_value.IGNORE_FRAC:
            return 0.0
        # (3) neither: she is out on her own.
        return self.w_wincon_mis

    def _hog_synergy(self, card_id: int, nx: float, ny: float) -> float:
        """Credit a SUPPORT card that completes a Hog push (user doctrine, 2026-08-20).

        The doctrine prior already aims these cells; nothing paid for them, so the policy had no
        reason to learn the pairing. Returns 0.0 whenever there is no committed Hog to support, so
        a support card on a quiet board is scored by the ordinary terms and nothing else.
        """
        # The committed push being supported: the Hog, or the Mighty Miner going in ahead of him.
        # The user names BOTH as legitimate escorts ("support a mighty miner... or support hog
        # rider"), and an escort behind the mini-tank is the same play one card earlier.
        hog = next((u for u in self.eng.units
                    if u.team == 0 and u.hp > 0 and u.spec.base == "hog_rider"
                    and u.y < self.hog_bridge_y), None)
        lead = hog or next((u for u in self.eng.units
                            if u.team == 0 and u.hp > 0 and u.spec.base == "mighty_miner"
                            and u.y < self.hog_bridge_y), None)
        if lead is None:
            return 0.0                                   # nothing committed: not a combo
        base = self.specs[card_id].base if 0 <= card_id < len(self.specs) else ""
        same_lane = abs(nx - lead.x) <= 0.18
        if base == "earthquake":
            # THE CLASSIC. Their BUILDING is what stops the Hog, and the quake deletes it while
            # clipping the tower behind it. Requires an actual building in the blast -- an EQ at
            # open ground is not the combo however close the Hog is.
            r = 3.5 / 18.0
            if hog is not None and any(
                    u.team == 1 and u.hp > 0 and u.spec.kind == "building"
                    and abs(u.x - nx) <= r and abs(u.y - ny) <= r for u in self.eng.units):
                return self.w_wincon * self.hog_support_mult
            return 0.0
        if base == "firecracker":
            # BEHIND HIM, same lane: she out-ranges the defence and shreds it while he tanks.
            if same_lane and ny > lead.y:
                return self.w_wincon * self.hog_support_mult
            return 0.0                                   # _support_alone judges the rest
        if base == "mighty_miner":
            # The mini-tank eats the building's attention; the Hog arrives behind it. Requires the
            # HOG specifically -- a Mighty Miner beside another Mighty Miner is not a push.
            if same_lane and hog is not None:
                return self.w_wincon * self.hog_support_mult
            return 0.0
        return 0.0

    def _hog_wincon(self, card_id: int, nx: float, ny: float) -> float:
        """A RUSH win condition (Hog Rider): judged on TIMING and LANE, not standing geometry.

        Deliberately not the X-Bow's term. The bow is a siege building scored on where it sits and
        what it can reach; the Hog is four elixir that walks, so what matters is whether it was
        sent at the bridge, into the right lane, and at a moment the board could afford.

        Ordered so the vetoes win: a send into a committed push is a misplace however good the
        lane was, because that is the play that turns a deficit into a loss.
        """
        # (a) NEVER INTO A COMMITTED PUSH -- the user's rule and the doctrine's. Triage decides
        # what counts, so a couple of Skeletons over the river is not a "push" (the same
        # group_ignore_frac gate every other tier in this project uses).
        committed = [u for u in self.eng.units
                     if u.team == 1 and u.hp > 0 and u.spec.kind != "spell" and u.y > 0.42]
        if committed and threat_value.bodies_ignore_frac(
                self.db, [u.spec.base for u in committed],
                tower_level=self._tower_level_for_triage) >= threat_value.IGNORE_FRAC:
            return self.w_wincon_mis
        # (b) BRIDGE ONLY. From our own half he walks the length of the board and is answered
        # twice on the way; the deck's prompt says it and nothing scored it.
        if ny > self.hog_bridge_y:
            return self.w_wincon_mis
        # (c) THE BEST APPLICABLE BONUS, not the product of all of them. These overlap by
        # construction -- a Mighty Miner ahead of the Hog IS a surviving friendly troop in the
        # lane, so multiplying "behind the mini-tank" by "counter-push" counted ONE FACT TWICE and
        # paid 4.50 where the send plus its best bonus is worth 3.75.
        bonuses = [1.0]
        # (c0) BEHIND THE MINI-TANK. Mighty Miner goes first and eats the defending building's
        # attention; the Hog arriving behind him in the same lane completes the pair from the
        # other side -- whichever card is played SECOND is the one making the decision.
        if any(u.team == 0 and u.hp > 0 and u.spec.base == "mighty_miner"
               and abs(u.x - nx) <= 0.18 and u.y <= self.hog_bridge_y for u in self.eng.units):
            bonuses.append(self.hog_support_mult)
        # (c) LANE. Opposite their committed mass is the punish; behind a defender who just
        # survived is the counter-push. Either is the doctrinal send, so either pays the bonus.
        enemy_mass_l = sum(u.spec.elixir for u in self.eng.units
                           if u.team == 1 and u.hp > 0 and u.x < 0.5)
        enemy_mass_r = sum(u.spec.elixir for u in self.eng.units
                           if u.team == 1 and u.hp > 0 and u.x >= 0.5)
        heavier_left = enemy_mass_l > enemy_mass_r
        if (enemy_mass_l or enemy_mass_r) and ((nx >= 0.5) if heavier_left else (nx < 0.5)):
            bonuses.append(self.hog_punish_mult)                      # opposite lane to their commitment
        elif any(u.team == 0 and u.hp > 0 and u.spec.kind == "troop"
                 and abs(u.x - nx) < 0.18 and u.y > 0.42 for u in self.eng.units):
            bonuses.append(self.hog_punish_mult)                      # same lane, behind a live defender
        return self.w_wincon * max(bonuses)

    def _wincon_exec(self, card_id: int, nx: float, ny: float) -> float:
        """(3) WIN-CONDITION execution: the deck's doctrine done right for the current phase -- X-Bow
        forward-in-range (offensive) / back-centre (defensive), Miner chipping the princess (not the king),
        rocket-cycle chip or the rocket 2-for-1. + when executed correctly, - when the win condition is
        thrown away. Non-win-condition cards return 0 (they're scored by threat_response / the trade term)."""
        princesses = [t for t in self.eng.towers[1][:2] if t.alive]
        d = min((tile_dist(nx, ny, t.x, t.y) for t in princesses), default=99.0)   # tiles
        if card_id in getattr(self, "wincon_ids", ()) and card_id not in self.miner_ids:
            return self._hog_wincon(card_id, nx, ny)
        _syn = self._hog_synergy(card_id, nx, ny)
        if _syn:
            return _syn                                  # a support card completing a Hog push
        _alone = self._support_alone(card_id, nx, ny)
        if _alone:
            return _alone                                # a support troop out on its own
        if card_id in self.miner_ids:
            king = self.eng.towers[1][2]                     # [L princess, R princess, KING]
            if king.alive and tile_dist(nx, ny, king.x, king.y) <= 2.9:
                return self.w_wincon_mis                      # Miner on the enemy KING wakes it early -> bad trade
            if d <= 2.9:                                      # tiles
                return self.w_wincon                          # Miner chipping the princess
        return 0.0







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
        if committed and threat_value.bodies_ignore_frac(
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


    def _in_roll_corridor(self, nx: float, ny: float, u, spec, margin: float = 1.5,
                          back: float = 0.4) -> bool:
        """Is `u` inside the forward corridor a rolling spell will sweep?

        Measured in TRUE TILES PER AXIS -- the board is 18x32, so a normalised radius understates y
        by 1.8x, the same anisotropy that made a Tornado's blast read as 7 tiles wide and 12 tall.
        The margin is generous on purpose: this snapshot decides whether the cast is later allowed
        to be called a WHIFF, so catching a body that walks into the corridor mid-roll matters more
        than excluding one that walks out. A whiff has to be unambiguous to be charged.
        """
        fwd = -1.0 if u.team == 1 else 1.0          # our rolls travel toward the ENEMY end (low y)
        ahead = (ny - float(u.y)) * _TILES_Y * (1.0 if fwd < 0 else -1.0)
        # ASYMMETRIC MARGINS, and the asymmetry is the doctrine. A roll goes FORWARD: the engine
        # gives it about a tile of back-slop and nothing more, so anything further behind the cast
        # is untouchable -- that IS the "played it too high, hit nothing" failure. A generous
        # backward margin re-broke the whiff test in a subtle way: bodies the roll never reached
        # sat in the snapshot, the TOWER shot them during the settle window, and their damage was
        # credited to the spell. Forward stays generous, because a body walking INTO the corridor
        # during the roll is genuinely hit.
        if ahead < -back or ahead > float(spec.roll_len) + margin:
            return False                            # behind the cast, or past the end of the roll
        lateral = abs(float(u.x) - nx) * _TILES_X
        return lateral <= float(spec.spell_radius or 0.0) + margin

    def _arm_spell_check(self, nx: float, ny: float, spec) -> None:
        """Snapshot what a just-cast damage spell COULD hit, to be settled once it lands.

        Judging at cast is the bug this replaces: the engine resolves spells after a delay and the
        board moves in between. The snapshot is deliberately generous in radius -- the question is
        not "was the aim good" but "did anything at all take damage from it", so a lead that looks
        wide at cast and lands perfectly must not be pre-judged.
        """
        rad = max(self.spell_waste_radius, float(spec.pull_radius or 0.0),
                  float(spec.spell_radius or 0.0)) + 2.0
        land = float(self.eng.t) + float(getattr(spec, "spell_delay", 0.0) or 0.0)
        if getattr(spec, "rolls", False) and float(getattr(spec, "roll_len", 0.0) or 0.0) > 0.0:
            # A ROLLING SPELL IS A LINE, NOT A CIRCLE. Snapshotting a disc around the cast point
            # charged spell_waste for every correct Log: the card is cast BEHIND a group precisely
            # so the corridor sweeps through it, and at 9.6 tiles of roll its victims sit well
            # outside a ~4 tile disc -- so `dealt` came back 0 and the roll was judged a miss.
            # Measured before this: rolling through a Skeleton Army and killing all of it scored
            # -0.150 against 0.000 for not casting at all.
            caught = [u for u in self.eng.units
                      if u.team == 1 and u.hp > 0 and self._in_roll_corridor(nx, ny, u, spec)]
        else:
            caught = [u for u in self.eng.units
                      if u.team == 1 and u.hp > 0 and tile_dist(nx, ny, u.x, u.y) <= rad]
        # ⚠ KEYED ON `deploy_seq`, NOT `id(u)`. CPython recycles a dead body's address, so a
        # victim this spell KILLED could be matched against a NEWER unit that reused the
        # address and read as alive at full hp -- billing a good cast `spell_waste` instead
        # of crediting `spell_defence`. The better the cast, the likelier the victim is gone
        # and its address reused, so the corruption is BIASED AGAINST correct play. Measured
        # (I10): 3 of 24 seeds diverged run-to-run on identical code; 0 of 24 once pinned.
        # `deploy_seq` is a monotonic counter stamped in Unit.__post_init__ (added in I7).
        hp = {u.deploy_seq: float(u.hp) for u in caught}
        # WHAT each catch would COST US if it lived, kept alongside the HP so the settle can pay
        # for damage prevented. Only bodies already on OUR half count as defence -- killing things
        # on their side is offence and is priced by the chip / win-condition terms.
        worth = {u.deploy_seq: str(u.spec.base) for u in caught if float(u.y) > 0.5}
        towers = {id(t): float(t.hp) for t in self.eng.towers[1] if getattr(t, "hp", 0) > 0}
        # HOW LONG THE EFFECT LASTS, so the verdict is taken after it, never during it. A Poison
        # zone and a Tornado vortex were already covered; RULING 21 made a rolling spell the third
        # case and it would otherwise have been judged mid-roll. MEASURED: The Log's corridor now
        # sweeps for roll_len / (roll_speed/60) = 9.6 / 3.333 = 2.88 s, while the old settle fired
        # at land + 0.35 = 0.75 s after the cast -- with the leading edge only 1.17 of 9.6 tiles
        # along. Every Log that killed anything past that first tile would have been billed
        # `spell_waste` for damage it had not dealt YET. This is the same bug §5 records for LIVE
        # spells ("judged before they arrived", which is why `spell_eval_time` went to 4.0), now
        # closed on the sim side too.
        _lasts = float(getattr(spec, "zone_s", 0.0) or spec.pull_duration or 0.0)
        if getattr(spec, "rolls", False) and float(getattr(spec, "roll_speed", 0.0) or 0.0) > 0.0:
            _lasts = max(_lasts, float(spec.roll_len) / float(spec.roll_speed))
        self._pending_spell_checks.append(
            {"t": land + _lasts + 0.35,
             "hp": hp, "tw": towers, "worth": worth,
             # RE-SNAPSHOT AT LANDING. The cast-time picture cannot contain a body that has not
             # spawned yet, so every pre-emptive cast -- pre-Log a swarm, Log the barrel as it
             # lands, both doctrine -- resolved against an empty list and was charged as a whiff.
             "snap_at": land, "aim": (float(nx), float(ny)), "spec": spec, "rad": float(rad)})


    def _resnap_spell_check(self, p) -> None:
        """Re-take a pending spell's before-picture at the moment it LANDS.

        The cast-time snapshot is kept as well (units are merged, keeping the EARLIER hp for
        anything in both) so a body that was already dying when the spell arrived still counts the
        damage it took. Everything else -- the corridor for a rolling spell, the disc for a blast,
        the our-half filter for the defensive credit -- is the same geometry as the arm, just
        evaluated later.
        """
        spec, (nx, ny), rad = p.get("spec"), p.get("aim", (0.0, 0.0)), float(p.get("rad", 0.0))
        if spec is None:
            return
        if getattr(spec, "rolls", False) and float(getattr(spec, "roll_len", 0.0) or 0.0) > 0.0:
            caught = [u for u in self.eng.units
                      if u.team == 1 and u.hp > 0 and self._in_roll_corridor(nx, ny, u, spec)]
        else:
            caught = [u for u in self.eng.units
                      if u.team == 1 and u.hp > 0 and tile_dist(nx, ny, u.x, u.y) <= rad]
        for u in caught:
            p["hp"].setdefault(u.deploy_seq, float(u.hp))   # keep the earlier hp if already known
            if float(u.y) > 0.5:
                p.setdefault("worth", {}).setdefault(u.deploy_seq, str(u.spec.base))

    def _settle_spell_casts(self) -> float:
        """Charge spell_waste for casts that, once resolved, damaged NOTHING.

        The user's own test: "if nothing gets damaged and no knockback is observed, the spell was a
        miss". Damage rather than proximity, so a rolling Log, a lingering Poison zone, a Tornado's
        spread damage and an instant Rocket are all judged by the same question -- and a unit that
        DIED counts, since it is missing from the engine entirely.
        """
        if not self._pending_spell_checks:
            return 0.0
        now = float(self.eng.t)
        # LANDING PASS: refresh the before-picture for anything that has just resolved, so a body
        # that spawned or walked in during the flight is measured rather than missed.
        for p in self._pending_spell_checks:
            if p.get("snap_at") is not None and now >= float(p["snap_at"]):
                self._resnap_spell_check(p)
                p["snap_at"] = None
        due = [p for p in self._pending_spell_checks if p["t"] <= now]
        if not due:
            return 0.0
        self._pending_spell_checks = [p for p in self._pending_spell_checks if p["t"] > now]
        live = {u.deploy_seq: float(u.hp) for u in self.eng.units if u.hp > 0}
        tw_now = {id(t): float(t.hp) for t in self.eng.towers[1]}
        total = 0.0
        for p in due:
            dealt = 0.0
            for uid, hp0 in p["hp"].items():
                dealt += max(0.0, hp0 - live.get(uid, 0.0))   # gone from the engine = it died
            for tid, hp0 in p["tw"].items():
                dealt += max(0.0, hp0 - tw_now.get(tid, hp0))
            if dealt <= 0.0:
                total += self.rw_stats.add("spell_waste", self.w_spell_waste)
                continue
            # IT LANDED -- pay for the damage it PREVENTED. Symmetric with the whiff charge above
            # and settled on the same evidence: the bodies that are gone, not the ones the aim was
            # near. Priced by the triage model, so a trickle earns nearly nothing and a committed
            # push earns real credit; the tower fraction it would have cost us IS what killing it
            # is worth.
            gone = [b for uid, b in (p.get("worth") or {}).items() if uid not in live]
            if gone:
                try:
                    saved = float(threat_value.bodies_ignore_frac(
                        self.db, gone, tower_level=self._tower_level_for_triage))
                except Exception:  # noqa: BLE001 -- an unknown card is not a payday
                    saved = 0.0
                if saved > 0.0:
                    total += self.rw_stats.add(
                        "spell_defence",
                        self.w_spell_defence * min(saved, self.spell_defence_cap))
        return total

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

    def _ability_value(self) -> float:
        """What Explosive Escape was actually worth, priced at the moment of the cast.

        Every guide says the same thing about this ability and it is entirely a TIMING skill: the
        bomb wants their counter already committed and standing on him, and triggering early is the
        classic way to waste it. So the reward is the enemy elixir caught in the blast, plus credit
        for escaping while genuinely under threat -- and a small charge for firing into nothing,
        which is the failure mode the timing rule exists to prevent.

        The bomb sits at the FRONT of the spell queue (champion_ability just appended it) rather than
        where the champion now stands, which is the whole point -- he is already in the other lane.
        """
        if not self.eng.spells:
            return 0.0
        sp = self.eng.spells[-1]
        rad = float(sp.spec.spell_radius or 2.0)
        caught = [u for u in self.eng.units
                  if u.team == 1 and u.hp > 0 and tile_dist(sp.x, sp.y, u.x, u.y) <= rad]
        elix = sum(float(u.spec.elixir) for u in caught)
        if elix <= 0.0:
            return self.w_ability_waste
        # Normalised on the ability's own cost: one elixir that removes four is the play it exists
        # for, and the cap keeps a lucky multi-catch from dwarfing the rest of the ledger.
        return min(self.ability_value_cap, elix / max(1.0, self.value_norm) * self.w_ability_value)

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




    # ---------------------------------------------------------------------------------- CARD VETO
    #
    # WHY A CARD VETO AND NOT A CELL MASK, AND WHY VALUE AND NOT A BODY COUNT.
    # `research/sim_parity/ledger/spell_experiments.md` measured, n=300 paired, GREEDY, that this
    # policy's spells are net-negative at the volume it casts them, and that a state-conditioned
    # CARD-level refusal is the lever: at a >=3-body clump test it is +0.233 tower fractions
    # (3.58 sigma) over the baseline and +0.207 (2.98 sigma) over a VOLUME-MATCHED random spell
    # ban, so the targeting criterion -- not merely "cast less" -- is doing the work.
    #
    # The body COUNT form was rejected by the owner and he is right: this deck's highest-value
    # casts are routinely SINGLE-body. `nado_king_activation` pulls exactly one Hog Rider;
    # `nado_the_sneaky_lock` drags exactly one Knight; `rocket_the_two_for_one` kills one Witch;
    # `rocket_the_pump_on_sight` hits one building. A count threshold at K=3 refuses every one of
    # them. So the threshold is on VALUE, in the project's own measured currency
    # (`threat_value.catch_value_frac`, tower fractions), plus an explicit exemption set for casts
    # whose payoff is not the bodies at all. Full enumeration with sources: decisions.md ruling 30.
    _ROLL_BACK_SLOP = 1.0                 # engine._LOG_BACK_SLOP

    def _cell_xy(self):
        """Cell centres, cached. The same cache `spell_target_mask` builds."""
        cc = getattr(self, "_cell_xy_cache", None)
        if cc is None:
            gw = int(self.actions.gw)
            pts = [self.actions.cell_center(c % gw, c // gw)
                   for c in range(int(self.actions.n_cells))]
            cc = self._cell_xy_cache = (np.asarray([p[0] for p in pts], np.float32),
                                        np.asarray([p[1] for p in pts], np.float32))
        return cc

    def _clamped_xy(self, anywhere: bool):
        """Cell centres AFTER `deploy_clamp` -- where the cast would actually land. The Log is
        `own_half_only`, so its cells clamp and its true footprint is not the unclamped one."""
        key = bool(anywhere)
        cache = getattr(self, "_clamp_xy_cache", None)
        if cache is None:
            cache = self._clamp_xy_cache = {}
        if key not in cache:
            cx, cy = self._cell_xy()
            idx = np.asarray([self.actions.deploy_clamp(key, c) for c in range(cx.shape[0])],
                             np.int64)
            cache[key] = (cx[idx].astype(np.float64), cy[idx].astype(np.float64))
        return cache[key]

    def _spell_footprint(self, card_id: int):
        """(hit, units): (n_cells, n_units) bool of what a cast at each cell would ACTUALLY touch.

        MIRRORS THE ENGINE, and that is load-bearing -- spell_experiments.md 4v retracted a whole
        finding for treating a rolling spell as a disc. `spell_radius` is a roll's HALF-WIDTH:

            roll   engine._tick_roll      -BACK_SLOP <= (uy-cy)*fdir*TY <= roll_len
                                          AND |ux-cx|*TX <= spell_radius,  ground only
            pull   engine._tick_vortex    hypot((dx)*TX, (dy)*TY) <= pull_radius
            blast  engine._resolve_spell  hypot(...) <= spell_radius, ground_only skips flyers

        A HIDDEN (retracted) building is excluded unless the spell carries `hits_hidden` -- the
        engine's own `_hurt` guard. Without it a Rocket "catches" a retracted Tesla it deals zero
        damage to, and the veto would wave that cast through.
        """
        spec = self.specs[int(card_id)]
        us = [u for u in self.eng.units if u.team == 1 and u.hp > 0
              and not (getattr(u, "hidden", False) and not getattr(spec, "hits_hidden", False))]
        cx, cy = self._clamped_xy(int(card_id) in self.anywhere_ids)
        if not us:
            return np.zeros((cx.shape[0], 0), bool), us
        tx, ty = float(self.eng.tiles_x), float(self.eng.tiles_y)
        ux = np.asarray([u.x for u in us], np.float64)
        uy = np.asarray([u.y for u in us], np.float64)
        fly = np.asarray([bool(getattr(u.spec, "flying", False))
                          or bool(getattr(u, "airborne_left", 0.0) > 0.0) for u in us], bool)
        if getattr(spec, "rolls", False) and float(getattr(spec, "roll_len", 0.0)) > 0.0:
            dy = (uy[None, :] - cy[:, None]) * -1.0 * ty          # team 0 rolls toward -y
            dx = np.abs(ux[None, :] - cx[:, None]) * tx
            hit = ((dy >= -self._ROLL_BACK_SLOP) & (dy <= float(spec.roll_len))
                   & (dx <= float(spec.spell_radius)))
        else:
            rad = (float(spec.pull_radius) if (getattr(spec, "pulls", False)
                                               and float(spec.pull_radius or 0.0) > 0.0)
                   else float(spec.spell_radius or 2.0))
            d = np.hypot((ux[None, :] - cx[:, None]) * tx, (uy[None, :] - cy[:, None]) * ty)
            hit = d <= rad
        if getattr(spec, "ground_only", False) and not getattr(spec, "pulls", False):
            hit = hit & ~fly[None, :]
        return hit, us

    def _veto_legal(self, card_id: int, legal=None):
        """The cell mask the veto judges over -- the caller's own, or the env's deploy mask.

        CACHED on (anywhere, pocket). `deployable_mask` rebuilds `no_king_mask` from 432 fresh
        `cell_center` calls, which PROFILED at 0.9 of the 1.0 s this veto spent over 180
        evaluations -- 87% of the cost was recomputing a mask that changes only when a tower
        falls. The trainer passes its own mask in and never reaches this path at all.
        """
        if legal is not None:
            return np.asarray(legal, bool)
        anywhere = bool(int(card_id) in self.anywhere_ids)
        if hasattr(self, "pocket_state"):
            key = (anywhere,) + tuple(self.pocket_state(0))
        else:
            key = (anywhere,)
        cache = getattr(self, "_veto_legal_cache", None)
        if cache is None:
            cache = self._veto_legal_cache = {}
        m = cache.get(key)
        if m is None:
            m = cache[key] = np.asarray(
                self.deploy_mask(anywhere, 0) if hasattr(self, "deploy_mask")
                else self.actions.deployable_mask(anywhere), bool)
        return m

    def spell_cast_value(self, card_id: int, legal=None) -> float:
        """Best TOWER FRACTIONS of enemy value any legal cell would catch with this spell.

        The currency is the project's own measured triage model
        (`threat_value.catch_value_frac`), not a body COUNT -- which is the whole point of the
        value form. A count cannot say that one Mini P.E.K.K.A. (0.644) outvalues three Skeletons
        (0.0038 together, since three bodies collapse to one card), and this deck's best casts are
        routinely single-body.
        """
        hit, us = self._spell_footprint(card_id)
        if not us:
            return 0.0
        rows = hit[self._veto_legal(card_id, legal)]
        if rows.size == 0 or not rows.any():
            return 0.0
        bases = [u.spec.base for u in us]
        best = 0.0
        for r in np.unique(rows, axis=0):          # distinct CAUGHT SETS, not distinct cells
            if not r.any():
                continue
            v = threat_value.catch_value_frac(
                self.db, [b for b, k in zip(bases, r) if k],
                tower_level=self._tower_level_for_triage)
            if v > best:
                best = v
                if not math.isfinite(best):
                    break
        return float(best)

    def spell_veto_exempt(self, card_id: int, legal=None):
        """Why this spell may be cast REGARDLESS of the value it catches, or None.

        Every entry is a play whose payoff is not the bodies in the footprint, enumerated from the
        doctrine files, the drills and the counter tables in decisions.md ruling 30. Each is
        decided from ENGINE STATE, and each names the source it comes from. The set is derived
        from the DECK'S OWN CARDS (spec flags: `pulls`, `knockback`, `spell_dmg`, `hits_hidden`),
        never from card names, so hogeq's Earthquake and Log take the entries that apply to them.
        """
        spec = self.specs[int(card_id)]
        anywhere = int(card_id) in self.anywhere_ids
        eng = self.eng
        pulls = bool(getattr(spec, "pulls", False))
        lg = self._veto_legal(card_id, legal)
        # --- 1. TOWER TARGET. A cast that chips or finishes a Crown Tower catches ZERO bodies by
        # definition. This is `spell_target_mask`'s own rule promoted from the cell to the card:
        # "a live enemy princess is a valid chip target for a DAMAGE spell (never for a pull)".
        # Sources: DOCTRINE.md rows 56/57 (rocket-cycle the weaker princess), drill
        # `rocket_the_two_for_one`, hogeq doctrine's "PURE CHIP", env._rocket_value's `on_tower`.
        if not pulls and float(getattr(spec, "spell_tower_dmg", 0.0) or 0.0) > 0.0:
            cx, cy = self._clamped_xy(anywhere)
            tx, ty = float(eng.tiles_x), float(eng.tiles_y)
            # ⚠ "A LEGAL CELL TOUCHES A LIVE TOWER" IS NOT ENOUGH, and it was measured: an
            # anywhere-spell can always reach a live princess, so an ungated version exempted the
            # Rocket on 300 of 300 sampled steps and the veto could never refuse it at all. The
            # gate is `_rocket_value`'s OWN: it pays `rocket_chip_early` 0.25 for a regulation
            # chip against `rocket_chip_behind` 1.2 once late and level-or-behind, i.e. the
            # project already prices an early chip as a quarter of a win-condition play, not as a
            # licence. So only the branches that pay are exempt: LETHAL, the TIEBREAK chip, and
            # the 2-for-1 (drill `rocket_the_two_for_one`, one Witch beside their princess).
            # ⚠ "LATE" IS OVERTIME, NOT `_defensive`. MEASURED: `_defensive` is already True at
            # t=0.0 whenever the opponent holds a split-lane counter, and env.py's own note above
            # `_punish_window` records that locking it on put 93.5% of steps in the defensive
            # phase -- so `_defensive or overtime` exempted the Rocket from the opening tick. And
            # `_tiebreak_gap` is NEGATIVE at t=0 on a level disadvantage alone (measured -0.098,
            # our 4424 HP towers against their 4858), so `gap <= 0` cannot carry the gate either.
            # DOCTRINE_RESEARCH §3.4 is explicit: "pure tower chip is a x2/OT and endgame tool
            # only", plus the endgame rule that 3-4 casts finish a low tower.
            late = float(eng.t) >= self._double_time
            gap = self._tiebreak_gap() if hasattr(self, "_tiebreak_gap") else 0.0
            hp_frac = float(getattr(self, "rocket_combo_hp_frac", 1.5))
            combo_r = float(getattr(self, "rocket_combo_radius", 3.5))
            for t in eng.towers[1][:2]:
                if not t.alive:
                    continue
                d = np.hypot((cx - float(t.x)) * tx, (cy - float(t.y)) * ty)
                if not bool((lg & (d <= self.spell_aim_radius)).any()):
                    continue
                if float(t.hp) <= float(spec.spell_tower_dmg):
                    return "tower_lethal"            # this cast finishes the tower: 0 bodies, a crown
                if float(t.hp) <= _TOWER_FINISH_CASTS * float(spec.spell_tower_dmg):
                    return "tower_finish"            # DOCTRINE_RESEARCH §3.4: 3-4 casts end it
                if late and gap <= 0.0:
                    return "tower_chip"              # in overtime the chip race IS the win condition
                # 2-FOR-1: a support THIS spell can (almost) one-shot standing beside that tower.
                # env._rocket_combo's rule, but scaled by the CASTING card's own damage rather
                # than by the deck's rocket, so a 240-damage Log cannot claim a rocket's kill.
                for u in eng.units:
                    if (u.team == 1 and u.hp > 0 and getattr(u.spec, "kind", "") == "troop"
                            and not u.spec.building_only and 4 <= float(u.spec.elixir) <= 6
                            and float(u.spec.hp) <= float(spec.spell_dmg) * hp_frac
                            and tile_dist(u.x, u.y, t.x, t.y) <= combo_r):
                        return "two_for_one"
        hit, us = self._spell_footprint(card_id)
        if us and hit.size:
            reach = hit[lg].any(0)
            knocks = float(getattr(spec, "knockback", 0.0) or 0.0) > 0.0
            for u, ok in zip(us, reach):
                if not ok:
                    continue
                # --- 2. BUILDING / ECONOMY TARGET. A building is exactly ONE body and killing it
                # IS the play: the pump (drills `rocket_the_pump_on_sight`, `eq_the_pump_on_sight`),
                # the building holding the Hog (`eq_clears_the_hogs_building`), the Tombstone at
                # half HP (doctrine.py's verbatim guide rule), their seated siege. A pull cannot
                # move a building at all (engine._tick_vortex skips them), so it is not exempted.
                if getattr(u.spec, "kind", "") == "building" and not pulls:
                    return "building"
                # --- 3. CHARGE / RAMP RESET. `engine._knock` zeroes `charge_dist` and `ramp_shots`
                # for anything a knockback spell shoves -- drill `log_resets_the_charge` is scored
                # in TOWER HITS TAKEN and explicitly not in bodies ("a Battle Ram ALWAYS dies, it
                # is kamikaze"). WARNING KNOCKBACK ONLY: the vortex displaces but does NOT clear
                # `charge_dist` in this engine (only `_knock` and `_apply_status` do), so the
                # tornado gets no charge-reset exemption. That is an engine fact, not a policy.
                # ⚠ BOTH GUARDED BY `trade_sane`. The Rocket also carries 1.0 tiles of knockback
                # and `_knock` disarms a charge for it too, so an unguarded reset exemption made a
                # SIX-elixir cast unrefusable on any charging body -- which is the exact trade
                # `trade_sane` was written for after the owner reported "rocketing wall breakers
                # (a horrible elixir trade)". Doctrine names the LOG for charge resets, never the
                # Rocket (DOCTRINE.md rows 4/28/67).
                if (knocks and threat_value.trade_sane(self.db, spec.base, [u.spec.base])
                        and (float(getattr(u.spec, "charge_range", 0.0) or 0.0) > 0.0
                             or int(getattr(u, "ramp_shots", 0) or 0) > 0)):
                    return "charge_reset"
                # --- 4. LOCK BREAK / RETARGET. Dragging or shoving a body off what it is chewing
                # is worth a card whatever that body is worth -- env._nado_catch says so in its own
                # comment ("most wincons pulled this way are worth less than one" rocket), and the
                # SNEAKY LOCK drill (`nado_the_sneaky_lock`, ONE Knight on our X-Bow) is exactly
                # this play. Both mechanics set `aggro_reset`: `_tick_vortex` when the pull takes a
                # body out of reach of its target, `_resolve_roll` on every shove.
                #
                # ⚠ TWO GATES, BOTH MEASURED INTO EXISTENCE. A first version asked only "is this
                # body locked onto something of ours", and it fired on 21% of every veto
                # evaluation -- an enemy is nearly always chewing on SOMETHING -- which on its own
                # took the value form from a working veto to a null (casts/match 7.83 -> 6.15
                # against the count form's 4.25). Two conditions were missing, and the project
                # already states both:
                #   * env._nado_catch's `targeters` are `building_only` bodies locked onto one of
                #     OUR TOWERS, gated at `nado_retarget_min_worth` (2.0) -- deliberately BELOW
                #     rocket_min_worth, because a pulled wincon is usually worth less than a rocket.
                #   * the sneaky lock is a defender on one of our BUILDINGS (the X-Bow), which is a
                #     unit, not a tower -- doctrine.py: "drag their DEFENDER off, not the building".
                # An enemy merely fighting one of our TROOPS is an ordinary defensive scrap and
                # buys nothing that a card should be spent on.
                tgt = getattr(u, "target", None)
                if (tgt is not None and bool(getattr(u, "locked", False))
                        and (pulls or knocks)
                        and threat_value.trade_sane(self.db, spec.base, [u.spec.base])):
                    tspec = getattr(tgt, "spec", None)
                    ours_building = (tspec is not None and int(getattr(tgt, "team", 1)) == 0
                                     and getattr(tspec, "kind", "") == "building")
                    on_our_tower = any(tgt is t for t in eng.towers[0])
                    worth = float(u.spec.elixir) / max(1, u.spec.squad_count or u.spec.count or 1)
                    if ours_building or (on_our_tower and bool(u.spec.building_only)
                                         and worth >= float(getattr(
                                             self, "nado_retarget_min_worth", 2.0))):
                        return "lock_break"
        # --- 5. KING ACTIVATION. The pull's value is waking our King Tower for the rest of the
        # match, not the single body it drags. The precondition is the doctrine's own and it is a
        # question about the attacker's PATH, not its current tile: `_king_spots` emits a spot only
        # when `_path_enters_pull` says the walk crosses the pull radius while the vortex lives.
        # Source: drill `nado_king_activation` (ONE Hog Rider), DOCTRINE.md rows 3/16/51.
        if pulls and not eng.towers[0][2].active:
            try:
                from . import doctrine as _doc
                for u in eng.units:
                    if (u.team == 1 and u.hp > 0 and not _doc._pull_resistant(u)
                            and (u.spec.building_only or u.y > 0.55) and u.y > 0.52
                            and _doc._king_spots(self, u)):
                        return "king_activation"
            except Exception:                      # noqa: BLE001 -- never break a rollout
                pass
        # --- 6. A TROOP-SPAWNING SPELL IS IN FLIGHT. Those bodies do not exist yet, so the
        # cast-time footprint is empty BY CONSTRUCTION: "pre-log beats post-log" (DOCTRINE.md rows
        # 19/21) and drill `log_the_barrel_on_landing`, whose barrel is still in the air at the
        # moment the reference line rolls. env._resnap_spell_check exists for exactly this problem
        # on the reward side ("every pre-emptive cast resolved against an empty list").
        inc = [s for s in (getattr(eng, "spells", None) or ())
               if int(getattr(s, "team", 0)) == 1
               and getattr(s.spec, "spawn_spec", None) is not None]
        if inc:
            # ...and the cast has to be able to REACH where those bodies will land. Without the
            # reach test this exempted every spell anywhere on the board for as long as any barrel
            # was in the air, which is not the play the doctrine describes ("Log the LANDING").
            cx, cy = self._clamped_xy(anywhere)
            tx, ty = float(eng.tiles_x), float(eng.tiles_y)
            reach_r = (float(spec.roll_len) if getattr(spec, "rolls", False)
                       else max(float(spec.spell_radius or 2.0), float(spec.pull_radius or 0.0)))
            for s in inc:
                d = np.hypot((cx - float(s.x)) * tx, (cy - float(s.y)) * ty)
                if bool((lg & (d <= reach_r)).any()):
                    return "incoming_spawn"
        return None

    def spell_card_ok(self, card_id: int, min_value: float, legal=None):
        """May this SPELL be chosen AT ALL on this board? -> (ok, reason).

        `min_value` is in TOWER FRACTIONS; <= 0.0 disables the veto entirely.
        """
        if float(min_value) <= 0.0:
            return True, "off"
        if getattr(self.specs[int(card_id)], "kind", "") != "spell":
            return True, "not_a_spell"
        ex = self.spell_veto_exempt(int(card_id), legal=legal)
        if ex is not None:
            return True, ex
        v = self.spell_cast_value(int(card_id), legal=legal)
        return (v >= float(min_value)), ("value %.4f" % v)

    def step(self, action: Action):
        play, card_id, cell = action
        reward = 0.0
        placed_id = -1
        if play and card_id == self.ability_id and self.ability_id >= 0 \
                and card_id in self._hand_ids():
            # CHAMPION ABILITY: no placement, no slot, no deploy. It either fires on the champion
            # where he stands or it does not fire at all, so the whole (cell -> clamp -> deploy)
            # path below is skipped and the cell the policy chose is ignored by design.
            if self.eng.champion_ability(0):
                placed_id = card_id
                reward += self.rw_stats.add("ability_use", self._bonus(self._ability_value()))
        elif play and 0 <= card_id < self.n_cards and card_id in self._hand_ids():
            spec = self.specs[card_id]
            cell = self.actions.deploy_clamp(card_id in self.anywhere_ids, cell)
            nx, ny = self.actions.cell_center(cell % self.gw, cell // self.gw)
            if self.eng.deploy(0, spec, nx, ny,
                               delay_s=self.action_latency):   # affordable + placed (lands when the live tap would)
                placed_id = card_id
                reward += self.rw_stats.add("threat_response", self._bonus(self._threat_response(card_id, nx, ny)))   # (1) counter to the assessed threat
                # ...and the OTHER lane. Prioritising the greater threat must not mean ignoring the
                # lesser one: a Mini Pekka opposite a Golem still needs a cheap answer, and nothing
                # priced it (measured: +0.000 for the correct Skeletons, while it saved 2266 tower HP).
                reward += self.rw_stats.add("threat_response_2nd",
                                            self._bonus(self._secondary_lane_response(card_id, nx, ny)))
                reward += self.rw_stats.add("wincon_exec", self._bonus(self._wincon_exec(card_id, nx, ny)))           # (3) win-condition executed right
                if card_id in self.damage_spell_ids:
                    # trade ledger: enemy deaths near this cast within 3 s credit as OUR kill
                    self._ev_spells.append((nx, ny, float(spec.spell_radius or 2.0), self.eng.t))
                if card_id in self.damage_spell_ids:
                    # DO NOT JUDGE IT YET. This used to charge spell_waste immediately, from
                    # `_spell_no_target(nx, ny, spec)` -- "is anything near the aim RIGHT NOW" --
                    # while the engine resolves the spell later (a rocket's cast+travel is over a
                    # second at range) and troops walk the whole time. The sim was therefore
                    # rewarding aim-where-they-stand and punishing the lead, teaching the exact
                    # "doesn't lead its target" behaviour the user reported (2026-08-20). Settled
                    # on DAMAGE ACTUALLY DEALT once it lands -- see _settle_spell_casts.
                    self._arm_spell_check(nx, ny, spec)
                reward += self.rw_stats.add("building_waste", self._building_waste(card_id))   # a Tesla spent on a quiet board while their wincon is still in hand
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
        reward += self.rw_stats.add("counterfactual", self._cf_shaping())   # did playing beat holding? (zero-mean)
        # (5) leak: sitting at capacity with nothing played this step wastes elixir.
        if placed_id < 0 and self.eng.elixir[0] >= 9.99:
            reward += self.rw_stats.add("leak", self.w_leak)
        self.rw_stats.step(placed_id >= 0)
        # OFFENSIVE -> DEFENSIVE phase: once you have TAKEN a tower (defend the lead), OR OVERTIME
        # arrives and the win condition never broke through (cumulative enemy chip <
        # env.xbow_success_frac of a tower). Both disjuncts are live for this deck.
        my_c, op_c = self.eng.crowns(0), self.eng.crowns(1)
        self._enemy_chip_total += chip0
        if not self._defensive and (
                my_c >= 1
                or (self.eng.t >= self._double_time
                    and self._enemy_chip_total < self.eng.towers[1][0].max_hp * self.wincon_success_frac)):
            self._defensive = True
        # --- OUTCOME compass (DEMOTED: winning is not the objective, just a faint direction) ---
        # CONVEX tower-chip proxy: partial chip is worth sub-proportionally little; the CROWN below is the
        # big JUMP when a tower is actually destroyed (a tower at 1-2 HP still works -> worth far less).
        reward += self._settle_spell_casts()   # spells that landed since the last step
        ep = self._chip_progress(self.eng.towers[1])
        reward += self.rw_stats.add("chip_offence", (ep - self._prev_chip_prog) * self.tower_chip_scale)
        self._prev_chip_prog = ep
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
