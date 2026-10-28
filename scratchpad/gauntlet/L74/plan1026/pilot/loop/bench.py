"""LOOP-INT throughput: K producer processes (loop/producer.py) playing jobs cloned from a dumped actor message
(fastloop FASTLOOP_DUMP=1) for a window after a warm-up; no learner. Reports matches/h, rows/s, process CPU per match
(every producer's getrusage: JVM engine + obs + GC + JIT + the Python side), the per-stage time split, GPU utilisation
(nvidia-smi every 2 s), and writes OUT.json.

usage (pod, run.sh's env): python bench.py MSG.pkl OUT.json --producers K --matches M --threads T --devices cuda:0
       [--warm 120 --seconds 180]
"""
from __future__ import annotations

import argparse
import json
import multiprocessing as mp
import os
import pickle
import resource
import subprocess
import sys
import threading
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE.parents[5]), str(HERE)]


def clone_jobs(jobs, n, k):
    """n jobs from the message's own: tag / seed shifted per copy (producer k's own range)."""
    out = []
    for c in range(n):
        i, spec, g = jobs[c % len(jobs)][:3]
        r = c // len(jobs)
        out.append((i, {**spec, "tag": f"{spec['tag']}_b{k}_{r}", "seed": int(spec["seed"]) + 7919 * (r + 1) + 104729 * k}, g))
    return out


def worker(k, a, base, update, sd, jobs, q):
    from producer import Producer
    P = Producer(base, a.matches, a.threads, a.devices.split(",")[k % len(a.devices.split(","))], Path(a.build), k)
    last = [0.0]

    def progress(matches, rows):
        t = time.perf_counter()
        if t - last[0] >= 5.0:
            last[0] = t
            u = resource.getrusage(resource.RUSAGE_SELF)
            q.put(("p", k, dict(t=time.time(), matches=matches, rows=rows, cpu=u.ru_utime + u.ru_stime,
                                tm=dict(P.tm), jeng=int(P.L.engineNs.get()) / 1e9, jobs=int(P.L.obsNs.get()) / 1e9,
                                rss_mb=u.ru_maxrss / 1024)))
    P.progress = progress
    q.put(("ready", k, None))
    res, skipped, st = P.run(update, sd, clone_jobs(jobs, a.jobs, k))
    q.put(("done", k, dict(matches=len(res), skipped=len(skipped), first_crash=st.get("first_crash"))))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("msg")
    ap.add_argument("out")
    ap.add_argument("--producers", type=int, default=1)
    ap.add_argument("--matches", type=int, default=64)
    ap.add_argument("--threads", type=int, default=4)
    ap.add_argument("--devices", default="cuda:0")
    ap.add_argument("--warm", type=float, default=120.0)
    ap.add_argument("--seconds", type=float, default=180.0)
    ap.add_argument("--jobs", type=int, default=100000, help="jobs per producer (more than the window needs)")
    ap.add_argument("--build", default=os.environ.get("CRFORGE_FACADE_BUILD", str(HERE / "jbuild")))
    a = ap.parse_args()
    base, update, sd, jobs = pickle.loads(Path(a.msg).read_bytes())
    base = {**base, "actor_device": a.devices.split(",")[0]}
    ctx = mp.get_context("spawn")
    q = ctx.Queue()
    ps = [ctx.Process(target=worker, args=(k, a, base, update, sd, jobs, q), daemon=True) for k in range(a.producers)]
    for p in ps:
        p.start()
    ready = 0
    while ready < a.producers:
        m = q.get(timeout=1800)
        ready += m[0] == "ready"
    gpu, stop = [], threading.Event()

    def sample():
        while not stop.is_set():
            try:
                o = subprocess.run(["nvidia-smi", "--query-gpu=index,utilization.gpu,memory.used", "--format=csv,noheader,nounits"],
                                   capture_output=True, text=True, timeout=10).stdout
                gpu.append((time.time(), [[float(x) for x in l.split(",")] for l in o.strip().splitlines()]))
            except Exception:
                pass
            stop.wait(2.0)
    threading.Thread(target=sample, daemon=True).start()
    t0, last, first = time.time(), {}, {}
    while time.time() - t0 < a.warm + a.seconds:
        try:
            m = q.get(timeout=5)
        except Exception:
            continue
        if m[0] == "p":
            last[m[1]] = m[2]
            if time.time() - t0 >= a.warm and m[1] not in first:
                first[m[1]] = m[2]
        elif m[0] == "done":
            raise SystemExit(f"producer {m[1]} ran out of jobs: {m[2]}")
    stop.set()
    ks = [k for k in first if k in last and last[k]["t"] > first[k]["t"]]
    d = lambda f: sum(f(last[k]) - f(first[k]) for k in ks)          # noqa: E731
    wall = max(last[k]["t"] for k in ks) - min(first[k]["t"] for k in ks)
    matches, rows, cpu = d(lambda x: x["matches"]), d(lambda x: x["rows"]), d(lambda x: x["cpu"])
    stages = {s: d(lambda x, s=s: x["tm"].get(s, 0.0)) for s in ("java", "fill", "start", "decide", "forward", "fwd_rows", "fwd_calls")}
    win = [g for t, g in gpu if first and min(first[k]["t"] for k in ks) <= t]
    util = {int(r[0]): sum(gg[i][1] for gg in win) / len(win) for i, r in enumerate(win[0])} if win else {}
    out = dict(producers=a.producers, matches_per_producer=a.matches, threads=a.threads, devices=a.devices,
               producers_measured=len(ks), window_s=wall, matches=matches, matches_per_h=matches / wall * 3600,
               rows=rows, rows_per_s=rows / wall, rows_per_match=rows / max(matches, 1), core_s_per_match=cpu / max(matches, 1),
               cores_busy=cpu / wall, stage_s_sum=stages, stage_s_per_match={s: v / max(matches, 1) for s, v in stages.items()},
               java_engine_core_s_per_match=d(lambda x: x["jeng"]) / max(matches, 1),
               java_obs_core_s_per_match=d(lambda x: x["jobs"]) / max(matches, 1),
               fwd_rows_per_call=stages["fwd_rows"] / max(stages["fwd_calls"], 1), gpu_util_mean=util,
               rss_mb_max=max(last[k]["rss_mb"] for k in ks), host=os.uname().nodename, nproc=os.cpu_count())
    Path(a.out).write_text(json.dumps(out, indent=1))
    print(json.dumps(out))
    for p in ps:
        p.kill()


if __name__ == "__main__":
    main()
