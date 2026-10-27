"""S4 (plan1026 Pillar 4b on crforge): one 4090, CLXIII fv6 inputs (the live row fixture, jittered, tiled).
  forward  rows/s of policy_server.Forward (stack + H2D + forward + p/hand) per size x mode x batch
  server   AsyncPolicyServer end to end: P producer threads, blocks of K rows, decide on / off
  slow     why S1's 146-row forward took 27-31 ms inside a rollout (12.8 alone): constant vs varying batch, one vs 8
           alternating models, quiet vs CPU burner processes
    python s4_bench.py --part forward --out f.json   (repo root, pod)"""
import argparse
import json
import multiprocessing as mp
import sys
import threading
import time
from pathlib import Path

import numpy as np
import torch

REPO = Path(__file__).resolve().parents[4]
sys.path[:0] = [str(REPO), str(REPO / "pipeline/tests"), str(Path(__file__).resolve().parent)]
from model_scale import build  # noqa: E402
from pipeline import batched_rollout as BR  # noqa: E402
from pipeline import e1_eval as E  # noqa: E402
from pipeline.policy_server import AsyncPolicyServer, Forward  # noqa: E402
from test_fast_obs import CK, _rows  # noqa: E402

SIZES = {"1.76M": (128, 4), "5M": (224, 6), "10M": (288, 8), "15M": (320, 10)}


def policy(size, st, dev="cuda"):
    d, L = SIZES[size]
    m = build(st, d, L, max(4, d // 32), dev)
    return BR.LazyRefine(E.GenPolicy(m, st["card_vocab"]))


def arrays(n_max=8192):
    rows = _rows(48)
    keys = rows[0].keys()
    return {k: np.ascontiguousarray(np.stack([rows[i % len(rows)][k] for i in range(n_max)])) for k in keys}


def pinned(arrs):
    return {k: torch.from_numpy(v).pin_memory().numpy() for k, v in arrs.items()}


def time_forward(fw, arrs, n, reps):
    for _ in range(3):
        fw(arrs, n)[2].cpu()
    torch.cuda.synchronize()
    t = time.perf_counter()
    for _ in range(reps):
        fw(arrs, n)[2].cpu()                                   # p to host = the decide's sync point
    return (time.perf_counter() - t) / reps


def part_forward(a, st):
    arrs = pinned(arrays())
    out = []
    for size in a.sizes.split(","):
        pol = policy(size, st)
        nparam = sum(p.numel() for p in pol.model.parameters())
        for mode in a.modes.split(","):
            fw = Forward(pol, "cuda", mode)
            for B in (256, 512, 1024, 2048, 4096, 8192):
                try:
                    s = time_forward(fw, arrs, B, max(3, 20 * 1024 // B))
                    row = dict(size=size, params=nparam, mode=mode, B=B, ms=round(s * 1000, 2), rows_per_s=round(B / s))
                except Exception as exc:                       # noqa: BLE001 -- OOM / capture failure: recorded
                    row = dict(size=size, params=nparam, mode=mode, B=B, error=repr(exc)[:200])
                    torch.cuda.empty_cache()
                print(json.dumps(row), flush=True)
                out.append(row)
            del fw
            torch.cuda.empty_cache()
    return out


def part_server(a, st):
    arrs = arrays(1024)
    out = []
    pol = policy("1.76M", st)
    for mode in a.modes.split(","):
        fw = Forward(pol, "cuda", mode)                       # one per mode: graphs captured once per bucket
        for decide_on, piped in ((False, False), (True, False), (True, True)):
            if piped and mode == "graphs":
                continue
            for K, P in ((256, 16), (64, 64)):
                srv = AsyncPolicyServer(pol, {"tau": 0.35, "T": 0.5, "T_gate": 0.3}, "cuda", max_batch=a.max_batch,
                                        wait_ms=1.0, mode=mode, decide=decide_on, pipelined=piped, forward=fw)
                blk = {k: v[:K] for k, v in arrs.items()}
                al = np.zeros((K, 8), bool)
                al[:, :4] = True
                stl = np.zeros(K, bool)
                stl[::7] = True                                 # forced plays: the cell path runs
                done, stop = [0], [False]

                def prod(seed):
                    g = [np.random.default_rng(seed * 10000 + i) for i in range(K)]
                    while not stop[0]:
                        srv.submit(blk, al, stl, g).result()
                        done[0] += K
                th = [threading.Thread(target=prod, args=(i,), daemon=True) for i in range(P)]
                for t in th:
                    t.start()
                time.sleep(5)
                d0, s0, t0 = done[0], dict(srv.stats), time.perf_counter()
                time.sleep(a.seconds)
                d1, t1 = done[0], time.perf_counter()
                S = srv.stats
                stop[0] = True
                for t in th:
                    t.join(timeout=30)
                srv.close()
                nb = S["batches"] - s0["batches"]
                row = dict(mode=mode, decide=decide_on, pipelined=piped, block=K, producers=P, rows_per_s=round((d1 - d0) / (t1 - t0)),
                           mean_batch=round((S["rows"] - s0["rows"]) / max(nb, 1)),
                           **{k: round((S[k] - s0[k]) / (t1 - t0), 3) for k in ("stack_s", "forward_s", "decide_s", "idle_s")})
                print(json.dumps(row), flush=True)
                out.append(row)
    return out


def burn(stop):
    x = 0
    while not stop.is_set():
        for i in range(100000):
            x += i * i


def part_slow(a, st):
    arrs = pinned(arrays(1024))
    import copy
    pols = [policy("1.76M", st)]
    for i in range(7):                                         # 7 more policies with their own weights (S1's league)
        q = copy.deepcopy(pols[0].pol)
        with torch.no_grad():
            for t in q.model.parameters():
                t.add_(torch.randn_like(t) * 1e-3)
        pols.append(BR.LazyRefine(q))
    fws = [Forward(p, "cuda", "eager") for p in pols]
    rng = np.random.default_rng(0)

    def run(varying, multi, reps=200):
        ns = rng.integers(19, 700, reps) if varying else np.full(reps, 146)
        for i in range(10):
            fws[0](arrs, 146)[2].cpu()
        torch.cuda.synchronize()
        t = time.perf_counter()
        tot = 0
        for i in range(reps):
            f = fws[i % 8] if multi else fws[0]
            f(arrs, int(ns[i]))[2].cpu()
            tot += int(ns[i])
        dt = time.perf_counter() - t
        return dict(ms_per_call=round(dt / reps * 1000, 2), ms_per_146_rows=round(dt / tot * 146 * 1000, 2))
    out = []
    for burners in (0, a.burners):
        ev = mp.get_context("fork").Event()
        procs = [mp.get_context("fork").Process(target=burn, args=(ev,), daemon=True) for _ in range(burners)]
        for p in procs:
            p.start()
        time.sleep(1)
        for varying in (False, True):
            for multi in (False, True):
                row = dict(burners=burners, varying_batch=varying, eight_models=multi, **run(varying, multi))
                print(json.dumps(row), flush=True)
                out.append(row)
        ev.set()
        for p in procs:
            p.join(timeout=10)
    return out


def _decisions(pol, arrs, n, ctx):
    """decide (sample, SAMPLE_RULES, the same per-row rng seeds every call) on rows [:n] under precision ``ctx``."""
    from pipeline.decision_options import DecisionOptions, decide, sample_rules
    fw = Forward(pol, "cuda", "eager")
    al = np.zeros((n, 8), bool)
    al[:, :4] = True
    stalled = np.zeros(n, bool)
    stalled[::4] = True                                        # forced plays: card and cell draws on a quarter of rows
    with ctx():
        enc, heads, p, _ = fw(arrs, n)
        hd = {k: v[:n].float() for k, v in heads.items()}
        out = decide(hd, p.cpu().numpy(), al, stalled, tau=0.35, options=sample_rules(DecisionOptions()),
                     rngs=[None] * n, decode="sample",
                     sampler={"tau_r": None, "T": 0.5, "T_gate": 0.3, "heads": frozenset(("gate", "card", "cell")),
                              "rngs": [np.random.default_rng(i) for i in range(n)]},
                     cell_logits=lambda ids, slots: fw.cell_logits(enc, n)(ids, slots).float())
    return [(d["play"], d["slot"], d["cell"]) for d in out], p.double().cpu().numpy()


def part_precision(a, st):
    """fp32 / TF32 matmuls / bf16 autocast: plateau rows/s per size (eager, B 1,024 and 2,048), FLOPs per row
    (torch.utils.flop_counter on one fp32 forward) -> achieved TFLOPS, and the decision-change rate vs fp32 on a fixed
    obs set of ``--fixed`` distinct rows (same per-row rng seeds)."""
    import contextlib
    from torch.utils.flop_counter import FlopCounterMode
    arrs = pinned(arrays())
    fixed = {k: np.ascontiguousarray(np.stack([r[k] for r in _rows(a.fixed)])) for k in _rows(1)[0]}
    fixed = pinned(fixed)

    def ctx_for(mode):
        def ctx():
            torch.backends.cuda.matmul.allow_tf32 = mode == "tf32"
            torch.backends.cudnn.allow_tf32 = mode == "tf32"
            return torch.autocast("cuda", dtype=torch.bfloat16) if mode == "bf16" else contextlib.nullcontext()
        return ctx
    out = []
    for size in a.sizes.split(","):
        pol = policy(size, st)
        nparam = sum(q.numel() for q in pol.model.parameters())
        fw = Forward(pol, "cuda", "eager")
        torch.backends.cuda.matmul.allow_tf32 = False
        torch.backends.cudnn.allow_tf32 = False
        b64 = {k: torch.from_numpy(arrs[k][:64]).cuda() for k in fw.keys}
        with FlopCounterMode(display=False) as fc, torch.enable_grad():   # grad on: the unfused encoder path, whose
            fw.fn(b64)                                                    # matmuls / attention the counter sees
        flops_row = fc.get_total_flops() / 64
        ref, p_ref = _decisions(pol, fixed, a.fixed, ctx_for("fp32"))
        for mode in ("fp32", "tf32", "bf16"):
            ctx = ctx_for(mode)
            row = dict(size=size, params=nparam, mode=mode, gflop_per_row=round(flops_row / 1e9, 4))
            for B in (1024, 2048):
                try:
                    with ctx():
                        s = time_forward(fw, arrs, B, max(3, 20 * 1024 // B))
                    row[f"rows_per_s_B{B}"] = round(B / s)
                except Exception as exc:                       # noqa: BLE001 -- OOM: recorded
                    row[f"rows_per_s_B{B}"] = repr(exc)[:80]
                    torch.cuda.empty_cache()
            best = max(v for k, v in row.items() if k.startswith("rows_per_s") and isinstance(v, int))
            row["achieved_tflops"] = round(best * flops_row / 1e12, 2)
            got, p_got = _decisions(pol, fixed, a.fixed, ctx)
            row["decision_change_rate"] = round(sum(x != y for x, y in zip(ref, got)) / a.fixed, 5)
            row["max_abs_dp_gate"] = float(np.abs(p_got - p_ref).max())
            print(json.dumps(row), flush=True)
            out.append(row)
        torch.backends.cuda.matmul.allow_tf32 = False
        torch.backends.cudnn.allow_tf32 = False
        del fw, pol
        torch.cuda.empty_cache()
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--part", choices=("forward", "server", "slow", "precision"), required=True)
    ap.add_argument("--fixed", type=int, default=2048, help="precision: distinct rows in the fixed obs set")
    ap.add_argument("--sizes", default="1.76M,5M,10M,15M")
    ap.add_argument("--modes", default="eager,graphs,compile")
    ap.add_argument("--seconds", type=float, default=20.0)
    ap.add_argument("--max-batch", type=int, default=2048)
    ap.add_argument("--burners", type=int, default=48)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    st = torch.load(CK, map_location="cpu")
    res = {"forward": part_forward, "server": part_server, "slow": part_slow,
           "precision": part_precision}[a.part](a, st)
    Path(a.out).write_text(json.dumps({"gpu": torch.cuda.get_device_name(0), "rows": res}, indent=1))


if __name__ == "__main__":
    main()
