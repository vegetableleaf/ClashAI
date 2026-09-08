"""L67f (2): does the chosen placement JITTER between consecutive decisions? Label-free, engine vs real live.

The prior-collapse of (1) predicts live should look MORE stable, not less -- a model falling back to a favourite
cell repeats it. So instability would be a second, separate failure and stability is not automatically good news.
Both sides are matched on the time gap between decisions, because a 1 s gap and a 4 s gap are not comparable.

  live   : consecutive sampled frames of one dry-run session (~1 s apart at --every 12 on 12 fps video)
  engine : consecutive VAL rows of one replay, bucketed by the tick gap between them

Reported: share of consecutive pairs choosing the SAME cell, and the median move in TILES when it changes.

usage: python scratchpad/gauntlet/L67/place_stability.py --ckpt <pt> --engine <npz> --live <jsonl...> --out <json>
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))

GRID_X, GRID_Y = 36, 64
TILES_X, TILES_Y = 18.0, 32.0


def _tiles(c0: int, c1: int) -> float:
    dx = ((c1 % GRID_X) - (c0 % GRID_X)) / GRID_X * TILES_X
    dy = ((c1 // GRID_X) - (c0 // GRID_X)) / GRID_Y * TILES_Y
    return float(np.hypot(dx, dy))


def pairs_stats(pairs: list[tuple[int, int]], label: str, gap_s: str) -> dict:
    if not pairs:
        return {"source": label, "n_pairs": 0}
    same = sum(1 for a, b in pairs if a == b)
    moves = [_tiles(a, b) for a, b in pairs if a != b]
    return {"source": label, "gap_s": gap_s, "n_pairs": len(pairs),
            "same_cell_frac": round(same / len(pairs), 4),
            "median_move_tiles": round(float(np.median(moves)), 2) if moves else None,
            "p90_move_tiles": round(float(np.percentile(moves, 90)), 2) if moves else None,
            "moves_over_5_tiles_frac": round(float(np.mean([m > 5 for m in moves])), 4) if moves else None}


def engine_pairs(ckpt: Path, npz: Path, device: str, gap_lo: float, gap_hi: float, limit: int) -> list:
    import torch
    from pipeline.dataset import load as load_ds
    from pipeline.model_v3 import S1Model
    from pipeline.train_s1 import Rows, hand_mask_from_sc

    arrs, _ = load_ds(npz)
    keep = np.flatnonzero(arrs["split"] == 1)[:limit]
    dev = torch.device(device)
    st = torch.load(ckpt, map_location=dev)
    a = dict(st.get("args", {}) or {})
    model = S1Model(d=int(a.get("d", 128)), layers=int(a.get("layers", 4))).to(dev)
    model.load_state_dict(st["model"])
    model.eval()
    rows = Rows(arrs, keep, dev)
    cells = []
    with torch.no_grad():
        for s0 in range(0, len(keep), 512):
            b = rows.batch(keep[s0:s0 + 512])
            enc = model.encode(b["tok"], b["mask"], b["sc"], b["past"])
            h = model.heads(enc, hand_mask_from_sc(b["sc"]))
            cells.extend(model.cell_logits(enc, h["card"].argmax(-1)).argmax(-1).tolist())
    cells = np.asarray(cells)
    rep, side, tick = arrs["rep"][keep], arrs["side"][keep], arrs["tick"][keep]
    out = []
    for i in range(len(keep) - 1):
        if rep[i] != rep[i + 1] or side[i] != side[i + 1]:
            continue                                    # never pair across matches or sides
        dt = (int(tick[i + 1]) - int(tick[i])) * 0.05    # engine tick = 0.05 s
        if gap_lo <= dt <= gap_hi:
            out.append((int(cells[i]), int(cells[i + 1])))
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ckpt", type=Path, required=True)
    ap.add_argument("--engine", type=Path, required=True)
    ap.add_argument("--live", type=Path, nargs="+", required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--device", default="cpu")
    ap.add_argument("--limit", type=int, default=6000)
    ap.add_argument("--gap-lo", type=float, default=0.5)
    ap.add_argument("--gap-hi", type=float, default=2.5)
    a = ap.parse_args()

    rec = []
    live_pairs, gaps = [], []
    for f in a.live:
        rows = [json.loads(l) for l in f.read_text(encoding="utf-8").splitlines()]
        rows = [r for r in rows if r.get("student_cell") is not None]
        for r0, r1 in zip(rows, rows[1:]):
            dt = float(r1["t_sec"]) - float(r0["t_sec"])
            if a.gap_lo <= dt <= a.gap_hi:
                live_pairs.append((int(r0["student_cell"]), int(r1["student_cell"])))
                gaps.append(dt)
    rec.append(pairs_stats(live_pairs, "real live frames",
                           f"{min(gaps):.1f}-{max(gaps):.1f}" if gaps else "-"))
    ep = engine_pairs(a.ckpt, a.engine, a.device, a.gap_lo, a.gap_hi, a.limit)
    rec.append(pairs_stats(ep, "engine v3 VAL (consecutive rows, same match+side)", f"{a.gap_lo}-{a.gap_hi}"))
    a.out.write_text(json.dumps(rec, indent=1), encoding="utf-8")
    for r in rec:
        print(json.dumps(r))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
