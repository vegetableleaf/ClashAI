"""Print compare.py's first diverging decision per side (prev / prod / fast, with opp_past / opp_cycle)."""
import json
import sys

d = json.load(open(sys.argv[1]))
for s in d["sides"][:int(sys.argv[2]) if len(sys.argv) > 2 else 2]:
    print(s["tag"], s.get("at"), s.get("decisions"))
    for w in ("prev_prod", "prod", "fast"):
        x = s.get(w)
        if x:
            print(" ", w, x["tick"], x["play"], x["slot"], x["cell"], round(x["p"], 5), x.get("h_diff"),
                  "\n    opp_past", x.get("opp_past"), "\n    opp_cycle", x.get("opp_cycle"))
