"""Hog-only live cells per Mark and band (ladder-graded rows of ../gate/live_targets.json) + Hog share of the eval deck pool."""
import json, sys
sys.path.insert(0, "C:/Users/benpe/ClashBot/scratchpad/gauntlet/L73/live_eval")
from live_eval import classify, wilson
R = json.load(open("C:/Users/benpe/ClashBot/scratchpad/gauntlet/L74/stage2/gate/live_targets.json"))
H = "Hog (incl. Royal Hogs)"
for mark in ("CXXXVIII", "CXXIV"):
    for band, f in (("13k", lambda s: s >= 13000), ("12k", lambda s: 12000 <= s < 13000)):
        rows = [x for x in R if x["mark"] == mark and x["src"] == "ladder" and x["start"] is not None and f(x["start"]) and x["cls"] == H]
        if not rows: continue
        w = sum(x["res"] == "WIN" for x in rows); ot = [x for x in rows if x["ot"]]; otw = sum(x["res"] == "WIN" for x in ot)
        print(f"{mark:9s} {band} Hog n {len(rows):3d} win {w}/{len(rows)} OT share {len(ot)}/{len(rows)} OT win {otw}/{len(ot)}")
P = json.load(open("C:/Users/benpe/ClashBot/scratchpad/gauntlet/L74/mix/decks_live_eval.json"))
decks = P["decks"]
def cards(d): return d["engine"]
hog = [d for d in decks if classify([c.split("@")[0] for c in cards(d)]) == H]
print("eval pool decks", len(decks), "Hog decks", len(hog), "Hog sides", sum(d["sides"] for d in hog), "of", sum(d["sides"] for d in decks))
