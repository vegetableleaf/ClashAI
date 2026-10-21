"""Base recipe, 6 seeds: tn_base_s74..s79 vs clx_fin15 (w7opp eval). usage: python w12_base6.py ROOT"""
import json, sys, math, collections, statistics as st
ROOT = sys.argv[1]; SEEDS = (741200, 742000, 743000, 744000)
def load(arm):
    out = {}
    for s in SEEDS:
        cnt = collections.Counter()
        for line in open(f"{ROOT}/{arm}/w12_{arm}/w12_{arm}_{s}/D3/matches.jsonl"):
            r = json.loads(line); k = (r["seed"], r["tag"], r["learner_side"], tuple(r["opp_deck"])); cnt[k] += 1
            out[k + (cnt[k],)] = r
    return out
clx = load("clx_fin15"); L = ["| arm | n | win% | delta vs CLX pp | 95% CI | lost_princess | gave_back | king_end |", "|---|---|---|---|---|---|---|---|"]
deltas = []; wins = []
for i in range(74, 80):
    a = f"tn_base_s{i}"; A = load(a); ks = sorted(set(A) & set(clx))
    d = [(A[k]["outcome"] == "win") - (clx[k]["outcome"] == "win") for k in ks]
    n = len(d); m = sum(d) / n; h = 1.96 * st.stdev(d) / math.sqrt(n)
    S = [A[k]["crown"]["summary"] for k in ks]; f = lambda x: sum(float(s.get(x) or 0) for s in S) / n
    w = 100 * sum(A[k]["outcome"] == "win" for k in ks) / n; deltas.append(100 * m); wins.append(w)
    L.append(f"| {a} | {n} | {w:.1f} | {100*m:+.2f} | [{100*(m-h):+.2f}, {100*(m+h):+.2f}] | {100*f('lost_princess'):.1f}% | {100*f('gave_back'):.1f}% | {f('king_end'):.3f} |")
cw = 100 * sum(r["outcome"] == "win" for r in clx.values()) / len(clx)
sd = st.stdev(deltas); se = sd / math.sqrt(len(deltas)); t = 2.571  # t(0.975, 5 df)
L.append(f"| **mean of 6** | | {st.mean(wins):.1f} | {st.mean(deltas):+.2f} | seed-level 95% CI [{st.mean(deltas)-t*se:+.2f}, {st.mean(deltas)+t*se:+.2f}] (t, 5 df) | | | |")
L.append(f"\nCLX win% {cw:.1f}. Across-seed SD of the delta {sd:.2f} pp (min {min(deltas):+.2f}, max {max(deltas):+.2f}, range {max(deltas)-min(deltas):.2f}); SD of win% {st.stdev(wins):.2f}.")
print("\n".join(L))
