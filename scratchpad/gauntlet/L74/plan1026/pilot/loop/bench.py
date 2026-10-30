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


def proc_cpu(pid: int) -> float:
    """utime + stime (s) of a process, all its threads (/proc/PID/stat)."""
    f = Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()
    return (int(f[11]) + int(f[12])) / os.sysconf("SC_CLK_TCK")


def clone_jobs(jobs, n, k):
    """n jobs from the message's own: tag / seed shifted per copy (producer k's own range)."""
    out = []
    for c in range(n):
        i, spec, g = jobs[c % len(jobs)][:3]
        r = c // len(jobs)
        out.append((i, {**spec, "tag": f"{spec['tag']}_b{k}_{r}", "seed": int(spec["seed"]) + 7919 * (r + 1) + 104729 * k}, g))
    return out


def start_servers(base, update, sd, jobs, devices, mode, block_max, root="/dev/shm/loop", push=True):
    """One serve.py per device (LOOP-SRV) + (push) this update's learner weights in the watch dir -> the Popen list; the
    producer for device g connects to ROOT/srv{g}.sock. base["init_path"] = the learner's architecture checkpoint."""
    import torch
    from pipeline import rl_royale as R
    wd = Path(root) / "weights"
    wd.mkdir(parents=True, exist_ok=True)
    if push:                                     # the ability head's tensors ride along (policy_server._load)
        from producer import server_version
        msd, _ = R.split_actor_sd(sd, "cpu")
        v = server_version(update, any(k.startswith(R.ABILITY_SD) for k in msd))
        torch.save({"version": v, "state_dict": msd}, wd / f"learner.v{v:08d}.pt")
        (wd / "learner.latest").write_text(str(v))
    opps = sorted({j[1]["opp"]["path"] for j in jobs})
    S = int(os.environ.get("FASTLOOP_SHARDS", "1"))      # SPEED2 F2' (opt-in): S model-sharded servers per device:
    servers = []                                          # srv{g}.sock = the learner only, srv{g}.s{j}.sock = opps[j-1::S-1]
    for g, dv in enumerate(devices):
        for j in range(S):
            addr = f"{root}/srv{g}.sock" if j == 0 else f"{root}/srv{g}.s{j}.sock"
            sub = opps if S == 1 else [] if j == 0 else opps[j - 1::S - 1]
            if j and not sub:
                raise SystemExit(f"FASTLOOP_SHARDS {S}: shard {j} has no opponent ({len(opps)} opponents)")
            Path(addr + ".ready").unlink(missing_ok=True)
            servers.append(subprocess.Popen([sys.executable, str(HERE / "serve.py"), "--listen", addr, "--device", dv,
                                             "--watch", str(wd), "--learner", base["init_path"] if "init_path" in base
                                             else opps[0], "--block-max", str(block_max), "--mode", mode, "--opp", *sub]
                                            + (["--mem-full", base["mem_full"]] if base.get("mem_full") else [])
                                            + (["--no-learner"] if j else [])))
            while not Path(addr + ".ready").exists():
                if servers[-1].poll() is not None:
                    raise SystemExit("serve.py exited")
                time.sleep(1)
    return servers


def worker(k, a, base, update, sd, jobs, q):
    try:
        _worker(k, a, base, update, sd, jobs, q)
    except BaseException:
        import traceback
        q.put(("error", k, traceback.format_exc()))


def _worker(k, a, base, update, sd, jobs, q):
    from producer import Producer
    dev = "cpu" if a.server and not a.local_forward else a.devices.split(",")[k % len(a.devices.split(","))]
    srv = f"/dev/shm/loop/srv{k % len(a.devices.split(','))}.sock" if a.server else None
    P = Producer({**base, "actor_device": dev}, a.matches, a.threads, dev, Path(a.build), k, server=srv)
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
    ap.add_argument("--server", default=None, help="eager | graphs: forwards on serve.py (LOOP-SRV), one per device")
    ap.add_argument("--local-forward", action="store_true", help="with --server: in-process forwards (timing heads) on the "
                    "producer's --devices entry, as fastloop --local-forward (absent = CPU)")
    a = ap.parse_args()
    base, update, sd, jobs = pickle.loads(Path(a.msg).read_bytes())
    base = {**base, "actor_device": a.devices.split(",")[0]}
    servers = start_servers(base, update, sd, jobs, a.devices.split(","), a.server, a.matches) if a.server else []
    ctx = mp.get_context("spawn")
    q = ctx.Queue()
    ps = [ctx.Process(target=worker, args=(k, a, base, update, sd, jobs, q), daemon=True) for k in range(a.producers)]
    for p in ps:
        p.start()
    ready = 0
    while ready < a.producers:
        m = q.get(timeout=1800)
        if m[0] == "error":
            raise SystemExit(f"producer {m[1]}:\n{m[2]}")
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
    srv_cpu0 = None
    while time.time() - t0 < a.warm + a.seconds:
        try:
            m = q.get(timeout=5)
        except Exception:
            continue
        if m[0] == "p":
            last[m[1]] = m[2]
            if time.time() - t0 >= a.warm and m[1] not in first:
                first[m[1]] = m[2]
                if srv_cpu0 is None:
                    srv_cpu0, srv_t0 = sum(proc_cpu(s.pid) for s in servers), time.time()
        elif m[0] in ("done", "error"):
            raise SystemExit(f"producer {m[1]} ran out of jobs / failed: {m[2]}")
    stop.set()
    srv_cpu = (sum(proc_cpu(s.pid) for s in servers) - srv_cpu0) / (time.time() - srv_t0) if servers else 0.0
    ks = [k for k in first if k in last and last[k]["t"] > first[k]["t"]]
    d = lambda f: sum(f(last[k]) - f(first[k]) for k in ks)          # noqa: E731
    wall = max(last[k]["t"] for k in ks) - min(first[k]["t"] for k in ks)
    matches, rows, cpu = d(lambda x: x["matches"]), d(lambda x: x["rows"]), d(lambda x: x["cpu"])
    stages = {s: d(lambda x, s=s: x["tm"].get(s, 0.0)) for s in ("java", "fill", "start", "decide", "gather", "forward", "forward_wait", "decide_py", "fwd_rows", "fwd_calls")}
    win = [g for t, g in gpu if first and min(first[k]["t"] for k in ks) <= t]
    util = {int(r[0]): sum(gg[i][1] for gg in win) / len(win) for i, r in enumerate(win[0])} if win else {}
    out = dict(producers=a.producers, matches_per_producer=a.matches, threads=a.threads, devices=a.devices,
               producers_measured=len(ks), window_s=wall, matches=matches, matches_per_h=matches / wall * 3600,
               rows=rows, rows_per_s=rows / wall, rows_per_match=rows / max(matches, 1), core_s_per_match=cpu / max(matches, 1),
               cores_busy=cpu / wall, stage_s_sum=stages, stage_s_per_match={s: v / max(matches, 1) for s, v in stages.items()},
               java_engine_core_s_per_match=d(lambda x: x["jeng"]) / max(matches, 1),
               java_obs_core_s_per_match=d(lambda x: x["jobs"]) / max(matches, 1),
               fwd_rows_per_call=stages["fwd_rows"] / max(stages["fwd_calls"], 1), gpu_util_mean=util,
               rss_mb_max=max(last[k]["rss_mb"] for k in ks), host=os.uname().nodename, nproc=os.cpu_count(),
               server=a.server, server_cores_busy=srv_cpu,
               all_in_core_s_per_match=(cpu + srv_cpu * wall) / max(matches, 1))
    Path(a.out).write_text(json.dumps(out, indent=1))
    print(json.dumps(out))
    for p in ps:
        p.kill()
    for s in servers:
        s.kill()


if __name__ == "__main__":
    main()
