"""Is the CXXXVIII 13k+ overtime collapse stable? Split its 13k+ matches by the loss review's cut (<= 20:35:10) vs later,
and its whole live run by start hour (time-of-day pool vs trophy band). Reads live_targets.json."""
import json, os, sys
sys.path.insert(0, "C:/Users/benpe/ClashBot/scratchpad/gauntlet/L74/loss_review/")
from review import wilson
X = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "live_targets.json")))
W = lambda Q: sum(x["res"] == "WIN" for x in Q)
def wil(Q):
    k, n = W(Q), len(Q)
    if not n: return "n/a"
    lo, hi = wilson(k, n); return f"{k}/{n} = {k / n:.1%} [{lo:.1%}, {hi:.1%}]"
C = sorted([x for x in X if x["mark"] == "CXXXVIII" and x["src"] == "ladder"], key=lambda x: x["ts"])
H = [x for x in C if x["start"] is not None and x["start"] >= 13000]
for lab, Q in (("13k+ up to the loss review (<= 20261017_203510)", [x for x in H if x["ts"] <= "20261017_203510"]),
               ("13k+ after it", [x for x in H if x["ts"] > "20261017_203510"])):
    O = [x for x in Q if x["ot"]]; hog = [x for x in Q if x["cls"].startswith("Hog")]
    print(f"{lab:50s} all {wil(Q):30s} OT {wil(O):30s} Hog {wil(hog)}")
for h0 in range(12, 24, 2):
    Q = [x for x in C if h0 <= int(x["ts"][9:11]) < h0 + 2]
    if Q:
        O = [x for x in Q if x["ot"]]
        print(f"CXXXVIII {h0:02d}-{h0 + 1:02d}h trophies {min(x['start'] or 0 for x in Q)}..{max(x['start'] or 0 for x in Q)}  all {wil(Q):30s} OT {wil(O)}")
# CXXIV evening matches (the same clock hours as CXXXVIII's 13k run), to separate hour from band
D = [x for x in X if x["mark"] == "CXXIV" and x["src"] == "ladder" and 16 <= int(x["ts"][9:11]) <= 23]
print(f"CXXIV 16-23h (any day) all {wil(D)} OT {wil([x for x in D if x['ot']])}")
