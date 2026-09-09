"""L67i: does an UNMAPPED HAND CARD collapse the gate? The last suspect standing.

Four hypotheses for the live p=0.00 are dead, two of them mine: overtime (model 0.374 vs pro 0.376), tower
loss (0.329 vs 0.311), every live-only scalar flag (they all RAISE p -- today's live path 0.475 vs 0.275
clean), and a stale `past` (0.288 even at an age of 1200 s). The collapse is also intermittent -- one match in
the 22:48 run recovered to p=0.95 between two p=0.00 stretches -- so it tracks something that flickers.

What flickers is the TRAY READER. `obs_contract._slot_onehot` encodes a hand card that is not in my deck --
which is what a misread returns -- into BIT 8 of that slot's one-hot. Measured on the training corpus: bit 8
is set in 0.0009% of 339,192 rows (3 rows), and the next-card bit 8 in 0.0000%. It is, to the gate head, an
input direction that does not exist. Live, the owner's 22:48 log shows it set in 8 of the 12 captured
collapse frames (hand=[0,4,164,-1], [6,-1,-1,3], [4,164,-1,3], ...).

This mutates real VAL rows into that state and reads the gate. If p collapses, the live freeze is a PERCEPTION
bug wearing a policy costume, and the fix belongs in the tray reader (or in refusing to act on a hand we
cannot read) rather than in the network.

usage: python scratchpad/gauntlet/L67/gate_unmapped_hand.py --ckpt <pt> --data <npz> --out <json>
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))

H0, H1 = 7, 43          # 4 hand slots x 9
N0, N1 = 43, 52         # next card x 9


def unmap(sc, slots):
    v = sc.copy()
    h = v[:, H0:H1].reshape(len(v), 4, 9)
    for k in slots:
        h[:, k, :] = 0.0
        h[:, k, 8] = 1.0            # "card not in my deck" -- what a misread tray produces
    v[:, H0:H1] = h.reshape(len(v), 36)
    return v


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ckpt", type=Path, required=True)
    ap.add_argument("--data", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--rows", type=int, default=8000)
    a = ap.parse_args()

    import torch
    from pipeline.dataset import load as load_ds
    from pipeline.model_v3 import S1Model, hand_mask_from_sc
    from pipeline.train_s1 import Rows

    arrs, _ = load_ds(a.data)
    idx = np.flatnonzero(arrs["split"] == 1)
    if len(idx) > a.rows:
        idx = np.sort(np.random.default_rng(0).choice(idx, a.rows, replace=False))
    dev = torch.device("cpu")
    st = torch.load(a.ckpt, map_location=dev)
    args = dict(st.get("args", {}) or {})
    model = S1Model(d=int(args.get("d", 128)), layers=int(args.get("layers", 4))).to(dev)
    model.load_state_dict(st["model"])
    model.eval()

    sc0 = arrs["sc"][idx]
    variants = {
        "clean": sc0,
        "1 hand slot unmapped": unmap(sc0, [2]),
        "2 hand slots unmapped": unmap(sc0, [1, 2]),
        "3 hand slots unmapped": unmap(sc0, [1, 2, 3]),
        "all 4 unmapped": unmap(sc0, [0, 1, 2, 3]),
    }
    v = sc0.copy(); v[:, N0:N1] = 0.0; v[:, N1 - 1] = 1.0
    variants["next card unmapped"] = v

    out = []
    for name, sc in variants.items():
        mut = dict(arrs)
        full = arrs["sc"].copy()
        full[idx] = sc
        mut["sc"] = full
        rows = Rows(mut, idx, dev)
        ps = []
        with torch.no_grad():
            for s0 in range(0, len(idx), 512):
                b = rows.batch(idx[s0:s0 + 512])
                enc = model.encode(b["tok"], b["mask"], b["sc"], b["past"])
                h = model.heads(enc, hand_mask_from_sc(b["sc"]))
                ps.append(torch.sigmoid(h["gate"]).cpu().numpy())
        p = np.concatenate(ps).astype(float)
        rec = {"variant": name, "mean_p": round(float(p.mean()), 4),
               "median_p": round(float(np.median(p)), 4),
               "frac_under_0.05": round(float((p < 0.05).mean()), 4),
               "frac_under_0.005": round(float((p < 0.005).mean()), 4)}
        out.append(rec)
        print(json.dumps(rec), flush=True)
    a.out.write_text(json.dumps(out, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
