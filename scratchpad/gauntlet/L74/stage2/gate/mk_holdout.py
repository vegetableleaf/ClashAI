"""Gate hold-out list: every live log of the two gated Marks (CXXXVIII, CXXIV). An imitation corpus for SIM opponents must
exclude these files (by name) or the gate is circular. Future sealed-set logs get appended by re-running after live_targets.py."""
import json, os
H = os.path.dirname(os.path.abspath(__file__))
X = json.load(open(os.path.join(H, "live_targets.json")))
names = sorted({x["file"] for x in X if x["mark"]})
open(os.path.join(H, "gate_holdout.txt"), "w").write("\n".join(names) + "\n")
print(len(names), "files ->", os.path.join(H, "gate_holdout.txt"))
