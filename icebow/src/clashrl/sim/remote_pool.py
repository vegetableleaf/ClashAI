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


def _worker(conn, n_envs: int, seed0: int, drill_frac=None) -> None:
    if _SRC not in sys.path:
        sys.path.insert(0, _SRC)
    import random

    import torch
    torch.set_num_threads(1)

    from clashrl.config import Config
    from clashrl.sim.env import SimMatchEnv
    from clashrl.sim.doctrine import doctrine_cells, doctrine_cards
    from clashrl.sim.opponents import SelfPlayOpponent, make_opponent

    cfg = Config.load()
    from clashrl.sim.drill_env import make_train_env
    # drill_frac ARRIVES FROM THE PARENT, because this worker re-reads config.yaml from disk and
    # would otherwise ignore any in-memory override -- which is exactly what `--drill-frac` is.
    envs = [make_train_env(cfg, seed=seed0 + i, frac=drill_frac) for i in range(n_envs)]
    state = {"league": [], "weights": [], "sp_prob": 0.0, "difficulty": 1.0}
    # DECK PFSP across processes. make_opponent reads the per-deck W/N record off `cfg`, and a
    # worker has its OWN cfg copy that the parent's record never reaches -- so deck exploiters
    # silently did nothing whenever --workers > 0, which is every real run. The parent aggregates
    # results (it is the only place that sees every episode) and ships the table down here.
    cfg._deck_record = {}
    rng = random.Random(seed0 * 7919 + 13)

    sp_cache = {}

    def _sp_net(sd):
        # League entries arrive as plain STATE_DICTS -- the DQN class is local to _build_net,
        # so net objects cannot cross the pipe. Rebuild here, cache per entry (the cache is
        # cleared when a new league lands, so stale snapshots are freed).
        n = sp_cache.get(id(sd))
        if n is None:
            from clashrl.train_rl import _build_net
            e0 = envs[0]
            n = _build_net(cfg, "cpu", e0.n_cards, e0.n_cells, e0.threat_dim,
                           int(e0.obs_shape[2]))       # obs_shape is (H, W, C): channels last
            n.policy.load_state_dict(sd["model"])
            n.gate.load_state_dict(sd["gate"])
            n.policy.eval(); n.gate.eval()
            sp_cache[id(sd)] = n
        return n

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
            opp = SelfPlayOpponent(cfg, env, _sp_net(sd), env.rng)
            opp._src_sd = sd             # identity key into state["league"] for PFSP reporting
            return opp
        return make_opponent(cfg, env.db, env.rng, env.meta_pool, adaptive=True)

    for e in envs:
        e.opponent_provider = provider

    def payload(i, env, obs, rew=0.0, done=False, outcome=None, pfsp=None,
                drill=None, verdict=None, deck=None):
        hand = env._hand_ids() if hasattr(env, "_hand_ids") else []
        return {
            "obs": obs, "hand": env.hand_vec.copy(), "nxt": env.next_vec.copy(),
            "elx": env.elixir_vec.copy(), "thr": env.threat_vec.copy(),
            "dc": {int(ci): doctrine_cells(env, int(ci)) for ci in hand},
            # WHICH card to nominate, not just where to put it -- the rocket was never SELECTED,
            # so its (already generous) placement prior and rewards were both unreachable.
            "dcard": doctrine_cards(env),
            "rew": float(rew), "done": bool(done), "outcome": outcome, "pfsp": pfsp,
            # WHICH DRILL, if this episode was one. The parent decides what counts as a match from
            # this, and without it every drill was recorded as a played-and-lost match -- which
            # feeds the winrate EMA, and through it the curriculum difficulty and the gate.
            "drill": drill, "verdict": verdict,
            # which META DECK this episode was against, so the parent can aggregate a per-deck
            # record and weight the pool toward the ones we lose to (sim.deck_pfsp_power)
            "deck": deck,
            # IS THIS ENV IN A DRILL RIGHT NOW -- needed every step, not just at the end, because
            # the parent picks the exploration floor per step and the envs live out here.
            "in_drill": bool(getattr(env, "_in_drill", False)),
            # WHEN the drill's reference line would play. The gate is sampled in the parent and the
            # envs live out here, the same split that made --drill-frac a no-op for two runs.
            "dgate": (env.drill_prior_gate() if hasattr(env, "drill_prior_gate") else None),
            # PER-DRILL SCAFFOLDING STRENGTH: up where the policy cannot reach a success at all,
            # down where the prior is winning the drill for it. See DrillEnv.drill_floor_scale.
            "dfloor": (env.drill_floor_scale() if hasattr(env, "drill_floor_scale") else 1.0),
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
                    drill = verdict = deck = None
                    if done:
                        outcome = info.get("outcome")
                        deck = info.get("deck")          # read BEFORE reset swaps the opponent
                        drill, verdict = info.get("drill"), info.get("verdict")
                        opp = getattr(e, "opponent", None)
                        if isinstance(opp, SelfPlayOpponent):
                            src = getattr(opp, "_src_sd", None)
                            pfsp = next((j for j, sd_ in enumerate(state["league"])
                                         if sd_ is src), None)
                        nobs = e.reset()
                    obs_cache[i] = nobs
                    out.append(payload(i, e, nobs, reward, done, outcome, pfsp, drill, verdict,
                                       deck))
                conn.send(out)
            elif kind == "deckrec":
                cfg._deck_record = dict(msg[1] or {})
                conn.send(True)
                continue
            elif kind == "league":
                state["league"] = msg[1]
                state["weights"] = msg[2]
                state["sp_prob"] = float(msg[3])
                sp_cache.clear()
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

    def __init__(self, n_envs: int, workers: int, seed: int = 0, drill_frac=None):
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
            pr = ctx.Process(target=_worker, args=(child_c, n, s0, drill_frac), daemon=True)
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

    def set_deck_record(self, rec: dict):
        """Ship the aggregated per-deck W/N table to every worker.

        The parent is the only process that sees every episode, so it owns the record; the workers
        own make_opponent, which is where the weighting is applied. Without this hop deck PFSP was
        inert for any run with --workers > 0.
        """
        for c in self.conns:
            c.send(("deckrec", dict(rec or {})))
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

    def doctrine_card(self, i: int):
        return (self.last[i] or {}).get("dcard") or {}

    def drill_floor(self, i: int):
        """Multiplier on the drill exploration floors for this env's current drill."""
        v = (self.last[i] or {}).get("dfloor")
        return 1.0 if v is None else float(v)

    def drill_gate(self, i: int):
        """P(play) the current drill's reference line would use, or None outside a drill."""
        return (self.last[i] or {}).get("dgate")

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
