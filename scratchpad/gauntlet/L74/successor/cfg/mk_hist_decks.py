"""Arm S2 HISTDECKS deck file: the training pool (decks_rl.json, sha b43dd085) with the owner rule's unimplemented half --
"plus any found in history" (memory train-on-unfavorable-matchups) -- applied to the 13k-core cards the live history shows
the bot losing to (win < 45 %, n >= 15 since 10-15: Mega Knight, Witch, Firecracker, Electro Giant, Elixir Golem, Golden
Knight; Hog Rider for Mark CXXXVIII 5/17).
Only decks that hold a core card and are NOT one of the owner's six (already boosted 4.95x) are re-weighted: their `sides`
are raked (iterative proportional fitting, one multiplier per core card) until each core card's presence in training
draws equals its live presence in Mark CXXXVIII's 81 ladder matches (drift.txt "Live CXXXVIII" column). 3x-live is
infeasible (Mega Knight 23.5 % x 3 = 70 %) and 3x-census is too (core-not-six census share 0.251 x 3 = 0.75 next to the
six's 0.60), so the target is 1x the 13k ladder. The six's sides are unchanged (one change vs the control); every other
deck's share shrinks proportionally, as it did when the six were boosted.
RL draws P ~ sides (alpha 1, floor 0: rl_royale.deck_weights).
    python mk_hist_decks.py IN.json OUT.json     -> prints presence before / after, the six's share, effective deck count"""
import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "weekend"))
import archetypes as A  # noqa: E402

TARGET = {"megaknight": .235, "witch": .284, "firecracker": .222, "hogrider": .210, "electrogiant": .074,
          "elixirgolem": .086, "goldenknight": .086}             # live presence, Mark CXXXVIII 13:29-20:50 10-17 (n 81)
src, out = sys.argv[1], sys.argv[2]
d = json.load(open(src, encoding="utf-8"))
sides = np.array([float(x["sides"]) for x in d["decks"]])
has = {c: np.array([c in {A.canon(n) for n in x["engine"]} for x in d["decks"]]) for c in TARGET}
six = np.array([A.unfavorable(A.classify(x["engine"])) for x in d["decks"]])
free = ~six & np.any(list(has.values()), axis=0)              # the decks whose weight may change


def pres(w, c):
    return w[has[c]].sum() / w.sum()


w = sides.copy()
for _ in range(500):
    for c, t in TARGET.items():
        w[has[c] & free] *= t / pres(w, c) if pres(w, c) > 0 else 1.0
gap = max(abs(pres(w, c) - t) for c, t in TARGET.items())
assert gap < 0.005, f"raking did not converge (max gap {gap:.4f})"
for x, v in zip(d["decks"], w):
    x["sides"] = max(1, int(round(v)))
d["hist_core_rake"] = {"targets": TARGET, "source": "decks_rl.json sha b43dd085", "six_sides": "unchanged",
                       "reweighted_decks": int(free.sum())}
json.dump(d, open(out, "w", encoding="utf-8"))
p0, p1 = sides / sides.sum(), w / w.sum()
print(f"re-weighted decks {free.sum()} of {len(w)}; max gap {gap:.4f}")
for c, t in TARGET.items():
    print(f"  {c:13s} {100 * pres(sides, c):5.1f}% -> {100 * pres(w, c):5.1f}%  (live {100 * t:.1f}%)")
anyc = np.any(list(has.values()), axis=0)
print(f"  any core card {100 * p0[anyc].sum():5.1f}% -> {100 * p1[anyc].sum():5.1f}%   owner six {100 * p0[six].sum():.1f}% -> "
      f"{100 * p1[six].sum():.1f}%")
print(f"  effective decks {1 / (p0 ** 2).sum():.0f} -> {1 / (p1 ** 2).sum():.0f}; top deck {100 * p0.max():.2f}% -> {100 * p1.max():.2f}%")
