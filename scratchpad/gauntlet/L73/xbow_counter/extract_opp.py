"""Stage B (pros): opponent plays + true opp hand/elixir at each own X-Bow play, from the re-drive jsons. Read-only."""
import json, glob, os, pickle, re, ctypes
try: ctypes.windll.kernel32.SetPriorityClass(ctypes.windll.kernel32.GetCurrentProcess(), 0x4000)
except Exception: pass
HERE = "C:/Users/benpe/ClashBot/scratchpad/gauntlet/L73/xbow_counter/"
BASE = {"Xbow", "Skeletons", "Log", "Knight", "Tesla", "Tornado", "IceWizard", "Rocket"}
def hy(n): return re.sub(r"(?<!^)(?=[A-Z])", "-", n.split("@")[0]).lower()
out = {}
for i, f in enumerate(sorted(glob.glob("C:/Users/benpe/ClashBot/scratchpad/gauntlet/ext/corpus_v6/icebow_public_v1/j*/replay_*.json"))):
    d = json.load(open(f)); tag = os.path.basename(f)[7:19]
    for s in (0, 1):
        if {c.split("@")[0] for c in d["final_decks"][str(s)]} != BASE: continue
        fx = (lambda x, y: (x / 1000.0, y / 1000.0)) if s == 1 else (lambda x, y: ((18000 - x) / 1000.0, (32000 - y) / 1000.0))
        opp = []
        for p in d["log"]:
            if p["side"] == s or not p.get("accepted") or "ability" in p: continue
            x, y = fx(p["x"], p["y"]); opp.append((p["tick"], p["card"], x, y))
        tru = {}
        for pf in d["play_frames"]:
            if pf["side"] == s and pf["card"] == "x-bow":
                o = [pl for pl in pf["players"] if pl["side"] != s][0]
                tru[pf["tick"]] = ([hy(h) for h in o["hand"]], o["elixir"])
        out[f"{tag}_s{s}"] = {"opp": opp, "true_at_xbow": tru}
    if i % 400 == 0: print(i, flush=True)
pickle.dump(out, open(HERE + "opp_pros.pkl", "wb")); print("saved", len(out))
