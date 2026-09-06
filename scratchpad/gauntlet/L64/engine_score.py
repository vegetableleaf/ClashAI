"""Score engine_play runs as per-tag deltas vs the no-plays control.
usage: engine_score.py <control_summary.json> <run_summary.json> [<run_summary.json> ...]
Runs must share the control's seed (same pool order) -- paired by match index and checked by tag."""
import json, sys
import numpy as np

def load(p):
    d = json.load(open(p, encoding="utf-8"))
    return d["args"], {r["match"]: r for r in d["results"]}

def score(ctrl, run, label):
    a, C = ctrl; b, R = run
    keys = sorted(set(C) & set(R))
    bad = [k for k in keys if C[k]["tag"] != R[k]["tag"]]
    assert not bad, f"tag mismatch at matches {bad[:5]} -- different seed/pool?"
    ds = np.array([R[k]["seconds"] - C[k]["seconds"] for k in keys])
    dcf = np.array([R[k]["crowns_for"] - C[k]["crowns_for"] for k in keys])
    dca = np.array([R[k]["crowns_against"] - C[k]["crowns_against"] for k in keys])
    out = {"label": label, "n": len(keys), "gate": b.get("gate"), "tau": b.get("tau"), "ckpt": b.get("ckpt"),
           "win": sum(R[k]["outcome"] == "win" for k in keys), "draw": sum(R[k]["outcome"] == "draw" for k in keys),
           "loss": sum(R[k]["outcome"] == "loss" for k in keys),
           "ctrl_win": sum(C[k]["outcome"] == "win" for k in keys),
           "seconds_mean": round(float(np.mean([R[k]["seconds"] for k in keys])), 1),
           "ctrl_seconds_mean": round(float(np.mean([C[k]["seconds"] for k in keys])), 1),
           "d_seconds_mean": round(float(ds.mean()), 1), "d_seconds_se": round(float(ds.std(ddof=1) / np.sqrt(len(ds))), 1),
           "d_seconds_median": round(float(np.median(ds)), 1),
           "survived_longer": int((ds > 0).sum()), "survived_shorter": int((ds < 0).sum()),
           "d_crowns_for_mean": round(float(dcf.mean()), 2), "d_crowns_against_mean": round(float(dca.mean()), 2),
           "crowns_against_mean": round(float(np.mean([R[k]["crowns_against"] for k in keys])), 2),
           "ctrl_crowns_against_mean": round(float(np.mean([C[k]["crowns_against"] for k in keys])), 2),
           "plays_per_min": round(sum(R[k]["plays"] for k in keys) / max(sum(R[k]["seconds"] for k in keys) / 60, 1e-9), 2),
           "accepted_frac": round(sum(R[k]["accepted"] for k in keys) / max(sum(R[k]["plays"] for k in keys), 1), 3),
           "p_gate_mean": round(float(np.mean([R[k].get("p_gate_mean", 0) for k in keys])), 4),
           "ghost_refused": sum(R[k]["ghost_refused"] for k in keys)}
    return out

if __name__ == "__main__":
    ctrl = load(sys.argv[1])
    for p in sys.argv[2:]:
        print(json.dumps(score(ctrl, load(p), p)))
