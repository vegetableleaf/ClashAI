"""P3-FORK L1 pilot report from a CF_DUMP jsonl (one line per rollout match: update, outcome, end_tick, wall_s, cf).

    python pilot_report.py DUMP.jsonl [--from-update U] [--budget 1.0] [--matches-per-update 128] > report.json

Per trigger: samples, candidates, the reliability of the K-mean advantage (cf_credit.reliability: factor, SNR, split-half r)
and a bootstrap 90% interval of the SNR over samples; K needed for SNR 0.5 (K' = 0.5 / snr^2 at the measured K = 2, if the
continuations' noise is independent); the mean advantage of each alternative kind (unshrunk, value units) with its SE; the
critic-slope audit (cf_credit.slope_audit) with a bootstrap interval; fork cost = fork ticks per match tick and fork wall per
match; trigger rates per match. BUDGET (needs the dump's ``cond_ticks``, written when the actor has the CF_DUMP env var):
the decisions per match at which each trigger's condition held, replayed through the gap / probability rule at any cf_p ->
expected samples per match; ``recommended_cf_p`` = the water-filling split of ``--budget`` x match ticks of fork ticks over
the triggers (equal ticks per trigger, a trigger that cannot use its share at p = 1 gives the rest to the others; ``random``
gets half a share), with the predicted fork ticks per match tick and samples per update."""
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[5]))
from pipeline import cf_credit as CF                                       # noqa: E402

RANDOM_SHARE = 0.5                                                          # a ``random`` share of the budget, in trigger shares


def boot(samples, fn, n=400, seed=0):
    rng = np.random.default_rng(seed)
    out = []
    for _ in range(n):
        idx = rng.integers(0, len(samples), len(samples))
        v = fn([samples[i] for i in idx])
        if v is not None and np.isfinite(v):
            out.append(v)
    return [float(np.percentile(out, 5)), float(np.percentile(out, 95))] if len(out) > 20 else None


def expected_samples(ticks_per_match: list, gap: int, p: float, reps: int = 30, seed: int = 0) -> float:
    """Samples per match of one trigger at probability ``p``: its condition ticks replayed through cf_credit.triggers' rule (a
    draw at every decision whose condition holds and that is >= ``gap`` ticks after the last SAMPLE), Monte Carlo over ``reps``."""
    if p <= 0 or not ticks_per_match:
        return 0.0
    rng = np.random.default_rng(seed)
    n = 0
    for _ in range(reps):
        for ticks in ticks_per_match:
            last = -10 ** 9
            u = rng.random(len(ticks))
            for t, ui in zip(ticks, u):
                if t - last >= gap and ui < p:
                    n += 1
                    last = t
    return n / (reps * len(ticks_per_match))


def budget_split(cost: dict, cap_samples: dict, per_tick_budget: float, share: dict) -> dict:
    """Water-filling: the fork ticks per match of each trigger (samples x cost), ``share`` weights summing the budget
    ``per_tick_budget`` (ticks per match), none above its p = 1 ticks ``cap_samples * cost``; the surplus is re-split."""
    spend = {t: 0.0 for t in cost}
    live = {t for t in cost if cap_samples.get(t, 0) > 0 and cost[t] > 0}
    left = per_tick_budget
    while live and left > 1e-9:
        w = sum(share[t] for t in live)
        done = set()
        for t in live:
            give = left * share[t] / w
            room = cap_samples[t] * cost[t] - spend[t]
            if give >= room:
                spend[t] += room
                done.add(t)
        if not done:
            for t in live:
                spend[t] += left * share[t] / w
            left = 0.0
            break
        left = per_tick_budget - sum(spend.values())
        live -= done
    return spend


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("dump")
    ap.add_argument("--from-update", type=int, default=0)
    ap.add_argument("--budget", type=float, default=1.0, help="fork ticks per match tick to plan for (target <= 1)")
    ap.add_argument("--matches-per-update", type=int, default=128)
    ap.add_argument("--gap", type=int, default=CF.DEFAULTS["cf_gap_ticks"])
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
        snr = rel.get("snr")
        out["triggers"][t] = {
            "samples": len(ss), "per_match": len(ss) / max(1, len(rows)), **rel,
            "snr_ci90": boot(ss, lambda x: CF.reliability([CF.sample_adv(s["cands"]) for s in x])["snr"]),
            "k_for_snr_0.5": (None if not snr else max(2, int(np.ceil(0.5 / snr ** 2)))),
            "fork_ticks_per_sample": float(np.mean([s["fork_ticks"] for s in ss])),
            "wall_s_per_sample": float(np.mean([s["wall_s"] for s in ss])),
            "cands_mean": float(np.mean([len(s["cands"]) for s in ss])),
            "terminal_share": float(np.mean([c["terminal"][k] for s in ss for c in s["cands"] for k in range(len(c["q"]))])),
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
                   "match_wall_s": sum(float(r.get("wall_s") or 0) for r in rows) / max(1, len(rows)),
                   "audit_samples": len(aud), "mean_match_ticks": mt / max(1, len(rows))}
    out["fired_per_match"] = {t: sum(r["cf"].get("fired", {}).get(t, 0) for r in rows) / max(1, len(rows))
                              for t in CF.TRIGGERS}
    out["cond_per_match"] = {t: sum(r["cf"].get("cond", {}).get(t, 0) for r in rows) / max(1, len(rows))
                             for t in CF.TRIGGERS}
    out["capped"] = {t: sum(r["cf"].get("capped", {}).get(t, 0) for r in rows) for t in CF.TRIGGERS}
    ticks = {t: [r["cf"]["cond_ticks"].get(t, []) for r in rows if "cond_ticks" in r["cf"]] for t in CF.TRIGGERS}
    if any(ticks[t] for t in CF.TRIGGERS) and mt:
        cost = {t: out["triggers"][t]["fork_ticks_per_sample"] for t in out["triggers"]}
        # triggers never sampled in the pilot have no cost estimate: use the pooled mean (one K x C x horizon sample)
        pooled = float(np.mean([s["fork_ticks"] for s in smp])) if smp else 0.0
        cost = {t: cost.get(t, pooled) for t in CF.TRIGGERS}
        cap = {t: expected_samples(ticks[t], a.gap, 1.0, reps=1) for t in CF.TRIGGERS}
        budget = a.budget * mt / len(rows)
        share = {t: (RANDOM_SHARE if t == "random" else 1.0) for t in CF.TRIGGERS}
        spend = budget_split(cost, cap, budget, share)
        rec, pred = {}, {}
        for t in CF.TRIGGERS:
            want = spend[t] / cost[t] if cost[t] > 0 else 0.0                    # samples per match
            if cap[t] <= 0 or want <= 0:
                rec[t], pred[t] = 0.0, 0.0
                continue
            lo, hi = 0.0, 1.0
            if want >= cap[t] - 1e-9:
                lo = hi = 1.0
            else:
                for _ in range(14):
                    mid = (lo + hi) / 2
                    if expected_samples(ticks[t], a.gap, mid, reps=8, seed=1) < want:
                        lo = mid
                    else:
                        hi = mid
            rec[t] = float(round((lo + hi) / 2, 5))
            pred[t] = expected_samples(ticks[t], a.gap, rec[t], reps=30, seed=2)
        out["budget"] = {"fork_ticks_budget_per_match": budget, "cost_per_sample": cost,
                         "samples_per_match_at_p1": cap, "recommended_cf_p": rec, "predicted_samples_per_match": pred,
                         "predicted_fork_ticks_per_match_tick": sum(pred[t] * cost[t] for t in CF.TRIGGERS) / (mt / len(rows)),
                         "predicted_samples_per_update": {t: pred[t] * a.matches_per_update for t in CF.TRIGGERS}}
    json.dump(out, sys.stdout, indent=1)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
