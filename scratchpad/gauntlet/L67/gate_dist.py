"""L67d: the student's PLAY-gate distribution on three input sources, one model, one rule.

  (i)  engine states      -- the v3 VAL rows the bench numbers come from
  (ii) modelled-live      -- the same rows through obs_contract.degrade (L67a's twin)
  (iii) real live frames  -- p_play recorded by student_dryrun.py on recorded sessions

(i) vs (ii) is PAIRED (same rows). (iii) is a DIFFERENT set of states from different matches, so it is a
distribution comparison, not a paired one -- it can only say whether real live looks like the modelled shift
or lands somewhere else entirely.

usage: python scratchpad/gauntlet/L67/gate_dist.py --ckpt <pt> --clean <npz> --degraded <npz> --live <jsonl...> --out <json>
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))


def gate_probs(ckpt: Path, npz: Path, device: str = "cpu", limit: int = 0,
                elixir_min: float = 0.0) -> np.ndarray:
    import torch
    from pipeline.dataset import load as load_ds
    from pipeline.model_v3 import S1Model
    from pipeline.train_s1 import Rows, hand_mask_from_sc

    arrs, _ = load_ds(npz)
    keep = arrs["split"] == 1                              # VAL rows only, the bench's own slice
    if elixir_min > 0:                                     # sc[3] = my_elixir/10 (obs_contract.to_tokens)
        keep &= arrs["sc"][:, 3] >= elixir_min / 10.0
    idx = np.flatnonzero(keep)
    if limit:
        idx = idx[:limit]
    dev = torch.device(device)
    st = torch.load(ckpt, map_location=dev)
    a = dict(st.get("args", {}) or {})
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
            out.append(torch.sigmoid(h["gate"]).cpu().numpy())
    return np.concatenate(out)


def describe(p: np.ndarray, label: str) -> dict:
    return {"source": label, "n": int(p.size), "median": round(float(np.median(p)), 4),
            "mean": round(float(p.mean()), 4), "p90": round(float(np.percentile(p, 90)), 4),
            "frac_gt_0.5": round(float((p > 0.5).mean()), 4), "frac_gt_0.25": round(float((p > 0.25).mean()), 4)}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ckpt", type=Path, required=True)
    ap.add_argument("--clean", type=Path, required=True)
    ap.add_argument("--degraded", type=Path, required=True)
    ap.add_argument("--live", type=Path, nargs="*", default=[])
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--device", default="cpu")
    ap.add_argument("--elixir-min", type=float, default=0.0,
                    help="compare only states with at least this much elixir, on BOTH sides of the comparison")
    a = ap.parse_args()

    rec = []
    pc = gate_probs(a.ckpt, a.clean, a.device, elixir_min=a.elixir_min)
    pd_ = gate_probs(a.ckpt, a.degraded, a.device, elixir_min=a.elixir_min)
    rec.append(describe(pc, "engine v3 VAL"))
    rec.append(describe(pd_, "modelled-live (degrade) v3 VAL"))
    live = []
    for f in a.live:
        for line in f.read_text(encoding="utf-8").splitlines():
            r = json.loads(line)
            if r.get("p_play") is None:
                continue
            if a.elixir_min and float(r.get("elixir", 0.0)) < a.elixir_min:
                continue
            live.append(float(r["p_play"]))
    if live:
        rec.append(describe(np.asarray(live), "real live frames (dry run)"))
    # the training prior the gate was fit to, for scale
    from pipeline.dataset import load as load_ds
    arrs, _ = load_ds(a.clean)
    v = arrs["split"] == 1
    rec.append({"source": "train target rate (v3 VAL y_gate)", "n": int(v.sum()),
                "median": None, "mean": round(float(arrs["y_gate"][v].mean()), 4),
                "p90": None, "frac_gt_0.5": None, "frac_gt_0.25": None})
    a.out.write_text(json.dumps(rec, indent=1), encoding="utf-8")
    for r in rec:
        print(json.dumps(r))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
