"""Rocket use in eval / gate rows (D3 matches.jsonl own_plays = [tick, land, card, accepted, ...]): accepted Rockets per match,
and those decided in 2x / OT (tick >= 2400). Owner 10-26: a candidate must USE Rocket. Usage: python rocket_rows.py GLOB [GLOB ...]
Last line: ROCKETS per_match=X late_per_match=Y n=N (night_decide's Rocket bar reads it)."""
import glob
import json
import sys

n = rk = late = 0
for pat in sys.argv[1:]:
    for f in sorted(glob.glob(pat)):
        for line in open(f, encoding="utf-8"):
            if not line.strip():
                continue
            r = json.loads(line)
            n += 1
            for p in r.get("own_plays") or []:
                if len(p) > 3 and str(p[2]).lower() == "rocket" and p[3]:
                    rk += 1
                    late += int(p[0] >= 2400)
print(f"ROCKETS per_match={rk / max(n, 1):.3f} late_per_match={late / max(n, 1):.3f} n={n}")
