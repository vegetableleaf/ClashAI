"""Re-weight a census deck file toward the unfavourable archetypes (owner 2026-10-10).
    python mk_weighted_decks.py IN.json OUT.json ALPHA FLOOR   (ALPHA / FLOOR = the consumer's deck_weights: RL 1.0 / 0, search_s0 0.5 / 0.5)
Unfavourable decks' `sides` are multiplied by m (bisection) so that their share of the consumer's sampling probability is
max(3 x natural share, 0.5), capped at 0.6.  Prints natural vs target vs achieved share and the per-archetype natural shares."""
import collections, json, os, sys
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import archetypes as A

src, out, alpha, floor = sys.argv[1], sys.argv[2], float(sys.argv[3]), float(sys.argv[4])
d = json.load(open(src))
sides = np.array([float(x["sides"]) for x in d["decks"]])
arch = [A.classify(x["engine"]) for x in d["decks"]]
unf = np.array([A.unfavorable(a) for a in arch])


def probs(s):
    w = s ** alpha
    w = np.maximum(w, floor * w.mean())
    return w / w.sum()


p0 = probs(sides)
nat = p0[unf].sum()
q = min(0.6, max(3 * nat, 0.5))
lo, hi = 1.0, 1e6
for _ in range(80):
    m = (lo * hi) ** 0.5
    if probs(np.where(unf, sides * m, sides))[unf].sum() < q:
        lo = m
    else:
        hi = m
s2 = np.where(unf, sides * hi, sides)
for x, v in zip(d["decks"], s2):
    x["sides"] = int(round(v))
got = probs(np.array([float(x["sides"]) for x in d["decks"]]))
d["weighted_archetypes"] = {"alpha": alpha, "floor": floor, "natural_share": float(nat), "target": float(q), "multiplier": float(hi)}
json.dump(d, open(out, "w"))
c = collections.Counter()
for a, pn, pg in zip(arch, p0, got):
    c[a, "nat"] += pn; c[a, "new"] += pg
print(f"unfavourable share natural {nat:.3f} -> target {q:.3f} -> got {got[unf].sum():.3f} (multiplier {hi:.1f})")
for a in sorted(set(arch)):
    print(f"  {a:18s} decks {arch.count(a):4d} natural {c[a, 'nat']:.3f} new {c[a, 'new']:.3f}")
