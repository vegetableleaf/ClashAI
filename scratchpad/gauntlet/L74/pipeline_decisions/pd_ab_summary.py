"""--pipeline-decisions SIM A/B summary (pod_pipeline_decisions.sh output: <dir>/<arm>_{evo,lad}/matches.jsonl, --record-plays).
Paired by (census, tag) against the reference arm; plays = ACCEPTED plays at their LANDING tick (= execution, as the pros' ticks).

    python pd_ab_summary.py OUTDIR [--ref off] [--arms pd0,pd1,pd2] [--pros pro_pairs24.json]

Acceptance bar (written before the run, HANDOFF): a candidate arm is non-inferior when its paired wins are >= the reference's minus
1.5 pp AND its play-pair profile is not worse than the failure the earlier attempts showed:
  <= 24-tick pairs per play within 2x the pros' (0.058), elixir at play not lower than the reference by > 0.3, P(Tornado | second play)
  within 2x the pros' second-card share (0.119 for <= 24).  The table prints each so the call is made on numbers, not on one p-value.
"""
import argparse
import json
import math
import os
import random
from collections import Counter

import numpy as np

ap = argparse.ArgumentParser()
ap.add_argument("out")
ap.add_argument("--ref", default="off")
ap.add_argument("--arms", default="pd0")
ap.add_argument("--pros", default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "pro_pairs24.json"))
A = ap.parse_args()
random.seed(0)
PH = (("1x", 0, 2400), ("2x", 2400, 3600), ("OT", 3600, 10 ** 9))
norm = lambda c: str(c).split("@")[0].replace("-", "_").split("_evo")[0].lower()      # noqa: E731


def load(arm):
    out = {}
    for s in ("evo", "lad"):
        p = f"{A.out}/{arm}_{s}/matches.jsonl"
        if os.path.exists(p):
            for line in open(p):
                r = json.loads(line)
                if r.get("arm") == "plain" and not r.get("skipped"):
                    out[(s, r["tag"])] = r
    return out


def score(r):
    return {"win": 1.0, "draw": 0.5}.get(r["outcome"], 0.0)


def sign_p(b, c):
    n, k = b + c, min(b, c)
    return min(1.0, 2 * sum(math.comb(n, i) for i in range(k + 1)) / 2 ** n) if n else 1.0


def boot(vals, B=2000):
    vals = list(vals)
    if not vals:
        return "n/a"
    m = [float(np.mean(random.choices(vals, k=len(vals)))) for _ in range(B)]
    return f"{np.mean(vals):.3f} [{np.percentile(m, 2.5):.3f},{np.percentile(m, 97.5):.3f}]"


def profile(rows):
    gaps, p24, pairs, second, elx = [], 0, Counter(), Counter(), []
    plays_n = pend_dec = sec_plays = 0
    for r in rows:
        own = r.get("own_plays") or []
        acc = sorted((q for q in own if q[3]), key=lambda q: q[1])
        plays_n += len(acc)
        elx += [q[4] for q in acc if q[4] is not None]
        for a, b in zip(acc, acc[1:]):
            g = b[1] - a[1]
            gaps.append(g)
            if g <= 24:
                p24 += 1
                pairs[f"{norm(a[2])}->{norm(b[2])}"] += 1
                second[norm(b[2])] += 1
        pd = r.get("pipeline_decisions") or {}
        pend_dec += pd.get("decisions_pending", 0)
        sec_plays += pd.get("second_plays", 0)
    g = np.array(gaps) if gaps else np.array([0])
    tot = max(sum(second.values()), 1)
    return dict(n=len(rows), plays_per_match=plays_n / max(len(rows), 1), share24=float((g <= 24).mean()) if gaps else 0.0,
                share20=float((g <= 20).mean()) if gaps else 0.0, gap_min=int(g.min()), pairs=pairs,
                second_mix={c: v / tot for c, v in second.most_common()}, elixir=float(np.mean(elx)) if elx else float("nan"),
                pend_dec=pend_dec / max(len(rows), 1), sec_plays=sec_plays / max(len(rows), 1))


ref = load(A.ref)
pros = json.load(open(A.pros)) if os.path.exists(A.pros) else None
print(f"reference arm {A.ref}: {len(ref)} matches")
for arm in A.arms.split(","):
    cand = load(arm)
    keys = sorted(set(ref) & set(cand))
    r0, r1 = [ref[k] for k in keys], [cand[k] for k in keys]
    up = sum(score(b) > score(a) for a, b in zip(r0, r1))
    dn = sum(score(b) < score(a) for a, b in zip(r0, r1))
    w0, w1 = sum(map(score, r0)), sum(map(score, r1))
    print(f"\n== {arm} vs {A.ref}: paired n={len(keys)} | wins {A.ref} {w0:.1f} vs {arm} {w1:.1f} ({100 * (w1 - w0) / max(len(keys), 1):+.2f} pp)"
          f" | better {up} worse {dn} sign p={sign_p(up, dn):.4f}")
    for cen in ("evo", "lad"):
        ks = [i for i, k in enumerate(keys) if k[0] == cen]
        u = sum(score(r1[i]) > score(r0[i]) for i in ks)
        d = sum(score(r1[i]) < score(r0[i]) for i in ks)
        print(f"   {cen}: {A.ref} {sum(score(r0[i]) for i in ks):.1f} {arm} {sum(score(r1[i]) for i in ks):.1f} better {u} worse {d} p={sign_p(u, d):.3f}")
    for name, rows in ((A.ref, r0), (arm, r1)):
        p = profile(rows)
        print(f"   [{name}] plays/match {p['plays_per_match']:.1f} | consecutive plays <= 24 ticks {p['share24']:.4f} (pros "
              f"{pros['share_gap_le_24'] if pros else 'n/a'}) <= 20 {p['share20']:.4f} | min gap {p['gap_min']} | elixir at play {p['elixir']:.2f}"
              f" | pending decisions/match {p['pend_dec']:.1f}, second plays/match {p['sec_plays']:.2f}")
        print("      <=24 second-card mix " + ", ".join(f"{c} {v:.2f}" for c, v in list(p['second_mix'].items())[:8])
              + (f"   [pros: Tornado {pros['second_mix_le_24'].get('tornado')}, Skeletons {pros['second_mix_le_24'].get('skeletons')}]" if pros else ""))
        print("      top <=24 pairs/match " + ", ".join(f"{k} {v / max(p['n'], 1):.3f}" for k, v in p["pairs"].most_common(8)))
    b = profile(r1)
    ok_wins = (w1 - w0) / max(len(keys), 1) >= -0.015
    ok_pairs = pros is None or b["share24"] <= 2 * pros["share_gap_le_24"]
    ok_elx = b["elixir"] >= profile(r0)["elixir"] - 0.3
    ok_torn = pros is None or b["second_mix"].get("tornado", 0.0) <= 2 * pros["second_mix_le_24"].get("tornado", 1.0)
    print(f"   BAR: wins non-inferior (>= -1.5 pp) {ok_wins} | pair share <= 2x pros {ok_pairs} | elixir at play ok {ok_elx} | Tornado share <= 2x pros {ok_torn}"
          f"  ->  {'PASS' if all((ok_wins, ok_pairs, ok_elx, ok_torn)) else 'FAIL'}")
