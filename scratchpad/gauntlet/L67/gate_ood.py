"""L67i: which LIVE-ONLY input flag drives the gate to p=0.00? Mutation test in the collapse state.

Established (gate_by_state.json): on engine states the gate tracks the pro in every condition that was
suspected -- overtime 0.374 vs 0.376, one princess down 0.329 vs 0.311, and in the EXACT state the live bot
sat frozen in (elixir 10, <=2 units, t>180) it wants to play 0.632 against a pro rate of 0.641. So the game
situation is not the cause; the live INPUT is. Both the owner's overtime hypothesis and my tower-latch
hypothesis are contradicted as explanations of the gate.

Every remaining suspect is a field that is CONSTANT in all 339,192 training rows and varies live (5cs.95 A):
`my_elixir_exact` is 1.0 in training and 0.0 live always; `opp_known` is 1.0 in training and is now 0.0 live
because L67g stopped sending the opponent-elixir estimate; tower `hp_known` is 1.0 in training but goes 0 live
whenever the HP reader cannot read a bar; `my_next` is resolved in training but -1 live when the next-card
reader fails. A flag that is never 0 in training is a direction the gate head has never been trained on, and
that is where a p=0.00 can come from.

Measured on the SLICE that matters (the live collapse state) as well as on all rows, because a flag can be
harmless on average and lethal in one corner.

usage: python scratchpad/gauntlet/L67/gate_ood.py --ckpt <pt> --data <npz> --out <json>
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))

S_T, S_ELX, S_EXACT, S_OPP, S_OPPK = 0, 3, 4, 5, 6
S_NEXT0, S_NEXT1 = 43, 52
S_THP0, S_THP1 = 52, 58
S_HPK0, S_HPK1 = 58, 64


def variants(sc):
    out = {"clean (engine, as trained)": sc}
    v = sc.copy(); v[:, S_EXACT] = 0.0
    out["exact_off (live ALWAYS)"] = v
    v = sc.copy(); v[:, S_OPP] = 0.0; v[:, S_OPPK] = 0.0
    out["opp_unknown (live since L67g)"] = v
    v = sc.copy(); v[:, S_HPK0:S_HPK1] = 0.0; v[:, S_THP0:S_THP1] = 0.0
    out["tower_hp_unknown"] = v
    v = sc.copy(); v[:, S_NEXT0:S_NEXT1] = 0.0
    out["next_card_blank"] = v
    v = sc.copy(); v[:, S_EXACT] = 0.0; v[:, S_OPP] = 0.0; v[:, S_OPPK] = 0.0
    out["exact_off + opp_unknown (TODAY'S LIVE PATH)"] = v
    v = v.copy(); v[:, S_HPK0:S_HPK1] = 0.0; v[:, S_THP0:S_THP1] = 0.0
    out["+ tower_hp_unknown"] = v
    v = v.copy(); v[:, S_NEXT0:S_NEXT1] = 0.0
    out["+ next_blank (worst case)"] = v
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ckpt", type=Path, required=True)
    ap.add_argument("--data", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--rows", type=int, default=12000)
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

    base = dict(arrs)
    sc0 = arrs["sc"][idx]
    t_sec = sc0[:, S_T] * 300.0
    elx = np.rint(sc0[:, S_ELX] * 10.0)
    rows_all = Rows(arrs, idx, dev)
    nun = []
    with torch.no_grad():
        for s0 in range(0, len(idx), 512):
            nun.append(rows_all.batch(idx[s0:s0 + 512])["mask"].sum(-1).cpu().numpy())
    nun = np.concatenate(nun).astype(int)
    slice_m = (elx >= 9) & (nun <= 2) & (t_sec > 120)      # the live collapse state
    print(f"collapse-state rows: {int(slice_m.sum())} of {len(idx)}", flush=True)

    out = []
    for name, sc in variants(sc0).items():
        mut = dict(base)
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
        rec = {"variant": name,
               "all_mean_p": round(float(p.mean()), 4),
               "all_frac_under_0.05": round(float((p < 0.05).mean()), 4),
               "collapse_state_mean_p": round(float(p[slice_m].mean()), 4),
               "collapse_state_frac_under_0.05": round(float((p[slice_m] < 0.05).mean()), 4)}
        out.append(rec)
        print(json.dumps(rec), flush=True)
    a.out.write_text(json.dumps({"ckpt": str(a.ckpt), "n_collapse_rows": int(slice_m.sum()), "rows": out},
                                indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
