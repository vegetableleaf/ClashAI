"""L67r: offline bisection of the CAPTURED live freeze states (data/freeze_states.jsonl, CaptureBudget, 5cs.99 W).

Every record is the exact model input (tok, mask, sc, past) at a live decision where the gate was pinned
(`pinned_hi`: p < 0.05 at elixir >= 8, t >= 20 s) or the anti-stall rule overrode it (`stall`). Two questions:

  1. COUNTERFACTUAL -- re-score each state with ONE input group changed. Which change lifts p over the live tau?
     A change that lifts p on these states is a candidate cause, NOT a proven one: the states were selected for
     low p, so any perturbation regresses toward the mean. Read every row against `noise_*` controls that
     perturb something irrelevant by the same amount.
  2. DISTRIBUTION -- how do these inputs differ from the TRAINING rows (split 0), overall and at elixir >= 8?
     A feature the live path produces and training never contained is the classic silent cause here.

usage: python freeze_bisect.py --states icebow/data/freeze_states.jsonl --ckpt icebow/data/pipeline/s1_icebow_v6lat_s0.pt
                               --data icebow/data/pipeline/s1_dataset_v6.npz --out <json> [--tau 0.27]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import torch

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))

from pipeline import obs_contract                                        # noqa: E402
from pipeline.model_v3 import S1Model, hand_mask_from_sc                 # noqa: E402


def load_states(path, opening_stalls=False):
    R = [json.loads(l) for l in open(path, encoding="utf-8")]
    if not opening_stalls:                        # stalls before the match's first play are the anti-stall bug, not a freeze
        R = [r for r in R if not (r.get("why") == "stall" and r.get("idle_s") is None)]
    tok = np.asarray([r["tok"] for r in R], dtype=np.float32)
    mask = np.asarray([r["mask"] for r in R], dtype=bool)
    sc = np.asarray([r["sc"] for r in R], dtype=np.float32)
    past = np.asarray([r["past"] for r in R], dtype=np.float32)
    why = np.asarray([r.get("why", "?") for r in R])
    p_rec = np.asarray([r["p"] for r in R], dtype=np.float32)
    return R, tok, mask, sc, past, why, p_rec


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--states", type=Path, required=True)
    ap.add_argument("--ckpt", type=Path, required=True)
    ap.add_argument("--data", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--tau", type=float, default=0.27)
    a = ap.parse_args()

    st = torch.load(a.ckpt, map_location="cpu")
    args = st.get("args", {}) or {}
    model = S1Model(d=int(args.get("d", 128)), layers=int(args.get("layers", 4)))
    model.load_state_dict(st["model"])
    model.eval()

    def gate(tok, mask, sc, past):
        with torch.no_grad():
            t, m, s, p = (torch.from_numpy(x) for x in (tok, mask, sc, past))
            enc = model.encode(t, m, s, p)
            return torch.sigmoid(model.heads(enc, hand_mask_from_sc(s))["gate"]).numpy()

    R, tok, mask, sc, past, why, p_rec = load_states(a.states)
    n_open = sum(1 for l in open(a.states, encoding="utf-8") if '"why": "stall"' in l and '"idle_s": null' in l)
    sides = obs_contract._SIDE_COL
    col = {k: v for k, v in sides.items()}
    base = gate(tok, mask, sc, past)
    out = {"n": int(len(R)), "excluded_opening_stalls": n_open, "by_why": {w: int((why == w).sum()) for w in np.unique(why)},
           "side_cols": {str(k): int(v) for k, v in col.items()},
           "rescore_max_abs_err": float(np.abs(base - p_rec).max()), "base_mean_p": float(base.mean())}
    rng = np.random.default_rng(0)

    def side_mask(side_name):
        c = [v for k, v in col.items() if str(k).lower().endswith(side_name)]
        return (tok[..., c[0]] > 0.5) if c else np.zeros(mask.shape, bool)

    def with_(tok_=None, mask_=None, sc_=None, past_=None):
        return (tok if tok_ is None else tok_, mask if mask_ is None else mask_,
                sc if sc_ is None else sc_, past if past_ is None else past_)

    def f_sc(**kv):
        s = sc.copy()
        for k, v in kv.items():
            lo, hi = (int(x) for x in k[1:].split("_")) if "_" in k[1:] else (int(k[1:]), int(k[1:]) + 1)
            s[:, lo:hi] = v
        return s

    past_fresh = past.copy(); past_fresh[..., 3] = np.where(past[..., 0] >= 0, 3.0, past[..., 3])
    past_stale = past.copy(); past_stale[..., 3] = np.where(past[..., 0] >= 0, 60.0, past[..., 3])
    tok_hp = tok.copy(); tok_hp[..., 6] = np.where(mask & (tok[..., 7] < 0.5), 1.0, tok[..., 6]); tok_hp[..., 7] = np.where(mask, 1.0, tok[..., 7])
    tok_conf = tok.copy(); tok_conf[..., 12] = np.where(mask, 1.0, tok[..., 12])
    tok_age = tok.copy(); tok_age[..., 10:12] = 0.0
    tok_dep = tok.copy(); tok_dep[..., 8:10] = 0.0
    tok_jit = tok.copy(); tok_jit[..., 4:6] = np.clip(tok[..., 4:6] + rng.normal(0, 0.02, tok[..., 4:6].shape), 0, 1) * mask[..., None]
    sc_jit = sc.copy(); sc_jit[:, 0] = np.clip(sc[:, 0] + rng.normal(0, 0.02, len(sc)), 0, 1)

    arms = {
        "board_empty": with_(mask_=np.zeros_like(mask)),
        "enemy_units_off": with_(mask_=mask & ~side_mask("enemy")),
        "my_units_off": with_(mask_=mask & ~side_mask("mine")),
        "unknown_side_off": with_(mask_=mask & ~side_mask("unknown")),
        "spells_off": with_(mask_=mask & ~(tok[..., 13] > 0.5)),
        "unit_hp_known_full": with_(tok_=tok_hp),
        "unit_conf_1": with_(tok_=tok_conf),
        "unit_age_unknown": with_(tok_=tok_age),
        "unit_deploying_unknown": with_(tok_=tok_dep),
        "past_clear": with_(past_=np.full_like(past, -1.0)),
        "past_age_3s": with_(past_=past_fresh),
        "past_age_60s": with_(past_=past_stale),
        "elixir_10": with_(sc_=f_sc(s3=1.0)),
        "elixir_6": with_(sc_=f_sc(s3=0.6)),
        "elixir_exact_on": with_(sc_=f_sc(s4=1.0)),
        "opp_elixir_5_known": with_(sc_=f_sc(s5=0.5, s6=1.0)),
        "time_60s_single": with_(sc_=f_sc(s0=0.2, s1=0.0, s2=0.0)),
        "time_150s_double": with_(sc_=f_sc(s0=0.5, s1=1.0, s2=0.0)),
        "towers_full_known": with_(sc_=f_sc(s52_58=1.0, s58_64=1.0, s64_70=1.0)),
        "towers_hp_unknown": with_(sc_=f_sc(s52_58=0.0, s58_64=0.0)),
        "next_unknown": with_(sc_=(lambda s: (s.__setitem__((slice(None), slice(43, 52)), 0.0), s.__setitem__((slice(None), 51), 1.0), s)[-1])(sc.copy())),
        "noise_unit_xy_2pct": with_(tok_=tok_jit),
        "noise_time_2pct": with_(sc_=sc_jit),
    }
    rows = {}
    for name, (t_, m_, s_, p_) in arms.items():
        p = gate(t_, m_, s_, p_)
        rows[name] = {"mean_p": round(float(p.mean()), 4), "frac_over_tau": round(float((p > a.tau).mean()), 3),
                      "mean_delta": round(float((p - base).mean()), 4),
                      **{f"frac_over_tau_{w}": round(float((p[why == w] > a.tau).mean()), 3) for w in np.unique(why)}}
    out["base"] = {"mean_p": round(float(base.mean()), 4), "frac_over_tau": round(float((base > a.tau).mean()), 3)}
    out["arms"] = rows

    # ---- 2. distribution vs training ----------------------------------------------------------------------------
    z = np.load(a.data, allow_pickle=True)
    tr = np.where(z["split"] == 0)[0]
    ztok, off, zsc, zpast, zg = z["tok"], z["off"], z["sc"], z["past"], z["y_gate"]
    hi = tr[zsc[tr, 3] >= 0.8]
    def scal(ix, S=None):
        S = zsc[ix] if S is None else S
        return {"t": round(float(S[:, 0].mean()), 3), "double": round(float(S[:, 1].mean()), 3), "overtime": round(float(S[:, 2].mean()), 3),
                "elixir": round(float(S[:, 3].mean()), 3), "exact": round(float(S[:, 4].mean()), 3), "opp_known": round(float(S[:, 6].mean()), 3),
                "hand_unmapped_slots": round(float(S[:, 7:43].reshape(-1, 4, 9)[:, :, 8].sum(1).mean()), 3),
                "next_unmapped": round(float(S[:, 51].mean()), 3),
                "tower_hp_known": [round(float(x), 2) for x in S[:, 58:64].mean(0)],
                "tower_alive": [round(float(x), 2) for x in S[:, 64:70].mean(0)]}
    sample = rng.choice(hi, size=min(20000, len(hi)), replace=False)
    def tokstats_train(ix):
        seg = np.concatenate([ztok[off[i]:off[i + 1]] for i in ix])
        cnt = np.array([off[i + 1] - off[i] for i in ix])
        return seg, cnt
    seg, cnt = tokstats_train(sample)
    live_seg = tok[mask]
    def tstats(T, counts):
        return {"tokens_per_state": round(float(np.mean(counts)), 2),
                **{f"side_{k}": round(float((T[:, v] > 0.5).mean()), 3) for k, v in col.items()},
                "hp_known": round(float(T[:, 7].mean()), 3), "deploying_known": round(float(T[:, 9].mean()), 3),
                "age_known": round(float(T[:, 11].mean()), 3), "conf_mean": round(float(T[:, 12].mean()), 3),
                "is_spell": round(float(T[:, 13].mean()), 3)}
    def pstats(P):
        known = P[..., 0] >= 0
        ages = P[..., 3][known]
        return {"past_slots_filled": round(float(known.sum(1).mean()), 2),
                "past_age_median": round(float(np.median(ages)), 2) if ages.size else None,
                "past_age_p90": round(float(np.percentile(ages, 90)), 2) if ages.size else None}
    out["distribution"] = {
        "live_captured": {**scal(None, sc), **tstats(live_seg, mask.sum(1)), **pstats(past)},
        "train_elixir_ge_8": {**scal(sample), **tstats(seg, cnt), **pstats(zpast[sample]),
                              "gate_play_rate": round(float(zg[sample].mean()), 3)},
        "train_all": {**scal(tr[:20000]), **pstats(zpast[tr[:20000]])},
    }
    a.out.write_text(json.dumps(out, indent=1, default=str), encoding="utf-8")
    print(json.dumps({k: out[k] for k in ("n", "excluded_opening_stalls", "by_why", "rescore_max_abs_err", "base")}))
    print(f"{'arm':26s} {'mean_p':>7s} {'>tau':>6s} {'d_mean':>7s}  per-why >tau")
    for name, r in rows.items():
        print(f"{name:26s} {r['mean_p']:7.3f} {r['frac_over_tau']:6.2f} {r['mean_delta']:+7.3f}  "
              + " ".join(f"{k[14:]}={v:.2f}" for k, v in r.items() if k.startswith("frac_over_tau_")))
    for k, v in out["distribution"].items():
        print(k, json.dumps(v))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
