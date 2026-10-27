"""S1b: why a real server forward runs at ~5-7k rows/s when the microbenchmark does 18.8k: one LazyRefine.forward_batch
(the learner, rlarm_succ48_o_s91_u0075: fv6 + cue, no refine) on B fixture rows, timed in parts (np.stack / H2D /
heads_t / outputs to host) and under torch.profiler (top CPU-side and CUDA ops).
    python server_prof.py --B 146 --out prof.json   (repo root, pod)"""
import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np
import torch

REPO = Path(__file__).resolve().parents[4]
sys.path[:0] = [str(REPO), str(REPO / "pipeline/tests")]
from pipeline import batched_rollout as BR  # noqa: E402
from pipeline import e1_eval as E  # noqa: E402
from test_fast_obs import _rows  # noqa: E402

CK = "icebow/data/bench/rl_royale/rlarm_succ48_o_s91/rlarm_succ48_o_s91_u0075.pt"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--B", type=int, default=146)
    ap.add_argument("--reps", type=int, default=30)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    ap2 = int(__import__("os").environ.get("TORCH_THREADS", "0"))
    if ap2:
        torch.set_num_threads(ap2)
    pol, _ = E.load_policy(REPO / CK, "cuda")
    lz = BR.LazyRefine(pol)
    rows = (_rows(24) * (a.B // 24 + 1))[:a.B]
    keys = E.gen_row_keys(pol.model)
    for _ in range(3):
        lz.forward_batch(rows, "cuda")
    T = {"stack": 0.0, "h2d": 0.0, "heads_t": 0.0, "to_host": 0.0, "full_forward_batch": 0.0}
    with torch.no_grad():
        for _ in range(a.reps):
            torch.cuda.synchronize()
            t0 = time.perf_counter()
            arr = {k: np.ascontiguousarray(np.stack([r[k] for r in rows])) for k in keys}
            t1 = time.perf_counter()
            b = {k: torch.from_numpy(v).to("cuda") for k, v in arr.items()}
            torch.cuda.synchronize()
            t2 = time.perf_counter()
            enc, heads = pol.heads_t(b)
            torch.cuda.synchronize()
            t3 = time.perf_counter()
            [x.float().cpu() for x in (heads["gate"], heads["card"], heads["card_hand"], enc["g"])]
            t4 = time.perf_counter()
            lz.forward_batch(rows, "cuda")
            t5 = time.perf_counter()
            for k, v in zip(T, (t1 - t0, t2 - t1, t3 - t2, t4 - t3, t5 - t4)):
                T[k] += v / a.reps
    out = {"B": a.B, "ms": {k: round(v * 1000, 2) for k, v in T.items()},
           "rows_per_s_full": round(a.B / T["full_forward_batch"])}
    from torch.profiler import ProfilerActivity, profile
    with torch.no_grad(), profile(activities=[ProfilerActivity.CPU, ProfilerActivity.CUDA]) as pr:
        lz.forward_batch(rows, "cuda")
    ka = pr.key_averages()
    out["cuda_ms_total"] = round(sum(e.self_device_time_total for e in ka) / 1000, 2)
    out["n_kernel_launches"] = sum(e.count for e in ka if e.key.startswith("cudaLaunchKernel"))
    out["top_cpu"] = [{"op": e.key[:60], "cpu_ms": round(e.cpu_time_total / 1000, 2), "n": e.count}
                      for e in sorted(ka, key=lambda e: -e.self_cpu_time_total)[:12]]
    out["top_cuda"] = [{"op": e.key[:60], "cuda_ms": round(e.self_device_time_total / 1000, 2)}
                       for e in sorted(ka, key=lambda e: -e.self_device_time_total)[:8]]
    print(json.dumps(out, indent=1))
    Path(a.out).write_text(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
