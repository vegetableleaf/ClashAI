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
from .engine import SimEngine, build_spec
from .meta_decks import load_meta_decks
from .opponents import make_opponent

Action = Tuple[int, int, int]
_THREAT_DIM = 16
_DEFEAT_CAP = 0.15


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
        self.threat_dim = _THREAT_DIM

        def _base(k):
            return k[:-4] if k.endswith("_evo") else k
        self.anywhere_ids = {i for i, k in enumerate(self.deck_keys) if _base(k) in ("rocket", "miner")}
        self.miner_ids = {i for i, k in enumerate(self.deck_keys) if _base(k) == "miner"}
        self.xbow_ids = {i for i, k in enumerate(self.deck_keys) if _base(k) == "x_bow"}

        r = lambda k, d: float(cfg.get("rewards", k, default=d))  # noqa: E731
        self.w_win = r("win", 10.0); self.w_loss = r("loss", -15.0)
        self.w_take = r("take_enemy_tower", 3.0); self.w_lose = r("lose_own_tower", -3.0)
        self.hp_scale = r("hp_scale", 2.0); self.troop_defeat = r("troop_defeat", 3.0)
        self.xbow_wc = r("xbow_wc_reward", 1.0); self.xbow_def = r("xbow_defense_reward", 0.3)
        self.xbow_mis = r("xbow_misplace_penalty", -0.75); self.miner_chip = r("miner_chip_reward", 0.6)
        self.shaping_cap = r("shaping_match_cap", 8.0)
        self.xbow_range = float(cfg.get("env", "xbow_range", default=0.36))
        self.xbow_def_y = float(cfg.get("env", "xbow_defense_y", default=0.62))
        self.agent_dt = float(cfg.get("sim", "agent_dt", default=1.0))
        self.sub_dt = float(cfg.get("sim", "sub_dt", default=0.1))

        self.eng = SimEngine(cfg, self.db, self.rng)
        self._reset_vectors()

    def _reset_vectors(self):
        self._last_obs = np.zeros(self.obs_shape, dtype=np.uint8)
        self.hand_vec = np.zeros(self.n_cards, np.float32)
        self.next_vec = np.zeros(self.n_cards, np.float32)
        self.elixir_vec = np.zeros(1, np.float32)
        self.threat_vec = np.zeros(self.threat_dim, np.float32)
        self.elixir = 0
        self._last_frame = self._last_obs

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
        enemy (team-1) units on YOUR half. Not a 1:1 layout -- enough to condition on in sim."""
        v = np.zeros(self.threat_dim, np.float32)
        foes = [u for u in self.eng.units if u.team == 1 and u.y >= 0.5]
        if not foes:
            return v
        mass = sum(min(1.0, u.hp / 800.0) for u in foes)
        biggest = max(u.hp for u in foes) / 3000.0
        cx = sum(u.x for u in foes) / len(foes)
        depth = (max(u.y for u in foes) - 0.5) / 0.5           # how far past the river toward your king
        v[0] = min(1.0, mass)
        v[1] = min(1.0, len(foes) / 6.0)
        v[2] = min(1.0, biggest)
        v[3] = 1.0 if cx < 0.4 else 0.0                        # left lane
        v[4] = 1.0 if cx > 0.6 else 0.0                        # right lane
        v[5] = min(1.0, max(0.0, depth))
        return v

    def _render(self) -> np.ndarray:
        oh, ow, _ = self.obs_shape
        img = np.zeros((oh, ow, 3), np.uint8)
        img[:, :] = (25, 80, 25)                               # grass (BGR)
        img[oh // 2, :] = (120, 90, 30)                        # river line
        for team, col in ((0, (230, 90, 60)), (1, (60, 60, 230))):   # you = blue, enemy = red (BGR)
            for tw in self.eng.towers[team]:
                if not tw.alive:
                    continue
                cxp, cyp = int(tw.x * ow), int(tw.y * oh)
                hw = 3 if tw.king else 2
                img[max(0, cyp - hw):cyp + hw + 1, max(0, cxp - hw):cxp + hw + 1] = col
        for u in self.eng.units:
            if u.hp <= 0:
                continue
            cxp, cyp = int(u.x * ow), int(u.y * oh)
            if 0 <= cyp < oh and 0 <= cxp < ow:
                img[cyp, cxp] = (230, 90, 60) if u.team == 0 else (60, 60, 230)
        return img

    # -- lifecycle ---------------------------------------------------------
    def reset(self) -> np.ndarray:
        self.eng.reset()
        self.opponent = make_opponent(self.cfg, self.db, self.rng, self.meta_pool)
        self.cycle = list(range(self.n_cards))
        self.rng.shuffle(self.cycle)
        self._match_bonus = 0.0
        self._prev_mass = 0.0
        self._prev_my_crowns = 0
        self._prev_op_crowns = 0
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
        if card_id in self.xbow_ids:
            d = min((np.hypot(nx - t.x, ny - t.y) for t in princesses), default=1.0)
            if d <= self.xbow_range:
                return self.xbow_wc
            if ny >= self.xbow_def_y and abs(nx - 0.48) <= 0.18:
                return self.xbow_def
            return self.xbow_mis
        if card_id in self.miner_ids:
            d = min((np.hypot(nx - t.x, ny - t.y) for t in princesses), default=1.0)
            if d <= 0.09:
                return self.miner_chip
        return 0.0

    def step(self, action: Action):
        play, card_id, cell = action
        reward = 0.0
        if play and 0 <= card_id < self.n_cards and card_id in self._hand_ids():
            spec = self.specs[card_id]
            cell = self.actions.deploy_clamp(card_id in self.anywhere_ids, cell)
            nx, ny = self.actions.cell_center(cell % self.gw, cell // self.gw)
            if self.eng.deploy(0, spec, nx, ny):               # affordable + placed
                reward += self._bonus(self._placement_reward(card_id, nx, ny))
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
        mass = self.eng.enemy_mass(0)
        delta = self._prev_mass - mass                                          # potential-based troop shaping
        if abs(delta) > 0.005:
            reward += float(np.clip(delta, -_DEFEAT_CAP, _DEFEAT_CAP)) * self.troop_defeat
        self._prev_mass = mass

        done = self.eng.done
        outcome = self.eng.outcome
        if done:
            reward += self.w_win if outcome == "win" else self.w_loss if outcome == "loss" else -1.0
        self._update_vectors()
        info = {"outcome": outcome, "crowns": (my_c, op_c)}
        return self._last_obs, float(reward), done, info
