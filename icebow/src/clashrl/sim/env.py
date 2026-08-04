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

import random
from typing import Tuple

import numpy as np

from ..actions import ActionSpace
from ..cards import CardDB
from .. import card_threat
from .. import interactions
from ..cycle import cycle_vector
from .engine import SimEngine, build_spec
from .meta_decks import load_meta_decks
from .opponents import make_opponent
from . import view

Action = Tuple[int, int, int]
_THREAT_DIM = 16


class SimMatchEnv:
    def __init__(self, cfg, seed: int = 0):
        self.cfg = cfg
        self.rng = random.Random(seed)
        self.db = CardDB(cfg)
        self.actions = ActionSpace(cfg)
        self.gw, self.gh = int(self.actions.gw), int(self.actions.gh)
        self.n_cells = int(self.actions.n_cells)
        self.deck_keys = self.db.deck_identities()
        self.deck_card_levels = self.db.deck_levels()
        self.n_cards = max(1, len(self.deck_keys))
        self.specs = [build_spec(self.db, k, lvl) for k, lvl in zip(self.deck_keys, self.deck_card_levels)]
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
        self.sight_range = float(cfg.get("sim", "sight_range", default=0.12))
        self.threat_dim = (_THREAT_DIM
                           + ((card_threat.IDENTITY_DIM + card_threat.OPP_MEMORY_DIM)
                              if self.use_detector else 0)
                           + (interactions.INTERACTION_DIM if self.use_interactions else 0))

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
        self.value_norm = float(cfg.get("env", "value_norm", default=10.0))             # elixir-value normaliser for the trade term
        self.trade_cap = float(cfg.get("env", "trade_cap", default=1.0))                # per-step clip on the trade term
        self.xbow_range = float(cfg.get("env", "xbow_range", default=0.36))
        self.xbow_front = float(cfg.get("env", "xbow_defense_front", default=0.52))
        self.xbow_back = float(cfg.get("env", "xbow_defense_back", default=0.62))
        self.xbow_deep_frac = float(cfg.get("rewards", "xbow_deep_frac", default=0.25))
        self.rocket_ids = {i for i, k in enumerate(self.deck_keys) if _base(k) == "rocket"}
        self.xbow_success_frac = float(cfg.get("env", "xbow_success_frac", default=0.30))
        self.rocket_combo_hp_frac = float(cfg.get("env", "rocket_combo_hp_frac", default=1.5))  # support ~one-shot
        self.rocket_combo_radius = float(cfg.get("env", "rocket_combo_radius", default=0.11))   # support near the aimed tower
        self._rocket_dmg = float(self.specs[next(iter(self.rocket_ids))].spell_dmg) if self.rocket_ids else 0.0
        self.spell_aim_radius = float(cfg.get("env", "spell_tower_aim_radius", default=0.12))
        # (soft) discourage a DAMAGE spell cast into emptiness (no unit in its blast + not aimed at a tower)
        self.damage_spell_ids = {i for i in range(self.n_cards)
                                 if self.specs[i].kind == "spell" and self.specs[i].spell_dmg > 0.0}
        self.w_spell_waste = r("spell_waste", -0.3)
        self.spell_waste_radius = float(cfg.get("env", "spell_waste_radius", default=0.14))
        self._double_time = float(cfg.get("sim", "regulation_s", default=180.0)) - 60.0  # 2x elixir start
        self.split_lane_counters = set(cfg.get("env", "split_lane_counter_cards",
                                               default=["royal_recruits", "royal_hogs"]))
        self.agent_dt = float(cfg.get("sim", "agent_dt", default=1.0))
        self.sub_dt = float(cfg.get("sim", "sub_dt", default=0.1))

        self.eng = SimEngine(cfg, self.db, self.rng)
        # Optional hook: train_sim sets this to inject SELF-PLAY opponents (a frozen past policy) mixed
        # with the scripted meta bots. Called with `self` in reset(); default None = always scripted.
        self.opponent_provider = None
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
        self._opp_mem.reset()

    # -- hand cycle --------------------------------------------------------
    def _hand_ids(self):
        return self.cycle[:4]

    def _update_vectors(self):
        self.hand_vec[:] = 0.0
        for i in self._hand_ids():
            self.hand_vec[i] = 1.0
        # graded UPCOMING-order vector (Next=1.0 grading down for the hidden cards) from the true
        # ordered queue -- lets the policy plan which cards to cycle toward. Superset of a next one-hot.
        self.next_vec[:] = cycle_vector(self.cycle, self.n_cards)
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
        mem = self._opp_mem.update(
            view.apply_detector_noise(view.opponent_memory_items(self.eng, 0, self.detector_cards),
                                      self.det_recall, self.det_precision, self.rng, self.detector_cards,
                                      self.det_recall_by_card))
        parts = [base, self._threat_id, mem]
        if self.use_interactions:                     # who is predicted to be marching at which tower
            units, mine_t, en_t = view.interaction_state(self.eng, 0, self.detector_cards, self.rng,
                                                         self.det_recall, self.det_recall_by_card)
            parts.append(interactions.interaction_vector(units, mine_t, en_t, self.db, self.sight_range))
        return np.concatenate(parts).astype(np.float32)

    def _render(self) -> np.ndarray:
        oh, ow, _ = self.obs_shape
        return view.render_obs(self.eng, oh, ow, team=0)

    # -- lifecycle ---------------------------------------------------------
    def reset(self) -> np.ndarray:
        self.eng.reset()
        self.opponent = (self.opponent_provider(self) if self.opponent_provider is not None
                         else make_opponent(self.cfg, self.db, self.rng, self.meta_pool))
        self.cycle = list(range(self.n_cards))
        self.rng.shuffle(self.cycle)
        self._match_bonus = 0.0
        self._prev_evalue = 0.0
        self._prev_chip_prog = 0.0       # convex enemy-tower chip progress (offense)
        self._prev_chip_prog_def = 0.0   # convex own-tower chip progress (defense)
        self._prev_my_crowns = 0
        self._prev_op_crowns = 0
        self._defensive = False          # icebow phase: False = offensive X-Bow win-condition; True = defence + rocket-cycle
        self._enemy_chip_total = 0.0     # cumulative enemy-tower HP the X-Bow/rocket has chipped (X-Bow success gauge)
        # MATCHUP-aware doctrine: vs a fast CYCLE or heavy BEATDOWN deck -- or a SPLIT-LANE deck built on
        # Royal Recruits / Royal Hogs (they hard-counter X-Bow: a wide two-lane push a single X-Bow can't
        # cover) -- play EXCLUSIVELY defensive X-Bow + rocket-cycle for the WHOLE match. vs control/siege
        # it's offensive-first (transition per the 2x/tower rule).
        self._matchup = getattr(self.opponent, "style", "control")
        opp_cards = set(getattr(self.opponent, "cards", ()) or ())
        self._split_lane_counter = bool(opp_cards & self.split_lane_counters)
        if self._matchup in ("cycle", "beatdown") or self._split_lane_counter:
            self._defensive = True
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

    def _threat_response(self, card_id: int, nx: float, ny: float) -> float:
        """(1) THREAT-RESPONSE correctness: did you play the KB-correct counter to the ASSESSED threat,
        placed to intercept it? Right counter in the threat's lane -> +; the WRONG role dropped as a
        defence, or a pure defender played with no threat (premature) -> -. Offensive placements are
        judged by wincon_exec / the trade term, not here."""
        tid = self._threat_id
        prof = self._deck_profiles[card_id]
        if tid is None or len(tid) < card_threat.IDENTITY_DIM or tid[0] < 0.5:
            if ny >= 0.5 and not prof.win_condition and not prof.spell and card_id not in self.miner_ids:
                return self.w_threat_miss * 0.4          # a defender played on a QUIET board = premature (small)
            return 0.0
        tx, ty = self._threat_pos()
        intercept = abs(nx - tx) <= self.intercept_lane and ny >= 0.5   # same lane, on your defensive half
        if card_threat.counters(prof, tid):
            return self.w_threat_response if intercept else 0.0          # right counter; full only if it intercepts
        return self.w_threat_miss if intercept else 0.0                  # wrong role dropped as a defence = a misread

    def _threat_miss_idle(self) -> float:
        """No play while an ANSWERABLE threat is present (a counter is in hand AND affordable) = a missed
        defence. Uncapped penalty (this is the 'ignored the push' case the old idle_penalty covered)."""
        tid = self._threat_id
        if tid is None or len(tid) < card_threat.IDENTITY_DIM or tid[0] < 0.5:
            return 0.0
        for cid in self._hand_ids():
            if (card_threat.counters(self._deck_profiles[cid], tid)
                    and self.specs[cid].elixir <= self.eng.elixir[0]):
                return self.w_threat_miss
        return 0.0

    def _wincon_exec(self, card_id: int, nx: float, ny: float) -> float:
        """(3) WIN-CONDITION execution: the deck's doctrine done right for the current phase -- X-Bow
        forward-in-range (offensive) / back-centre (defensive), Miner chipping the princess (not the king),
        rocket-cycle chip or the rocket 2-for-1. + when executed correctly, - when the win condition is
        thrown away. Non-win-condition cards return 0 (they're scored by threat_response / the trade term)."""
        princesses = [t for t in self.eng.towers[1][:2] if t.alive]
        d = min((np.hypot(nx - t.x, ny - t.y) for t in princesses), default=1.0)
        if card_id in self.xbow_ids:
            # "back-centre" = the CENTER INTERCEPT band behind the bridge (where a Tesla would sit), NOT
            # behind the princess towers. In-band = full credit; DEEPER than the towers = a small fraction
            # (soft shaping: rarely useful, but not punished like a true misplace).
            central = abs(nx - 0.48) <= 0.18
            in_band = central and self.xbow_front <= ny <= self.xbow_back
            behind = central and ny > self.xbow_back
            frac = 1.0 if in_band else (self.xbow_deep_frac if behind else 0.0)
            if self._defensive:                              # DEFENSIVE phase: centre-band only; forward is wrong now
                return self.w_wincon * frac if frac > 0.0 else self.w_wincon_mis
            if d <= self.xbow_range:                         # OFFENSIVE: forward, in tower range = win condition set
                return self.w_wincon
            return self.w_wincon * 0.4 * frac if frac > 0.0 else self.w_wincon_mis
        if card_id in self.rocket_ids:
            if self._rocket_combo(nx, ny):                   # rocket a princess tower + a valuable support = 2-for-1
                return self.w_wincon * self.combo_mult
            if self._defensive and d <= self.spell_aim_radius:
                return self.w_wincon * 0.6                   # rocket-cycle chip = sanctioned tower damage once defensive
            return 0.0
        if card_id in self.miner_ids:
            king = self.eng.towers[1][2]                     # [L princess, R princess, KING]
            if king.alive and np.hypot(nx - king.x, ny - king.y) <= 0.09:
                return self.w_wincon_mis                      # Miner on the enemy KING wakes it early -> bad trade
            if d <= 0.09:
                return self.w_wincon                          # Miner chipping the princess
        return 0.0

    def _rocket_combo(self, nx: float, ny: float) -> bool:
        """True when a rocket aimed at (nx, ny) hits an alive enemy PRINCESS tower AND catches a VALUABLE
        (4-6 elixir), rocket-(almost)-one-shottable enemy support troop in the same blast -- the classic
        'rocket the Musketeer behind the tower' 2-for-1 (tower chip + a card-advantage kill). The engine
        already applies the damage to both; this just REWARDS lining the two up so the policy learns it."""
        if self._rocket_dmg <= 0.0:
            return False
        tgt = next((t for t in self.eng.towers[1][:2]
                    if t.alive and np.hypot(nx - t.x, ny - t.y) <= self.spell_aim_radius), None)
        if tgt is None:
            return False
        for u in self.eng.units:
            if (u.team == 1 and u.spec.kind == "troop" and not u.spec.building_only
                    and 4 <= u.spec.elixir <= 6
                    and u.spec.hp <= self._rocket_dmg * self.rocket_combo_hp_frac
                    and np.hypot(u.x - tgt.x, u.y - tgt.y) <= self.rocket_combo_radius):
                return True
        return False

    def _needed_counter_coming(self, hand) -> bool:
        """True when the current hand has NO KB counter to the assessed threat but the deck DOES (an
        upcoming card) -- i.e. deliberately cycling toward that counter is worthwhile."""
        tid = self._threat_id
        if tid is None or len(tid) < card_threat.IDENTITY_DIM or tid[0] < 0.5:
            return False
        if any(card_threat.counters(self._deck_profiles[c], tid) for c in hand):
            return False                                     # already hold a counter -> no need to cycle
        return any(card_threat.counters(self._deck_profiles[c], tid)
                   for c in range(self.n_cards) if c not in hand)

    def _cycle_plan(self, card_id: int) -> float:
        """(4) CYCLE-PLAN correctness: reward a CHEAP play that advances toward a NEEDED counter you don't
        hold (but the deck does) when you have SPARE elixir -- deliberate cycling. Penalise cheap spam with
        no such plan and no spare elixir. Neutral otherwise. ``card_id`` = the card just played, or -1."""
        if card_id < 0 or self.specs[card_id].elixir > self.cycle_cheap_max:
            return 0.0                                       # only cheap 'cycle' cards qualify
        elx = self.eng.elixir[0]
        if self._needed_counter_coming(set(self._hand_ids())):
            return self.w_cycle_plan if elx >= self.cycle_spare_elixir else 0.0
        return self.w_cycle_waste if elx < self.cycle_spare_elixir else 0.0

    def _trade_reward(self, value_eliminated: float, spent: float) -> float:
        """(2) ELIXIR-TRADE correctness: potential-based (enemy effective value eliminated this step minus
        the elixir you spent), normalised + clipped. Trading UP (kill more value than you spent) -> +;
        overspending / whiffing -> -. Telescopes over the match so idling can't farm it."""
        net = (value_eliminated - spent) / self.value_norm
        return float(np.clip(net, -self.trade_cap, self.trade_cap)) * self.w_elixir_trade

    def _enemy_value(self) -> float:
        """Total REMAINING effective elixir value of the enemy's (team-1) troops = sum of each unit's deck
        elixir cost x its remaining-HP fraction (ground truth). Falls as you damage/kill units, so the
        per-step DROP is the value you actually eliminated -- weighted by how healthy + valuable it was.
        A card's elixir is split across its count (a Skeleton Army's 3 elixir spreads over ~15 skeletons)
        so a whole card is worth its elixir at full HP -- swarms don't inflate the value."""
        v = 0.0
        for u in self.eng.units:
            if u.team == 1 and u.spec.kind == "troop":
                frac = max(0.0, min(1.0, u.hp / u.spec.hp)) if u.spec.hp > 0 else 1.0
                v += (u.spec.elixir / max(1, u.spec.count)) * frac
        return v

    def _forced_expensive_spend(self, card_id: int, ny: float) -> bool:
        """A defensive spend is FORCED (waive its elixir-trade penalty) when a threat is recognised, the
        play is on your defensive half, and NO CHEAPER card in hand or the NEXT slot could counter that
        threat -- e.g. rocket the hogs/balloon, or centre X-Bow to pull a wincon, when Tesla is too deep in
        the cycle. Overspending when a cheaper answer WAS immediately available is NOT waived."""
        if ny < 0.5:
            return False                                  # offensive placements pay their spend normally
        tid = self._threat_id
        if tid is None or len(tid) < card_threat.IDENTITY_DIM or tid[0] < 0.5:
            return False
        my_elix = self.specs[card_id].elixir
        avail = set(self._hand_ids())
        if len(self.cycle) > 4:
            avail.add(self.cycle[4])                     # the NEXT (preview) card counts as immediately available
        for c in avail:
            if (c != card_id and self.specs[c].elixir < my_elix
                    and card_threat.counters(self._deck_profiles[c], tid)):
                return False                             # a cheaper counter was in hand / next -> not forced
        return True

    def _spell_no_target(self, nx: float, ny: float, spec) -> bool:
        """True when a DAMAGE spell is cast with NOTHING to hit -- no enemy unit within its blast radius AND
        not aimed at a live enemy princess tower (chipping a tower is a valid target). A SOFT nudge against
        casting into emptiness; env.spell_waste_radius is GENEROUS so near-miss / predictive casts aren't
        punished -- only truly empty ones."""
        for t in self.eng.towers[1][:2]:
            if t.alive and np.hypot(nx - t.x, ny - t.y) <= self.spell_aim_radius:
                return False                             # aimed at an enemy princess tower = a valid chip target
        rad = self.spell_waste_radius
        return not any(u.team == 1 and u.hp > 0 and np.hypot(nx - u.x, ny - u.y) <= rad
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

    def step(self, action: Action):
        play, card_id, cell = action
        reward = 0.0
        spent = 0.0
        placed_id = -1
        if play and 0 <= card_id < self.n_cards and card_id in self._hand_ids():
            spec = self.specs[card_id]
            cell = self.actions.deploy_clamp(card_id in self.anywhere_ids, cell)
            nx, ny = self.actions.cell_center(cell % self.gw, cell // self.gw)
            if self.eng.deploy(0, spec, nx, ny):               # affordable + placed
                spent = float(spec.elixir)
                placed_id = card_id
                if self._forced_expensive_spend(card_id, ny):
                    spent = 0.0            # forced defensive counter (no cheaper answer available) -> waive its spend
                reward += self._bonus(self._threat_response(card_id, nx, ny))   # (1) counter to the assessed threat
                reward += self._bonus(self._wincon_exec(card_id, nx, ny))       # (3) win-condition executed right
                reward += self._bonus(self._cycle_plan(card_id))                # (4) deliberate cycling
                if card_id in self.damage_spell_ids and self._spell_no_target(nx, ny, spec):
                    reward += self.w_spell_waste                                 # (soft) damage spell cast into emptiness
                idx = self.cycle.index(card_id)                                 # cycle the played card to the back
                self.cycle.append(self.cycle.pop(idx))
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
            if self.eng.done:
                break
        # (2) ELIXIR-TRADE correctness: signed potential-based enemy-value change (telescopes, anti-farm)
        # minus the elixir committed this step -> nets to (value removed - elixir spent) over the match.
        evalue = self._enemy_value()
        edelta = self._prev_evalue - evalue
        self._prev_evalue = evalue
        reward += self._trade_reward(edelta, spent)
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
