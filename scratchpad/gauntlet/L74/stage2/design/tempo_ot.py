"""OT share / OT win / overall win per opponent setup in the 10-15 human-tempo sweep (L74/human/data, learner F1 u65).
SIM OT = end > 3600 ticks (gate_fit's rule). Wilson 95% intervals.
  icebow/.venv/Scripts/python.exe tempo_ot.py"""
import glob, gzip, json, math, os
def wil(k, n, z=1.96):
    if not n: return (float('nan'),) * 2
    p = k / n; d = 1 + z * z / n; c = (p + z * z / (2 * n)) / d; h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return c - h, c + h
D = "C:/Users/benpe/ClashBot/scratchpad/gauntlet/L74/human/data/"
for f in sorted(glob.glob(D + "sim_*.json.gz")):
    rows = json.load(gzip.open(f))
    n = len(rows); w = sum(r["res"] == 1 for r in rows); ot = [r for r in rows if (r.get("end") or 0) > 3600]
    otw = sum(r["res"] == 1 for r in ot); lo, hi = wil(len(ot), n)
    rl = sum(r["res"] != 1 and (r.get("end") or 0) <= 3600 for r in rows) / n
    print(f"reg-loss {rl:5.1%}  " + f"{os.path.basename(f)[4:-8]:18s} n {n:4d}  win {w/n:5.1%}  OT share {len(ot)/n:5.1%} [{lo:.1%},{hi:.1%}]  OT win {otw/max(1,len(ot)):5.1%} (n {len(ot)})")
assert wil(5, 10)[0] < .5 < wil(5, 10)[1]
