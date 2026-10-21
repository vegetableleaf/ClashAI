"""W16 distributed rollouts (pipeline/remote_actors.py) + the moving KL anchor (``kl_ref_refresh_every``).

    research/ext/Royale/.venv/Scripts/python.exe -m pytest -q pipeline/tests/test_w16_distrib.py

Absent = HEAD f4df581 (PRE): load_config dict and config hash unchanged; ``remote_actors`` never enters the hash.
Sharding over the REAL transport (a loopback server thread; the actor pools are fakes whose rows record the exact share
-- i.e. the in-flight batch -- each job ran in): local + remote == one pool of N actors, row for row, also when the
remote fails mid-run (its shares re-run locally). The real-actor identity check is a pod run (DISTRIB.md).
"""
from __future__ import annotations

import os
import socket
import subprocess
import sys
import threading
import time
import types
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from pipeline import remote_actors as RA                                  # noqa: E402
from pipeline import rl_royale as RL                                      # noqa: E402

PRE = "f4df581"
YAML = REPO / "scratchpad/gauntlet/L74/stepd/cfg/tn_base_s74.yaml"
NOEX = ["league_exploiters=null"]                                        # w7opp.pt is pod-only
os.environ.setdefault("RL_REMOTE_TOKEN", "w16-unit-test-token-0123456789")


def _pre_module():
    src = subprocess.run(["git", "-C", str(REPO), "show", f"{PRE}:pipeline/rl_royale.py"], capture_output=True,
                         text=True, encoding="utf-8", timeout=60)
    if src.returncode:
        raise unittest.SkipTest(f"git show {PRE} failed: {src.stderr.strip()}")
    mod = types.ModuleType("rl_royale_pre_w16")
    mod.__file__ = str(REPO / "pipeline" / "rl_royale.py")
    exec(compile(src.stdout, "rl_royale_pre_w16", "exec"), mod.__dict__)
    return mod


class TestAbsentIsPre(unittest.TestCase):
    def test_load_config_and_hash(self):
        P = _pre_module()
        a, b = P.load_config(YAML, NOEX, False), RL.load_config(YAML, NOEX, False)
        self.assertEqual(a, b)
        self.assertEqual(P.config_sha(a), RL.config_sha(b))
        self.assertEqual(RL.config_sha(b), RL.config_sha({**b, "kl_ref_refresh_every": None}))
        self.assertEqual(RL.config_sha(b), RL.config_sha({**b, "remote_actors": "x.txt"}))   # infra only
        self.assertNotEqual(RL.config_sha(b), RL.config_sha({**b, "kl_ref_refresh_every": 50}))

    def test_validation(self):
        with self.assertRaises(SystemExit):
            RL.load_config(YAML, NOEX + ["kl_ref_refresh_every=0"], False)
        with self.assertRaises(SystemExit):
            RL.load_config(YAML, NOEX + ["remote_actors=no/such/file.txt"], False)
        self.assertEqual(RL.load_config(YAML, NOEX + ["kl_ref_refresh_every=25"], False)["kl_ref_refresh_every"], 25)


# ---- transport + sharding, fake actor pools -----------------------------------------------------------------------
class FakePool:
    """ActorPool's run contract; each row records the share (= the actor's in-flight batch) it ran in."""
    fail_n = None                         # a pool of this size (the server's) raises: the failover test

    def __init__(self, base, n, log, timeout_s, pid_file=None):
        self.n, self.pids, self.runs = int(n), {a: 0 for a in range(int(n))}, 0

    def run(self, kind, update, sd, jobs, shares=None):
        self.runs += 1
        if self.n == FakePool.fail_n:
            raise RL.ActorCrash("fake crash")
        shares = {a: jobs[a::self.n] for a in range(self.n) if jobs[a::self.n]} if shares is None else shares
        rows = []
        for a, js in shares.items():
            batch = tuple(j[0] for j in js)
            rows += [{"tag": f"t{j[0]:03d}", "k": j[2], "entry_index": j[0], "side": "a", "batch": batch,
                      "w": len(sd), "u": update} for j in js]
        rows.sort(key=RL.row_key)
        return rows, [], {a: {"wall_s": 1.0, "matches": len(js), "gpu_peak_mb": None} for a, js in shares.items()}

    def close(self):
        pass


def _free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


class TestDistPool(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._orig = RL.ActorPool
        RL.ActorPool = FakePool
        cls.port = _free_port()
        threading.Thread(target=RA.serve, args=(cls.port, 3, 30.0), daemon=True).start()
        time.sleep(0.5)

    @classmethod
    def tearDownClass(cls):
        RL.ActorPool = cls._orig

    def _ep_file(self):
        f = REPO / ".foreman" / "scratch" / "w16_endpoints.txt"
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(f"# test\n127.0.0.1:{self.port}\n", encoding="utf-8")
        return f

    def test_same_rows_as_one_pool(self):
        jobs = [(i, {"tag": f"t{i:03d}"}, g) for i in range(13) for g in range(4)]
        ref, _, _ = FakePool({}, 5, print, 30).run("rollout", 3, b"x" * 1000, jobs)
        logs = []
        d = RA.DistPool(FakePool({}, 2, print, 30), self._ep_file(), {"b": 1}, logs.append, 30)
        self.assertEqual(d.n, 5)
        got, sk, st = d.run("rollout", 3, b"x" * 1000, jobs)
        self.assertEqual(got, ref)
        self.assertEqual(sorted(st), list(range(5)))
        FakePool.fail_n = 3                                   # the server's pool now crashes: failover to local
        try:
            got2, _, st2 = d.run("rollout", 3, b"x" * 1000, jobs)
        finally:
            FakePool.fail_n = None
        self.assertEqual(got2, ref)
        self.assertEqual(sorted(st2), list(range(5)))
        self.assertTrue(any("FAILOVER" in x for x in logs), logs)
        self.assertNotIn(f"127.0.0.1:{self.port}", d.remotes)   # dropped, retried after RETRY_EVERY runs
        d.close()

    def test_code_mismatch_refused(self):
        code = {**RA.code_hash(), "rl_royale.py": "0" * 64}
        with self.assertRaises(RuntimeError):
            RA._open(f"127.0.0.1:{self.port}", RA.token(), {"b": 1}, code)

    def test_bad_token_rejected(self):
        with self.assertRaises(Exception):
            RA._open(f"127.0.0.1:{self.port}", b"wrong-token-wrong-token", {"b": 1}, RA.code_hash())


class TestHelpers(unittest.TestCase):
    def test_deal_matches_actorpool(self):
        jobs = list(range(37))
        self.assertEqual(RA.deal(jobs, 6), [jobs[a::6] for a in range(6)])

    def test_safe_rel(self):
        for bad in ("/etc/passwd", "../x.pt", "a/../../x.pt"):
            with self.assertRaises(ValueError):
                RA.safe_rel(bad)
        self.assertEqual(RA.safe_rel("icebow/data/x.pt"), REPO / "icebow/data/x.pt")


if __name__ == "__main__":
    unittest.main()
