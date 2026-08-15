"""Subprocess env shards for train-sim-ppo (2026-08-14).

The match engine is pure Python, so one process can step ~6.5k matches/h while the other 15
cores idle (measured; the old single-process trainer additionally burned ~7 cores of torch
thread-pool churn on tiny tensors). This module runs the ENGINES in P worker processes while
the learner keeps batched action selection and all PPO updates in the parent:

    parent:  choose actions for all K envs (one batched forward)  ->  step_all(acts)
    workers: step their env shard in parallel, auto-reset on done, and reply per env with
             (obs, hand/nxt/elx/thr vectors, doctrine cells for the hand, reward, done,
              outcome, self-play attribution)

Self-play league snapshots and the difficulty scalar are broadcast to workers when they
change. Workers pin torch to one thread each; everything clashrl is imported INSIDE the
worker function so Windows spawn works without the package on the child's implicit path.
"""
from __future__ import annotations

import multiprocessing as mp
import sys
from pathlib import Path

_SRC = str(Path(__file__).resolve().parents[2])


def _worker(conn, n_envs: int, seed0: int) -> None:
    if _SRC not in sys.path:
        sys.path.insert(0, _SRC)
    import random

    import torch
    torch.set_num_threads(1)

    from clashrl.config import Config
    from clashrl.sim.env import SimMatchEnv
    from clashrl.sim.doctrine import doctrine_cells
    from clashrl.sim.opponents import SelfPlayOpponent, make_opponent

    cfg = Config.load()
    envs = [SimMatchEnv(cfg, seed=seed0 + i) for i in range(n_envs)]
    state = {"league": [], "weights": [], "sp_prob": 0.0, "difficulty": 1.0}
    rng = random.Random(seed0 * 7919 + 13)

    def provider(env):
        # CURRICULUM (2026-08-14): at 0/40 wins the full ladder pool (levels 13-16 + adaptive
        # + evos) gives the policy literally no win signal. The difficulty scalar follows the
        # recent training winrate; the easy tier is the same meta decks at OUR level, without
        # the adaptive counter-play. Full ladder returns as the winrate climbs.
        if rng.random() > state["difficulty"]:
            return make_opponent(cfg, env.db, env.rng, env.meta_pool, level=11, adaptive=False)
        if state["league"] and state["sp_prob"] > 0 and rng.random() < state["sp_prob"]:
            if state["weights"] and len(state["weights"]) == len(state["league"]):
                sd = rng.choices(state["league"], weights=state["weights"], k=1)[0]
            else:
                sd = rng.choice(state["league"])
            opp = SelfPlayOpponent(cfg, env, sd, env.rng)
            opp._src_sd = sd
            return opp
        return make_opponent(cfg, env.db, env.rng, env.meta_pool, adaptive=True)

    for e in envs:
        e.opponent_provider = provider

    def payload(i, env, obs, rew=0.0, done=False, outcome=None, pfsp=None):
        hand = env._hand_ids() if hasattr(env, "_hand_ids") else []
        return {
            "obs": obs, "hand": env.hand_vec.copy(), "nxt": env.next_vec.copy(),
            "elx": env.elixir_vec.copy(), "thr": env.threat_vec.copy(),
            "dc": {int(ci): doctrine_cells(env, int(ci)) for ci in hand},
            "rew": float(rew), "done": bool(done), "outcome": outcome, "pfsp": pfsp,
        }

    obs_cache = [e.reset() for e in envs]
    try:
        while True:
            msg = conn.recv()
            kind = msg[0]
            if kind == "reset":
                obs_cache = [e.reset() for e in envs]
                conn.send([payload(i, e, obs_cache[i]) for i, e in enumerate(envs)])
            elif kind == "step":
                acts = msg[1]
                out = []
                for i, e in enumerate(envs):
                    nobs, reward, done, info = e.step(acts[i])
                    outcome = pfsp = None
                    if done:
                        outcome = info.get("outcome")
                        opp = getattr(e, "opponent", None)
                        if isinstance(opp, SelfPlayOpponent):
                            src = getattr(opp, "_src_sd", None)
                            pfsp = next((j for j, sd_ in enumerate(state["league"])
                                         if sd_ is src), None)
                        nobs = e.reset()
                    obs_cache[i] = nobs
                    out.append(payload(i, e, nobs, reward, done, outcome, pfsp))
                conn.send(out)
            elif kind == "league":
                state["league"] = msg[1]
                state["weights"] = msg[2]
                state["sp_prob"] = float(msg[3])
                conn.send("ok")
            elif kind == "difficulty":
                state["difficulty"] = float(msg[1])
                conn.send("ok")
            elif kind == "close":
                conn.send("bye")
                return
    except (EOFError, KeyboardInterrupt):
        return


class RemotePool:
    """Parent-side handle: the trainer's env surface, sharded over worker processes."""

    def __init__(self, n_envs: int, workers: int, seed: int = 0):
        ctx = mp.get_context("spawn")
        self.K = int(n_envs)
        workers = max(1, min(int(workers), self.K))
        base, extra = divmod(self.K, workers)
        self.shards = []
        self.conns = []
        self.procs = []
        s0 = seed
        for w in range(workers):
            n = base + (1 if w < extra else 0)
            if n <= 0:
                continue
            parent_c, child_c = ctx.Pipe()
            pr = ctx.Process(target=_worker, args=(child_c, n, s0), daemon=True)
            pr.start()
            self.shards.append(n)
            self.conns.append(parent_c)
            self.procs.append(pr)
            s0 += n
        self.last = [None] * self.K          # last payload per env (vectors + doctrine)

    def _scatter(self, msg_builder):
        i0 = 0
        for c, n in zip(self.conns, self.shards):
            c.send(msg_builder(i0, n))
            i0 += n

    def _gather(self):
        out = []
        for c in self.conns:
            out.extend(c.recv())
        return out

    def reset_all(self):
        self._scatter(lambda i0, n: ("reset",))
        self.last = self._gather()
        return [p["obs"] for p in self.last]

    def step_all(self, acts):
        self._scatter(lambda i0, n: ("step", acts[i0:i0 + n]))
        self.last = self._gather()
        return self.last

    def set_league(self, sds, weights, sp_prob):
        for c in self.conns:
            c.send(("league", sds, weights, sp_prob))
        for c in self.conns:
            c.recv()

    def set_difficulty(self, d: float):
        for c in self.conns:
            c.send(("difficulty", float(d)))
        for c in self.conns:
            c.recv()

    def doctrine(self, i: int, ci: int):
        p = self.last[i]
        return (p or {}).get("dc", {}).get(int(ci)) or []

    def close(self):
        for c in self.conns:
            try:
                c.send(("close",))
            except Exception:  # noqa: BLE001
                pass
        for pr in self.procs:
            pr.join(timeout=2)
            if pr.is_alive():
                pr.terminate()
