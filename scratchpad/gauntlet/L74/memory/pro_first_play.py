"""Pro first-play time (s) per match side, from the pro memory tables (first own play event). Context for the drift test's
'first play s' flag (CLXIII 12.7 s in SIM). Usage: python pro_first_play.py <memory_tables.npz>"""
import sys

import numpy as np

sys.path.insert(0, __file__.rsplit("scratchpad", 1)[0])
from pipeline.match_memory import _COL  # noqa: E402

z = np.load(sys.argv[1])
off, vals, tick = z["tab_off"], z["tab_vals"], z["tab_tick"]
mine, play = vals[:, _COL["mine"]] > 0, vals[:, _COL["is_play"]] > 0
first = []
for j in range(len(off) - 1):
    a, b = int(off[j]), int(off[j + 1])
    t = tick[a:b][(mine[a:b] & play[a:b])]
    if len(t):
        first.append(t.min() * 0.05)
f = np.array(first)
print(f"{len(f)} pro match sides: first own play s median {np.median(f):.1f}, mean {f.mean():.1f}, "
      f"p25 {np.percentile(f, 25):.1f}, p75 {np.percentile(f, 75):.1f}, share > 15 s {np.mean(f > 15):.2f}, > 20 s {np.mean(f > 20):.2f}")
