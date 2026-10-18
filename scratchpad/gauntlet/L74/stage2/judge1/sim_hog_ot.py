"""SIM Hog x OT 2x2 for eval dirs (learner win rate). Usage: sim_hog_ot.py NAME=glob ..."""
import glob, json, sys
sys.path.insert(0, "C:/Users/benpe/ClashBot/scratchpad/gauntlet/L74/stage2/gate")
from gate_fit import sim
H = "Hog (incl. Royal Hogs)"
for a in sys.argv[1:]:
    name, pat = a.split("=", 1)
    rows = sim(pat)
    ot = sum(o for _, _, o in rows)
    print(f"{name}: n {len(rows)} win {sum(w for w,_,_ in rows)/max(1,len(rows)):.1%} OT share {ot/max(1,len(rows)):.1%}")
    for g in ("Hog", "rest"):
        for o in (False, True):
            s = [w for w, c, oo in rows if (c == H) == (g == "Hog") and oo == o]
            print(f"   {g:4s} {'OT ' if o else 'reg'} {sum(s):4d}/{len(s):4d}" + (f" {sum(s)/len(s):6.1%}" if s else ""))
