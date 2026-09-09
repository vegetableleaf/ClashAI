"""L67i: what STATE makes the gate collapse to p=0.00? Owner report, tested on real rows with pro labels.

Live evidence (scratchpad/live_run4.log, 2 matches, student ON, opp-elixir withheld): the gate is healthy for
a while and then pins at p=0.00 for the rest of the match -- at 10 elixir with 1-5 units, where the model's
own calibration says ~0.29-0.43. Owner's hypothesis: overtime. That does not fit the timings (match 1
collapsed BEFORE 2x elixir; match 2's collapse began a minute before 3x), so this asks the data instead.

Method: SELECT real VAL rows by condition rather than mutating states into conditions that never occur. Each
bucket reports the model's mean gate p AND the pro's own play rate in the same rows, so a low p is only a
defect if the pro plays there.

Conditions come from the live log's candidates: match phase (double/overtime, t_sec), tower losses on either
side, how long since MY last play (the `past` recency the live path feeds), and board occupancy as a control.

usage: python scratchpad/gauntlet/L67/gate_by_state.py --ckpt <pt> --data <npz> --out <json>
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))

# to_tokens scalar layout (obs_contract): 0 t/300, 1 dbl, 2 ot, 3 my_elixir/10, 4 exact, 5 opp/10, 6 opp_known,
# 7:43 hand, 43:52 next, 52:58 tower hp (my K,L,R then opp K,L,R), 58:64 hp_known, 64:70 alive
S_T, S_DBL, S_OT, S_ELX = 0, 1, 2, 3
S_ALIVE = 64


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ckpt", type=Path, required=True)
    ap.add_argument("--data", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--rows", type=int, default=30000)
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
    rows = Rows(arrs, idx, dev)

    ps, nunits = [], []
    with torch.no_grad():
        for s0 in range(0, len(idx), 512):
            b = rows.batch(idx[s0:s0 + 512])
            enc = model.encode(b["tok"], b["mask"], b["sc"], b["past"])
            h = model.heads(enc, hand_mask_from_sc(b["sc"]))
            ps.append(torch.sigmoid(h["gate"]).cpu().numpy())
            nunits.append(b["mask"].sum(-1).cpu().numpy())
    p = np.concatenate(ps).astype(float)
    nun = np.concatenate(nunits).astype(int)
    sc = arrs["sc"][idx]
    y = arrs["y_gate"][idx].astype(float)
    past = arrs["past"][idx]
    t_sec = sc[:, S_T] * 300.0
    my_alive = sc[:, S_ALIVE + 1] + sc[:, S_ALIVE + 2]        # my two princesses
    opp_alive = sc[:, S_ALIVE + 4] + sc[:, S_ALIVE + 5]
    last_dt = np.where(past[:, 0, 0] >= 0, past[:, 0, 3], -1.0)   # seconds since my most recent play

    def bucket(name, m):
        if m.sum() < 40:
            return None
        return {"condition": name, "n": int(m.sum()),
                "model_p": round(float(p[m].mean()), 4),
                "model_frac_under_0.05": round(float((p[m] < 0.05).mean()), 4),
                "pro_play_rate": round(float(y[m].mean()), 4)}

    conds = [
        ("ALL", np.ones(len(idx), bool)),
        ("single elixir (t<120s)", t_sec < 120),
        ("double elixir (120-180s)", (t_sec >= 120) & (t_sec < 180)),
        ("overtime flag set", sc[:, S_OT] > 0.5),
        ("t_sec > 180s", t_sec > 180),
        ("t_sec > 240s", t_sec > 240),
        ("both my princesses alive", my_alive > 1.5),
        ("ONE of my princesses down", (my_alive > 0.5) & (my_alive < 1.5)),
        ("BOTH my princesses down", my_alive < 0.5),
        ("one enemy princess down", (opp_alive > 0.5) & (opp_alive < 1.5)),
        ("my last play < 10s ago", (last_dt >= 0) & (last_dt < 10)),
        ("my last play 10-30s ago", (last_dt >= 10) & (last_dt < 30)),
        ("my last play 30-60s ago", (last_dt >= 30) & (last_dt < 60)),
        ("my last play > 60s ago", last_dt >= 60),
        ("no play yet this match", past[:, 0, 0] < 0),
        ("elixir 10 AND units<=2", (np.rint(sc[:, S_ELX] * 10) >= 10) & (nun <= 2)),
        ("elixir 10 AND units<=2 AND t>180", (np.rint(sc[:, S_ELX] * 10) >= 10) & (nun <= 2) & (t_sec > 180)),
    ]
    out = [r for r in (bucket(n, m) for n, m in conds) if r]
    for r in out:
        print(json.dumps(r), flush=True)
    a.out.write_text(json.dumps({"ckpt": str(a.ckpt), "rows": out}, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
