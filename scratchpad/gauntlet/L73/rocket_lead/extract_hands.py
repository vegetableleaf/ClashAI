"""Own hand (names) before each own log entry of the pro re-drives -> own hand over time (hand is constant between own plays)."""
import json, glob, os, pickle, ctypes
try: ctypes.windll.kernel32.SetPriorityClass(ctypes.windll.kernel32.GetCurrentProcess(), 0x4000)
except Exception: pass
BASE = {"Xbow", "Skeletons", "Log", "Knight", "Tesla", "Tornado", "IceWizard", "Rocket"}
out = {}
for i, f in enumerate(sorted(glob.glob("C:/Users/benpe/ClashBot/scratchpad/gauntlet/ext/corpus_v6/icebow_public_v1/j*/replay_*.json"))):
    d = json.load(open(f)); tag = os.path.basename(f)[7:19]
    for s in (0, 1):
        if {c.split("@")[0] for c in d["final_decks"][str(s)]} != BASE: continue
        out[f"{tag}_s{s}"] = sorted((p["tick"], [h.split("@")[0] for h in p["hand_before"]]) for p in d["log"] if p["side"] == s and "hand_before" in p)
    if i % 500 == 0: print(i, flush=True)
pickle.dump(out, open("C:/Users/benpe/ClashBot/scratchpad/gauntlet/L73/rocket_lead/hands_pros.pkl", "wb")); print("saved", len(out))
