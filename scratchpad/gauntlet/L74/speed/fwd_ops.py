"""SPEED.md (c): where a B=1024 CLXIII-shape forward spends its CUDA time (torch.profiler, top ops), and rows/s under
fp32 / TF32 matmuls / bf16 autocast for each size (the batched server's precision options; the training actors are
fp32 on CPU today, so anything but fp32 changes the sampled log-probs' bits).
    python fwd_ops.py --ckpt CLXIII.pt --batch X.batch.pt --out ops.json
"""
import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from model_scale import build  # noqa: E402


def rate(m, b, mode, reps=10):
    import torch
    torch.backends.cuda.matmul.allow_tf32 = mode == "tf32"
    torch.backends.cudnn.allow_tf32 = mode == "tf32"
    ctx = torch.autocast("cuda", dtype=torch.bfloat16) if mode == "bf16" else torch.autocast("cuda", enabled=False)
    with torch.no_grad(), ctx:
        for _ in range(3):
            m(b)
        torch.cuda.synchronize()
        t = time.perf_counter()
        for _ in range(reps):
            m(b)
        torch.cuda.synchronize()
    return round(b["tok"].shape[0] * reps / (time.perf_counter() - t))


def main():
    import torch
    ap = argparse.ArgumentParser()
    ap.add_argument("--ckpt", required=True)
    ap.add_argument("--batch", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--B", type=int, default=1024)
    ap.add_argument("--sizes", default="128x4,192x6,256x6,288x8,320x8")
    a = ap.parse_args()
    st = torch.load(a.ckpt, map_location="cpu")
    b1 = torch.load(a.batch)
    b = {k: v.cuda().expand(a.B, *v.shape[1:]).contiguous() for k, v in b1.items()}
    out = {"B": a.B, "shapes": {k: list(v.shape) for k, v in b1.items()}, "rates": []}
    for spec in a.sizes.split(","):
        d, L = map(int, spec.split("x"))
        m = build(st, d, L, max(4, d // 32), "cuda")
        row = {"d": d, "layers": L, "params": sum(p.numel() for p in m.parameters())}
        for mode in ("fp32", "tf32", "bf16"):
            row[mode] = rate(m, b, mode)
        print(json.dumps(row), flush=True)
        out["rates"].append(row)
        if d == 128:
            from torch.profiler import ProfilerActivity, profile
            torch.backends.cuda.matmul.allow_tf32 = False
            with torch.no_grad(), profile(activities=[ProfilerActivity.CUDA]) as pr:
                m(b)
                torch.cuda.synchronize()
            ev = sorted(pr.key_averages(), key=lambda e: -e.device_time_total)[:15]
            tot = sum(e.device_time_total for e in pr.key_averages() if e.device_time_total)
            out["top_ops_fp32_d128"] = [{"op": e.key[:80], "cuda_ms": round(e.device_time_total / 1000, 2)} for e in ev]
            out["total_cuda_ms_selfsum"] = round(tot / 1000, 2)
        del m
        torch.cuda.empty_cache()
    Path(a.out).write_text(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
