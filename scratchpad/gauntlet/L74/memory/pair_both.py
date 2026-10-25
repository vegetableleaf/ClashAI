"""Paired win-rate delta, candidate A vs base B, per suite (E4, cal) and pooled over both (3,840 games); paircmp_pooled's pairing.
Usage: python pair_both.py A_E4_PAT A_CAL_PAT B_E4_PAT B_CAL_PAT   (patterns with {s} = seed block)
Last line: PASS / FAIL (pooled 95% CI low > 0; owner 10-22 bar, 10-25 night: vs CLXIII, the live model)."""
import collections
import glob
import json
import math
import sys

SEEDS = (741200, 742000, 743000, 744000)


def load(pat, suite):
    out = {}
    for s in SEEDS:
        for f in sorted(glob.glob(pat.format(s=s))):
            cnt = collections.Counter()
            for line in open(f):
                r = json.loads(line)
                k = (suite, r["seed"], r["tag"], r["learner_side"], tuple(r["opp_deck"]))
                cnt[k] += 1
                out[k + (cnt[k],)] = r["outcome"] == "win"
    return out


def delta(a, b):
    ks = sorted(set(a) & set(b))
    d = [a[k] - b[k] for k in ks]
    n = len(d)
    m = sum(d) / n
    sd = math.sqrt(sum((x - m) ** 2 for x in d) / (n - 1))
    h = 1.96 * sd / math.sqrt(n)
    return n, m, m - h, m + h


def main():
    ae, ac, be, bc = sys.argv[1:5]
    A = {"e4": load(ae, "e4"), "cal": load(ac, "cal")}
    B = {"e4": load(be, "e4"), "cal": load(bc, "cal")}
    for s in ("e4", "cal"):
        n, m, lo, hi = delta(A[s], B[s])
        print(f"{s}: n={n} delta={100 * m:+.2f} pp [{100 * lo:+.2f}, {100 * hi:+.2f}]")
    n, m, lo, hi = delta({**A["e4"], **A["cal"]}, {**B["e4"], **B["cal"]})
    print(f"pooled: n={n} delta={100 * m:+.2f} pp [{100 * lo:+.2f}, {100 * hi:+.2f}]")
    print("PASS" if n >= 3000 and lo > 0 else "FAIL")


if __name__ == "__main__":
    main()
