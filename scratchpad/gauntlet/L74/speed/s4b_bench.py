"""S4b: the forward-only server (policy_server.ProcServer) with the P1 decide in P producer PROCESSES (spawned), fp32
eager, one 4090: end-to-end rows/s (decided rows the producers got back, inside a common window after every producer
is ready) vs the bare forward at the same batch (s4_bench.time_forward). Target >= 95%.
  --ckpt  default the TRAINING learner (rlarm_succ48_o_s91_u0075: 1.55M, no refine -> cell calls overlap forwards);
          the deployed CLXIII (refine layers -> cell calls serialized with forwards) with --ckpt clxiii
    python s4b_bench.py --out s4b.json   (repo root, pod)"""
import argparse
import json
import multiprocessing as mp
import sys
import time
from pathlib import Path

import numpy as np


sys.path.insert(0, str(Path(__file__).resolve().parent))
LEARNER = "icebow/data/bench/rl_royale/rlarm_succ48_o_s91/rlarm_succ48_o_s91_u0075.pt"


def producer(client, block, seconds, seed, q, go):
    import torch as t
    t.set_num_threads(1)
    __import__("pipeline.decision_options")             # imports before the window
    arr, al, st = block
    K = len(al)
    rngs = [np.random.default_rng(seed * 100000 + i) for i in range(K)]
    q.put("ready")
    go.wait()
    n = plays = 0
    t0 = time.perf_counter()
    cpu0 = time.process_time()
    while time.perf_counter() - t0 < seconds:
        out = client.decide(arr, al, st, rngs)
        n += K
        plays += sum(d["play"] for d in out)
    q.put((n, plays, time.perf_counter() - t0, time.process_time() - cpu0))
    client.close()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--seconds", type=float, default=30.0)
    ap.add_argument("--max-batch", type=int, default=2048)
    ap.add_argument("--wait-ms", type=float, default=5.0)
    ap.add_argument("--ckpt", default="learner", choices=("learner", "clxiii"))
    ap.add_argument("--configs", default="256x16,256x32,512x24")
    ap.add_argument("--forced-every", type=int, default=7, help="every k-th row is forced to play (cell calls)")
    a = ap.parse_args()
    from pipeline import batched_rollout as BR
    from pipeline import e1_eval as E
    from pipeline.policy_server import Forward, ProcServer, row_spec
    from s4_bench import CK, REPO, arrays, pinned, time_forward
    if a.ckpt == "learner":
        pol = BR.LazyRefine(E.load_policy(REPO / LEARNER, "cuda")[0])
    else:
        pol = BR.LazyRefine(E.load_policy(CK, "cuda")[0])
    keys = E.gen_row_keys(pol.model)
    res = {"ckpt": a.ckpt, "params": sum(p.numel() for p in pol.model.parameters()), "max_batch": a.max_batch,
           "wait_ms": a.wait_ms, "rows": []}
    fw = Forward(pol, "cuda", "eager")
    big = pinned({k: v for k, v in arrays(a.max_batch).items() if k in keys})
    res["bare_forward_rows_per_s"] = round(a.max_batch / time_forward(fw, big, a.max_batch, 20))
    print(json.dumps(res), flush=True)
    for cfgs in a.configs.split(","):
        K, P = map(int, cfgs.split("x"))
        arr = {k: np.ascontiguousarray(v[:K]) for k, v in arrays(K).items() if k in keys}
        al = np.zeros((K, 8), bool)
        al[:, :4] = True
        stl = np.zeros(K, bool)
        stl[::a.forced_every] = True                        # forced plays: the cell path runs (7: about 15% of rows)
        srv = ProcServer(pol, row_spec(arr, keys), P, K, {"tau": 0.35, "T": 0.5, "T_gate": 0.3}, "cuda",
                         max_batch=a.max_batch, wait_ms=a.wait_ms)
        ctx = mp.get_context("spawn")
        q, go = ctx.Queue(), ctx.Event()
        procs = [ctx.Process(target=producer, args=(srv.clients[i], (arr, al, stl), a.seconds, i, q, go))
                 for i in range(P)]
        for p in procs:
            p.start()
        srv.start()
        for _ in procs:
            assert q.get(timeout=300) == "ready"
        s0 = dict(srv.stats)
        go.set()
        got = [q.get(timeout=a.seconds + 300) for _ in procs]
        S = {k: srv.stats[k] - s0[k] for k in s0}
        for p in procs:
            p.join(timeout=30)
        srv.close()
        wall = max(g[2] for g in got)
        rows = sum(g[0] for g in got)
        row = dict(block=K, producers=P, rows_per_s=round(rows / wall), play_frac=round(sum(g[1] for g in got) / rows, 3),
                   vs_bare=round(rows / wall / res["bare_forward_rows_per_s"], 3), serialized_cells=srv.serialized_cells,
                   mean_batch=round(S["rows"] / max(S["batches"], 1)),
                   cell_calls_per_batch=round(S["cell_calls"] / max(S["batches"], 1), 2),
                   server_s={k: round(S[k], 2) for k in ("stack_s", "forward_s", "cell_s", "idle_s")},
                   producer_cpu_us_per_row=round(sum(g[3] for g in got) / rows * 1e6, 2))
        print(json.dumps(row), flush=True)
        res["rows"].append(row)
    Path(a.out).write_text(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
