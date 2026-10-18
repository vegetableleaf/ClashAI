"""Critic lens 2: does S2's up-weighted training mass sit on decks that are also in the D3 eval census (train/test overlap)?"""
import json, sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "weekend"))
import archetypes as A
tr = json.load(open(sys.argv[1], encoding="utf-8"))["decks"]
ev = json.load(open(sys.argv[2], encoding="utf-8"))["decks"]
key = lambda x: frozenset(A.canon(n.split("@")[0]) for n in x["engine"])
keyf = lambda x: frozenset(x["engine"])
evk = {}; evf = {}
for x in ev:
    evk[key(x)] = evk.get(key(x), 0) + x["sides"]; evf[keyf(x)] = evf.get(keyf(x), 0) + x["sides"]
T = sum(float(x["sides"]) for x in tr); E = sum(x["sides"] for x in ev)
m = sum(float(x["sides"]) for x in tr if key(x) in evk) / T
mf = sum(float(x["sides"]) for x in tr if keyf(x) in evf) / T
print(f"train mass on decks whose base cards match an eval deck: {100*m:.1f}%  (exact forms: {100*mf:.1f}%)")
print(f"eval decks {len(ev)}  sides {E}")
for x in sorted(tr, key=lambda x: -float(x["sides"]))[:12]:
    k = key(x)
    print(f"{100*float(x['sides'])/T:5.2f}%  in_eval={'Y' if k in evk else '-'} eval_share={100*evk.get(k,0)/E:4.2f}%  {sorted(k)}")
