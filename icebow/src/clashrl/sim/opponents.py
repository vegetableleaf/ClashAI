"""Opponents for the sim. Two kinds:

* :class:`ScriptedBot` -- pilots a real meta deck (sampled from the meta-deck pool, see meta_decks.py)
  with simple, deck-agnostic heuristics whose aggression is set by the deck's inferred STYLE
  (cycle / control / beatdown / siege). Not strong -- just varied, plausible pressure so the policy
  learns robust responses across MANY decks.
* :class:`SelfPlayOpponent` -- pilots team 1 with a FROZEN past copy of the agent's own policy, viewing
  a MIRRORED board (see sim/view.py) so the same policy plays both sides. Snapshotted into a small
  league by train_sim and mixed in with the scripted bots (`sim.selfplay_prob`).
"""
from __future__ import annotations

from typing import List

import numpy as np

from .engine import build_spec
from .. import card_threat
from .. import interactions
from ..cycle import cycle_vector
from . import view


class ScriptedBot:
    """One heuristic action per agent step: defend the deepest threat in our half, else apply
    pressure per the deck's style (beatdown saves to ~full then commits; the rest chip more freely)."""

    def __init__(self, cfg, db, rng, cards: List[str], style: str, levels: "List[int] | None" = None):
        self.style = style
        self.cards = list(cards)                                  # deck card keys (for matchup detection)
        self.rng = rng
        levels = levels or [11] * len(cards)
        self.specs = [build_spec(db, k, lvl) for k, lvl in zip(cards, levels)]
        self._backline_done = False                              # one backline-support opening per match
        self._backline_prob = float(cfg.get("sim", "backline_support_prob", default=0.05))
        self._backline_until = float(cfg.get("sim", "backline_support_until_s", default=45.0))

    def act(self, eng) -> None:
        team = 1
        elix = eng.elixir[team]
        affordable = [s for s in self.specs if s.elixir <= elix]
        if not affordable:
            return
        # DEFEND: an enemy (team 0) unit has entered our half (y < 0.5)
        threats = [u for u in eng.units if u.team == 0 and u.y < 0.5]
        if threats:
            deepest = min(threats, key=lambda u: u.y)             # closest to our king
            troops = [s for s in affordable if s.kind == "troop" and not s.building_only]
            if troops:
                s = min(troops, key=lambda s: s.elixir)
                eng.deploy(team, s, deepest.x, max(0.12, deepest.y - 0.06))
                return
            spells = [s for s in affordable if s.kind == "spell"]
            if spells and len(threats) >= 3:
                s = min(spells, key=lambda s: s.elixir)
                eng.deploy(team, s, deepest.x, deepest.y)
                return
        # BACKLINE SUPPORT OPENING (control/beatdown): once, early, drop a mid-cost ranged support BEHIND the
        # king (the "Musketeer behind the tower" open) -- realistic pressure AND the setup the agent learns to
        # punish (rocket the support + tower for a 2-for-1).
        if (not self._backline_done and not threats and eng.t < self._backline_until
                and self.style in ("control", "beatdown") and self.rng.random() < self._backline_prob):
            supports = [s for s in affordable if s.kind == "troop" and not s.building_only
                        and 4 <= s.elixir <= 6 and not s.flying]
            if supports:
                self._backline_done = True
                eng.deploy(team, self.rng.choice(supports), self.rng.choice([0.25, 0.75]), 0.10)
                return
        # ATTACK
        if self.style == "beatdown" and elix < 9.5:
            return                                                # save up for a big push
        offense = [s for s in affordable if s.kind != "spell"]
        if not offense:
            return
        lane = self.rng.choice([0.25, 0.75])
        if self.style == "beatdown":
            tank = max(offense, key=lambda s: s.hp)               # heaviest unit BEHIND the king (deep back)
            eng.deploy(team, tank, lane, 0.10)
        elif self.style == "siege":
            sieges = [s for s in offense if s.siege] or offense
            eng.deploy(team, self.rng.choice(sieges), lane, 0.42)
        else:                                                     # cycle / control: chip at the bridge
            wc = [s for s in offense if s.building_only] or offense
            eng.deploy(team, self.rng.choice(wc), lane, 0.46)


def make_opponent(cfg, db, rng, pool: List[dict], level: "int | None" = None) -> ScriptedBot:
    """Sample a meta deck (weighted by its popularity) and pilot it per its inferred style. Each of its
    cards rolls a RANDOM level (sim.enemy_levels weighted by sim.enemy_level_weights -- default 13-16
    with 14 most likely, 16 least), so the opponent's card levels vary like a real ladder opponent.

    ``level`` (FAIR eval): if given, ALL the opponent's cards use this fixed level instead of the rolled
    ladder levels -- removing the level handicap. The roll still happens first so rng consumption (and
    thus the sampled deck sequence) is IDENTICAL to the handicapped path, making fair-vs-ladder an
    apples-to-apples comparison on the same matchups."""
    if not pool:
        from .meta_decks import load_meta_decks
        pool = load_meta_decks(cfg, db)
    weights = [max(0.01, float(d.get("weight", 1.0))) for d in pool]
    deck = rng.choices(pool, weights=weights, k=1)[0]
    lv = cfg.get("sim", "enemy_levels", default=[13, 14, 15, 16])
    lw = cfg.get("sim", "enemy_level_weights", default=[3, 5, 2, 1])
    levels = [rng.choices(lv, weights=lw, k=1)[0] for _ in deck["cards"]]
    if level is not None:
        levels = [int(level)] * len(deck["cards"])
    return ScriptedBot(cfg, db, rng, deck["cards"], deck["style"], levels)


class SelfPlayOpponent:
    """Pilots team 1 with a FROZEN copy of the agent's policy. The policy only ever learned team 0's
    point of view (you at the bottom, deploy low, attack up), so we show it a 180-degree MIRRORED board
    (sim/view.py) where team 1 sits at the bottom, run the exact same greedy gate/card/cell choice the
    trainer uses, then transform the chosen cell back to the engine frame before deploying. It plays the
    AGENT's deck (the only deck the policy understands) at random ladder levels, and cycles its hand the
    same way the env does, so it is a genuine self-mirror -- a strong, adaptive sparring partner."""

    def __init__(self, cfg, env, net, rng):
        self.rng = rng
        self.net = net                                           # frozen DQN (policy + gate), eval mode
        self.actions = env.actions
        self.db = env.db
        self.n_cards = env.n_cards
        self.gw, self.gh = env.gw, env.gh
        self.n_cells = env.n_cells
        self.obs_shape = env.obs_shape
        self.threat_dim = env.threat_dim
        self.use_detector = env.use_detector          # Stage 3: mirror the identity block for team 1
        self.detector_cards = env.detector_cards
        self.det_recall = env.det_recall              # mirror the sim detector-noise so a snapshot self sees
        self.det_precision = env.det_precision         # the same sparse/noisy identity signal it trained on
        self.det_recall_by_card = env.det_recall_by_card   # ...including the per-card recall override
        self.use_interactions = env.use_interactions   # mirror the troop-interaction block for team 1
        self.sight_range = env.sight_range
        self.agent_dt = env.agent_dt
        self.predict_horizon = env.predict_horizon
        self._prev_ident_depth = 0.0
        self._opp_mem = card_threat.OpponentMemory(env.db)   # per-match opponent memory (mirrors team 0)
        self.anywhere_ids = env.anywhere_ids
        self.deck_keys = env.deck_keys
        lv = cfg.get("sim", "enemy_levels", default=[13, 14, 15, 16])
        lw = cfg.get("sim", "enemy_level_weights", default=[3, 5, 2, 1])
        levels = [rng.choices(lv, weights=lw, k=1)[0] for _ in self.deck_keys]
        self.specs = [build_spec(self.db, k, lvl) for k, lvl in zip(self.deck_keys, levels)]
        # exposed so the env's matchup doctrine (reads opponent .style / .cards) still works
        from .meta_decks import classify_style
        self.cards = list(self.deck_keys)
        self.style = classify_style(self.db, self.deck_keys)
        self.cycle = list(range(self.n_cards))
        self.rng.shuffle(self.cycle)

    def _hand_ids(self):
        return self.cycle[:4]

    def act(self, eng) -> None:
        import torch

        oh, ow, _ = self.obs_shape
        obs = view.render_obs(eng, oh, ow, team=1)
        hand = np.zeros(self.n_cards, np.float32)
        for i in self._hand_ids():
            hand[i] = 1.0
        nxt = cycle_vector(self.cycle, self.n_cards)   # graded upcoming-order (matches the trained policy input)
        elx = np.array([eng.elixir[1] / 10.0], np.float32)
        base_dim = self.threat_dim \
            - ((card_threat.IDENTITY_DIM + card_threat.OPP_MEMORY_DIM) if self.use_detector else 0) \
            - (interactions.INTERACTION_DIM if self.use_interactions else 0)
        thr = view.threat_vector(eng, base_dim, team=1)
        if self.use_detector:
            ident = card_threat.identity_threat_vector(
                view.apply_detector_noise(view.identity_items(eng, 1, self.detector_cards),
                                          self.det_recall, self.det_precision, self.rng, self.detector_cards,
                                          self.det_recall_by_card),
                self.db, prev_depth=self._prev_ident_depth, dt=self.agent_dt, horizon=self.predict_horizon)
            self._prev_ident_depth = float(ident[7])
            mem = self._opp_mem.update(
                view.apply_detector_noise(view.opponent_memory_items(eng, 1, self.detector_cards),
                                          self.det_recall, self.det_precision, self.rng, self.detector_cards,
                                          self.det_recall_by_card))
            thr = np.concatenate([thr, ident, mem]).astype(np.float32)
        if self.use_interactions:                      # mirrored: team 1 sees ITS towers as 'mine'
            units, mine_t, en_t = view.interaction_state(eng, 1, self.detector_cards, self.rng,
                                                         self.det_recall, self.det_recall_by_card)
            ivec = interactions.interaction_vector(units, mine_t, en_t, self.db, self.sight_range)
            thr = np.concatenate([thr, ivec]).astype(np.float32)

        dev = next(self.net.parameters()).device
        obs_t = torch.from_numpy(obs).float().permute(2, 0, 1).unsqueeze(0).to(dev) / 255.0
        hand_t = torch.from_numpy(hand).unsqueeze(0).to(dev)
        nxt_t = torch.from_numpy(nxt).unsqueeze(0).to(dev)
        elx_t = torch.from_numpy(elx).unsqueeze(0).to(dev)
        thr_t = torch.from_numpy(thr).unsqueeze(0).to(dev)
        with torch.no_grad():
            cq, ceq, gq = self.net(obs_t, hand_t, nxt_t, elx_t, thr_t)
        cq = cq.masked_fill(hand_t < 0.5, float("-inf"))
        if gq[0, 0] >= gq[0, 1] + cq[0].max() + ceq[0].max():
            return                                               # gate says WAIT
        card = int(cq[0].argmax())
        cell = int(ceq[0].argmax())

        cell = self.actions.deploy_clamp(card in self.anywhere_ids, cell)
        lnx, lny = self.actions.cell_center(cell % self.gw, cell // self.gw)
        ex, ey = 1.0 - lnx, 1.0 - lny                            # mirror the local cell back to engine coords
        if eng.deploy(1, self.specs[card], ex, ey):
            idx = self.cycle.index(card)
            self.cycle.append(self.cycle.pop(idx))

