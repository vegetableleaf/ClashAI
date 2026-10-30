"""SPEED2 (2): what holds a fast-loop producer's GB. One loop/producer.py Producer in this process (CPU, in-process
forwards unless --server ADDR), RSS (smaps_rollup: anon / file) after each stage, the JVM's own accounting (heap
committed / used, non-heap, GC count + seconds; NMT summary when JAVA_TOOL_OPTIONS has -XX:NativeMemoryTracking=summary),
the Python heap of the recorded rows, and a 1 s RSS sampler during one run() of --jobs jobs on --matches slots.

  python mem_probe.py MSG.pkl OUT.json --matches 16 --threads 4 --jobs 16 [--server /dev/shm/loop/srv0.sock]
(run.sh's env; CRFORGE_XMX sets -Xmx)"""
import argparse
import json
import os
import pickle
import subprocess
import sys
import threading
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
LOOP = HERE.parents[1] / "loop"
sys.path[:0] = [str(HERE.parents[6]), str(LOOP)]


def mem() -> dict:
    out = {}
    for line in Path("/proc/self/smaps_rollup").read_text().splitlines()[1:]:
        k, v = line.split(":", 1)
        if k in ("Rss", "Anonymous", "Pss_File", "Pss_Anon"):
            out[k] = round(int(v.split()[0]) / 1024, 1)
    return out


def jvm() -> dict:
    import jpype
    if not jpype.isJVMStarted():
        return {}
    MF = jpype.JClass("java.lang.management.ManagementFactory")
    h, nh = MF.getMemoryMXBean().getHeapMemoryUsage(), MF.getMemoryMXBean().getNonHeapMemoryUsage()
    gc = [(str(b.getName()), int(b.getCollectionCount()), int(b.getCollectionTime())) for b in MF.getGarbageCollectorMXBeans()]
    pools = {str(p.getName()): round(int(p.getUsage().getUsed()) / 2**20) for p in MF.getMemoryPoolMXBeans()}
    return {"heap_committed_mb": round(int(h.getCommitted()) / 2**20), "heap_used_mb": round(int(h.getUsed()) / 2**20),
            "heap_max_mb": round(int(h.getMax()) / 2**20), "nonheap_committed_mb": round(int(nh.getCommitted()) / 2**20),
            "gc": gc, "pools_used_mb": pools}


def nmt() -> str:
    try:
        return subprocess.run(["jcmd", str(os.getpid()), "VM.native_memory", "summary"], capture_output=True, text=True,
                              timeout=60).stdout
    except Exception as e:                                   # noqa: BLE001
        return repr(e)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("msg")
    ap.add_argument("out")
    ap.add_argument("--matches", type=int, default=16)
    ap.add_argument("--threads", type=int, default=4)
    ap.add_argument("--jobs", type=int, default=16)
    ap.add_argument("--server", default=None)
    ap.add_argument("--build", default=os.environ.get("CRFORGE_FACADE_BUILD"))
    a = ap.parse_args()
    st = {"xmx": os.environ.get("CRFORGE_XMX", "16g"), "stages": []}

    def mark(name, **kw):
        st["stages"].append({"stage": name, "t": round(time.time() - t0, 1), **mem(), **kw})
        print(json.dumps(st["stages"][-1]), flush=True)
    t0 = time.time()
    import numpy as np                                       # noqa: F401
    import torch                                             # noqa: F401
    mark("import torch")
    base, update, sd, jobs = pickle.loads(Path(a.msg).read_bytes())
    mark("message loaded", msg_mb=round(Path(a.msg).stat().st_size / 2**20, 1))
    del sd
    from bench import clone_jobs
    from producer import Producer
    P = Producer({**base, "actor_device": "cpu"}, a.matches, a.threads, "cpu", Path(a.build), 0, server=a.server)
    mark("Producer built (JVM + tables + capture env)", jvm=jvm())
    _, update, sd, _ = pickle.loads(Path(a.msg).read_bytes())
    peak, stop = [0.0], threading.Event()

    def sampler():
        while not stop.wait(1.0):
            peak[0] = max(peak[0], mem()["Rss"])
    threading.Thread(target=sampler, daemon=True).start()
    w = time.time()
    res, skipped, stats = P.run(update, sd, clone_jobs(jobs, a.jobs, 0))
    stop.set()
    mark("after run()", run_s=round(time.time() - w, 1), peak_rss_mb=peak[0], matches=len(res), jvm=jvm(),
         opp_models=len(P.opp_cache), time=stats["time"])
    r = pickle.dumps(res)
    mark("results pickled", results_mb=round(len(r) / 2**20, 1), per_match_mb=round(len(r) / 2**20 / max(1, len(res)), 2))
    del res, r
    import gc
    gc.collect()
    mark("results freed + gc", jvm=jvm())
    st["nmt"] = nmt()
    Path(a.out).write_text(json.dumps(st, indent=1))


if __name__ == "__main__":
    main()
