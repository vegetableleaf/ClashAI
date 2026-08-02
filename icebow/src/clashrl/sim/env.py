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
from .engine import SimEngine, build_spec
from .meta_decks import load_meta_decks
from .opponents import make_opponent
from . import view

Action = Tuple[int, int, int]
_THREAT_DIM = 16
_DEFEAT_CAP = 0.15
_VALUE_NORM = 10.0   # elixir-value normaliser: this many elixir of effective value eliminated per step = 1.0
_VALUE_CAP = 1.0     # per-step clip on the (normalised) value-elimination reward


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
        self.threat_dim = _THREAT_DIM + (card_threat.IDENTITY_DIM if self.use_detector else 0)

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
        self.counter_reward = float(cfg.get("rewards", "counter_reward", default=0.5))

        r = lambda k, d: float(cfg.get("rewards", k, default=d))  # noqa: E731
        self.w_win = r("win", 10.0); self.w_loss = r("loss", -15.0)
        self.w_take = r("take_enemy_tower", 3.0); self.w_lose = r("lose_own_tower", -3.0)
        self.hp_scale = r("hp_scale", 2.0); self.troop_defeat = r("troop_defeat", 3.0)
        # ELIXIR-EFFICIENCY: also reward eliminating an enemy's REMAINING effective value (its deck elixir
        # cost x remaining-HP fraction, ground truth). A fresh Musketeer is worth far more than a near-dead
        # one -> the policy learns to spend for max impact per elixir and NOT over-kill nearly-dead units.
        self.value_defeat = r("value_defeat", 0.6)
        self.xbow_wc = r("xbow_wc_reward", 1.0); self.xbow_def = r("xbow_defense_reward", 0.3)
        self.xbow_mis = r("xbow_misplace_penalty", -0.75); self.miner_chip = r("miner_chip_reward", 0.6)
        self.shaping_cap = r("shaping_match_cap", 8.0)
        self.xbow_range = float(cfg.get("env", "xbow_range", default=0.36))
        self.xbow_def_y = float(cfg.get("env", "xbow_defense_y", default=0.62))
        self.rocket_ids = {i for i, k in enumerate(self.deck_keys) if _base(k) == "rocket"}
        self.log_ids = {i for i, k in enumerate(self.deck_keys) if _base(k) == "the_log"}
        self.log_reset = r("log_reset_reward", 0.3)          # The Log knocked a push back on YOUR side (buys time)
        self.log_swarm_unit = r("log_swarm_unit", 0.1)       # + per enemy unit it caught (a swarm / barrel wipe)
        self.log_air_penalty = r("log_air_penalty", -0.5)    # The Log (ground-only) dropped onto AIR units = wasted
        self.rd_ids = {i for i, k in enumerate(self.deck_keys) if _base(k) == "royal_delivery"}
        self.rd_hit = r("rd_hit_reward", 0.5)                # Royal Delivery blast landed ON an enemy mass (air+ground)
        self.rd_hit_unit = r("rd_hit_unit", 0.15)            # + per enemy unit caught in the blast
        self.rd_whiff = r("rd_whiff_penalty", -0.5)          # RD on empty ground = the AoE + recruit wasted
        self.rd_radius = float(cfg.get("env", "rd_radius", default=0.11))  # ~ the engine spell_radius for RD
        self.miner_king_penalty = r("miner_king_penalty", -2.0)  # Miner on the enemy KING wakes it early -> bad trade
        # icebow OFFENSE->DEFENSE transition: if the X-Bow hasn't chipped >= xbow_success_frac of a tower by
        # double elixir (or once you TAKE a tower), flip to a DEFENSIVE X-Bow (back-centre) + rocket-cycle
        # doctrine -- rocket-at-tower becomes the only sanctioned tower damage; everything else defends/cycles.
        self.xbow_success_frac = float(cfg.get("env", "xbow_success_frac", default=0.30))
        self.defensive_rocket_reward = r("defensive_rocket_reward", 0.3)
        # ROCKET COMBO: rocket a princess tower that ALSO catches a valuable, rocket-(almost)-one-shottable
        # enemy support (the "rocket the Musketeer behind the tower" 2-for-1: tower chip + a card-advantage kill).
        self.rocket_combo_reward = r("rocket_combo_reward", 3.0)
        self.rocket_combo_hp_frac = float(cfg.get("env", "rocket_combo_hp_frac", default=1.5))  # support ~one-shot: hp <= rocket_dmg x this
        self.rocket_combo_radius = float(cfg.get("env", "rocket_combo_radius", default=0.11))    # support within this of the aimed tower
        self._rocket_dmg = float(self.specs[next(iter(self.rocket_ids))].spell_dmg) if self.rocket_ids else 0.0
        self.spell_aim_radius = float(cfg.get("env", "spell_tower_aim_radius", default=0.12))
        # CYCLE-BAIT: opponents drop a LONE Skeletons / spirit (<= cycle_bait_elixir_max elixir) at the bridge
        # purely to cycle; spending a 3-4 elixir defender on a ~1-elixir troop that barely reaches the tower is a
        # bad trade -> penalise it UNLESS a real threat (bigger card / tower-targeter) is alongside. See
        # _wasted_cycle_defense. SIM-only (ground-truth card ID); the live-native version needs the detector.
        self.cycle_waste_penalty = r("cycle_waste_penalty", -0.6)
        self.cycle_bait_elixir_max = int(cfg.get("env", "cycle_bait_elixir_max", default=1))
        self.cycle_waste_min_elixir = int(cfg.get("env", "cycle_waste_min_elixir", default=3))
        self.cycle_threat_y = float(cfg.get("env", "cycle_threat_y", default=0.45))
        self._double_time = float(cfg.get("sim", "regulation_s", default=180.0)) - 60.0  # 2x elixir start
        self.punish_xbow_reward = r("punish_xbow_reward", 1.0)
        self.beatdown_punish_elixir = int(cfg.get("env", "beatdown_punish_elixir", default=7))
        self.beatdown_punish_window = float(cfg.get("env", "beatdown_punish_window_s", default=3.0))
        self.king_behind_y = float(cfg.get("env", "enemy_king_behind_y", default=0.18))
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

    # -- hand cycle --------------------------------------------------------
    def _hand_ids(self):
        return self.cycle[:4]

    def _update_vectors(self):
        self.hand_vec[:] = 0.0
        for i in self._hand_ids():
            self.hand_vec[i] = 1.0
        self.next_vec[:] = 0.0
        if len(self.cycle) > 4:
            self.next_vec[self.cycle[4]] = 1.0
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
            view.identity_items(self.eng, 0, self.detector_cards), self.db,
            prev_depth=self._prev_ident_depth, dt=self.agent_dt, horizon=self.predict_horizon)
        self._prev_ident_depth = float(self._threat_id[7])
        return np.concatenate([base, self._threat_id]).astype(np.float32)

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
        self._prev_mass = 0.0
        self._prev_evalue = 0.0
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
        self._punish_lane_x = None       # beatdown-punish: bridge X-Bow the OPPOSITE lane to their expensive drop
        self._punish_until = -1.0
        self._punish_seen_t = -1.0
        self._reset_vectors()
        self._update_vectors()
        return self._last_obs

    def _bonus(self, credit: float) -> float:
        if credit <= 0.0:
            return credit
        allowed = min(credit, max(0.0, self.shaping_cap - self._match_bonus))
        self._match_bonus += allowed
        return allowed

    def _placement_reward(self, card_id: int, nx: float, ny: float) -> float:
        princesses = [t for t in self.eng.towers[1][:2] if t.alive]
        d = min((np.hypot(nx - t.x, ny - t.y) for t in princesses), default=1.0)
        if card_id in self.xbow_ids:
            if (self._punish_lane_x is not None and self.eng.t <= self._punish_until
                    and abs(nx - self._punish_lane_x) <= 0.12 and ny <= 0.55):
                return self.punish_xbow_reward           # counter-push: bridge X-Bow punishing a beatdown's expensive drop
            back_centre = ny >= self.xbow_def_y and abs(nx - 0.48) <= 0.18
            if self._defensive:                              # DEFENSIVE: back-centre snipe only; forward is wrong now
                return self.xbow_def if back_centre else self.xbow_mis
            if d <= self.xbow_range:                         # OFFENSIVE: forward, in tower range = win condition
                return self.xbow_wc
            return self.xbow_def if back_centre else self.xbow_mis
        if card_id in self.rocket_ids:
            if self._rocket_combo(nx, ny):                   # rocket a princess tower + a valuable support in one blast
                return self.rocket_combo_reward              # 2-for-1: big tower chip AND a card-advantage kill
            if self._defensive and d <= self.spell_aim_radius:
                return self.defensive_rocket_reward          # rocket-cycle is the win path once defensive
        if card_id in self.miner_ids:
            king = self.eng.towers[1][2]                     # [L princess, R princess, KING]
            if king.alive and np.hypot(nx - king.x, ny - king.y) <= 0.09:
                return self.miner_king_penalty               # Miner on the enemy KING wakes it early -> bad trade
            if d <= 0.09:
                return self.miner_chip
        if card_id in self.log_ids and ny >= 0.5:            # The Log on YOUR side (past the sim river) onto a
            near = [u for u in self.eng.units if u.team == 1  # push -> knock it back where your towers help
                    and abs(u.x - nx) <= 0.12 and abs(u.y - ny) <= 0.14]
            ground = [u for u in near if not u.spec.flying]  # the Log is GROUND-ONLY (can't touch air)
            if ground:
                return self.log_reset + min(len(ground), 4) * self.log_swarm_unit
            if near:                                         # only AIR units there -> the Log is wasted on them
                return self.log_air_penalty
        if card_id in self.rd_ids:                           # Royal Delivery: an AREA blast (air+ground) + a Recruit --
            near = [u for u in self.eng.units if u.team == 1  # land it ON the enemy push, NOT to the side / back
                    and abs(u.x - nx) <= self.rd_radius and abs(u.y - ny) <= self.rd_radius]
            if near:
                return self.rd_hit + min(len(near), 5) * self.rd_hit_unit   # reward the group it blasts
            return self.rd_whiff                             # empty ground -> the blast + recruit wasted
        if self._wasted_cycle_defense(card_id, ny):          # a 3-4 elixir defender on LONE cycle bait = bad trade
            return self.cycle_waste_penalty
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

    def _wasted_cycle_defense(self, card_id: int, ny: float) -> bool:
        """True when a SIGNIFICANT card (>= cycle_waste_min_elixir) is placed DEFENSIVELY (your half) while the
        ONLY enemy on your side is cheap CYCLE bait (Skeletons / spirits, <= cycle_bait_elixir_max elixir).
        Opponents drop those solo just to cycle, so a 3-4 elixir card spent on a ~1-elixir troop that barely
        reaches the tower is a big elixir loss. Suppressed the moment a REAL threat (a bigger card, or a
        tower-targeter like a Miner behind your tower) is alongside the bait -- then you SHOULD defend."""
        if self.specs[card_id].elixir < self.cycle_waste_min_elixir:
            return False                                 # cheap answers (The Log / your own spirits) trade fine
        if ny < 0.5:                                     # only DEFENSIVE placements on your half; offense is exempt
            return False
        onside = [u for u in self.eng.units if u.team == 1 and u.spec.kind == "troop"
                  and u.y >= self.cycle_threat_y]
        if not onside:
            return False                                 # nothing on your side -> premature-defense covers that
        real = any(u.spec.elixir > self.cycle_bait_elixir_max or u.spec.building_only for u in onside)
        return not real                                  # only cheap cycle bait present -> defending it is a waste

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

    def step(self, action: Action):
        play, card_id, cell = action
        reward = 0.0
        if play and 0 <= card_id < self.n_cards and card_id in self._hand_ids():
            spec = self.specs[card_id]
            cell = self.actions.deploy_clamp(card_id in self.anywhere_ids, cell)
            nx, ny = self.actions.cell_center(cell % self.gw, cell // self.gw)
            if self.eng.deploy(0, spec, nx, ny):               # affordable + placed
                reward += self._bonus(self._placement_reward(card_id, nx, ny))
                if self.use_detector and card_threat.counters(self._deck_profiles[card_id], self._threat_id):
                    reward += self._bonus(self.counter_reward)  # right role-counter to a RECOGNISED threat
                idx = self.cycle.index(card_id)                # cycle the played card to the back
                self.cycle.append(self.cycle.pop(idx))
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
        # --- reward from ground truth ---
        reward += self._bonus((chip0 / self.eng.princess_hp) * self.hp_scale)   # enemy-tower chip (offence)
        reward -= (chip1 / self.eng.princess_hp) * abs(self.w_lose)             # your-tower chip (defence)
        my_c, op_c = self.eng.crowns(0), self.eng.crowns(1)
        if my_c > self._prev_my_crowns:
            reward += self.w_take * (my_c - self._prev_my_crowns)
        if op_c > self._prev_op_crowns:
            reward += self.w_lose * (op_c - self._prev_op_crowns)
        self._prev_my_crowns, self._prev_op_crowns = my_c, op_c
        # OFFENSIVE -> DEFENSIVE phase (icebow): once you've TAKEN a tower (defend the lead), OR double elixir
        # arrives and the X-Bow never broke through (cumulative enemy chip < xbow_success_frac of a tower),
        # flip to defence -- rocket-cycle becomes the tower damage; the X-Bow reward moves to back-centre.
        self._enemy_chip_total += chip0
        if not self._defensive and (
                my_c >= 1
                or (self.eng.t >= self._double_time
                    and self._enemy_chip_total < self.eng.princess_hp * self.xbow_success_frac)):
            self._defensive = True
        # BEATDOWN PUNISH: opponent dropped a 7+ elixir TROOP behind their king during 1x elixir -> open a
        # short window to reward an offensive bridge X-Bow in the OPPOSITE lane (punish the committed play).
        if self._matchup == "beatdown" and self.eng.t < self._double_time:
            ld = self.eng.last_deploy[1]
            if ld is not None:
                spec_e, ex_x, ex_y, ex_t = ld
                if (ex_t > self._punish_seen_t and spec_e.kind == "troop"
                        and spec_e.elixir >= self.beatdown_punish_elixir and ex_y <= self.king_behind_y):
                    self._punish_seen_t = ex_t
                    self._punish_lane_x = 0.75 if ex_x < 0.5 else 0.25
                    self._punish_until = self.eng.t + self.beatdown_punish_window
        mass = self.eng.enemy_mass(0)
        delta = self._prev_mass - mass                                          # potential-based troop shaping
        if abs(delta) > 0.005:
            reward += float(np.clip(delta, -_DEFEAT_CAP, _DEFEAT_CAP)) * self.troop_defeat
        self._prev_mass = mass
        # ELIXIR-EFFICIENCY: potential-based reward for eliminating enemy EFFECTIVE VALUE (elixir x HP-frac).
        # Nets to the value actually removed over each unit's life -> favours killing HEALTHY, valuable units
        # and makes over-killing near-dead ones barely worth anything (their remaining value is already low).
        evalue = self._enemy_value()
        edelta = self._prev_evalue - evalue
        if abs(edelta) > 0.02:
            reward += float(np.clip(edelta / _VALUE_NORM, -_VALUE_CAP, _VALUE_CAP)) * self.value_defeat
        self._prev_evalue = evalue

        done = self.eng.done
        outcome = self.eng.outcome
        if done:
            reward += self.w_win if outcome == "win" else self.w_loss if outcome == "loss" else -1.0
        self._update_vectors()
        info = {"outcome": outcome, "crowns": (my_c, op_c), "defensive": self._defensive}
        return self._last_obs, float(reward), done, info
