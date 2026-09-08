"""L67h: how much headroom is there for a RERANKER (search) over the student's own ranking?

The rollout-search result that licenses distillation (research/sim_parity/ledger/rollout_search.md) was
measured on the OLD CNN policy, and its headline was "the information needed to play twice as well is already
in the policy's own action ranking; the policy does not use it". That is a claim about THAT policy. Before
building a search around the S1 student, ask the same question of the student, on pro labels:

  * if the pro's actual cell is in the student's top-K, a reranker CAN find it; if top-K ~ top-1, there is
    nothing to rerank and search over this policy cannot buy placement.
  * same for the card head.

Read against the two anchors measured today: the student's top-1 cell is 21.0%, and two PROS in near-identical
positions agree on the cell 27.8% (agreement_ceiling2.json). A top-K that sits far above 27.8% means the
ranking carries more than one plausible answer, which is exactly what a value-based reranker needs.

usage: python scratchpad/gauntlet/L67/topk_headroom.py --ckpt <pt> --data <npz> --out <json>
"""
from __future__ import annotations
import argparse, json, sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))

TILES_X, TILES_Y = 18.0, 32.0
GRID_X, GRID_Y = 36, 64


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ckpt", type=Path, required=True)
    ap.add_argument("--data", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--rows", type=int, default=12000)
    a = ap.parse_args()

    import torch
    from pipeline.dataset import load as load_ds
    from pipeline.model_v3 import S1Model, cell_label, cell_xy, hand_mask_from_sc
    from pipeline.train_s1 import Rows

    arrs, _ = load_ds(a.data)
    idx = np.flatnonzero((arrs["split"] == 1) & (arrs["y_gate"] == 1))     # PLAY rows only: cell has a label
    if len(idx) > a.rows:
        idx = np.sort(np.random.default_rng(0).choice(idx, a.rows, replace=False))
    dev = torch.device("cpu")
    st = torch.load(a.ckpt, map_location=dev)
    args = dict(st.get("args", {}) or {})
    grid = str(args.get("grid", "floor"))
    model = S1Model(d=int(args.get("d", 128)), layers=int(args.get("layers", 4))).to(dev)
    model.load_state_dict(st["model"])
    model.eval()
    rows = Rows(arrs, idx, dev)

    y_cell = cell_label(torch.from_numpy(arrs["y_xy"][idx]), grid).numpy()
    y_slot = arrs["y_slot"][idx].astype(int)
    xy = arrs["y_xy"][idx]

    KS = (1, 2, 3, 5, 8, 16, 32)
    cell_hit = {k: 0 for k in KS}
    cell_near = {k: 0 for k in KS}          # best of top-K within 1 tile of the pro's point
    card_hit = {k: 0 for k in (1, 2, 3, 4)}
    n = 0
    with torch.no_grad():
        for s0 in range(0, len(idx), 256):
            sl = idx[s0:s0 + 256]
            b = rows.batch(sl)
            enc = model.encode(b["tok"], b["mask"], b["sc"], b["past"])
            h = model.heads(enc, hand_mask_from_sc(b["sc"]))
            true_slot = torch.from_numpy(y_slot[s0:s0 + len(sl)])
            cl = model.cell_logits(enc, true_slot)             # teacher-forced card, as evaluate() does
            top = torch.topk(cl, max(KS), dim=-1).indices.numpy()
            ctop = torch.topk(h["card"], 4, dim=-1).indices.numpy()
            tc = y_cell[s0:s0 + len(sl)]
            txy = xy[s0:s0 + len(sl)]
            for i in range(len(sl)):
                for k in KS:
                    if tc[i] in top[i, :k]:
                        cell_hit[k] += 1
                    d = min(float(np.hypot((cell_xy(int(c), grid)[0] - txy[i, 0]) * TILES_X,
                                           (cell_xy(int(c), grid)[1] - txy[i, 1]) * TILES_Y))
                            for c in top[i, :k])
                    if d <= 1.0:
                        cell_near[k] += 1
                for k in (1, 2, 3, 4):
                    if y_slot[s0 + i] in ctop[i, :k]:
                        card_hit[k] += 1
            n += len(sl)

    out = {"n_play_rows": int(n), "ckpt": str(a.ckpt),
           "cell_topk_pct": {str(k): round(100.0 * cell_hit[k] / n, 2) for k in KS},
           "cell_topk_within1_pct": {str(k): round(100.0 * cell_near[k] / n, 2) for k in KS},
           "card_topk_pct": {str(k): round(100.0 * card_hit[k] / n, 2) for k in (1, 2, 3, 4)}}
    print(json.dumps(out, indent=1), flush=True)
    a.out.write_text(json.dumps(out, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
