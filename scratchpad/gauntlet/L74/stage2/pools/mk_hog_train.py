"""S2-02: Hog-only slice of L74/mix/decks_live_train.json (mvp/mk_hog_pool.py's rule on the TRAIN pool; same schema, so
rl_royale league_decks takes it) + its overlap with mvp/decks_hog_eval.json (the gate pool). Self-check: every kept deck
classifies Hog and none that does was dropped."""
import json, sys
R = "C:/Users/benpe/ClashBot/scratchpad/gauntlet/"
sys.path.insert(0, R + "L73/live_eval")
from live_eval import classify
H = "Hog (incl. Royal Hogs)"
P = json.load(open(R + "L74/mix/decks_live_train.json"))
cls = lambda d: classify([c.split("@")[0] for c in d["engine"]])
hog = [d for d in P["decks"] if cls(d) == H]
assert hog and len(hog) == sum(cls(d) == H for d in P["decks"])
json.dump({**P, "decks": hog, "source": "stage2/pools/mk_hog_train.py <- mix/decks_live_train.json (" + P["source"] + ")"},
          open(R + "L74/stage2/pools/decks_hog_train.json", "w"))
E = json.load(open(R + "L74/stage2/mvp/decks_hog_eval.json"))["decks"]
key = lambda d: tuple(sorted(d["engine"]))
tr, ev = {key(d): d for d in hog}, {key(d): d for d in E}
both = set(tr) & set(ev)
print(f"train Hog decks {len(tr)} (sides {sum(d['sides'] for d in hog)}); eval Hog decks {len(ev)} (sides {sum(d['sides'] for d in E)})")
print(f"overlap by exact 8-card deck: {len(both)} decks = {len(both) / len(ev):.1%} of eval decks, "
      f"{sum(ev[k]['sides'] for k in both) / sum(d['sides'] for d in E):.1%} of eval sides")
