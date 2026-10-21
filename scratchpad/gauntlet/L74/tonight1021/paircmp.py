import json, glob, sys, math, collections
def load(pat):
    out = {}
    for f in sorted(glob.glob(pat)):
        cnt = collections.Counter()
        for line in open(f):
            r = json.loads(line)
            k = (r["seed"], r["tag"], r["learner_side"], tuple(r["opp_deck"]))
            cnt[k] += 1
            out[k + (cnt[k],)] = r["outcome"] == "win"
    return out
A, B, base = sys.argv[1], sys.argv[2], sys.argv[3:]
res = {}
for name, seeds in (("std", (741200, 742000)), ("fresh", (743000, 744000))):
    a, b = {}, {}
    for s in seeds:
        a.update(load(A.format(s=s))); b.update(load(B.format(s=s)))
    ks = sorted(set(a) & set(b))
    d = [a[k] - b[k] for k in ks]
    n = len(d); m = sum(d) / n; sd = math.sqrt(sum((x - m) ** 2 for x in d) / (n - 1))
    print(f"{name}: n={n} A={sum(a[k] for k in ks)} B={sum(b[k] for k in ks)} delta={100*m:+.2f} pp [{100*(m-1.96*sd/math.sqrt(n)):+.2f}, {100*(m+1.96*sd/math.sqrt(n)):+.2f}]")
