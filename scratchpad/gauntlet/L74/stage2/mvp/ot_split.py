"""Live 2x2 per Mark/band: Hog vs rest x regulation vs OT (ladder-graded rows of ../gate/live_targets.json)."""
import json
R = json.load(open("C:/Users/benpe/ClashBot/scratchpad/gauntlet/L74/stage2/gate/live_targets.json"))
H = "Hog (incl. Royal Hogs)"
for mark, band, f in (("CXXXVIII", "13k", lambda s: s >= 13000), ("CXXXVIII", "12k", lambda s: 12000 <= s < 13000),
                      ("CXXIV", "12k", lambda s: 12000 <= s < 13000)):
    rows = [x for x in R if x["mark"] == mark and x["src"] == "ladder" and x["start"] is not None and f(x["start"])]
    for g in ("Hog", "rest"):
        for ot in (False, True):
            s = [x for x in rows if (x["cls"] == H) == (g == "Hog") and x["ot"] == ot]
            w = sum(x["res"] == "WIN" for x in s)
            print(f"{mark:9s} {band} {g:4s} {'OT ' if ot else 'reg'} {w:3d}/{len(s):3d}" + (f" {w/len(s):6.1%}" if s else ""))
