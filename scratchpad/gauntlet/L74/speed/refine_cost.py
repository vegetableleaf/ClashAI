"""SPEED.md (c): CLXIII forward rows/s (B=1024, cuda) with / without the cell_refine features (encode_gen computes them
for EVERY row although only playing rows ask for cell logits) and the tower_refine cell features.
    python refine_cost.py --ckpt CLXIII.pt --batch X.batch.pt"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from fwd_ops import rate  # noqa: E402
from model_scale import build  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--ckpt", required=True)
ap.add_argument("--batch", required=True)
ap.add_argument("--B", type=int, default=1024)
a = ap.parse_args()
import torch  # noqa: E402
st = torch.load(a.ckpt, map_location="cpu")
b1 = torch.load(a.batch)
b = {k: v.cuda().expand(a.B, *v.shape[1:]).contiguous() for k, v in b1.items()}
m = build(st, 128, 4, 4, "cuda")
out = {"full": {md: rate(m, b, md) for md in ("fp32", "bf16")}}
cr = m.cell_refine
m.cell_refine = None
out["no_cell_refine_features"] = {md: rate(m, b, md) for md in ("fp32", "bf16")}
m.cell_refine, tr = cr, m.tower_refine
m.tower_refine = None
out["no_tower_refine"] = {md: rate(m, b, md) for md in ("fp32", "bf16")}
m.cell_refine = None
out["neither"] = {md: rate(m, b, md) for md in ("fp32", "bf16")}
print(json.dumps(out))
