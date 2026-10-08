"""Barrel-heavy benchmark (~/eval_ns/reactgb_<name>): wins, crowns against, tower hp, paired sign tests.
    python gb_paired.py NAME [NAME ...]        (first = base; pairs: every name vs base, then consecutive)"""
import json, math, os, sys
O = os.path.expanduser("~/eval_ns")


def load(n):
    rows = [json.loads(l) for l in open(f"{O}/reactgb_{n}/matches.jsonl")]
    return {r["tag"]: r for r in rows if r["arm"] == "plain"}


sc = lambda r: {"win": 1.0, "draw": 0.5}.get(r["outcome"], 0.0)


def sp(b, c):
    n, k = b + c, min(b, c)
    return min(1.0, 2 * sum(math.comb(n, i) for i in range(k + 1)) / 2 ** n) if n else 1.0


names = sys.argv[1:]
A = {n: load(n) for n in names}
for n, r in A.items():
    k = sorted(r)
    print(f"{n:24s} n={len(k)} wins {sum(sc(r[x]) for x in k):.1f}  crowns against {sum(r[x]['crowns_against'] for x in k)}"
          f"  crowns for {sum(r[x]['crowns_for'] for x in k)}  mean own tower hp {sum(r[x]['tower_hp_for'] for x in k) / len(k):.0f}"
          f"  mean hp diff {sum(r[x]['tower_hp_diff'] for x in k) / len(k):+.0f}")
pairs = [(names[0], b) for b in names[1:]] + list(zip(names[1:], names[2:]))
for a, b in pairs:
    k = sorted(set(A[a]) & set(A[b]))
    up = sum(sc(A[b][x]) > sc(A[a][x]) for x in k); dn = sum(sc(A[b][x]) < sc(A[a][x]) for x in k)
    ca = sum(A[b][x]["crowns_against"] - A[a][x]["crowns_against"] for x in k)
    print(f"{b} vs {a}: better {up} worse {dn} p={sp(up, dn):.3f}  crowns-against delta {ca:+d}")
