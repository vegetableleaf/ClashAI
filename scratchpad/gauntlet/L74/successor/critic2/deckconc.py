"""Critic lens 2: concentration of the S2 deck file (effective deck count, top decks, share of the raked decks)."""
import json, sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "weekend"))
import archetypes as A
d = json.load(open(sys.argv[1], encoding="utf-8"))
w = [float(x["sides"]) for x in d["decks"]]
T = sum(w); p = [v / T for v in w]
six = [A.unfavorable(A.classify(x["engine"])) for x in d["decks"]]
print("decks", len(w), "effective", round(1 / sum(q * q for q in p)), "top5", [round(100 * q, 2) for q in sorted(p)[-5:]])
print("six share", round(100 * sum(q for q, s in zip(p, six) if s), 1))
core = {"megaknight", "witch", "firecracker", "hogrider", "electrogiant", "elixirgolem", "goldenknight"}
for c in sorted(core):
    idx = [i for i, x in enumerate(d["decks"]) if c in {A.canon(n) for n in x["engine"]}]
    ps = sorted((p[i] for i in idx), reverse=True)
    print(f"{c:13s} decks {len(idx):4d} share {100*sum(ps):5.1f}% top3 {[round(100*q,2) for q in ps[:3]]} eff {round(sum(ps)**2/max(1e-12,sum(q*q for q in ps)))}")
print(d.get("hist_core_rake", {}).get("reweighted_decks"))
