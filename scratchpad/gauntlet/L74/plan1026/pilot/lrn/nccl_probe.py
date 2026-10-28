"""LEARNER-SCALE DDP probe: NCCL all-reduce (sum) of one fp32 gradient-sized vector (the learner's 2,004,016 trainable
params) across the visible GPUs, timed, and its determinism (two identical all-reduces -> bit-equal results).

    CUDA_VISIBLE_DEVICES=0,1 /workspace/venvf16/bin/python nccl_probe.py --out /workspace/lscale/out/nccl.json
"""
import argparse
import json
import os
import time

import torch
import torch.distributed as dist
import torch.multiprocessing as mp

P = 2_004_016


def rank_main(r, w, out, reps):
    os.environ.update(MASTER_ADDR="127.0.0.1", MASTER_PORT="29533")
    dist.init_process_group("nccl", rank=r, world_size=w)
    torch.cuda.set_device(r)
    g = torch.Generator(device="cuda").manual_seed(1000 + r)
    x = torch.randn(P, device="cuda", generator=g)
    ts = []
    for i in range(reps + 5):
        y = x.clone()
        torch.cuda.synchronize(); t = time.perf_counter()
        dist.all_reduce(y)
        torch.cuda.synchronize()
        if i >= 5:
            ts.append(time.perf_counter() - t)
        if i == 5:
            first = y.clone()
    same = torch.equal(first, y)
    if r == 0:
        ts.sort()
        res = {"world": w, "params": P, "ms_p50": 1000 * ts[len(ts) // 2], "ms_p90": 1000 * ts[int(len(ts) * 0.9)],
               "deterministic": bool(same)}
        print(json.dumps(res), flush=True)
        open(out, "w").write(json.dumps(res))
    dist.destroy_process_group()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--reps", type=int, default=50)
    a = ap.parse_args()
    w = torch.cuda.device_count()
    mp.spawn(rank_main, args=(w, a.out, a.reps), nprocs=w)
