"""LOOP-SRV bench: policy_server.PolicyServer at the production row mix, one GPU (pod, repo root).
  bare   rows/s of each model's padded forward (eager; graphs up to 512) per bucket
  mix    P producer PROCESSES; each round sends one block per model at once (learner K rows, opponent j K * share_j)
         and runs the P1 decide on every block itself (every 7th row forced to play: cell calls); a learner weight
         push every --push-every s. rows/s inside a window after every producer is ready.
    python srv_bench.py --part bare|mix --out OUT.json [--mode eager|graphs] [--configs 256x16,...]"""
import argparse
import json
import multiprocessing as mp
import sys
import threading
import time
from pathlib import Path

import numpy as np
import torch

REPO = Path.cwd()
sys.path[:0] = [str(REPO), str(REPO / "pipeline/tests")]
CB = "/workspace/cb_arm/icebow/data"
# production pool (LOOP-OPP 10-28): learner B0 (grafted) + PFSP at u0 = init (B0 copy) + 5 externals (11.7% of matches
# each, decide 10) + w14opp_I (30% of matches, decide 20 -> half the rows); learner rows = 1 per opponent-seat match row
POOL = [("learner", "/workspace/exploit/ckpt/mem_best_ze_grafted.pt", 1.0),
        ("init", "/workspace/exploit/ckpt/mem_best_ze_grafted.pt", 0.117),
        *[(n, f"{CB}/bench/rl_royale/{n}/{n}_u0015.pt", 0.117)
          for n in ("wk_adapt_exp1", "wk_adapt_exp2", "wk_adapt_exp3", "newsim_base_exp1", "newsim_base_exp2")],
        ("w14opp_I", f"{CB}/pipeline/o2/w14opp_I.pt", 0.15)]
CFG = {"tau": 0.35, "T": 0.5, "T_gate": 0.3}


def rows_for(model, n, seed=0):
    """n rows with the model's gen_row_keys: the live fixture rows (jittered) + random memory events if it has memory."""
    from test_fast_obs import _rows
    from pipeline import e1_eval as E
    rr = _rows(48)
    arr = {k: np.ascontiguousarray(np.stack([rr[i % 48][k] for i in range(n)])) for k in rr[0]}
    if getattr(model, "mem", None) is not None:
        from pipeline.match_memory import empty_rows
        r = np.random.default_rng(seed)
        m = empty_rows(n, model.mem.version)
        for i in range(n):
            k = int(r.integers(1, 60))
            m["mem_mask"][i, :k] = True
            m["mem_ev"][i, :k] = r.normal(0, 0.5, (k, m["mem_ev"].shape[2]))
            m["mem_card"][i, :k] = r.choice(arr["deck_card"][i], k)
            m["mem_form"][i, :k] = 0
        arr.update(m)
    return {k: arr[k] for k in E.gen_row_keys(model)}


def load(path):
    from pipeline import e1_eval as E
    return E.load_policy(path, "cuda")[0]


def part_bare(a):
    from pipeline import batched_rollout as BR
    from pipeline.policy_server import BUCKETS_FINE, Forward, configure
    configure("fp32")
    out = []
    for name, path, _ in POOL[:1] + POOL[2:3] + POOL[-1:] + ([("E4", f"{CB}/bench/rl_royale/rdef_e4/"
                                                              "rdef_e4_u0020_barrel2k_cellref_towerref_w2.pt", 0)]):
        pol = BR.LazyRefine(load(path)).split()
        arr = {k: torch.from_numpy(v).pin_memory().numpy() for k, v in rows_for(pol.model, 2048).items()}
        for mode in ("eager", "graphs"):
            fw = Forward(pol, "cuda", mode, buckets=BUCKETS_FINE, pad=True, graph_max=512)
            for B in (64, 128, 256, 512, 1024, 2048):
                if mode == "graphs" and B > 512:
                    continue
                for _ in range(3):
                    fw(arr, B)[2].cpu()
                torch.cuda.synchronize()
                t = time.perf_counter()
                reps = max(5, 20000 // B)
                for _ in range(reps):
                    fw(arr, B)[2].cpu()
                r = dict(model=name, params=sum(p.numel() for p in pol.model.parameters()), mode=mode, B=B,
                         rows_per_s=round(B * reps / (time.perf_counter() - t)))
                print(json.dumps(r), flush=True)
                out.append(r)
        del pol
        torch.cuda.empty_cache()
    return {"bare": out}


def producer(client, blocks, seconds, seed, q, go):
    torch.set_num_threads(1)
    __import__("pipeline.decision_options")
    rngs = {name: [np.random.default_rng(seed * 100000 + j * 1000 + i) for i in range(len(b[1]))]
            for j, (name, b) in enumerate(blocks)}
    q.put("ready")
    go.wait()
    n = plays = 0
    vers = set()
    t0, c0 = time.perf_counter(), time.process_time()
    while time.perf_counter() - t0 < seconds:
        fs = client.forward([(name, b[0], len(b[1])) for name, b in blocks])
        for f, (name, (arr, al, st)) in zip(fs, blocks):
            out = client.decide_fwd(f, al, st, rngs[name])
            n += len(out)
            plays += sum(d["play"] for d in out)
            if name == "learner":
                vers.add(f.ver)
        client.done(fs)
    q.put((n, plays, time.perf_counter() - t0, time.process_time() - c0, sorted(vers)))
    client.close()


def part_mix(a):
    from pipeline import batched_rollout as BR
    from pipeline import e1_eval as E
    from pipeline.policy_server import PolicyServer, row_spec
    res = {"mode": a.mode, "max_batch": a.max_batch, "wait_ms": a.wait_ms, "pool": [(n, s) for n, _, s in POOL], "rows": []}
    pols = {name: load(path) for name, path, _ in POOL}
    base = {name: rows_for(pols[name].model, 512, seed=j) for j, (name, _, _) in enumerate(POOL)}
    learner_sd = {k: v.detach().cpu().clone() for k, v in pols["learner"].model.state_dict().items()}
    for cfgs in a.configs.split(","):
        K, P = map(int, cfgs.split("x"))
        blocks = []
        for name, _, share in POOL:
            k = max(1, round(K * share))
            arr = {kk: np.ascontiguousarray(v[:k]) for kk, v in base[name].items()}
            al = np.zeros((k, 8), bool)
            al[:, :4] = True
            st = np.zeros(k, bool)
            st[::7] = True
            blocks.append((name, (arr, al, st)))
        models = [{"name": name, "policy": BR.LazyRefine(pols[name]), "spec": row_spec(b[0], E.gen_row_keys(pols[name].model)),
                   "cfg": CFG, "block_max": len(b[1]), "swap": name == "learner"} for name, b in blocks]
        srv = PolicyServer(models, n_clients=P, device="cuda", max_batch=a.max_batch, wait_ms=a.wait_ms, mode=a.mode)
        ctx = mp.get_context("spawn")
        q, go = ctx.Queue(), ctx.Event()
        procs = [ctx.Process(target=producer, args=(srv.clients[i], blocks, a.seconds, i, q, go)) for i in range(P)]
        for p in procs:
            p.start()
        t = time.perf_counter()
        srv.start(warm={name: base[name] for name, _ in blocks})
        warm_s = time.perf_counter() - t
        for _ in procs:
            assert q.get(timeout=600) == "ready"
        s0 = json.loads(json.dumps(srv.stats))
        stop = threading.Event()

        def pusher():                                    # the learner's weight versions, same weights re-pushed
            v = 1
            while not stop.wait(a.push_every):
                srv.push("learner", v, learner_sd)
                v += 1
        th = threading.Thread(target=pusher, daemon=True)
        go.set()
        if a.push_every > 0:
            th.start()
        got = [q.get(timeout=a.seconds + 600) for _ in procs]
        stop.set()
        S = srv.stats
        for p in procs:
            p.join(timeout=30)
        srv.close()
        wall = max(g[2] for g in got)
        rows = sum(g[0] for g in got)
        pm = {n: {"rows_per_s": round((S["per_model"][n]["rows"] - s0["per_model"][n]["rows"]) / wall),
                  "mean_batch": round((S["per_model"][n]["rows"] - s0["per_model"][n]["rows"])
                                      / max(1, S["per_model"][n]["batches"] - s0["per_model"][n]["batches"])),
                  "pad_frac": round((S["per_model"][n]["pad_rows"] - s0["per_model"][n]["pad_rows"])
                                    / max(1, S["per_model"][n]["rows"] - s0["per_model"][n]["rows"]), 3)}
              for n in S["per_model"]}
        row = dict(block=K, producers=P, rows_per_s=round(rows / wall), learner_rows_per_s=pm["learner"]["rows_per_s"],
                   play_frac=round(sum(g[1] for g in got) / rows, 3), warm_s=round(warm_s, 1),
                   batches_per_s=round((S["batches"] - s0["batches"]) / wall),
                   server_s={k: round(S[k] - s0[k], 2) for k in ("stack_s", "forward_s", "cell_s", "idle_s", "push_s")},
                   pushes=S["pushes"] - s0["pushes"], push_ms=round(1000 * (S["push_s"] - s0["push_s"])
                                                                    / max(1, S["pushes"] - s0["pushes"]), 1),
                   learner_versions_seen=sorted({v for g in got for v in g[4]})[-3:],
                   producer_cpu_us_per_row=round(sum(g[3] for g in got) / rows * 1e6, 1),
                   gpu_mem_gb=round(torch.cuda.max_memory_allocated() / 2**30, 2), per_model=pm)
        print(json.dumps(row), flush=True)
        res["rows"].append(row)
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--part", choices=("bare", "mix"), required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--mode", default="eager")
    ap.add_argument("--configs", default="256x16,256x32,512x24")
    ap.add_argument("--seconds", type=float, default=30.0)
    ap.add_argument("--max-batch", type=int, default=2048)
    ap.add_argument("--wait-ms", type=float, default=2.0)
    ap.add_argument("--push-every", type=float, default=6.0)
    a = ap.parse_args()
    res = part_bare(a) if a.part == "bare" else part_mix(a)
    Path(a.out).write_text(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
