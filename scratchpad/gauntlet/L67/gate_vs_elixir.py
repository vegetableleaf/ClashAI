"""L67g: does the GATE respond to MY ELIXIR? Model p_play vs the pro's own play rate, engine VAL.

The live freeze (live_run3.log, 2026-09-08) is ~50 s stretches at 10 elixir with 0 plays. Measured in that
log: among WAIT frames the mean p is 0.062 at elixir 10 and 0.026-0.081 at elixir 2-6 -- FLAT in elixir,
while it rises with units on board. That is a live, label-free reading; this script asks the same question
where the labels are pro placements, so the answer can be attributed to the model rather than to the live path.

Reported per (elixir bucket x unit-count bucket): the model's mean sigmoid(gate) and the TRUE pro play rate.
usage: python scratchpad/gauntlet/L67/gate_vs_elixir.py --ckpt <pt> --data <npz> --out <json>
"""
from __future__ import annotations
import argparse, json, sys
from pathlib import Path
import numpy as np

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ckpt", type=Path, required=True)
    ap.add_argument("--data", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--device", default="cpu")
    a = ap.parse_args()

    import torch
    from pipeline.dataset import load as load_ds
    from pipeline.model_v3 import S1Model, hand_mask_from_sc
    from pipeline.train_s1 import Rows

    arrs, _ = load_ds(a.data)
    idx = np.flatnonzero(arrs["split"] == 1)
    dev = torch.device(a.device)
    st = torch.load(a.ckpt, map_location=dev)
    args = dict(st.get("args", {}) or {})
    model = S1Model(d=int(args.get("d", 128)), layers=int(args.get("layers", 4))).to(dev)
    model.load_state_dict(st["model"])
    model.eval()
    rows = Rows(arrs, idx, dev)

    ps, us = [], []
    with torch.no_grad():
        for s0 in range(0, len(idx), 512):
            b = rows.batch(idx[s0:s0 + 512])
            enc = model.encode(b["tok"], b["mask"], b["sc"], b["past"])
            h = model.heads(enc, hand_mask_from_sc(b["sc"]))
            ps.append(torch.sigmoid(h["gate"]).cpu().numpy())
            us.append(b["mask"].sum(-1).cpu().numpy())
    p = np.concatenate(ps).astype(np.float64)
    nun = np.concatenate(us).astype(np.int64)
    elix = np.rint(arrs["sc"][idx, 3] * 10.0).astype(int)     # sc[3] = my_elixir/10
    y = arrs["y_gate"][idx].astype(np.float64)

    def bucket(n):
        return "0-1" if n <= 1 else "2-3" if n <= 3 else "4-6" if n <= 6 else "7+"

    ub = np.array([bucket(n) for n in nun])
    rec = []
    for e in range(0, 11):
        m = elix == e
        if m.sum() < 50:
            continue
        rec.append({"elixir": e, "n": int(m.sum()), "model_p": round(float(p[m].mean()), 4),
                    "pro_rate": round(float(y[m].mean()), 4)})
        print(json.dumps(rec[-1]), flush=True)
    grid = []
    for u in ("0-1", "2-3", "4-6", "7+"):
        for e in ((0, 3), (4, 6), (7, 8), (9, 10)):
            m = (ub == u) & (elix >= e[0]) & (elix <= e[1])
            if m.sum() < 50:
                continue
            grid.append({"units": u, "elixir": f"{e[0]}-{e[1]}", "n": int(m.sum()),
                         "model_p": round(float(p[m].mean()), 4), "pro_rate": round(float(y[m].mean()), 4)})
            print(json.dumps(grid[-1]), flush=True)
    a.out.write_text(json.dumps({"ckpt": str(a.ckpt), "by_elixir": rec, "grid": grid}, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
