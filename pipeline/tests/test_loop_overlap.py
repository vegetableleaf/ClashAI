"""LOOP-ASYNC: fastloop --overlap scheduling (plan1026/pilot/loop/OVERLAP.md), on a fake rl_royale (no JVM, no torch).

Checks: absent = the alternating call sequence; --overlap 1 = update u+1's wave submitted with version u right after
rollout(u) returns and collected by rollout(u+1) (staleness 1, u0 on-policy, no prefetch at the last update / with a STOP
file); --overlap 0 and 1 play the same matchups whatever the learner rng draws; a prefetch whose jobs changed is dropped
and replayed fresh; refusals; FastPool.collect's wver guard."""
import queue
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

import numpy as np

LOOP = Path(__file__).resolve().parents[2] / "scratchpad/gauntlet/L74/plan1026/pilot/loop"
sys.path.insert(0, str(LOOP))
import fastloop as FL  # noqa: E402

E_, G_ = 3, 2


class FakePool:
    def __init__(self, base, a, log):
        self.log, self.prefetch_miss, self.busy, self.calls = log, 0, False, []

    def submit(self, update, sd, jobs, ver):
        assert not self.busy, "two waves in flight"
        self.busy = True
        self.calls.append(("submit", update, sd, ver))
        return {"update": update, "sd": sd, "jobs": jobs, "ver": ver}

    def collect(self, h):
        self.busy = False
        self.calls.append(("collect", h["update"], h["ver"]))
        return [{"u": h["update"], "ver": h["ver"], "job": j} for j in h["jobs"]], [], {}


def fake_R():
    R = SimpleNamespace()

    class ActorPool:
        def __init__(self, base, n, log, *a, **k):
            pass

        def run(self, kind, update, sd, jobs, shares=None):
            return [("orig", kind)], [], {}

    def sample_matchups(rng, n, update, snaps, cfg, census, p, league_state=None, exploiters=None):
        return [{"tag": f"sp{update:04d}_{i:02d}", "seed": int(rng.integers(2 ** 31 - 1)), "snaps": len(snaps)}
                for i in range(n)]

    class Learner:
        def __init__(self, cfg, kl_steps, snap_at=None):
            self.cfg, self.kl_steps, self.snap_at = cfg, kl_steps, snap_at
            self.rng, self.update, self.trained = np.random.default_rng(cfg["seed"]), 0, []
            self.league, self.census, self.census_p = {"snapshots": []}, None, None
            self.actors = R.ActorPool(None, 0, print)

        def _actor_bytes(self):
            return f"W{self.update}".encode()

        def rollout(self, u):                                 # production's league branch, shape only
            specs = R.sample_matchups(self.rng, int(self.cfg["E"]), u, self.league["snapshots"], self.cfg, None, None)
            jobs = [(i, sp, g) for i, sp in enumerate(specs) for g in range(int(self.cfg["G"]))]
            res, _, _ = self.actors.run("selfplay", u, self._actor_bytes(), jobs)
            return res, {}

        def one_update(self, u):
            res, _ = self.rollout(u)
            pool = self.actors._fl_pool
            pool.calls.append(("train", u))
            self.trained.append({"u": u, "vers": sorted({r["ver"] for r in res}),
                                 "jobs": [r["job"] for r in res]})
            self.rng.permutation(self.kl_steps[u])            # PPO's draws: their count varies (kl_stop)
            if self.snap_at == u:
                self.league["snapshots"].append({"id": f"snap{u}"})
            self.update = u + 1

        def loop(self):
            for u in range(int(self.cfg["max_updates"])):
                self.one_update(u)

    R.ActorPool, R.Learner, R.sample_matchups = ActorPool, Learner, sample_matchups
    return R


def setup(overlap, server=True, cfg_over=None, rl_dir=None):
    R = fake_R()
    d = rl_dir or tempfile.mkdtemp()
    a = SimpleNamespace(overlap=overlap, server="eager" if server else None, rl_dir=d, out=None)
    state = {}
    FL.install(R, a, state, pool=FakePool)
    cfg = {"seed": 7, "E": E_, "G": G_, "max_updates": 4, "stored_values": True, "kl_stop_prev": 0.02,
           "kl_ref_refresh_every": 1, **(cfg_over or {})}
    return R, state, cfg


def drive(overlap, kl_steps=(5, 5, 5, 5), snap_at=None, **kw):
    R, state, cfg = setup(overlap, **kw)
    L = R.Learner(cfg, list(kl_steps), snap_at=snap_at)      # the patched ActorPool.__init__ makes the pool
    L.actors._fl_pool = state["fast"]
    L.loop()
    return L, state["fast"]


class TestOverlap(unittest.TestCase):
    def test_absent_is_alternating(self):
        L, P = drive(None)
        self.assertEqual([t["vers"] for t in L.trained], [[0], [1], [2], [3]])
        self.assertEqual([c for c in P.calls if c[0] == "submit"],
                         [("submit", u, f"W{u}".encode(), u) for u in range(4)])
        for u in range(4):                                    # submit u -> collect u -> train u, nothing prefetched
            i = P.calls.index(("submit", u, f"W{u}".encode(), u))
            self.assertEqual(P.calls[i + 1:i + 3], [("collect", u, u), ("train", u)])

    def test_overlap1_one_stale(self):
        L, P = drive(1)
        self.assertEqual([t["vers"] for t in L.trained], [[0], [0], [1], [2]])   # u0 on-policy, then staleness 1
        subs = [c for c in P.calls if c[0] == "submit"]
        self.assertEqual(subs, [("submit", 0, b"W0", 0), ("submit", 1, b"W0", 0), ("submit", 2, b"W1", 1),
                                ("submit", 3, b"W2", 2)])            # none for u4 = max_updates
        for u in range(3):                                    # u+1's wave is in flight while u trains
            self.assertLess(P.calls.index(("submit", u + 1, f"W{u}".encode(), u)), P.calls.index(("train", u)))
        self.assertEqual(P.prefetch_miss, 0)
        self.assertFalse(P.busy)

    def test_same_matchups_any_ppo_draws(self):
        L0, _ = drive(0, kl_steps=(5, 9, 2, 7))
        L1, _ = drive(1, kl_steps=(3, 1, 8, 4))
        self.assertEqual([t["jobs"] for t in L0.trained], [t["jobs"] for t in L1.trained])
        self.assertEqual([t["vers"] for t in L0.trained], [[0], [1], [2], [3]])
        La, _ = drive(None, kl_steps=(5, 9, 2, 7))            # production: matchups follow the learner rng
        Lb, _ = drive(None, kl_steps=(3, 1, 8, 4))
        self.assertNotEqual([t["jobs"] for t in La.trained][1:], [t["jobs"] for t in Lb.trained][1:])

    def test_changed_jobs_dropped(self):
        L, P = drive(1, snap_at=1)                            # update 1 adds a snapshot: u2's prefetched jobs are stale
        self.assertEqual(P.prefetch_miss, 1)
        self.assertEqual([t["vers"] for t in L.trained], [[0], [0], [2], [2]])   # u2 replayed fresh with W2
        self.assertTrue(all(j[1]["snaps"] == 1 for j in L.trained[2]["jobs"]))

    def test_stop_file_no_prefetch(self):
        d = tempfile.mkdtemp()
        (Path(d) / "STOP").write_text("x")
        L, P = drive(1, rl_dir=d)
        self.assertEqual([t["vers"] for t in L.trained], [[0], [1], [2], [3]])
        self.assertEqual(sum(c[0] == "submit" for c in P.calls), 4)

    def test_refusals(self):
        for kw in ({"server": False}, {"cfg_over": {"stored_values": False}},
                   {"cfg_over": {"kl_ref_refresh_every": 50}}):
            with self.assertRaises(SystemExit):
                drive(1, **kw)
        R, state, cfg = setup(0)
        L = R.Learner(cfg, [1] * 4)
        L.league = None
        with self.assertRaises(SystemExit):
            L.rollout(0)

    def test_other_kinds_untouched(self):
        R, state, cfg = setup(1)
        pool = R.ActorPool(None, 0, print)
        self.assertEqual(pool.run("screen", 0, b"W0", [])[0], [("orig", "screen")])


class TestCollectGuard(unittest.TestCase):
    def pool(self, wver):
        P = FL.FastPool.__new__(FL.FastPool)
        P.a = SimpleNamespace(overlap=1, rl_dir=None, out=None)
        P.log, P.restarts, P.prefetch_miss, P.gen, P.busy = (lambda *_: None), 0, 0, [1], True
        P.out_q = queue.Queue()
        r = {"tag": "sp0001_00", "k": 0, "side": 0, "traj": {"wver": np.array(wver, np.int64)}}
        P.out_q.put(("done", (0, 1), ([r], [], {"wall_s": 1.0, "matches": 1, "rows": 2, "time": {},
                                                "java_engine_core_s": 0.0, "java_obs_core_s": 0.0})))
        return P, {"update": 1, "sd": b"", "ver": 0, "shares": {0: [None]}, "t0": 0.0}

    def test_wver(self):
        rk = sys.modules.get("pipeline.rl_royale")
        sys.modules["pipeline.rl_royale"] = SimpleNamespace(row_key=lambda r: (r["tag"], r["k"]))
        try:
            P, h = self.pool([0, 0])
            P.a.rl_dir = tempfile.mkdtemp()
            res, _, _ = P.collect(h)
            self.assertEqual(len(res), 1)
            self.assertFalse(P.busy)
            P, h = self.pool([0, 1])
            P.a.rl_dir = tempfile.mkdtemp()
            with self.assertRaises(RuntimeError):
                P.collect(h)
        finally:
            if rk is None:
                sys.modules.pop("pipeline.rl_royale", None)
            else:
                sys.modules["pipeline.rl_royale"] = rk


if __name__ == "__main__":
    unittest.main()
