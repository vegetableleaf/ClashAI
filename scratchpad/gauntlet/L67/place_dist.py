"""L67f: the student's PLACEMENT distribution on engine states vs REAL live frames -- label-free.

Owner's ruling (2026-09-08): his recorded clicks are NOT a quality standard (his skill is not pro), so they are
not used as labels anywhere. What his sessions provide is the only real detector input we have, so the only
questions asked here are about the OBSERVATION SHIFT, never about whether a placement is good:

  own-half fraction, mean depth (board y, 1.0 = my king edge), lane balance, distinct-cell spread.

Same model, same rule, two input pipelines. The cell is read the way LIVE reads it -- the model picks its own
card (hand-masked), then the card-conditioned cell head is argmaxed -- NOT teacher-forced on the pro's card the
way the bench does it, because the live path has no pro to force.

usage: python scratchpad/gauntlet/L67/place_dist.py --ckpt <pt> --engine <npz> --live <dryrun jsonl...> --out <json>
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))


def engine_cells(ckpt: Path, npz: Path, device: str = "cpu", limit: int = 0) -> np.ndarray:
    """(x, y) in the board frame for each VAL row, from the model's OWN card choice."""
    import torch
    from pipeline.dataset import load as load_ds
    from pipeline.model_v3 import S1Model, cell_xy
    from pipeline.train_s1 import Rows, hand_mask_from_sc

    arrs, _ = load_ds(npz)
    idx = np.flatnonzero(arrs["split"] == 1)
    if limit:
        idx = idx[:limit]
    dev = torch.device(device)
    st = torch.load(ckpt, map_location=dev)
    a = dict(st.get("args", {}) or {})
    grid = str(a.get("grid", "floor"))
    model = S1Model(d=int(a.get("d", 128)), layers=int(a.get("layers", 4))).to(dev)
    model.load_state_dict(st["model"])
    model.eval()
    rows = Rows(arrs, idx, dev)
    out = []
    with torch.no_grad():
        for s0 in range(0, len(idx), 512):
            b = rows.batch(idx[s0:s0 + 512])
            enc = model.encode(b["tok"], b["mask"], b["sc"], b["past"])
            h = model.heads(enc, hand_mask_from_sc(b["sc"]))
            slot = h["card"].argmax(-1)
            cell = model.cell_logits(enc, slot).argmax(-1).cpu().numpy()
            out.extend(cell_xy(int(c), grid) for c in cell)
    return np.asarray(out, dtype=np.float64)


def describe(xy: np.ndarray, label: str, n_cells: int) -> dict:
    """Board frame (obs_contract): x across, y DOWN the screen with ME at the bottom, so my half is y > 0.5
    and my king edge is y ~ 0.9 (actions.py's own anchors: my princess row 0.797, my king 0.906)."""
    x, y = xy[:, 0], xy[:, 1]
    return {"source": label, "n": int(len(xy)),
            "own_half_frac": round(float((y > 0.5).mean()), 4),
            "y_median": round(float(np.median(y)), 4),
            "y_p10": round(float(np.percentile(y, 10)), 4),
            "y_p90": round(float(np.percentile(y, 90)), 4),
            "left_lane_frac": round(float((x < 0.5).mean()), 4),
            "x_median": round(float(np.median(x)), 4),
            "distinct_cells": int(n_cells),
            "distinct_per_100": round(100.0 * n_cells / max(len(xy), 1), 1)}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ckpt", type=Path, required=True)
    ap.add_argument("--engine", type=Path, required=True)
    ap.add_argument("--live", type=Path, nargs="+", required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--device", default="cpu")
    ap.add_argument("--limit", type=int, default=4000)
    a = ap.parse_args()

    eng = engine_cells(a.ckpt, a.engine, a.device, a.limit)
    rec = [describe(eng, "engine v3 VAL (model's own card)", len({tuple(v) for v in eng}))]

    live_xy, live_cells = [], set()
    for f in a.live:
        for line in f.read_text(encoding="utf-8").splitlines():
            r = json.loads(line)
            if r.get("board_xy"):
                live_xy.append(tuple(r["board_xy"]))
                live_cells.add(r.get("student_cell"))
    if live_xy:
        rec.append(describe(np.asarray(live_xy, dtype=np.float64), "real live frames", len(live_cells)))
    a.out.write_text(json.dumps(rec, indent=1), encoding="utf-8")
    for r in rec:
        print(json.dumps(r))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
