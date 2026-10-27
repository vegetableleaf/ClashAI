"""SPEED.md (a)/(c): forward cost of the CLXIII GenModel shape (1.76 M) and of wider / deeper copies (~5 / 10 / 15 M,
random weights, same inputs) on a real live batch (live_profile.py --out X.json writes X.batch.pt).
    batch 1    : ms per forward (live decide), cpu (4 threads, live_play's setting) and cuda
    batch B    : rows/s on cuda at B = 256 / 1024 / 4096 (the batched rollout's server), fp32 as trained
    python model_scale.py --ckpt CLXIII.pt --batch X.batch.pt --out scale.json
"""
import argparse
import json
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO))


def build(st, d, layers, heads, device):
    import torch
    from pipeline.model_gen import GenModel
    a = st["args"]
    torch.manual_seed(0)
    m = GenModel(d=d, layers=layers, heads=heads, d_c=int(st["d_c"]), n_cards=len(st["card_vocab"]),
                 feature_version=int(a.get("feature_version", 1)))
    sd = st["model"]
    if any(k.startswith("cue_in.") for k in sd):
        m.add_cue_in()
    if "cell_refine.cfg" in sd:                                  # CLXIII's refine modules, at this width
        m.add_cell_refine(*(int(v) for v in sd["cell_refine.cfg"]))
    if "tower_refine.cfg" in sd:
        c, L2, hidden, card, cell = (int(v) for v in sd["tower_refine.cfg"])
        m.add_tower_refine(c=c, layers=L2, hidden=hidden, card=bool(card), cell=bool(cell))
    if (d, layers) == (int(a["d"]), int(a["layers"])):
        m.load_state_dict(sd)                                    # the real CLXIII weights at its own shape
    return m.to(device).eval()


def bench(m, b, reps):
    import torch
    with torch.no_grad():
        for _ in range(5):
            m(b)
        if b["tok"].is_cuda:
            torch.cuda.synchronize()
        t = time.perf_counter()
        for _ in range(reps):
            out = m(b)
        if b["tok"].is_cuda:
            torch.cuda.synchronize()
        _ = out
    return (time.perf_counter() - t) / reps


def main():
    import torch
    ap = argparse.ArgumentParser()
    ap.add_argument("--ckpt", required=True)
    ap.add_argument("--batch", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--sizes", default="128x4,192x6,256x6,288x8,320x8,256x10")
    a = ap.parse_args()
    st = torch.load(a.ckpt, map_location="cpu")
    b1 = torch.load(a.batch)
    torch.set_num_threads(4)
    res = []
    for spec in a.sizes.split(","):
        d, L = map(int, spec.split("x"))
        heads = max(4, d // 32)
        row = {"d": d, "layers": L, "heads": heads}
        for dev in ("cpu", "cuda"):
            m = build(st, d, L, heads, dev)
            row["params"] = sum(p.numel() for p in m.parameters())
            bb = {k: v.to(dev) for k, v in b1.items()}
            row[f"{dev}_b1_ms"] = round(bench(m, bb, 30 if dev == "cpu" else 200) * 1000, 2)
            if dev == "cuda":
                for B in (256, 1024, 4096):
                    bb = {k: v.to(dev).expand(B, *v.shape[1:]).contiguous() for k, v in b1.items()}
                    try:
                        s = bench(m, bb, 10)
                        row[f"cuda_b{B}_rows_per_s"] = round(B / s)
                        row[f"cuda_b{B}_ms"] = round(s * 1000, 1)
                    except torch.cuda.OutOfMemoryError:
                        row[f"cuda_b{B}_rows_per_s"] = "OOM"
                    torch.cuda.empty_cache()
            del m
        print(json.dumps(row), flush=True)
        res.append(row)
    Path(a.out).write_text(json.dumps({"gpu": torch.cuda.get_device_name(0), "rows": res}, indent=1))


if __name__ == "__main__":
    main()
