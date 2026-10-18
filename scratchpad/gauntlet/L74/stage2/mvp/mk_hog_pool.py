"""Hog-only slice of L74/mix/decks_live_eval.json (same schema, so gap.py --census-file takes it). Self-check: every kept deck
classifies Hog, none dropped that does."""
import json, sys
R = "C:/Users/benpe/ClashBot/scratchpad/gauntlet/"
sys.path.insert(0, R + "L73/live_eval")
from live_eval import classify
H = "Hog (incl. Royal Hogs)"
P = json.load(open(R + "L74/mix/decks_live_eval.json"))
cls = lambda d: classify([c.split("@")[0] for c in d["engine"]])
hog = [d for d in P["decks"] if cls(d) == H]
assert hog and all(cls(d) == H for d in hog) and len(hog) == sum(cls(d) == H for d in P["decks"])
json.dump({**P, "decks": hog, "source": "mk_hog_pool.py <- " + P["source"]}, open(R + "L74/stage2/mvp/decks_hog_eval.json", "w"))
print(len(hog), "Hog decks,", sum(d["sides"] for d in hog), "sides")
