"""~/paired.py split by opponent (gen / s1) + learner play counts.  python paired_split.py BASE CAND [CAND ...]"""
import json, math, os, sys
O = os.path.expanduser("~/eval_ns")


def load(name):
    out = {}
    for pre in ("react", "reactlad"):
        for l in open(f"{O}/{pre}_{name}/matches.jsonl"):
            r = json.loads(l)
            if r["arm"] == "plain":
                out[(pre, r["tag"])] = r
    return out


score = lambda r: {"win": 1.0, "draw": 0.5}.get(r["outcome"], 0.0)


def sign_p(b, c):
    n, k = b + c, min(b, c)
    return min(1.0, 2 * sum(math.comb(n, i) for i in range(k + 1)) / 2 ** n) if n else 1.0


base = load(sys.argv[1])
for cand in sys.argv[2:]:
    c = load(cand)
    for opp in ("gen", "s1", "all"):
        keys = sorted(k for k in set(base) & set(c) if opp == "all" or c[k]["opp"] == opp)
        up = sum(score(c[k]) > score(base[k]) for k in keys); dn = sum(score(c[k]) < score(base[k]) for k in keys)
        z = sum(c[k]["plays_accepted"] == 0 for k in keys)
        print(f"{cand:22s} {opp:4s} n={len(keys)} wins {sum(score(c[k]) for k in keys):.1f} vs {sum(score(base[k]) for k in keys):.1f}"
              f" better {up} worse {dn} p={sign_p(up, dn):.3f} | learner 0-play games cand {z} base {sum(base[k]['plays_accepted'] == 0 for k in keys)}")
