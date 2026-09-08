"""L67f (4): is SUPPLYING a plausible value better than marking it UNKNOWN? Measured against pro labels.

The live ablation (L67f 3) showed the placement head disperses when unit HP / exact elixir / opponent elixir /
king HP are supplied instead of flagged unknown. But dispersion is label-free -- it says the output moved, not
that it moved somewhere RIGHT. Filling a missing field with a plausible constant is a LIE about the state, and
a lie can disperse the output while making it worse.

So the same manipulation is run on the ENGINE v3 VAL, where the labels are pro placements: blank each field
(what live actually has), then blank-and-fill it with the plausible constant, and read exact-cell agreement.
If fill > blank, supplying beats flagging and the live wiring is justified; if not, the live dispersion was
cosmetic and the honest `unknown` flag stays.

Token columns (obs_contract._token): 0 cls, 1-3 side mine/enemy/unknown, 4 x, 5 y, 6 hp_frac, 7 hp_known,
8 deploying, 9 deploying_known, 10 age, 11 age_known, 12 conf, 13 is_spell.
Scalars (to_tokens): 3 my_elixir/10, 4 my_elixir_exact, 5 opp_elixir/10, 6 opp_known,
52:58 tower hp_frac, 58:64 tower hp_known, 64:70 tower alive  (tower order: my K,L,R then opp K,L,R).

usage: python scratchpad/gauntlet/L67/fill_vs_blank.py --ckpt <pt> --data <npz> --out <json>
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))

KING_SLOTS = (0, 3)          # my king, opp king within the 6-tower blocks


def apply_variant(arrs: dict, name: str) -> dict:
    a = {k: (v.copy() if isinstance(v, np.ndarray) else v) for k, v in arrs.items()}
    tok, sc = a["tok"], a["sc"]
    if name in ("blank_hp", "blank_both"):
        tok[:, 6] = 0.0
        tok[:, 7] = 0.0
    if name in ("fill_hp", "fill_both"):
        tok[:, 6] = 1.0                      # "full health" -- the plausible constant a live path would send
        tok[:, 7] = 1.0
    if name in ("blank_scalars", "blank_both"):
        sc[:, 4] = 0.0                       # my_elixir is a pip read, not exact
        sc[:, 5] = 0.0
        sc[:, 6] = 0.0                       # opponent elixir unknown
        for k in KING_SLOTS:                 # king HP is never printed on screen
            sc[:, 52 + k] = 0.0
            sc[:, 58 + k] = 0.0
    if name == "opp_none":                   # what the live path sent BEFORE the L67f wiring
        sc[:, 5] = 0.0
        sc[:, 6] = 0.0
    if name == "opp_pinned10":               # what the LIVE ESTIMATOR degenerates to: est = my + my_spent -
        sc[:, 5] = 1.0                       #   opp_spent, clipped at 10, and every MISSED enemy play pushes
        sc[:, 6] = 1.0                       #   it up. Measured live: opp>=7.5 cuts the play rate to ~0.11.
    if name == "opp_const5":
        sc[:, 5] = 0.5
        sc[:, 6] = 1.0
    if name in ("fill_scalars", "fill_both"):
        sc[:, 4] = 0.0                       # still a pip read -- only the MISSING fields get filled
        sc[:, 5] = 0.5                       # opponent elixir guessed at 5
        sc[:, 6] = 1.0
        for k in KING_SLOTS:
            sc[:, 52 + k] = 1.0              # king assumed undamaged while alive (play.py's own proxy)
            sc[:, 58 + k] = 1.0
    return a


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ckpt", type=Path, required=True)
    ap.add_argument("--data", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--device", default="cpu")
    a = ap.parse_args()

    import torch
    from pipeline.dataset import load as load_ds
    from pipeline.model_v3 import S1Model
    from pipeline.train_s1 import Rows, evaluate

    base, _ = load_ds(a.data)
    dev = torch.device(a.device)
    st = torch.load(a.ckpt, map_location=dev)
    args = dict(st.get("args", {}) or {})
    grid = str(args.get("grid", "floor"))
    model = S1Model(d=int(args.get("d", 128)), layers=int(args.get("layers", 4))).to(dev)
    model.load_state_dict(st["model"])
    model.eval()
    idx = np.flatnonzero(base["split"] == 1)

    rec = []
    for name in ("clean", "opp_none", "opp_const5", "opp_pinned10"):
        arrs = base if name == "clean" else apply_variant(base, name)
        m = evaluate(model, Rows(arrs, idx, dev), grid=grid)
        rec.append({"variant": name, "cell_half_top1": round(float(m["cell_half_top1"]), 4),
                    "card_top1": round(float(m["card_top1"]), 4),
                    "place_dist": round(float(m["place_dist"]), 4),
                    "gate_acc": round(float(m["gate_acc"]), 4), "n_play": int(m["n_play"])})
        print(json.dumps(rec[-1]), flush=True)
    a.out.write_text(json.dumps({"ckpt": str(a.ckpt), "data": str(a.data), "rows": rec}, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
