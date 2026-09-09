"""L67g: does a STALE `past` (my last plays long ago) suppress the gate? The freeze's remaining suspect.

Ruled out already: the gate head is elixir-calibrated on engine states (gate_vs_elixir.json) AND responds
to elixir on real live frames (live_gate_elixir.json: p 0.109 -> 0.567 across elixir 0-3 -> 9-10), and forcing
`my_elixir_exact` on only LOWERS p. Neither explains a 50 s stall at 10 elixir.

What the live probe could NOT reproduce is the bot's own history: it scored every frame with `past` empty
(the match-start sentinel, 5.2% of training rows), while the frozen bot carries three real plays that are 40-60 s
old. Training's past dt is median 8.55 s, p90 21.95, p99 36.75 -- so a frozen bot's own history walks OUT of
the distribution, and if a stale past suppresses the gate the stall is self-reinforcing by construction.

Measured here on ENGINE VAL rows (labels available): the same states re-scored with the past ages rewritten.
usage: python scratchpad/gauntlet/L67/gate_vs_past.py --ckpt <pt> --data <npz> --out <json>
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
    ap.add_argument("--rows", type=int, default=6000)
    a = ap.parse_args()

    import torch
    from pipeline.dataset import load as load_ds
    from pipeline.model_v3 import S1Model, hand_mask_from_sc
    from pipeline.train_s1 import Rows

    arrs, _ = load_ds(a.data)
    idx = np.flatnonzero(arrs["split"] == 1)
    rng = np.random.default_rng(0)
    idx = np.sort(rng.choice(idx, size=min(a.rows, len(idx)), replace=False))
    has_past = arrs["past"][idx][:, 0, 0] >= 0
    dev = torch.device("cpu")
    st = torch.load(a.ckpt, map_location=dev)
    args = dict(st.get("args", {}) or {})
    model = S1Model(d=int(args.get("d", 128)), layers=int(args.get("layers", 4))).to(dev)
    model.load_state_dict(st["model"])
    model.eval()
    rows = Rows(arrs, idx, dev)
    y = arrs["y_gate"][idx].astype(float)

    def score(mut) -> np.ndarray:
        out = []
        with torch.no_grad():
            for s0 in range(0, len(idx), 512):
                b = rows.batch(idx[s0:s0 + 512])
                past = b["past"].clone()
                mut(past)
                enc = model.encode(b["tok"], b["mask"], b["sc"], past)
                out.append(torch.sigmoid(model.heads(enc, hand_mask_from_sc(b["sc"]))["gate"]).numpy())
        return np.concatenate(out)

    def age(v):
        def f(p):
            m = p[:, :, 0] >= 0
            p[:, :, 3] = torch.where(m, torch.full_like(p[:, :, 3], float(v)), p[:, :, 3])
        return f

    # L67i: the live student's `past` is wall-clock and is NEVER reset between matches, so once it stops
    # playing the ages grow without bound and cross match boundaries. Training's max is 95.5 s (median 8.55,
    # p99 36.75), so everything past ~100 s is a direction the gate head has never seen.
    variants = {"as_recorded": (lambda p: None), "no_past": (lambda p: p.fill_(-1.0)),
                "age_3s": age(3.0), "age_10s": age(10.0), "age_30s": age(30.0),
                "age_60s": age(60.0), "age_95s (training max)": age(95.0),
                "age_120s": age(120.0), "age_200s": age(200.0), "age_300s": age(300.0),
                "age_600s": age(600.0), "age_1200s": age(1200.0)}
    rec = []
    for name, mut in variants.items():
        p = score(mut)
        rec.append({"variant": name, "n": int(len(p)), "mean_p": round(float(p.mean()), 4),
                    "mean_p_rows_with_past": round(float(p[has_past].mean()), 4),
                    "frac_over_0.27": round(float((p > 0.27).mean()), 4),
                    "pro_rate": round(float(y.mean()), 4)})
        print(json.dumps(rec[-1]), flush=True)
    a.out.write_text(json.dumps(rec, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
