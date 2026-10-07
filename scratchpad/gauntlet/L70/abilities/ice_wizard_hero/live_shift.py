import sys, glob, random, json
sys.path.insert(0, "C:/Users/benpe/ClashBot/scratchpad/gauntlet/L68/live_reader")
import numpy as np, ability_ice_wizard as A
from live_log_replay import replay
m = A.load_model(); mu = dict(zip(m["feature_names"], m["mean"])); sd = dict(zip(m["feature_names"], m["scale"]))
rng = random.Random(1); F = []
for f in sorted(glob.glob("C:/Users/benpe/ClashBot/scratchpad/gauntlet/L68/live_reader/live_play_2026100[56]_*.jsonl"))[:40]:
    dep = None; ok = False
    for r, pilot in replay(f):
        if r.get("event") == "confirmed" and r["name"] == "IceWizard": dep = int(r["tick"])
        if r.get("event") == "frame" and dep is not None and 20 <= r["tick"] - dep <= 600 and rng.random() < 0.02:
            F.append(A.live_features(pilot, r["_frame"], pilot.public.side, dep))
print(len(F))
for n in A.BASE_FEATURES:
    v = np.array([x[n] for x in F]); print("%-18s live %.2f  train-at-risk %.2f  (sd %.2f)  z %+.2f" % (n, v.mean(), mu[n], sd[n], (v.mean() - mu[n]) / sd[n]))
