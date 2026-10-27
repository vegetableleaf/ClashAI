"""S4: is the varying-batch slowdown (146 rows: 11.4 ms at a constant batch, 92 ms per 146 rows with a new batch size
every call) a FIRST-SIGHT cost per shape (allocator / cuBLAS heuristics) or a cost of varying itself? 1.76M LazyRefine,
eager: (1) 200 calls, sizes drawn from 20 sizes, after every size was seen once; (2) 200 fresh sizes, first pass vs the
same 200 sizes again; (3) the same 200 sizes padded to the next power-of-two bucket.
    python shape_probe.py --out shape.json"""
import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np
import torch

sys.path.insert(0, str(Path(__file__).resolve().parent))
from s4_bench import CK, arrays, pinned, policy  # noqa: E402
from pipeline.policy_server import Forward, bucket  # noqa: E402


def timed(fw, arrs, sizes, pad=False):
    torch.cuda.synchronize()
    t = time.perf_counter()
    for n in sizes:
        fw(arrs, bucket(int(n)) if pad else int(n))[2].cpu()
    dt = time.perf_counter() - t
    return dict(ms_per_call=round(dt / len(sizes) * 1000, 2), ms_per_146_rows=round(dt / sum(sizes) * 146 * 1000, 2))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    st = torch.load(CK, map_location="cpu")
    fw = Forward(policy("1.76M", st), "cuda", "eager")
    arrs = pinned(arrays(1024))
    rng = np.random.default_rng(1)
    out = {}
    out["constant_146"] = timed(fw, arrs, [146] * 200)
    few = rng.integers(19, 700, 20)
    timed(fw, arrs, few)                                        # every one of the 20 sizes seen once
    out["20_sizes_seen"] = timed(fw, arrs, rng.choice(few, 200))
    fresh = rng.integers(19, 700, 200)
    out["200_fresh_first_pass"] = timed(fw, arrs, fresh)
    out["200_same_second_pass"] = timed(fw, arrs, fresh)
    fresh2 = rng.integers(19, 700, 200)
    timed(fw, arrs, [bucket(int(n)) for n in fresh2[:1]] + [64, 128, 256, 512, 1024])
    out["200_fresh_padded_to_bucket"] = timed(fw, arrs, fresh2, pad=True)
    out["allocator"] = {k: torch.cuda.memory_stats()[k] for k in ("num_alloc_retries", "num_device_alloc",
                                                                    "num_device_free")}
    print(json.dumps(out, indent=1))
    Path(a.out).write_text(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
