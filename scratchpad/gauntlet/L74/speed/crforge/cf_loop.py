"""S3 step 3 (plan1026 Pillar 4b on crforge): the full-loop prototype, CPU side.

Java-side envs + our observation tensors in direct buffers (CfSpeed.Rollout: N matches per cohort on T Java threads,
tok / mask / sc / unit_form + per-slot legality for both seats after every 10-tick decision) and a Python server that
serves the cohorts in turn. The pod's GPU belongs to ticket S2, so the policy here is a numpy stand-in that draws a legal
action from Java's legality bits (play rate 0.3 per decision, a random point); the forward is projected from SPEED.md.

    A.stepAsync(); B.stepAsync()
    loop: for c in cohorts: c.await_()            # c's rows are ready, zero-copy numpy views
                            act = policy(c views)  # <- the GPU server's forward_batch + decide go here
                            c.stepAsync()          # Java steps c while Python serves the next cohort

usage (pod 32657): /workspace/venvf15/bin/python -I cf_loop.py --envs 2048 --cohorts 2 --threads 24 --seconds 90 \
                   --warm 60 --out runs/loop_n2048_c2_t24.json
"""
from __future__ import annotations

import argparse
import json
import resource
import sys
import time
from pathlib import Path

CF = Path("/workspace/cfspeed")
sys.path[:0] = [str(CF / "pylib"), str(CF), str(CF / "cb")]

import jpype  # noqa: E402
import numpy as np  # noqa: E402
import torch  # noqa: E402

from cf_obs import read_decks, start_jvm  # noqa: E402


def proc_cpu() -> float:
    u = resource.getrusage(resource.RUSAGE_SELF)
    return u.ru_utime + u.ru_stime


class Cohort:
    def __init__(self, CfSpeed, tables, decks, slots, n, threads, seed):
        self.r = CfSpeed.Rollout(tables, decks, slots, None, n, threads, 10)
        self.r.javaPolicy = False
        self.r.buildObs = True
        self.r.legal = True
        self.n = n
        v = lambda b, dt: np.frombuffer(memoryview(b), dt)  # noqa: E731
        self.tok = v(self.r.tokB, np.float32).reshape(n * 2, 64, 14)
        self.mask = v(self.r.maskB, np.uint8).reshape(n * 2, 64)
        self.sc = v(self.r.scB, np.float32).reshape(n * 2, 70)
        self.form = v(self.r.formB, np.int8).reshape(n * 2, 64)
        self.legal = v(self.r.legalB, np.uint8).reshape(n * 2, 4)
        self.act = v(self.r.actB, np.int32).reshape(n * 2, 3)
        self.rng = np.random.default_rng(seed)


def policy(c: Cohort, p_play: float) -> int:
    """Stand-in for the GPU server: hands the rows to torch without a copy (what forward_batch would take), then draws
    each seat's action from the legality bits. Returns the rows served."""
    rows = dict(tok=torch.from_numpy(c.tok), mask=torch.from_numpy(c.mask), sc=torch.from_numpy(c.sc),
                unit_form=torch.from_numpy(c.form))
    k = c.tok.shape[0]
    slot = c.rng.integers(0, 4, k)
    play = (c.rng.random(k) < p_play) & (c.legal[np.arange(k), slot] != 0)
    c.act[:, 0] = np.where(play, slot, -1)
    c.act[:, 1] = c.rng.integers(500, 17500, k)
    c.act[:, 2] = c.rng.integers(500, 31500, k)
    return int(rows["mask"].shape[0])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--envs", type=int, default=2048, help="matches per cohort")
    ap.add_argument("--cohorts", type=int, default=2)
    ap.add_argument("--threads", type=int, default=24, help="Java threads per cohort")
    ap.add_argument("--warm", type=float, default=60.0, help="seconds before the window (JIT, name tables)")
    ap.add_argument("--seconds", type=float, default=90.0, help="measured window")
    ap.add_argument("--p-play", type=float, default=0.3)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()

    start_jvm(a.threads * a.cohorts, xmx="24g")
    CfSpeed = jpype.JClass("CfSpeed")
    tables = CfSpeed.load(str(CF / "crforge_cache/tables/16.402.22"))
    pairs = read_decks(CF / "decks.tsv")
    JStr, JInt = jpype.JArray(jpype.JString), jpype.JArray(jpype.JInt)
    decks = jpype.JArray(JStr)([JStr(d) for p in pairs for d in (p[0], p[2])])
    slots = jpype.JArray(JInt)([JInt(s) for p in pairs for s in (p[1], p[3])])
    cs = [Cohort(CfSpeed, tables, decks, slots, a.envs, a.threads, 100 + k) for k in range(a.cohorts)]
    for c in cs:
        c.r.stepAsync()
    t_start = time.perf_counter()
    win = None
    st = dict(rounds=0, rows=0, wait_s=0.0, serve_s=0.0)
    while True:
        now = time.perf_counter()
        if win is None and now - t_start >= a.warm:
            win = dict(t=now, cpu=proc_cpu(), py=time.thread_time(), matches=sum(int(c.r.matches.get()) for c in cs),
                       ticks=sum(int(c.r.ticks.get()) for c in cs), plays=sum(int(c.r.plays.get()) for c in cs),
                       decisions=sum(int(c.r.decisions.get()) for c in cs))
            st = dict(rounds=0, rows=0, wait_s=0.0, serve_s=0.0)
        if win is not None and now - win["t"] >= a.seconds:
            break
        for c in cs:
            w0 = time.perf_counter()
            c.r.await_()
            w1 = time.perf_counter()
            for s in c.r.names.takeMissing():  # cost probe: every new name maps to a stand-in class (no vocab here)
                (c.r.names.putUnit(s[2:], 1, 0) if s.startswith("U:") else c.r.names.putSpell(s[2:], 1))
            st["rows"] += policy(c, a.p_play)
            c.r.stepAsync()
            st["wait_s"] += w1 - w0
            st["serve_s"] += time.perf_counter() - w1
            st["rounds"] += 1
    end = dict(t=time.perf_counter(), cpu=proc_cpu(), py=time.thread_time(),
               matches=sum(int(c.r.matches.get()) for c in cs), ticks=sum(int(c.r.ticks.get()) for c in cs),
               plays=sum(int(c.r.plays.get()) for c in cs), decisions=sum(int(c.r.decisions.get()) for c in cs))
    for c in cs:
        c.r.await_()
    m = end["matches"] - win["matches"]
    wall = end["t"] - win["t"]
    out = dict(envs_per_cohort=a.envs, cohorts=a.cohorts, threads_per_cohort=a.threads, warm_s=a.warm, wall_s=wall,
               matches=m, matches_per_h=m / wall * 3600, core_s_per_match=(end["cpu"] - win["cpu"]) / m,
               python_main_core_s_per_match=(end["py"] - win["py"]) / m,
               cores_busy=(end["cpu"] - win["cpu"]) / wall,
               rows_per_s=st["rows"] / wall, rows_per_match=st["rows"] / m,
               ticks_per_match=(end["ticks"] - win["ticks"]) / m, plays_per_side=(end["plays"] - win["plays"]) / (2 * m),
               decisions_per_match=(end["decisions"] - win["decisions"]) / m,
               rounds=st["rounds"], round_ms=wall / max(st["rounds"], 1) * 1e3,
               python_wait_frac=st["wait_s"] / wall, python_serve_frac=st["serve_s"] / wall,
               peak_rss_mb=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss // 1024,
               java_heap_used_mb=int(jpype.JClass("java.lang.Runtime").getRuntime().totalMemory()
                                     - jpype.JClass("java.lang.Runtime").getRuntime().freeMemory()) >> 20)
    Path(a.out).write_text(json.dumps(out, indent=1))
    print(json.dumps(out))


if __name__ == "__main__":
    main()
