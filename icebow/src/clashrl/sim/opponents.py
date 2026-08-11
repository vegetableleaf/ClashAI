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
from ..cycle import cycle_vector
from .. import card_threat
from .. import interactions
from . import view

_NEG = -1e9   # finite mask value (matches train_sim_ppo; -inf can NaN through a softmax)


class ScriptedBot:
    """One heuristic action per agent step: defend the deepest threat in our half, else apply
    pressure per the deck's style (beatdown saves to ~full then commits; the rest chip more freely).

    ADAPTIVE mode (Tier-1 'smart opponents', training-only -- the eval benchmark stays frozen on
    non-adaptive bots): observation-driven counter-play vs the agent, each behaviour gated by a
    per-bot knowledge roll + a human reaction delay:
      * ANTI-SIEGE -- the meta response to icebow: an agent X-Bow on the field gets answered after
        ``reaction_s`` with a big spell (when the bow is supported) or their heaviest troop dropped
        on top of it.
      * COUNTER-HOLDING -- once the X-Bow has been SEEN, their heaviest troop is reserved as the
        siege answer (not spent on casual defence/cycle) unless elixir overflows.
      * DUMP PUNISH -- the agent committing 8+ elixir within ~6s gets punished immediately in the
        OPPOSITE lane (real players' core habit vs siege decks over-committing).
      * SPLIT-PUSH -- after SEEING one agent tornado, pushes alternate/split lanes so a single
        clump-pull can no longer catch the whole attack (the human counter to tornado value -- and
        exactly the pressure pattern that forces the agent to learn real tornado timing).
    """

    def __init__(self, cfg, db, rng, cards: List[str], style: str, levels: "List[int] | None" = None,
                 adaptive: bool = False):
        self.style = style
        self.cards = list(cards)                                  # deck card keys (for matchup detection)
        self.rng = rng
        levels = levels or [11] * len(cards)
        self.specs = [build_spec(db, k, lvl) for k, lvl in zip(cards, levels)]
        self._backline_done = False                              # one backline-support opening per match
        self._backline_prob = float(cfg.get("sim", "backline_support_prob", default=0.05))
        self._backline_until = float(cfg.get("sim", "backline_support_until_s", default=45.0))
        self.anywhere_prob = float(cfg.get("sim", "anywhere_deploy_prob", default=0.75))   # Miner-style tower drops
        # --- adaptive knobs (rolled per bot -> a POPULATION of skill levels, not one clone) ---
        self.adaptive = bool(adaptive)
        ad = cfg.get("sim", "adaptive", default={}) or {}
        rs = ad.get("reaction_s", [1.0, 3.0])
        self.reaction_s = rng.uniform(float(rs[0]), float(rs[1]))
        self.anti_siege_know = adaptive and rng.random() < float(ad.get("anti_siege_prob", 0.8))
        self.hold_counter = adaptive and rng.random() < float(ad.get("hold_counter_prob", 0.6))
        self.punish_know = adaptive and rng.random() < float(ad.get("punish_prob", 0.6))
        self.split_know = adaptive and rng.random() < float(ad.get("split_prob", 0.7))
        troops = [s for s in self.specs if s.kind == "troop" and not s.building_only and not s.flying]
        self._reserved = max(troops, key=lambda s: s.hp) if troops else None   # the held siege answer
        self._xbow_ever = False          # agent siege seen at least once this match
        self._siege_seen_t = None        # when the CURRENT bow was first seen (reaction delay)
        self._nado_seen = False          # agent tornado seen -> start splitting pushes
        self._spend: list = []           # (t, elixir, x) of observed agent deploys
        self._seen_deploy_t = -1.0
        self._punish_cd = 0.0
        self._flip = rng.random() < 0.5  # split-push lane alternator
        # HAND + CYCLE. A real opponent holds 4 of its 8 cards and must cycle the rest before it can
        # repeat one. Without this the bot chose from the WHOLE deck every step, so it could open the
        # same card twice in a row (and never ran out of its best answer) -- the agent was training
        # against a deck with no cycle cost at all.
        self.cycle = list(range(len(self.specs)))
        rng.shuffle(self.cycle)

    def _hand_specs(self):
        """The 4 cards currently in hand (the rest are cycling)."""
        return [self.specs[i] for i in self.cycle[:4]]

    def _play(self, eng, spec, x: float, y: float) -> bool:
        """Deploy + send that card to the back of the cycle. EVERY deploy goes through here, so no
        branch can bypass the cycle."""
        if not eng.deploy(1, spec, x, y):
            return False
        idx = next((i for i, s in enumerate(self.specs) if s is spec), -1)
        if idx >= 0 and idx in self.cycle:
            self.cycle.remove(idx)
            self.cycle.append(idx)
        return True

    # ---- observation (what a human sees: the agent's deploys) -----------------
    def _observe(self, eng) -> None:
        d = eng.last_deploy.get(0)
        if not d:
            return
        spec, x, _y, t = d
        if t == self._seen_deploy_t:
            return
        self._seen_deploy_t = t
        self._spend.append((t, float(spec.elixir), float(x)))
        if len(self._spend) > 24:
            self._spend.pop(0)
        if spec.base == "tornado":
            self._nado_seen = True
        if spec.siege:
            self._xbow_ever = True

    def _usable(self, affordable, elix):
        """Affordable specs minus the RESERVED siege answer while counter-holding (released when
        elixir overflows -- a human doesn't sit at 10 forever holding one card)."""
        if not (self.hold_counter and self._xbow_ever) or self._reserved is None or elix >= 9.5:
            return affordable
        return [s for s in affordable if s is not self._reserved]

    def _try_anti_siege(self, eng, affordable, elix) -> bool:
        if not self.anti_siege_know:
            return False
        team = 1
        bows = [u for u in eng.units
                if u.team == 0 and u.spec.siege and u.hp > 0 and u.deploy_left <= 0]
        if not bows:
            self._siege_seen_t = None
            return False
        self._xbow_ever = True
        xb = min(bows, key=lambda u: u.y)                        # the most forward bow
        if self._siege_seen_t is None:
            self._siege_seen_t = eng.t
        if eng.t - self._siege_seen_t < self.reaction_s:
            return False
        # supported bow + a big spell in hand -> spell it (fireball/lightning value); else heaviest
        # troop dropped ON TOP so it tanks/kills the bow (the classic anti-siege answer).
        support = sum(1 for u in eng.units
                      if u.team == 0 and u is not xb and u.hp > 0
                      and abs(u.x - xb.x) + abs(u.y - xb.y) < 0.16)
        spells = [s for s in affordable if s.kind == "spell" and s.spell_dmg >= 300]
        if support >= 2 and spells:
            s = max(spells, key=lambda sp: sp.spell_dmg)
            self._play(eng, s, xb.x, xb.y)
            self._siege_seen_t = None                            # re-arm (reacts again if the bow survives)
            return True
        troops = [s for s in affordable if s.kind == "troop" and not s.building_only and not s.flying]
        if troops:
            tank = max(troops, key=lambda s: s.hp)
            self._play(eng, tank, xb.x, max(0.08, xb.y - 0.05))
            self._siege_seen_t = None
            return True
        return False

    def _try_punish(self, eng, affordable) -> bool:
        if not self.punish_know or eng.t < self._punish_cd:
            return False
        recent = [(t, e, x) for (t, e, x) in self._spend if eng.t - t <= 6.0]
        tot = sum(e for _, e, _ in recent)
        if tot < 8.0:
            return False
        mean_x = sum(x for _, _, x in recent) / len(recent)
        lane = eng.lanes[1] if mean_x < 0.5 else eng.lanes[0]    # punish the OPPOSITE lane
        offense = [s for s in affordable if s.kind != "spell"]
        if not offense:
            return False
        wc = [s for s in offense if s.building_only] or offense
        s = max(wc, key=lambda sp: sp.elixir)                    # commit the punish, don't poke
        self._play(eng, s, lane, 0.46)
        self._punish_cd = eng.t + 15.0
        return True

    def act(self, eng) -> None:
        team = 1
        if self.adaptive:
            self._observe(eng)
        elix = eng.elixir[team]
        affordable = [s for s in self._hand_specs() if s.elixir <= elix]
        if not affordable:
            return
        if self.adaptive and self._try_anti_siege(eng, affordable, elix):
            return
        usable = self._usable(affordable, elix)
        # DEFEND: an enemy (team 0) unit has entered our half (y < 0.5)
        threats = [u for u in eng.units if u.team == 0 and u.y < 0.5]
        if threats:
            deepest = min(threats, key=lambda u: u.y)             # closest to our king
            troops = [s for s in usable if s.kind == "troop" and not s.building_only]
            if troops:
                s = min(troops, key=lambda s: s.elixir)
                self._play(eng, s, deepest.x, max(0.12, deepest.y - 0.06))
                return
            spells = [s for s in usable if s.kind == "spell"]
            if spells and len(threats) >= 3:
                s = min(spells, key=lambda s: s.elixir)
                self._play(eng, s, deepest.x, deepest.y)
                return
        if self.adaptive and self._try_punish(eng, affordable):
            return
        # BACKLINE SUPPORT OPENING (control/beatdown): once, early, drop a mid-cost ranged support BEHIND the
        # king (the "Musketeer behind the tower" open) -- realistic pressure AND the setup the agent learns to
        # punish (rocket the support + tower for a 2-for-1).
        if (not self._backline_done and not threats and eng.t < self._backline_until
                and self.style in ("control", "beatdown") and self.rng.random() < self._backline_prob):
            supports = [s for s in usable if s.kind == "troop" and not s.building_only
                        and 4 <= s.elixir <= 6 and not s.flying]
            if supports:
                self._backline_done = True
                self._play(eng, self.rng.choice(supports), self.rng.choice(eng.lanes), 0.10)
                return
        # PUMP OPENING: an Elixir Collector in the deck is placed like a real player -- at spare elixir,
        # under no pressure, at most one on the field. Placement VARIETY is deliberate: behind the KING
        # (king-adjacent = the agent must NOT rocket it), the PRINCESS pocket (rocketable together with
        # the tower = the double hit), or mid-back (the solo-rocket case) -- all three answers train.
        pump = next((s for s in usable if s.gen_every > 0), None)
        if (pump is not None and not threats and elix >= pump.elixir + 2
                and not any(u.team == team and u.spec.gen_every > 0 for u in eng.units)
                and self.rng.random() < 0.35):
            spot = self.rng.choice(((0.5 + self.rng.choice([-0.06, 0.06]), 0.06),    # hugging the king
                                    (self.rng.choice(eng.lanes), 0.13),              # princess pocket
                                    (self.rng.choice([0.35, 0.62]), 0.10)))          # mid-back
            self._play(eng, pump, spot[0], spot[1])
            return        # ATTACK
        if self.style == "beatdown" and elix < 9.5:
            return                                                # save up for a big push
        offense = [s for s in usable if s.kind != "spell" and s.gen_every <= 0]
        if not offense:
            return
        # DEPLOY-ANYWHERE cards (Miner / Goblin Drill, KB flag) tunnel STRAIGHT to the defender's tower --
        # they never walk the lane. Dropping one at the bridge like a Knight, which is what the generic
        # offense path did, means the agent never trains on the scenario the card actually creates: an
        # enemy suddenly ON its tower with no approach to read. Placed on a live princess tower here.
        anywhere = [s for s in offense if s.deploy_anywhere]
        if anywhere and self.rng.random() < self.anywhere_prob:
            tw = [t for t in eng.towers[1 - team][:2] if t.alive]
            if tw:
                target = self.rng.choice(tw)
                if self._play(eng, self.rng.choice(anywhere), target.x, target.y):
                    return
        splitting = self.adaptive and self.split_know and self._nado_seen
        if splitting:
            self._flip = not self._flip                          # tornado seen -> stop stacking one lane
            lane = eng.lanes[0] if self._flip else eng.lanes[1]
        else:
            lane = self.rng.choice(eng.lanes)
        if self.style == "beatdown":
            tank = max(offense, key=lambda s: s.hp)               # heaviest unit BEHIND the king (deep back)
            self._play(eng, tank, lane, 0.10)
            if splitting:                                         # split the support into the OTHER lane
                cheap = [s for s in offense if s is not tank and s.elixir <= 4]
                if cheap and eng.elixir[team] >= min(s.elixir for s in cheap):
                    self._play(eng, self.rng.choice(cheap), 1.0 - lane, 0.14)
        elif self.style == "siege":
            sieges = [s for s in offense if s.siege] or offense
            self._play(eng, self.rng.choice(sieges), lane, 0.42)
        else:                                                     # cycle / control: chip at the bridge
            wc = [s for s in offense if s.building_only] or offense
            pick = self.rng.choice(wc)
            self._play(eng, pick, lane, 0.46)
            if splitting:                                         # two-lane chip so one tornado can't catch all
                cheap = [s for s in offense if s is not pick and s.elixir <= 3]
                if cheap and eng.elixir[team] >= min(s.elixir for s in cheap):
                    self._play(eng, self.rng.choice(cheap), 1.0 - lane, 0.46)


def make_opponent(cfg, db, rng, pool: List[dict], level: "int | None" = None,
                  adaptive: bool = False) -> ScriptedBot:
    """Sample a meta deck (weighted by its popularity) and pilot it per its inferred style. Each of its
    cards rolls a RANDOM level (sim.enemy_levels weighted by sim.enemy_level_weights -- default 13-16
    with 14 most likely, 16 least), so the opponent's card levels vary like a real ladder opponent.

    ``level`` (FAIR eval): if given, ALL the opponent's cards use this fixed level instead of the rolled
    ladder levels -- removing the level handicap. The roll still happens first so rng consumption (and
    thus the sampled deck sequence) is IDENTICAL to the handicapped path, making fair-vs-ladder an
    apples-to-apples comparison on the same matchups.

    ``adaptive`` (TRAINING only -- the eval benchmark never passes it, so eval curves stay comparable):
    each bot rolls sim.adaptive_prob to become an ADAPTIVE bot (counter-holding / anti-siege / dump
    punish / split-push, see ScriptedBot). The roll uses a DERIVED rng so the deck/level sequence
    stays identical whether or not adaptation is enabled."""
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
    is_adaptive = adaptive and rng.random() < float(cfg.get("sim", "adaptive_prob", default=0.65))
    return ScriptedBot(cfg, db, rng, deck["cards"], deck["style"], levels, adaptive=is_adaptive)


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
        self.use_tower_obs = getattr(env, "use_tower_obs", False)   # ...and the crown-tower HP block
        self.use_canvas = getattr(env, "use_canvas", False)         # ...and the semantic obs CANVAS
        self.canvas_presence_recall = getattr(env, "canvas_presence_recall", 1.0)
        self.sight_range = env.sight_range
        self.agent_dt = env.agent_dt
        self.predict_horizon = env.predict_horizon
        self._dr = env.domain_rand                    # share the match's visual restyle (resampled by env.reset)
        self._prev_ident_depth = 0.0
        self._opp_mem = card_threat.OpponentMemory(env.db)   # per-match opponent memory (mirrors team 0)
        self.anywhere_ids = env.anywhere_ids
        self.deck_keys = env.deck_keys
        lv = cfg.get("sim", "enemy_levels", default=[13, 14, 15, 16])
        lw = cfg.get("sim", "enemy_level_weights", default=[3, 5, 2, 1])
        levels = [rng.choices(lv, weights=lw, k=1)[0] for _ in self.deck_keys]
        self.specs = [build_spec(self.db, k, lvl) for k, lvl in zip(self.deck_keys, levels)]
        # The snapshot must choose actions under the SAME mask the trainer applies (see
        # train_sim_ppo.masked_logits): card = in-hand AND affordable, cell = the deployable set.
        # Kept as plain lists here and cached as tensors on first act() (torch is imported lazily).
        self._costs = [float(s.elixir) for s in self.specs]
        self._yourhalf = self.actions.deployable_mask(False)
        self._mask_cache: dict = {}
        self._gate_tau = float(cfg.get("sim", "ppo_gate_threshold", default=0.25))
        # exposed so the env's matchup doctrine (reads opponent .style / .cards) still works
        from .meta_decks import classify_style
        self.cards = list(self.deck_keys)
        self.style = classify_style(self.db, self.deck_keys)
        # PHYSICAL card slots (8), not the 10 policy identities -- an Evolution shares its base
        # card's cycle position and only appears once that slot has banked `cycles` plays.
        self.slots = self.db.deck_slots()
        self.n_slots = max(1, len(self.slots))
        self.slot_base_id = [self.deck_keys.index(s["base"]) for s in self.slots]
        self.slot_evo_id = [self.deck_keys.index(s["evo"]) if s["evo"] in self.deck_keys else -1
                            for s in self.slots]
        self.slot_cycles = [int(s["cycles"]) for s in self.slots]
        self.slot_of = {}
        for si in range(self.n_slots):
            self.slot_of[self.slot_base_id[si]] = si
            if self.slot_evo_id[si] >= 0:
                self.slot_of[self.slot_evo_id[si]] = si
        self.evo_charge = [0] * self.n_slots
        self.cycle = list(range(self.n_slots))
        self.rng.shuffle(self.cycle)

    def _slot_card_id(self, slot: int) -> int:
        evo = self.slot_evo_id[slot]
        if evo >= 0 and self.evo_charge[slot] >= self.slot_cycles[slot]:
            return evo
        return self.slot_base_id[slot]

    def _hand_ids(self):
        return [self._slot_card_id(s) for s in self.cycle[:4]]

    def _play_slot(self, card_id: int) -> None:
        slot = self.slot_of.get(card_id)
        if slot is None:
            return
        if card_id == self.slot_evo_id[slot]:
            self.evo_charge[slot] = 0
        elif self.slot_evo_id[slot] >= 0:
            self.evo_charge[slot] += 1
        self.cycle.remove(slot)
        self.cycle.append(slot)

    def act(self, eng) -> None:
        import torch

        oh, ow, _ = self.obs_shape
        obs = view.render_obs(eng, oh, ow, team=1, dr=self._dr)   # same match 'arena look' as team 0
        if self.use_canvas:                                       # mirrored semantic canvas for team 1
            obs = np.concatenate(
                [obs, view.semantic_channels(eng, oh, ow, team=1, rng=self.rng,
                                             presence_recall=self.canvas_presence_recall)], axis=2)
        hand = np.zeros(self.n_cards, np.float32)
        for i in self._hand_ids():
            hand[i] = 1.0
        nxt = cycle_vector([self._slot_card_id(s) for s in self.cycle], self.n_cards)   # graded upcoming-order
        elx = np.array([eng.elixir[1] / 10.0], np.float32)
        base_dim = self.threat_dim \
            - ((card_threat.IDENTITY_DIM + card_threat.OPP_MEMORY_DIM) if self.use_detector else 0) \
            - (interactions.INTERACTION_DIM if self.use_interactions else 0) \
            - (view.TOWER_DIM if self.use_tower_obs else 0)
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
                                          self.det_recall_by_card), dt=self.agent_dt)
            # Slot 5 mirrors the opponent-elixir signal from team 1's perspective.
            mem[5] = eng.elixir[0] / 10.0
            thr = np.concatenate([thr, ident, mem]).astype(np.float32)
        if self.use_interactions:                      # mirrored: team 1 sees ITS towers as 'mine'
            units, mine_t, en_t = view.interaction_state(eng, 1, self.detector_cards, self.rng,
                                                         self.det_recall, self.det_recall_by_card)
            ivec = interactions.interaction_vector(units, mine_t, en_t, self.db)
            thr = np.concatenate([thr, ivec]).astype(np.float32)
        if self.use_tower_obs:                         # ...same mirroring for the tower block
            thr = np.concatenate([thr, view.tower_vector(eng, 1)]).astype(np.float32)

        dev = next(self.net.parameters()).device
        obs_t = torch.from_numpy(obs).float().permute(2, 0, 1).unsqueeze(0).to(dev) / 255.0
        hand_t = torch.from_numpy(hand).unsqueeze(0).to(dev)
        nxt_t = torch.from_numpy(nxt).unsqueeze(0).to(dev)
        elx_t = torch.from_numpy(elx).unsqueeze(0).to(dev)
        thr_t = torch.from_numpy(thr).unsqueeze(0).to(dev)
        with torch.no_grad():
            cq, ceq, gq = self.net(obs_t, hand_t, nxt_t, elx_t, thr_t)
        cache = self._mask_cache
        if not cache:
            cache["cost"] = torch.tensor(self._costs, dtype=torch.float32, device=dev)
            cache["half"] = torch.tensor(self._yourhalf, dtype=torch.bool, device=dev)
        # AFFORDABILITY, not just in-hand. Without the cost term the snapshot argmaxes onto a card it
        # cannot pay for, eng.deploy() returns False and the tick is silently wasted -- that made the
        # frozen self far weaker than the agent it is meant to mirror (inflating training winrate).
        playable = (hand_t[0] >= 0.5) & (cache["cost"] <= float(eng.elixir[1]) + 1e-6)
        if not bool(playable.any()):
            return                                   # nothing playable: the trainer masks the play gate
        cq = cq.masked_fill(~playable.unsqueeze(0), _NEG)
        # PPO snapshots (net._ppo) carry LOGITS: the gate is a PROBABILITY thresholded at
        # sim.ppo_gate_threshold (a raw logit compare is tau=0.5, which under-deploys badly).
        # DQN snapshots keep the additive Q rule (wait_q vs play_q + best card + best cell).
        if getattr(self.net, "_ppo", False):
            wait = bool(torch.sigmoid(gq[0, 1] - gq[0, 0]) <= self._gate_tau)
        else:
            wait = bool(gq[0, 0] >= gq[0, 1] + cq[0].max() + ceq[0].max())
        if wait:
            return                                               # gate says WAIT
        card = int(cq[0].argmax())
        # Mask cells to the legal set BEFORE the argmax (what the trainer does). Clamping afterwards
        # folds many illegal cells onto one boundary cell and distorts the placement the policy chose.
        if card not in self.anywhere_ids:
            ceq = ceq.masked_fill(~cache["half"].unsqueeze(0), _NEG)
        cell = int(ceq[0].argmax())

        cell = self.actions.deploy_clamp(card in self.anywhere_ids, cell)
        lnx, lny = self.actions.cell_center(cell % self.gw, cell // self.gw)
        ex, ey = 1.0 - lnx, 1.0 - lny                            # mirror the local cell back to engine coords
        if eng.deploy(1, self.specs[card], ex, ey):
            self._play_slot(card)

