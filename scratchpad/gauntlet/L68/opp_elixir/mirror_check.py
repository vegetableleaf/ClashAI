"""What does the engine charge for Mirror? log `cost` says 1; implied charge = elixir_before + regen - next frame.
First 9 Mirror plays in corpus_v6 (rate 0.0178 single / 0.0357 double; triple-phase rows read ~0.04-0.4 low)."""
import glob, json
from pathlib import Path
REPO = Path(__file__).resolve().parents[4]
n = 0
for deck in ("icebow", "hogeq"):
    for f in sorted(glob.glob(str(REPO / f"scratchpad/gauntlet/ext/corpus_v6/{deck}/replay_*.json"))):
        d = json.load(open(f)); log = [e for e in d["log"] if e.get("accepted")]
        for i, e in enumerate(log):
            if e["card"] != "mirror" or n >= 9: continue
            prev = [x for x in log[:i] if x["side"] == e["side"]][-1]
            fr = next(x for x in d["frames"] if x["tick"] > e["tick"])
            rate = 0.0178 if fr["tick"] < 2400 else 0.0357
            drop = e["elixir_before"] + rate * (fr["tick"] - e["tick"]) - fr["elixir"][e["side"]]
            print(f[-20:], e["tick"], "mirrored", prev["card"], prev["cost"], "log cost", e["cost"], f"implied charge {drop:.2f}")
            n += 1
