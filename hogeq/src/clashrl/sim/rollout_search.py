"""EVAL-ONLY FLAT ROLLOUT SEARCH -- a MEASUREMENT harness, not shipped code.

HANDOFF section 4x. At every Nth decision, clone `env.eng` (+ the opponent, sharing one RNG),
play each candidate action out for H seconds under a cheap default policy for BOTH sides, score
the resulting board on ACTUAL OUTCOME, and take the argmax. FLAT rollout search: no tree, no
reuse across iterations, no backup. This is NOT MCTS and must not be reported as MCTS.

Nothing here is imported by the repo's source. Run it, read the JSON, throw it away.

SCORING (section 4x, owner-refined). One currency: PRINCESS-TOWER FRACTIONS.

    score =  enemy tower fraction destroyed over the rollout
           - our tower fraction lost over the rollout
           - elixir we spent          * threat_value.ELIXIR_TO_TOWER   (0.061, measured / 113 cards)
           + (our surviving board value - theirs) at the horizon, as a DELTA from the start
           + CROWN_W * (crowns taken - crowns lost)

Never the shaped reward: search optimises whatever objective it is given, and this project spent a
week finding that objective to be wrong in three separate places (section 4x).

TWO IMPLEMENTATION DECISIONS the design note does not settle, both recorded because they change
the number:

  1. `threat_value.bodies_ignore_frac` returns `inf` for a siege building, for anything that
     outranges the crown tower, and for unknown cards -- MEASURED on our own deck that is x_bow,
     and on the enemy side every siege/spawner-ish body. An `inf` in a score is not a score, so a
     body with no finite ignore cost is priced at what it COST, `elixir * ELIXIR_TO_TOWER`, using
     the same measured constant the elixir term already uses. That makes deploying such a card
     instantaneously NEUTRAL (spend 0.366, gain 0.366 for a 6-elixir X-Bow) so only the
     CONSEQUENCE scores -- exactly the property `SimMatchEnv._position`'s docstring demands.
  2. Each side's pooled board value is capped at BOARD_CAP tower fractions. Same argument as
     `threat_value._SPAWNER_CAP`: past a full tower the exact number changes no decision.

DEFAULT ROLLOUT POLICY: our side IDLES for the whole horizon; the opponent keeps playing its
scripted line. That is precisely what the shipped counterfactual fork already does
(`SimMatchEnv._roll_fork`, "the AGENT DOING NOTHING"). It biases every candidate the same way but
NOT by the same amount -- see the WAIT analysis in the ledger.
"""
from __future__ import annotations

import argparse
import copy
import json
import math
import os
import pathlib
import random
import sys
import time



# PACKAGE MODULE. The research script this came from pinned an ABSOLUTE icebow path and
# pushed it onto sys.path -- which, imported from hogeq, would have loaded ICEBOW's engine
# and cards. As a module it resolves through the owning package, so each deck searches its
# OWN sim.
#
# The PYTHONHASHSEED default the script set at import time is DELIBERATELY DROPPED: it ran
# after interpreter start and was a NO-OP (HANDOFF 4x). Leaving it in implies a determinism
# it never provided. Export PYTHONHASHSEED=0 in the environment instead.

import numpy as np  # noqa: E402
import torch  # noqa: E402
import torch.nn as nn  # noqa: E402

from clashrl.config import Config  # noqa: E402
from clashrl.model import PolicyNet  # noqa: E402
from clashrl.sim.env import SimMatchEnv  # noqa: E402
from clashrl import threat_value as TV  # noqa: E402

_NEG = -1e9
BOARD_CAP = 1.0          # tower fractions; see module docstring, decision 2
TILES_X, TILES_Y = 18.0, 32.0


# ---------------------------------------------------------------------------- net

class PPONet(nn.Module):
    """Same shape as train_sim_ppo's actor-critic, so the checkpoint loads verbatim."""

    def __init__(self, in_ch, n_cards, n_cells, threat_dim):
        super().__init__()
        self.policy = PolicyNet(in_ch, n_cards, n_cells, threat_dim=threat_dim)
        self.gate = nn.Linear(self.policy.embed_dim, 2)
        self.value = nn.Linear(self.policy.embed_dim, 1)
        self.value_d = nn.Linear(self.policy.embed_dim, 1)

    def forward(self, x, hand, nxt, elx, thr):
        z, cards, cells = self.policy.forward_parts(x, hand, nxt, elx, thr)
        return cards, cells, self.gate(z), self.value(z).squeeze(-1), self.value_d(z).squeeze(-1)


def load_net(ckpt_path, env, device):
    net = PPONet(int(env.obs_shape[2]), env.n_cards, env.n_cells, env.threat_dim).to(device)
    ck = torch.load(ckpt_path, map_location="cpu")
    dropped = PolicyNet.load_compat(net.policy, ck["model"])
    if dropped:
        raise SystemExit(f"checkpoint tensors did not carry over: {dropped[:8]}")
    net.gate.load_state_dict(ck["gate"])
    if "value" in ck:
        net.value.load_state_dict(ck["value"])
    net.eval()
    return net


# ---------------------------------------------------------------------------- scoring

class Scorer:
    """Everything in PRINCESS-TOWER FRACTIONS."""

    def __init__(self, env, crown_w: float):
        self.db = env.db
        self.tower_level = int(getattr(env, "_tower_level_for_triage", 15))
        self.crown_w = float(crown_w)
        self._finite = {}       # base -> bool, is ignore_cost_frac finite
        self.crown_fires = 0    # how often the crown term was ever non-zero in a rollout

    def _has_finite_ignore(self, base: str) -> bool:
        v = self._finite.get(base)
        if v is None:
            try:
                v = math.isfinite(TV.ignore_cost_frac(self.db, base, tower_level=self.tower_level))
            except Exception:       # noqa: BLE001 -- an unknown card is never ignorable
                v = False
            self._finite[base] = v
        return v

    def board_value(self, eng, team: int) -> float:
        finite, extra = [], 0.0
        for u in eng.units:
            if u.team != team or u.hp <= 0 or u.spec.kind not in ("troop", "building"):
                continue
            b = u.spec.base
            if self._has_finite_ignore(b):
                finite.append(b)
            else:
                per = max(1, u.spec.squad_count or u.spec.count)
                extra += (float(u.spec.elixir) / per) * TV.ELIXIR_TO_TOWER
        v = 0.0
        if finite:
            v = float(TV.bodies_ignore_frac(self.db, finite, tower_level=self.tower_level))
            if not math.isfinite(v):
                v = BOARD_CAP
        return min(BOARD_CAP, v + extra)

    @staticmethod
    def tower_frac(eng, team: int) -> float:
        """Total standing tower HP for `team`, in units of ONE OF ITS OWN PRINCESS TOWERS.

        Same normalisation `SimMatchEnv._position` uses, so the king is worth more than a princess
        by exactly its HP ratio rather than by a chosen number.
        """
        ref = max(1.0, float(eng.towers[team][0].max_hp))
        return sum(max(0.0, float(t.hp)) for t in eng.towers[team]) / ref

    def snapshot(self, eng):
        return {
            "t": float(eng.t),
            "ours": self.tower_frac(eng, 0),
            "theirs": self.tower_frac(eng, 1),
            "bv0": self.board_value(eng, 0),
            "bv1": self.board_value(eng, 1),
            "cr0": eng.crowns(0),
            "cr1": eng.crowns(1),
        }

    def score(self, s0, eng, spent: float):
        s1 = self.snapshot(eng)
        enemy_destroyed = s0["theirs"] - s1["theirs"]
        ours_lost = s0["ours"] - s1["ours"]
        board = (s1["bv0"] - s1["bv1"]) - (s0["bv0"] - s0["bv1"])
        d_crowns = (s1["cr0"] - s0["cr0"]) - (s1["cr1"] - s0["cr1"])
        if d_crowns:
            self.crown_fires += 1
        return (enemy_destroyed
                - ours_lost
                - spent * TV.ELIXIR_TO_TOWER
                + board
                + self.crown_w * d_crowns)


# ---------------------------------------------------------------------------- search

class Searcher:
    def __init__(self, env, net, device, horizon, interval, topk, crown_w, gate_tau,
                 force_policy=False, cells=1, force_play=False, reseed_opp=False,
                 phase_lo=None, phase_hi=None, jit_drop=0.0, jit_pos=0.0, jit_hp=0.0,
                 jit_play=False, dump_decisions=False):
        self.env, self.net, self.device = env, net, device
        self.horizon, self.interval, self.topk = float(horizon), int(interval), int(topk)
        self.gate_tau = float(gate_tau)
        # LEAK PROBE: run every rollout, then throw the answer away and play the policy's action.
        # If the match record still equals the baseline's, the search provably writes nothing back
        # into the live match (RNG included). That is the check section 4x's determinism note asks for.
        self.force_policy = bool(force_policy)
        # How many CELLS per candidate card. 1 = the policy's argmax only (placement is not
        # searched). >1 adds that card's next-best masked cells, which is the arm section 4r's
        # near-uniform log/tornado cell heads argue for.
        self.cells = max(1, int(cells))
        # ABLATION (no rollouts): at a searched decision, OVERRIDE THE GATE and play the policy's
        # argmax card at its argmax cell whenever anything is affordable. Search's measured effect
        # is almost entirely "override WAIT with a play", so this isolates HOW MUCH of the gain is
        # simply playing more from how much is CHOOSING better.
        self.force_play = bool(force_play)
        # ⚠ THE ORACLE PROBLEM. The fork carries the opponent's RNG STATE, so the branch replays the
        # opponent's actual future draws -- which lane it will push, which card it will pick. That is
        # information no real search could have. With this on, each searched decision draws ONE fresh
        # seed and every candidate at that decision is rolled out under it (common random numbers, so
        # candidates stay comparable), turning the branch from THE future into A SAMPLE of it.
        self.reseed_opp = bool(reseed_opp)
        self._rs_ctr = 0
        self._rs_seed = 0
        self.pick_card = {}          # card_id (or -1 for WAIT) -> times SEARCH picked it
        self.pol_card = {}           # ...and times the POLICY picked it, on searched decisions
        self.moved_cell = 0          # search kept the card but moved the CELL
        self.scorer = Scorer(env, crown_w)
        self.yourhalf = torch.tensor(env.actions.deployable_mask(False), dtype=torch.bool, device=device)
        self.allcells = torch.ones(env.n_cells, dtype=torch.bool, device=device)
        self.costs = torch.tensor([float(s.elixir) for s in env.specs], dtype=torch.float32, device=device)
        self.anywhere = set(env.anywhere_ids)
        self.rollout_steps = max(1, int(round(self.horizon / env.agent_dt)))
        self.subs = max(1, int(round(env.agent_dt / env.sub_dt)))
        # counters
        self.searched = self.disagree = 0
        self.policy_wait = self.search_wait = 0
        self.wait_over_play = self.play_over_wait = 0      # search chose WAIT / chose a PLAY instead
        self.cands = 0
        self.rollout_s = 0.0
        self.margins = []
        # -- MATCH-POSITION CONFOUND instrumentation -------------------------------
        # A rollout that reaches `eng.done` has OBSERVED the terminal outcome instead of
        # predicting it. Counted so the horizon curve can be read against how often that happens.
        self.phase_lo = phase_lo          # only search decisions with phase_lo <= eng.t < phase_hi
        self.phase_hi = phase_hi
        self.roll_total = 0
        self.roll_clamped = 0             # rollouts that hit eng.done before the horizon ran out
        self.dec_rows = []                # per-decision [t, ncand, nclamped, disagree, polplay, pickplay]
        self.dump_decisions = bool(dump_decisions)
        self._clamped_now = 0
        # -- LIVE-SEARCH PERCEPTION probe ------------------------------------------
        # Perturb the forked board the way the DETECTOR would mis-see it, then ask whether the
        # search still picks the same action. Grounded in this project's own measured detector
        # numbers (config observation.sim_detector_recall 0.823 / presence_recall 0.85).
        self.jit_drop = float(jit_drop)   # per-unit dropout probability
        self.jit_pos = float(jit_pos)     # gaussian sigma on x,y in TILES
        self.jit_hp = float(jit_hp)       # uniform +- fractional HP error
        self.jit_play = bool(jit_play)    # play the JITTERED choice (else play clean, just measure)
        self.jit_on = (self.jit_drop > 0 or self.jit_pos > 0 or self.jit_hp > 0)
        self._jit_active = False
        self._jit_plan = None
        self._jit_rng = random.Random(20260827)
        self.jit_dec = 0                  # decisions where both searches ran
        self.jit_agree = 0                # ...and they chose the SAME action
        self.jit_agree_card = 0           # ...same card (cell may differ)
        self.jit_dropped = 0
        self.jit_seen = 0
        # WALL-CLOCK DEADLINE, live only. None => no clock is consulted anywhere below, so SIM
        # BEHAVIOUR IS UNCHANGED BY CONSTRUCTION -- this must stay true, because the sim search
        # result (37.0% -> 85.7%) is the reference every live claim is measured against.
        self.deadline = None
        self.truncated = 0                # decisions that scored only a PREFIX of the candidates
        self.scored = 0                   # rollouts actually run, for cost accounting

    # -- policy ------------------------------------------------------------
    def _forward(self):
        e = self.env
        obs = torch.from_numpy(e._last_obs).float().permute(2, 0, 1).unsqueeze(0).to(self.device) / 255.0
        def v(a):
            return torch.from_numpy(np.asarray(a, np.float32)).unsqueeze(0).to(self.device)
        with torch.no_grad():
            _out = self.net(obs, v(e.hand_vec), v(e.next_vec), v(e.elixir_vec), v(e.threat_vec))
        # THREE NETS FEED THIS, AND THEY RETURN DIFFERENT ARITIES:
        #   sim PPONet      -> (cards, cells, gate, value, value_d)   5
        #   train-rl DQN    -> (cards, cells, gate)                   3
        #   play.py         -> PolicyNet + a separate gate head
        # The first THREE are identical in meaning and order; the two value heads are DISCARDED
        # here anyway. Unpacking exactly five turned that non-difference into a hard failure --
        #     ValueError: not enough values to unpack (expected 5, got 3)
        # -- on every live decision, because live runs the DQN. Take the first three and the same
        # searcher serves all three nets unchanged.
        cq, ceq, gq = _out[0], _out[1], _out[2]
        elixir = v(e.elixir_vec) * 10.0
        playable = (v(e.hand_vec) > 0.5) & (self.costs.view(1, -1) <= elixir + 1e-6)
        cq_m = cq.masked_fill(~playable, _NEG)
        gq_m = gq.clone()
        if not bool(playable.any()):
            gq_m[:, 1] = _NEG
        return cq_m[0], ceq[0], gq_m[0], playable[0]

    def _cell_for(self, ceq, ci):
        m = self.allcells if ci in self.anywhere else self.yourhalf
        return int(ceq[ci].masked_fill(~m, _NEG).argmax())

    def _cells_for(self, ceq, ci, n):
        m = self.allcells if ci in self.anywhere else self.yourhalf
        row = ceq[ci].masked_fill(~m, _NEG)
        return [int(x) for x in torch.topk(row, min(n, int(m.sum()))).indices]

    def greedy_action(self):
        """Byte-identical to train_sim_ppo.choose_greedy for one env."""
        cq_m, ceq, gq_m, playable = self._forward()
        if not bool(playable.any()) or float(torch.sigmoid(gq_m[1] - gq_m[0])) <= self.gate_tau:
            return (0, 0, 0), (cq_m, ceq, gq_m, playable)
        ci = int(cq_m.argmax())
        return (1, ci, self._cell_for(ceq, ci)), (cq_m, ceq, gq_m, playable)

    # -- rollout -----------------------------------------------------------
    def _rollout(self, action):
        """Fork, apply `action`, then idle our side / run theirs for the horizon. Returns score."""
        e = self.env
        # ONE deepcopy of the PAIR: `eng.rng` and `opponent.rng` are the SAME object in the live
        # match (SimMatchEnv hands env.rng to both), and two separate deepcopy calls -- which is
        # what the shipped `_fork` does -- would split them into two independent streams. Copying
        # the tuple preserves the aliasing, so the branch is a faithful continuation.
        eng, opp = copy.deepcopy((e.eng, e.opponent))
        if self._jit_active and self._jit_plan is not None:
            self._apply_jitter(eng)
        if self.reseed_opp:
            # eng.rng IS opp.rng inside the fork (one deepcopy of the pair), so this reseeds both.
            opp.rng.seed(self._rs_seed)
        s0 = self.scorer.snapshot(eng)
        spent = 0.0
        play, card_id, cell = action
        if play:
            spec = e.specs[card_id]
            cell = e.actions.deploy_clamp(card_id in e.anywhere_ids, cell)
            nx, ny = e.actions.cell_center(cell % e.gw, cell // e.gw)
            if eng.deploy(0, spec, nx, ny, delay_s=e.action_latency):
                spent = float(spec.elixir)
        for _ in range(self.rollout_steps):
            if eng.done:
                break
            opp.act(eng)
            for _ in range(self.subs):
                eng.advance(e.sub_dt)
                if eng.done:
                    break
        self.roll_total += 1
        if eng.done:                      # the horizon ran past the END of the match
            self.roll_clamped += 1
            self._clamped_now += 1
        return self.scorer.score(s0, eng, spent)

    # -- perception jitter --------------------------------------------------
    def _plan_jitter(self, eng):
        '''One coherent misperception per DECISION, shared by every candidate at that decision.

        Keyed on `Unit.deploy_seq`, never `id()` (conflicts.md I10-FOLLOWUP: CPython recycles a
        dead body's address). Common random numbers across candidates, so the comparison between
        candidates stays fair and only the STARTING STATE is wrong -- which is the live case.
        '''
        r = self._jit_rng
        plan = {}
        for u in eng.units:
            drop = (r.random() < self.jit_drop) if self.jit_drop > 0 else False
            dx = r.gauss(0.0, self.jit_pos) if self.jit_pos > 0 else 0.0
            dy = r.gauss(0.0, self.jit_pos) if self.jit_pos > 0 else 0.0
            hm = (1.0 + r.uniform(-self.jit_hp, self.jit_hp)) if self.jit_hp > 0 else 1.0
            plan[u.deploy_seq] = (drop, dx, dy, hm)
            self.jit_seen += 1
            if drop:
                self.jit_dropped += 1
        self._jit_plan = plan

    def _apply_jitter(self, eng):
        plan = self._jit_plan
        keep, gone = [], set()
        for u in eng.units:
            pl = plan.get(u.deploy_seq)
            if pl is None:
                keep.append(u)
                continue
            drop, dx, dy, hm = pl
            if drop:
                gone.add(u.deploy_seq)
                continue
            if dx or dy:
                u.x += dx
                u.y += dy
            if hm != 1.0:
                u.hp = max(1.0, u.hp * hm)
            keep.append(u)
        if gone:
            eng.units = keep
            # a dropped body must not stay as someone's target -- the engine re-acquires on None
            for u in eng.units:
                t = getattr(u, 'target', None)
                if t is not None and getattr(t, 'deploy_seq', None) in gone:
                    u.target = None
            for team in (0, 1):
                for tw in eng.towers[team]:
                    t = getattr(tw, 'target', None)
                    if t is not None and getattr(t, 'deploy_seq', None) in gone:
                        tw.target = None

    def candidates(self, cq_m, ceq, playable):
        """The policy's top-K PLAYABLE cards at their own argmax cell, plus WAIT -- always."""
        out = [(0, 0, 0)]
        if bool(playable.any()):
            order = torch.argsort(cq_m, descending=True)
            for t in order[: self.topk]:
                ci = int(t)
                if not bool(playable[ci]):
                    break
                for cell in self._cells_for(ceq, ci, self.cells):
                    out.append((1, ci, cell))
        return out

    def act(self, step_i: int):
        pol, (cq_m, ceq, gq_m, playable) = self.greedy_action()
        if self.interval <= 0 or (step_i % self.interval) or self.env.eng.done:
            return pol, False
        tnow = float(self.env.eng.t)
        if self.phase_lo is not None and tnow < self.phase_lo:
            return pol, False
        if self.phase_hi is not None and tnow >= self.phase_hi:
            return pol, False
        if self.force_play:
            if not bool(playable.any()):
                return pol, False
            ci = int(cq_m.argmax())
            pick = (1, ci, self._cell_for(ceq, ci))
            self.searched += 1
            if pol[0] == 0:
                self.policy_wait += 1
            if pick != pol:
                self.disagree += 1
                if pol[0] == 0:
                    self.play_over_wait += 1
            return pick, True
        cands = self.candidates(cq_m, ceq, playable)
        if len(cands) < 2:
            return pol, False
        self._rs_ctr += 1
        self._rs_seed = 1_000_003 * self._rs_ctr + 7
        t0 = time.perf_counter()
        self._clamped_now = 0
        self._jit_active = False
        # INTERRUPTIBLE SCORING. Rollout cost scales steeply with how crowded the board is --
        # MEASURED on the live path: 2 bodies 61 ms, 6 bodies 151 ms, 12 bodies 262 ms, 20 bodies
        # 602 ms, 30 bodies 927 ms. At 20+ bodies a full sweep costs MORE THAN THE WHOLE 600 ms
        # act_period, and the bot is blind for all of it. The old shape was all-or-nothing: pay the
        # entire cost, then have the caller discard the answer for being late (22 of 25 decisions).
        # That is the worst of both -- maximum latency, zero benefit, and it bit hardest on exactly
        # the busy boards where search is worth most.
        # `cands` is ordered WAIT-first then by descending policy preference, so a PREFIX is the
        # right subset to keep: we lose the least-preferred options, never the plausible ones.
        # At least two must be scored or there is nothing to compare and the policy stands.
        scores = []
        for _a in cands:
            scores.append(self._rollout(_a))
            if (self.deadline is not None and len(scores) >= 2
                    and time.perf_counter() >= self.deadline):
                self.truncated += 1
                break
        self.scored += len(scores)
        if len(scores) < len(cands):
            cands = cands[:len(scores)]
        clean_pick = cands[int(np.argmax(scores))]
        if self.jit_on and not (self.deadline is not None
                                and time.perf_counter() >= self.deadline):
            # SAME decision, SAME candidates, a MISPERCEIVED starting board.
            self._plan_jitter(self.env.eng)
            self._jit_active = True
            jscores = [self._rollout(a) for a in cands]
            self._jit_active = False
            self._jit_plan = None
            jit_pick = cands[int(np.argmax(jscores))]
            self.jit_dec += 1
            if jit_pick == clean_pick:
                self.jit_agree += 1
            if (jit_pick[0] == clean_pick[0]) and (jit_pick[0] == 0 or jit_pick[1] == clean_pick[1]):
                self.jit_agree_card += 1
            if self.jit_play:
                scores = jscores
        self.rollout_s += time.perf_counter() - t0
        self.cands += len(cands)
        best = int(max(range(len(cands)), key=lambda i: scores[i]))
        pick = cands[best] if not self.force_policy else pol
        self.searched += 1
        srt = sorted(scores, reverse=True)
        self.margins.append(srt[0] - srt[1])
        if pol[0] == 0:
            self.policy_wait += 1
        if pick[0] == 0:
            self.search_wait += 1
        self.pick_card[pick[1] if pick[0] else -1] = self.pick_card.get(pick[1] if pick[0] else -1, 0) + 1
        self.pol_card[pol[1] if pol[0] else -1] = self.pol_card.get(pol[1] if pol[0] else -1, 0) + 1
        if pick[0] == 1 and pol[0] == 1 and pick[1] == pol[1] and pick[2] != pol[2]:
            self.moved_cell += 1
        if self.dump_decisions:
            self.dec_rows.append([round(tnow, 2), len(cands), self._clamped_now,
                                  1 if pick != pol else 0, int(pol[0]), int(pick[0])])
        if pick != pol:
            self.disagree += 1
            if pick[0] == 0 and pol[0] == 1:
                self.wait_over_play += 1
            elif pick[0] == 1 and pol[0] == 0:
                self.play_over_wait += 1
        return pick, True


# ---------------------------------------------------------------------------- diagnostics

def spell_geometry(env, card_id, cell):
    """Section 4r's probe, inline: distance to the nearest enemy and how many enemies sit inside
    the spell's OWN radius at the instant of the cast. A DUMP = zero enemies in radius."""
    spec = env.specs[card_id]
    c = env.actions.deploy_clamp(card_id in env.anywhere_ids, cell)
    nx, ny = env.actions.cell_center(c % env.gw, c // env.gw)
    rad = float(spec.spell_radius or 2.0)
    best, inside = 1e9, 0
    for u in env.eng.units:
        if u.team != 1 or u.hp <= 0:
            continue
        d = math.hypot((nx - u.x) * TILES_X, (ny - u.y) * TILES_Y)
        best = min(best, d)
        inside += d <= rad
    return spec.base, (None if best > 1e8 else best), inside


# ---------------------------------------------------------------------------- match loop

def play_match(env, searcher, seed, max_steps=2000):
    env.rng.seed(seed)
    env.reset()
    dmg_spells = set(getattr(env, "damage_spell_ids", set()))
    rec = {"seed": seed, "steps": 0, "plays": 0, "elixir_sum": 0.0, "ge6": 0,
           "casts": 0, "dumped": 0, "cast_rows": []}
    t0 = time.perf_counter()
    for i in range(max_steps):
        act, _did = searcher.act(i)
        rec["elixir_sum"] += float(env.eng.elixir[0])
        rec["ge6"] += float(env.eng.elixir[0]) >= 6.0
        if act[0] == 1:
            rec["plays"] += 1
            if act[1] in dmg_spells or env.specs[act[1]].kind == "spell":
                base, dist, inside = spell_geometry(env, act[1], act[2])
                rec["casts"] += 1
                rec["dumped"] += inside == 0
                rec["cast_rows"].append([base, dist, inside])
        _o, _r, done, info = env.step(act)
        rec["steps"] = i + 1
        if done:
            rec["outcome"] = info.get("outcome")
            rec["crowns"] = list(info.get("crowns", (0, 0)))
            break
    else:
        rec["outcome"] = "timeout"
        rec["crowns"] = [env.eng.crowns(0), env.eng.crowns(1)]
    eng = env.eng
    rec["t_end"] = float(eng.t)
    rec["our_tower"] = Scorer.tower_frac(eng, 0)
    rec["their_tower"] = Scorer.tower_frac(eng, 1)
    rec["tower_delta"] = rec["our_tower"] - rec["their_tower"]
    rec["crown_delta"] = rec["crowns"][0] - rec["crowns"][1]
    rec["wall_s"] = time.perf_counter() - t0
    return rec


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--matches", type=int, default=60)
    ap.add_argument("--seed0", type=int, default=900000)
    ap.add_argument("--horizon", type=float, default=0.0, help="0 = baseline, policy alone")
    ap.add_argument("--interval", type=int, default=5, help="search every Nth decision")
    ap.add_argument("--topk", type=int, default=4)
    ap.add_argument("--crown", type=float, default=1.0)
    ap.add_argument("--tag", default="arm")
    ap.add_argument("--out", default=None)
    ap.add_argument("--cells", type=int, default=1,
                    help="cells per candidate card (1 = the policy's argmax, i.e. no cell search)")
    ap.add_argument("--reseed-opp", action="store_true",
                    help="reseed the forked opponent so the rollout SAMPLES the opponent's future "
                         "instead of replaying its actual draws (removes the oracle)")
    ap.add_argument("--perfect-obs", action="store_true",
                    help="give the POLICY ground-truth perception (recall/precision/presence = 1)")
    ap.add_argument("--gate-tau", type=float, default=None,
                    help="override sim.ppo_gate_threshold (0.25). The control for 'search just "
                         "plays more': if lowering tau to match the search arm's plays/match "
                         "reproduces the gain, the finding is a MIScalibrated GATE, not search.")
    ap.add_argument("--force-play", action="store_true",
                    help="ABLATION: at every Nth decision play the policy's top card, no rollouts")
    ap.add_argument("--phase-lo", type=float, default=None,
                    help="only search decisions at game time >= this (MATCH-POSITION arm)")
    ap.add_argument("--phase-hi", type=float, default=None,
                    help="only search decisions at game time < this")
    ap.add_argument("--jit-drop", type=float, default=0.0,
                    help="fork-state dropout prob per unit (detector recall miss)")
    ap.add_argument("--jit-pos", type=float, default=0.0, help="fork-state x/y gaussian sigma, TILES")
    ap.add_argument("--jit-hp", type=float, default=0.0, help="fork-state +- fractional HP error")
    ap.add_argument("--jit-play", action="store_true",
                    help="PLAY the jittered choice (default: play the clean one, measure agreement)")
    ap.add_argument("--dump-decisions", action="store_true",
                    help="record [t, ncand, nclamped, disagree, polplay, pickplay] per decision")
    ap.add_argument("--force-policy", action="store_true",
                    help="roll everything out, then play the POLICY's action anyway (leak probe)")
    ap.add_argument("--ckpt", default=r"C:\Users\benpe\ClashBot\scratchpad\_rs_policy.pt")
    args = ap.parse_args()

    torch.set_num_threads(1)
    torch.manual_seed(0)
    np.random.seed(0)
    random.seed(0)

    cfg = Config.load()
    env = SimMatchEnv(cfg, seed=12345)
    env.domain_rand.enabled = False
    env.domain_rand.resample()
    env.opponent_provider = None                 # LADDER pool, exactly the trainer's default eval
    if args.perfect_obs:
        env.det_recall = 1.0
        env.det_precision = 1.0
        env.det_recall_by_card = {}
        env.canvas_presence_recall = 1.0
    device = torch.device("cpu")
    net = load_net(args.ckpt, env, device)
    gate_tau = float(cfg.get("sim", "ppo_gate_threshold", default=0.25))
    if args.gate_tau is not None:
        gate_tau = float(args.gate_tau)

    interval = args.interval if args.horizon > 0 else 0
    s = Searcher(env, net, device, max(args.horizon, 1e-6), interval, args.topk, args.crown,
                 gate_tau, force_policy=args.force_policy, cells=args.cells,
                 force_play=args.force_play, reseed_opp=args.reseed_opp,
                 phase_lo=args.phase_lo, phase_hi=args.phase_hi,
                 jit_drop=args.jit_drop, jit_pos=args.jit_pos, jit_hp=args.jit_hp,
                 jit_play=args.jit_play, dump_decisions=args.dump_decisions)

    recs = []
    wall0 = time.perf_counter()
    for m in range(args.matches):
        recs.append(play_match(env, s, args.seed0 + m))
        if (m + 1) % 10 == 0:
            wr = 100.0 * sum(r["outcome"] == "win" for r in recs) / len(recs)
            print(f"  [{args.tag}] {m+1}/{args.matches}  wr={wr:.1f}%  "
                  f"{(time.perf_counter()-wall0)/(m+1):.2f} s/match", flush=True)

    out = {
        "tag": args.tag, "horizon": args.horizon, "interval": args.interval, "topk": args.topk,
        "crown_w": args.crown, "matches": args.matches, "seed0": args.seed0,
        "ckpt": os.path.basename(args.ckpt),
        "wall_s": time.perf_counter() - wall0,
        "rollout_s": s.rollout_s, "candidates": s.cands,
        "searched": s.searched, "disagree": s.disagree,
        "policy_wait": s.policy_wait, "search_wait": s.search_wait,
        "wait_over_play": s.wait_over_play, "play_over_wait": s.play_over_wait,
        "crown_fires": s.scorer.crown_fires, "cells": args.cells,
        "force_play": bool(args.force_play), "gate_tau": gate_tau,
        "perfect_obs": bool(args.perfect_obs), "reseed_opp": bool(args.reseed_opp),
        "moved_cell": s.moved_cell,
        "pick_card": {str(k): v for k, v in s.pick_card.items()},
        "pol_card": {str(k): v for k, v in s.pol_card.items()},
        "deck": list(env.deck_keys),
        "margin_mean": float(np.mean(s.margins)) if s.margins else 0.0,
        "phase_lo": args.phase_lo, "phase_hi": args.phase_hi,
        "roll_total": s.roll_total, "roll_clamped": s.roll_clamped,
        "jit_drop": args.jit_drop, "jit_pos": args.jit_pos, "jit_hp": args.jit_hp,
        "jit_play": bool(args.jit_play),
        "jit_dec": s.jit_dec, "jit_agree": s.jit_agree, "jit_agree_card": s.jit_agree_card,
        "jit_seen": s.jit_seen, "jit_dropped": s.jit_dropped,
        "dec_rows": s.dec_rows,
        "records": recs,
    }
    path = args.out or rf"C:\Users\benpe\ClashBot\scratchpad\rs_{args.tag}.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(out, f)
    wr = 100.0 * sum(r["outcome"] == "win" for r in recs) / max(1, len(recs))
    print(f"[{args.tag}] wr={wr:.1f}%  towerdelta={np.mean([r['tower_delta'] for r in recs]):.4f}  "
          f"searched={s.searched} disagree={s.disagree} "
          f"wait->play={s.play_over_wait} play->wait={s.wait_over_play}  "
          f"wall={out['wall_s']:.1f}s -> {path}", flush=True)


if __name__ == "__main__":
    main()
