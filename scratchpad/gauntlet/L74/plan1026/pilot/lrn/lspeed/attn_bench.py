"""LEARNER-SPEED ticket A bench: forward + backward of the pilot's two encoders at the pilot's shapes, torch's
nn.MultiheadAttention vs SplitMHA (pipeline/learner_attn.py). fp32, TF32 off, deterministic (the learner's settings).
Trunk: d 128, 4 heads, ff 512, 4 layers, 209 tokens (1 global + 144 patches + 64 units, ~half padded).
Memory encoder: d 64, 4 heads, ff 128, 2 layers, 129 tokens (BOS + 128 events). Prints ms / kernels per fwd+bwd and the
bitwise check.   PY attn_bench.py --rows 256,1024 --out OUT.json
"""
import argparse
import copy
import json
import os
import statistics
import sys
from pathlib import Path

os.environ.setdefault("CUBLAS_WORKSPACE_CONFIG", ":4096:8")
import torch  # noqa: E402
import torch.nn as nn  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parents[7]))
from pipeline.learner_attn import use_split_attn  # noqa: E402

torch.use_deterministic_algorithms(True)
torch.backends.cuda.matmul.allow_tf32 = torch.backends.cudnn.allow_tf32 = False
SHAPES = {"trunk": (128, 512, 4, 209), "memory": (64, 128, 2, 129)}


def run(enc, x0, pad, n=20):
    ts, out = [], None
    for i in range(n + 3):
        x = x0.clone().requires_grad_(True)
        a, b = torch.cuda.Event(enable_timing=True), torch.cuda.Event(enable_timing=True)
        a.record()
        y = enc(x, src_key_padding_mask=pad)
        y.square().mean().backward()
        b.record()
        torch.cuda.synchronize()
        if i >= 3:
            ts.append(a.elapsed_time(b))
        out = (y.detach(), x.grad, [p.grad.clone() for p in enc.parameters()])
        enc.zero_grad(set_to_none=True)
    with torch.profiler.profile(activities=[torch.profiler.ProfilerActivity.CUDA]) as prof:
        x = x0.clone().requires_grad_(True)
        enc(x, src_key_padding_mask=pad).square().mean().backward()
        torch.cuda.synchronize()
    ev = [e for e in prof.events() if e.device_type == torch.autograd.DeviceType.CUDA and not e.name.startswith(("forward", "backward"))]
    enc.zero_grad(set_to_none=True)
    return statistics.median(ts), len(ev), sum(e.device_time for e in ev) / 1e3, out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rows", default="256,1024")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    res = []
    for name, (d, ff, layers, L) in SHAPES.items():
        torch.manual_seed(0)
        ref = nn.TransformerEncoder(nn.TransformerEncoderLayer(d, 4, ff, dropout=0.0, batch_first=True, norm_first=True),
                                    layers, enable_nested_tensor=False).cuda().eval()
        new = copy.deepcopy(ref)
        use_split_attn(new)
        for B in map(int, a.rows.split(",")):
            g = torch.Generator().manual_seed(B)
            x0 = torch.randn(B, L, d, generator=g).cuda()
            pad = (torch.arange(L)[None] >= torch.randint(L // 4, L + 1, (B, 1), generator=g)).cuda()
            pad[:, 0] = False
            r = run(ref, x0, pad)
            s = run(new, x0, pad)
            same = (torch.equal(r[3][0], s[3][0]) and torch.equal(r[3][1], s[3][1])
                    and all(torch.equal(u, v) for u, v in zip(r[3][2], s[3][2])))
            row = {"enc": name, "rows": B, "torch_ms": r[0], "split_ms": s[0], "speedup": r[0] / s[0],
                   "torch_kernels": r[1], "split_kernels": s[1], "torch_kernel_ms": r[2], "split_kernel_ms": s[2],
                   "bitwise_equal": same}
            print(json.dumps(row), flush=True)
            res.append(row)
    Path(a.out).write_text(json.dumps({"device": torch.cuda.get_device_name(), "torch": torch.__version__,
                                       "results": res}, indent=1))


if __name__ == "__main__":
    main()
