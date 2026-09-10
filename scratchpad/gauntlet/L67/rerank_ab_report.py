"""L67n: pair a reranker arm against the unsearched student AND the rollout search, per seed, on both slices.

One fixed script for the verdict, so the comparison cannot drift by hand arithmetic. Every arm here was run on
the same seeds and the same instrument (the sim's play_match, degraded view):

  slice A = seeds 900000..900011   baseline student_sim_deg.json (first 12)   search arm_search.json
  slice B = seeds 911000..911011   baseline arm2_baseline.json                 search arm2_search.json

Reported per slice and pooled: paired tower-delta difference vs baseline (mean +- sem, t), wins, plays per match,
and the same against the search -- the reranker is only worth deploying if it keeps a meaningful share of the
search's +1.46-1.71 while costing no rollouts.

usage: python scratchpad/gauntlet/L67/rerank_ab_report.py --a <rerank sim json, slice A> --b <slice B> [--label X]
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

L67 = Path("scratchpad/gauntlet/L67")
BASE = {"A": (L67 / "student_sim_deg.json", 12), "B": (L67 / "arm2_baseline.json", 12)}
SEARCH = {"A": L67 / "arm_search.json", "B": L67 / "arm2_search.json"}


def by_seed(path, limit=None):
    ms = json.loads(Path(path).read_text(encoding="utf-8"))["matches"]
    ms = ms[:limit] if limit else ms
    return {int(m["seed"]): m for m in ms}


def paired(arm, ref):
    ks = sorted(set(arm) & set(ref))
    d = np.array([arm[k]["tower_delta"] - ref[k]["tower_delta"] for k in ks])
    if len(d) < 2:
        return {"n": len(d)}
    se = float(d.std(ddof=1) / np.sqrt(len(d)))
    return {"n": len(d), "mean": round(float(d.mean()), 3), "sem": round(se, 3),
            "t": round(float(d.mean()) / se, 2) if se > 0 else None, "diffs": d}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--a", type=Path, required=True)
    ap.add_argument("--b", type=Path, required=True)
    ap.add_argument("--label", default="rerank")
    a = ap.parse_args()

    pooled_base, pooled_search = [], []
    print(f"{'slice':5s} {'arm':10s} {'tower':>7s} {'wins':>5s} {'plays':>6s} | {'vs student (paired)':>24s} | {'vs search (paired)':>24s}")
    for sl, path in (("A", a.a), ("B", a.b)):
        arm = by_seed(path)
        base = by_seed(*BASE[sl])
        srch = by_seed(SEARCH[sl])
        for name, d in (("student", base), ("search", srch), (a.label, arm)):
            ms = list(d.values())
            print(f"{sl:5s} {name:10s} {np.mean([m['tower_delta'] for m in ms]):+7.3f} "
                  f"{sum(m['outcome'] == 'win' for m in ms):2d}/{len(ms):<2d} "
                  f"{np.mean([m['plays'] for m in ms]):6.1f}", end="")
            if name == a.label:
                pb, ps = paired(arm, base), paired(arm, srch)
                pooled_base.append(pb["diffs"]); pooled_search.append(ps["diffs"])
                print(f" | {pb['mean']:+.3f} +- {pb['sem']:.3f} (t={pb['t']}) | {ps['mean']:+.3f} +- {ps['sem']:.3f} (t={ps['t']})")
            else:
                print()
    for nm, parts in (("vs student", pooled_base), ("vs search", pooled_search)):
        d = np.concatenate(parts)
        se = d.std(ddof=1) / np.sqrt(len(d))
        print(f"POOLED {a.label} {nm}: {d.mean():+.3f} +- {se:.3f} (t={d.mean() / se:.2f}, n={len(d)})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
