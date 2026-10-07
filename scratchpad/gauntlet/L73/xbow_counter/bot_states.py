"""Bot decision states: tick, own hand names, own elixir (for the X-Bow-opportunity denominators)."""
import sys, pickle, ctypes
try: ctypes.windll.kernel32.SetPriorityClass(ctypes.windll.kernel32.GetCurrentProcess(), 0x4000)
except Exception: pass
sys.path.insert(0, "C:/Users/benpe/ClashBot/scratchpad/gauntlet/L73/live_review")
import load as L
HERE = "C:/Users/benpe/ClashBot/scratchpad/gauntlet/L73/xbow_counter/"
ids = [m["id"] for m in pickle.load(open("C:/Users/benpe/ClashBot/scratchpad/gauntlet/L73/xbow_switch/bot.pkl", "rb"))]
out = {}
for fid in ids:
    d = L.load(L.D + fid)
    out[fid] = [(s["tick"], s["el"], s["hand"], s["dec"]) for s in d["states"]]
pickle.dump(out, open(HERE + "bot_states.pkl", "wb")); print("saved", len(out))
