"""Paired counterfactual rollouts ("branching") for the play/wait gate (opt3 T1; contract
scratchpad/gauntlet/L73/opt3/INTERFACE.md section T1).

At a decision of a SelfPlayMatch where our side decides, fork the game (search_s0.fork_into: RoyaleSim
save_state/load_state into pooled engines + deep copies of the env's and BOTH sides' python state, which includes the
public observer / opp-elixir counter / opponent cycle, the extrapolation look-ahead state (_prev_raw) and the env's
ability state) into
  PLAY  our side plays NOW: the live rule's card argmax / cell argmax with the gate forced open (= the live rule's own
        action whenever p > tau; at p <= tau the live rule would wait, so the PLAY branch is a forced play), then the
        live rule (tau from learner_cfg).
  HOLD  for hold_s seconds from the root (root decision included) our side plays only if p > hold_tau OR anti-stall
        fires (the same live_decide_batch path, tau = hold_tau); afterwards the live rule (tau from learner_cfg).
Both: our side = the live rule on its own model (argmax, afford mask, anti-stall, delay, extrapolation, counter, all
from the side's cfg); the opponent = the REAL opponent of ``m`` (its own model and cfg, live or sample), never a
self-model. k continuations per branch, run to the end of the match or ``horizon_s``, all 2k forks in LOCKSTEP rounds
(one forward per (model, gate) group per round, as search_s0.Runner.rollout_scores).

COMMON RANDOM NUMBERS. Continuation j of PLAY and of HOLD start from the same blob and get the same seeds, derived from
(spec.seed, j, side), for every python RNG a side owns: rng_behave (sample policy), rng_obs (live_view noise), rng_rand
(random policy), rng_decision_options (decision_options) -- plus env.seed, the only input of the v2 ability-press
draw. The engine's own Rng is part of save_state (state_hash covers it) and is NOT reseedable from python: it is the
same in PLAY_j and HOLD_j but also the same for every j. So continuations differ across j only through those python
RNGs: with a deterministic opponent (policy live, no decision options, no obs noise) all k continuations are equal.

The caller has PREPARED every due side (``s.prepare()``) and applied nothing yet (search_s0.Runner.round's state at
the forward). ``pair`` never touches ``m``: fork copies only.

End snapshot (``BranchResult.play_end[j]`` / ``hold_end[j]``), a dict:
  tick, side (our team), terminated, state (engine BattleState), raw (env.raw(), what reward_shaping.phi_record reads),
  learner: our side's SelfPlaySide PREPARED at the end state (``learner.gen_row(policy)`` gives a gen row for any
  policy whose features do not read the env), its ``env`` detached (None) because the pooled engine is reused.
Outcome: +1 win / -1 loss / 0 draw when the match ended (game over, or the match's own tail_cap), None at the horizon.
"""
from __future__ import annotations

import random
import time
from dataclasses import dataclass
from typing import Optional

import numpy as np

from pipeline import e1_eval as E
from pipeline.decision_options import match_kwargs
from pipeline.search_s0 import fork_into

OUTCOME = {"win": 1, "loss": -1, "draw": 0}


@dataclass(kw_only=True)
class BranchSpec:
    hold_s: float
    hold_tau: float = 0.55
    horizon_s: Optional[float]          # None = play to the end of the match
    k: int
    seed: int


@dataclass
class BranchResult:
    tick: int                           # the root decision tick
    phase: str                          # single / double / overtime (our view at the root)
    p_play: float                       # our gate P(play) at the root
    elixir: float                       # our integer elixir at the root (what the gate and afford mask see)
    play_end: list
    hold_end: list
    play_outcome: list
    hold_outcome: list
    wall_s: float


def reseed(f, seed: int, j: int) -> None:
    """Common random numbers: continuation ``j``'s seeds for every python RNG of fork ``f`` (module docstring)."""
    for s in (f.learner, f.opp):
        a, b, c, d = np.random.SeedSequence([int(seed), int(j), int(s.side)]).spawn(4)
        s.rng_obs, s.rng_behave = np.random.default_rng(a), np.random.default_rng(b)
        s.rng_decision_options = np.random.default_rng(c)
        s.rng_rand = random.Random(int(d.generate_state(1)[0]))
    f.env.seed = int(np.random.SeedSequence([int(seed), int(j)]).generate_state(1)[0])


class BranchRunner:
    """``make_env()`` -> RoyaleSelfPlayEnv (pooled, reused across pair() calls); ``learner`` = our policy (must be
    ``m.learner.model``); ``opps`` kept for the caller (the opponent in a fork is always ``m.opp``'s own model/cfg);
    ``learner_cfg["tau"]`` = the live gate; ``device`` = our forwards' device."""

    def __init__(self, make_env, learner, opps: dict, learner_cfg: dict, *, device: str = "cpu"):
        self.make_env, self.learner, self.opps = make_env, learner, opps
        self.tau, self.dev = float(learner_cfg["tau"]), device
        self.pool: list = []
        self.last_forks: list = []      # (branch, j, fork) of the last pair(), for inspection

    def _pool(self, n: int) -> list:
        while len(self.pool) < n:
            self.pool.append(self.make_env())
        return self.pool[:n]

    def pair(self, m, ds, spec: BranchSpec) -> BranchResult:
        t0 = time.perf_counter()
        env, L = m.env, m.learner
        tick = int(env.tick)
        if L not in ds:
            raise ValueError("our side does not decide at this tick")
        if L.model is not self.learner:
            raise ValueError("m.learner.model is not this runner's learner")
        for s in ds:
            if getattr(s, "_cur", (None,))[0] != tick or s.next_tick > tick:
                raise ValueError("every due side must be prepared at this tick and not yet applied")
        _, bs, view = L._cur
        if spec.k < 1:
            raise ValueError("spec.k must be >= 1")
        cap = env.tail_cap if spec.horizon_s is None else min(env.tail_cap, tick + int(round(spec.horizon_s / E.TICK_S)))
        hold_until = tick + int(round(spec.hold_s / E.TICK_S))
        blob, n0 = env.core.save_state(), len(L.p_gates)
        runs = [(b, j) for b in ("play", "hold") for j in range(spec.k)]
        forks = []
        for e2, (b, j) in zip(self._pool(len(runs)), runs):
            f = fork_into(m, e2, blob)
            f.env.tail_cap = cap
            reseed(f, spec.seed, j)
            forks.append(f)

        def our_tau(f, b, t, root):
            if b == "play" and root:
                return float("-inf")                       # gate forced open: play the argmax card at the argmax cell
            return float(spec.hold_tau) if b == "hold" and t < hold_until else self.tau

        self._round([(f, b, f.learner if s is L else f.opp) for f, (b, _) in zip(forks, runs) for s in ds],
                    our_tau, True)
        if forks[0].learner.pending is None and len(forks[0].learner.plays) == len(L.plays):
            raise ValueError("no affordable card at the root: nothing to branch")
        while True:
            due = []
            for f, (b, _) in zip(forks, runs):
                got = f.due()
                for s in got:
                    s.prepare()
                due += [(f, b, s) for s in got]
            if not due:
                break
            self._round(due, our_tau, False)
        ends = [(self._snapshot(f, L.side), self._outcome(f, L.side, env.tail_cap)) for f in forks]
        self.last_forks = [(b, j, f) for (b, j), f in zip(runs, forks)]
        k = spec.k
        return BranchResult(tick=tick, phase="overtime" if bs.overtime else "double" if bs.double_elixir else "single",
                            p_play=float(forks[0].learner.p_gates[n0]), elixir=float(int(view.my_elixir)),
                            play_end=[e for e, _ in ends[:k]], hold_end=[e for e, _ in ends[k:]],
                            play_outcome=[o for _, o in ends[:k]], hold_outcome=[o for _, o in ends[k:]],
                            wall_s=time.perf_counter() - t0)

    def _round(self, due, our_tau, root: bool) -> None:
        """Prepared due sides across forks: one forward + one batched decide per group, then apply in due order
        (run_selfplay_batch's order). Our side: live rule at its branch's tau; the opponent: its own policy and cfg."""
        groups: dict = {}
        for f, b, s in due:
            if s is f.learner:
                key = ("ours", id(s.model), our_tau(f, b, s._cur[0], root), self.dev)
            else:
                key = ("opp", id(s.model), id(s.cfg), s.cfg["device"])
            groups.setdefault(key, []).append(s)
        todo = {}
        for (who, _, tau, dev), sides in groups.items():           # "opp": tau slot = id(cfg), cfg["tau"] used
            model, cfg = sides[0].model, sides[0].cfg
            if isinstance(model, E.GenPolicy):
                enc, heads, p, hand = model.forward_batch([s.gen_row(model) for s in sides], dev)
            else:
                enc, heads, p, hand = E.model_forward_batch(model, *zip(*[s._obs for s in sides]), device=dev)
            pre = [s.pre(hand[r]) for r, s in enumerate(sides)]
            allowed = np.stack([x[1] for x in pre])
            stalled = np.array([x[2] for x in pre], dtype=bool)
            if who == "ours" or cfg["policy"] == "live":
                dec = E.live_decide_batch(model, enc, heads, p, allowed, stalled,
                                          tau=tau if who == "ours" else cfg["tau"], device=dev, **match_kwargs(sides))
            else:
                dec = E.sample_decide_batch(model, enc, heads, p, allowed, stalled, sides, cfg)
            todo.update({id(s): (p[r], dec[r]) for r, s in enumerate(sides)})
        for _, _, s in due:
            s.apply(*todo[id(s)])

    @staticmethod
    def _snapshot(f, side: int) -> dict:
        env, s = f.env, f.learner
        raw = env.raw()
        s.state = raw
        s.prepare()
        snap = {"tick": int(env.tick), "side": int(side), "terminated": bool(env.terminated),
                "state": env.core.state(), "raw": raw, "learner": s}
        s.env = None
        return snap

    @staticmethod
    def _outcome(f, side: int, match_cap: int) -> Optional[int]:
        env = f.env
        if env.terminated or env.tick >= match_cap:
            return OUTCOME[env.outcome(side)[0]]
        return None
