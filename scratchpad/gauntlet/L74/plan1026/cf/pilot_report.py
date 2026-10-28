"""P3-FORK L1 pilot report from a CF_DUMP jsonl (one line per rollout match: update, outcome, end_tick, wall_s, cf).

    python pilot_report.py DUMP.jsonl [--from-update U] > report.json

Per trigger: samples, candidates, the reliability of the K-mean advantage (cf_credit.reliability: factor, SNR,
split-half r) and a bootstrap 90% interval of the SNR over samples; the mean advantage of each alternative kind
(unshrunk, value units) with its SE; the critic-slope audit (cf_credit.slope_audit) with a bootstrap interval; fork
cost = fork ticks per match tick and fork wall per match wall; trigger rates per match."""
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[5]))
from pipeline import cf_credit as CF                                       # noqa: E402


def boot(samples, fn, n=400, seed=0):
    rng = np.random.default_rng(seed)
    out = []
    for _ in range(n):
        idx = rng.integers(0, len(samples), len(samples))
        v = fn([samples[i] for i in idx])
        if v is not None and np.isfinite(v):
            out.append(v)
    return [float(np.percentile(out, 5)), float(np.percentile(out, 95))] if len(out) > 20 else None


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("dump")
    ap.add_argument("--from-update", type=int, default=0)
    a = ap.parse_args(argv)
    rows = [json.loads(x) for x in Path(a.dump).read_text().splitlines() if x.strip()]
    rows = [r for r in rows if r["update"] >= a.from_update]
    smp = [s for r in rows for s in r["cf"]["samples"] if all(q is not None for c in s["cands"] for q in c["q"])]
    by = defaultdict(list)
    for s in smp:
        by[s["trigger"]].append(s)
    out = {"matches": len(rows), "updates": sorted({r["update"] for r in rows}), "samples": len(smp), "triggers": {}}
    for t, ss in sorted(by.items()):
        rel = CF.reliability([CF.sample_adv(s["cands"]) for s in ss])
        kinds = defaultdict(list)
        for s in ss:
            A = CF.sample_adv(s["cands"]).mean(axis=1)
            for c, ai in zip(s["cands"], A):
                kinds[c["kind"]].append(float(ai))
        out["triggers"][t] = {
            "samples": len(ss), "per_match": len(ss) / max(1, len(rows)), **rel,
            "snr_ci90": boot(ss, lambda x: CF.reliability([CF.sample_adv(s["cands"]) for s in x])["snr"]),
            "kinds": {k: {"n": len(v), "a_mean": float(np.mean(v)), "se": float(np.std(v) / np.sqrt(len(v)))}
                      for k, v in sorted(kinds.items())}}
    out["reliability_pooled"] = CF.reliability([CF.sample_adv(s["cands"]) for s in smp])
    aud = [s for s in smp if s.get("audit")]
    out["slope_audit"] = {**CF.slope_audit(aud),
                          "levels_ci90": boot(aud, lambda x: CF.slope_audit(x)["levels"]["slope"]),
                          "diffs_ci90": boot(aud, lambda x: CF.slope_audit(x)["diffs"]["slope"]),
                          "band": [0.7, 1.3]}
    mt = sum(int(r.get("end_tick") or 0) for r in rows)
    ft = sum(int(r["cf"].get("fork_ticks", 0)) for r in rows)
    out["cost"] = {"fork_ticks_per_match_tick": ft / mt if mt else None,
                   "fork_wall_s_per_match": sum(r["cf"]["wall_s"] for r in rows) / max(1, len(rows)),
                   "audit_samples": len(aud)}
    out["fired_per_match"] = {t: sum(r["cf"].get("fired", {}).get(t, 0) for r in rows) / max(1, len(rows))
                              for t in CF.TRIGGERS}
    out["capped"] = {t: sum(r["cf"].get("capped", {}).get(t, 0) for r in rows) for t in CF.TRIGGERS}
    json.dump(out, sys.stdout, indent=1)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
