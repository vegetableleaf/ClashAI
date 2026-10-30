"""SPEED2 (1): why producers wait on serve.py -- PolicyServer at the pilot box's per-server block SHAPE.
One PolicyServer (in this process, = serve.py's threads) + P spawned producer processes. Each round a producer sends one block
per model (learner K rows; each of the 8 pilot opponents max(1, round(K / 8)) rows: 16 matches x 2 seats split over the
learner + 8 frozen opponents), runs the P1 decide on each (its cell calls on the server), then sleeps --java-ms (the
JVM step of a real producer). Reports per round: forward wait / decide (cell wait inside) / java, the server's stats and
the CPU seconds of each server thread (GIL load: their sum near the window = one core saturated).

  python srvshape.py --out OUT.json --configs 16x21,64x5,128x3 [--mode eager|graphs] [--seconds 40] [--java-ms 20]
(pod, repo root; PYTHONPATH = repo + pipeline/tests)"""
import argparse
import faulthandler
import signal
import json
import multiprocessing as mp
import os
import sys
import threading
import time
from pathlib import Path

import numpy as np
import torch

REPO = Path.cwd()
sys.path[:0] = [str(REPO), str(REPO / "pipeline/tests"), str(REPO / "scratchpad/gauntlet/L74/plan1026/pilot/loopsrv")]
D = "icebow/data"
B0 = f"{D}/bench/rl_royale/b0/b0_clxiii_s3aux_grafted.pt"
# pilot.yaml's pool: init (= B0) + 5 externals + E4 + w14opp_I, 1/8 of the opponent rows each (G u0160 = timing head:
# forwarded in each producer, not on the server)
POOL = [("learner", B0), ("init", B0)] + [(n, f"{D}/bench/rl_royale/{n}/{n}_u0015.pt") for n in
        ("wk_adapt_exp1", "wk_adapt_exp2", "wk_adapt_exp3", "newsim_base_exp1", "newsim_base_exp2")] + [
        ("E4", f"{D}/bench/rl_royale/rdef_e4/rdef_e4_u0020_barrel2k_cellref_towerref_w2.pt"),
        ("w14opp_I", f"{D}/pipeline/o2/w14opp_I.pt")]
CFG = {"tau": 0.35, "T": 0.5, "T_gate": 0.1}


def thread_cpu() -> dict:
    """native thread id -> utime + stime seconds (this process)."""
    out, tck = {}, os.sysconf("SC_CLK_TCK")
    for t in os.listdir("/proc/self/task"):
        f = Path(f"/proc/self/task/{t}/stat").read_text().rsplit(")", 1)[1].split()
        out[int(t)] = (int(f[11]) + int(f[12])) / tck
    return out


def producer(client, blocks, seconds, java_s, seed, q, go):
    torch.set_num_threads(1)
    __import__("pipeline.decision_options")
    rngs = {name: [np.random.default_rng(seed * 100000 + j * 1000 + i) for i in range(len(b[1]))]
            for j, (name, b) in enumerate(blocks)}
    tm = {"fwd": 0.0, "decide": 0.0, "cell": 0.0, "cell_calls": 0, "java": 0.0, "rounds": 0}
    real_cells = client.cells

    def cells(*a):
        c0 = time.perf_counter()
        try:
            return real_cells(*a)
        finally:
            tm["cell"] += time.perf_counter() - c0
            tm["cell_calls"] += 1
    client.cells = cells
    q.put("ready")
    go.wait()
    n = 0
    t0 = time.perf_counter()
    while time.perf_counter() - t0 < seconds:
        a = time.perf_counter()
        fs = client.forward([(name, b[0], len(b[1])) for name, b in blocks])
        b_ = time.perf_counter()
        for f, (name, (arr, al, st)) in zip(fs, blocks):
            n += len(client.decide_fwd(f, al, st, rngs[name]))
        client.done(fs)
        c = time.perf_counter()
        if java_s:
            time.sleep(java_s)
        tm["fwd"] += b_ - a
        tm["decide"] += c - b_
        tm["java"] += time.perf_counter() - c
        tm["rounds"] += 1
    q.put((n, time.perf_counter() - t0, tm))
    client.close()


def main():
    faulthandler.register(signal.SIGUSR1, all_threads=True)
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--mode", default="eager")
    ap.add_argument("--configs", default="16x21,64x5,128x3")
    ap.add_argument("--seconds", type=float, default=40.0)
    ap.add_argument("--java-ms", type=float, default=20.0)
    ap.add_argument("--wait-ms", type=float, default=1.0)       # serve.py's PolicyServer default
    ap.add_argument("--forced-every", type=int, default=7)
    ap.add_argument("--models", type=int, default=len(POOL), help="first N of POOL (learner first)")
    a = ap.parse_args()
    from srv_bench import rows_for
    from pipeline import batched_rollout as BR
    from pipeline import e1_eval as E
    from pipeline.policy_server import PolicyServer, row_spec
    pool = POOL[:a.models]
    pols = {name: E.load_policy(REPO / p, "cuda")[0] for name, p in pool}
    base = {name: rows_for(pols[name].model, 512, seed=j) for j, (name, _) in enumerate(pool)}
    res = {"mode": a.mode, "java_ms": a.java_ms, "wait_ms": a.wait_ms, "models": [n for n, _ in pool], "rows": []}
    for cfgs in a.configs.split(","):
        K, P = map(int, cfgs.split("x"))
        blocks = []
        for name, _ in pool:
            k = K if name == "learner" else max(1, round(K / (len(pool) - 1)))
            arr = {kk: np.ascontiguousarray(v[:k]) for kk, v in base[name].items()}
            al = np.zeros((k, 8), bool)
            al[:, :4] = True
            st = np.zeros(k, bool)
            st[::a.forced_every] = True
            blocks.append((name, (arr, al, st)))
        models = [{"name": name, "policy": BR.LazyRefine(pols[name]), "cfg": CFG, "block_max": len(b[1]),
                   "spec": row_spec(b[0], E.gen_row_keys(pols[name].model)), "swap": name == "learner"}
                  for name, b in blocks]
        srv = PolicyServer(models, n_clients=P, device="cuda", max_batch=2048, wait_ms=a.wait_ms, mode=a.mode)
        ctx = mp.get_context("spawn")
        q, go = ctx.Queue(), ctx.Event()
        procs = [ctx.Process(target=producer, args=(srv.clients[i], blocks, a.seconds, a.java_ms / 1000, i, q, go))
                 for i in range(P)]
        for p in procs:
            p.start()
        srv.start(warm={name: base[name] for name, _ in blocks})
        for _ in procs:
            assert q.get(timeout=900) == "ready"
        names = {t.native_id: getattr(t, "_target", None).__name__ if getattr(t, "_target", None) else t.name
                 for t in threading.enumerate()}
        s0, c0 = json.loads(json.dumps(srv.stats)), thread_cpu()
        w0 = time.perf_counter()
        go.set()
        got = [q.get(timeout=a.seconds + 900) for _ in procs]
        win = time.perf_counter() - w0
        c1, S = thread_cpu(), srv.stats
        for p in procs:
            p.join(timeout=30)
        srv.close()
        cpu = {}
        for tid, v in c1.items():
            nm = names.get(tid, "other")
            cpu[nm] = round(cpu.get(nm, 0.0) + v - c0.get(tid, 0.0), 2)
        rounds = sum(g[2]["rounds"] for g in got)
        per = {k: round(sum(g[2][k] for g in got) / rounds * 1000, 2) for k in ("fwd", "decide", "cell", "java")}
        row = dict(K=K, producers=P, rows_per_s=round(sum(g[0] for g in got) / max(g[1] for g in got)),
                   round_ms=round(sum(g[1] for g in got) / rounds * 1000, 2), per_round_ms=per,
                   cell_calls_per_round=round(sum(g[2]["cell_calls"] for g in got) / rounds, 2),
                   batches_per_s=round((S["batches"] - s0["batches"]) / win, 1),
                   mean_batch={n: round((S["per_model"][n]["rows"] - s0["per_model"][n]["rows"])
                                        / max(1, S["per_model"][n]["batches"] - s0["per_model"][n]["batches"]), 1)
                               for n in S["per_model"]},
                   server_s={k: round(S[k] - s0[k], 2) for k in ("stack_s", "forward_s", "cell_s", "idle_s")},
                   cell_calls_per_s=round((S["cell_calls"] - s0["cell_calls"]) / win, 1),
                   window_s=round(win, 1), server_thread_cpu_s=cpu,
                   server_cpu_frac=round(sum(cpu.values()) / win, 2))
        print(json.dumps(row), flush=True)
        res["rows"].append(row)
        Path(a.out).write_text(json.dumps(res, indent=1))
        torch.cuda.empty_cache()


if __name__ == "__main__":
    main()
