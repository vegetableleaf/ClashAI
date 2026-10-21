"""W12: every arm vs CLX paired on the w7opp eval. usage: python w12_analyze.py ROOT  (ROOT/<w12_NAME>/<w12_NAME>_<seed>/D3/matches.jsonl)"""
import json, sys, math, collections, os
ROOT = sys.argv[1]
ARMS = ["tn_base_s74", "tn_base_s75", "tn_lead_s74", "tn_rocket_s74", "tn_tornado_s74", "tn_redirect_s74", "clx_fin15"]
SEEDS = {"std": (741200, 742000), "fresh": (743000, 744000)}
def load(arm, seed):
    f = f"{ROOT}/{arm}/w12_{arm}/w12_{arm}_{seed}/D3/matches.jsonl"
    out = {}; cnt = collections.Counter()
    for line in open(f):
        r = json.loads(line)
        k = (r["seed"], r["tag"], r["learner_side"], tuple(r["opp_deck"])); cnt[k] += 1
        out[k + (cnt[k],)] = r
    return out
D = {a: {s: load(a, s) for g in SEEDS.values() for s in g} for a in ARMS}
def ci(d):
    n = len(d); m = sum(d) / n; sd = math.sqrt(sum((x - m) ** 2 for x in d) / (n - 1)); h = 1.96 * sd / math.sqrt(n)
    return n, 100 * m, 100 * (m - h), 100 * (m + h)
def grp(a, ss): 
    o = {}
    for s in ss: o.update(D[a][s])
    return o
L = ["| arm | split | n | win% | CLX win% | delta pp | 95% CI |", "|---|---|---|---|---|---|---|"]
for a in ARMS[:-1] + ["clx_fin15"]:
    for name, ss in list(SEEDS.items()) + [("pooled", SEEDS["std"] + SEEDS["fresh"])]:
        A, B = grp(a, ss), grp("clx_fin15", ss); ks = sorted(set(A) & set(B))
        w = lambda R: 100 * sum(R[k]["outcome"] == "win" for k in ks) / len(ks)
        if a == "clx_fin15": L.append(f"| clx_fin15 | {name} | {len(ks)} | {w(A):.1f} | - | - | - |"); continue
        n, m, lo, hi = ci([(A[k]["outcome"] == "win") - (B[k]["outcome"] == "win") for k in ks])
        L.append(f"| {a} | {name} | {n} | {w(A):.1f} | {w(B):.1f} | {m:+.2f} | [{lo:+.2f}, {hi:+.2f}] |")
C = ["| arm | n | lost_princess | gave_back | king_end | tornados_after_fall | toward_after_fall | rockets_tower |", "|---|---|---|---|---|---|---|---|"]
for a in ARMS:
    R = list(grp(a, SEEDS["std"] + SEEDS["fresh"]).values()); S = [r["crown"]["summary"] for r in R if r.get("crown")]
    f = lambda k: sum(float(s.get(k) or 0) for s in S) / len(S)
    C.append(f"| {a} | {len(S)} | {100*f('lost_princess'):.1f}% | {100*f('gave_back'):.1f}% | {f('king_end'):.3f} | {f('tornados_after_fall'):.3f} | {f('toward_after_fall'):.3f} | {f('rockets_tower'):.3f} |")
print("\n".join(L)); print(); print("\n".join(C))
