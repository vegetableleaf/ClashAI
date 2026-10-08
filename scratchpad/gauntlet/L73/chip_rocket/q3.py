"""Q3: after a failed offensive X-Bow (destroyed, <10% tower damage), what comes in the next 30 s? Reuses xbow_switch/analyze.py (Q4 there)."""
import pickle, math, os, sys, json
sys.path.insert(0, "C:/Users/benpe/ClashBot/scratchpad/gauntlet/L73/xbow_switch")
import analyze as A
HERE = os.path.dirname(os.path.abspath(__file__))
bot = pickle.load(open(os.path.join(HERE, "bot_xbow.pkl"), "rb"))
R = json.load(open("C:/Users/benpe/ClashBot/scratchpad/gauntlet/L73/xbow_switch/results.json"))
f = lambda t: "n/a" if t is None or t[0] is None else f"{100*t[0]:.0f}% [{100*t[1]:.0f},{100*t[2]:.0f}] n={int(t[4])}"
KEYS = ["new_offensive_Xbow", "defensive_Xbow", "tower_Rocket", "Tesla", "none_of_Xbow/Tesla/towerRocket(hold)"]
def show(name, q4):
    for ph in ("all", "ph_OT", "ph_2x"):
        if ph in q4: print(f"{name:10s} {ph:6s} n={q4[ph]['n']:5d} " + " | ".join(f"{k.split('(')[0]} {f(q4[ph][k])}" for k in KEYS))
show("pros", R["pros_all"]["q4"])
for k in ("R1e", "live"):
    Ms = bot[k]
    for M in Ms:
        for p in M["plays"]: p["x"] = math.floor(p["x"]) + 0.5; p["y"] = math.floor(p["y"]) + 0.5
        M["tiebreak"] = M["end"] >= 5900
    RD, nr = A.rocket_damage(Ms)
    res, X = A.analyze(Ms, RD)
    print(k, "matches", len(Ms), "rocket tower drop median", RD, "n", nr, "off X-Bows", res["xbow_counts"])
    show(k, res["q4"])
