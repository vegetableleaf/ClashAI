"""Training win vs the CLXIII T .5 sampled partner (window u-10..u+9) against the D3 opponent win (greedy live stack, 480
games) at each scored checkpoint. D3 rows parsed from lead_d3.log (full 480-game blocks only)."""
import re, os, numpy as np
from curves import run, H

LOG = r"C:/Users/benpe/ClashBot/scratchpad/gauntlet/L74/plan1026/opp/learner/out/lead_d3.log"
d3 = {}
for l in open(LOG, encoding="utf-8"):
    m = re.search(r"Z (oplc_\S+?)_u(\d{4})(?:_635)? (?:\[[^\]]+\] )?CLXIII W (\d+) / 480", l)
    if m:
        d3[(m.group(1), int(m.group(2)))] = 1 - int(m.group(3)) / 480   # last block wins (reruns)
pts = []
for name in sorted({k[0] for k in d3}):
    try:
        rows, _ = run(name)
    except FileNotFoundError:
        print(f"{name}: no train log on disk (pod down)")
        continue
    for (n, u), y in sorted(d3.items()):
        if n != name:
            continue
        seg = [r for r in rows if u - 10 <= r["u"] < u + 10]
        nb = sum(r["n_bot"] for r in seg)
        x = sum(r["wr_bot"] * r["n_bot"] for r in seg) / nb
        xi = sum(r["wr_init"] * r["n_init"] for r in seg) / sum(r["n_init"] for r in seg)
        klx = np.mean([r["klx"] for r in seg])
        pts.append((x, y))
        print(f"{name:28s} u{u:03d} train_bot {x:.3f} (n {nb}) train_init {xi:.3f} klx {klx:.2f}  D3_opp {y:.3f}  gap {x - y:+.3f}")
u0 = [run(n)[0][0] for n in ("oplc_ftR_l003_a10", "oplc_ftR_l001_a10", "oplc_ftR_l01_a10", "oplc_ftR_l003_lr1e4",
                              "oplc_ftR_l0001_a10", "oplc_ftR_l003_a10_tpg32m")]
x0 = sum(r["wr_bot"] * r["n_bot"] for r in u0) / sum(r["n_bot"] for r in u0)
print(f"init ftR: u0 train_bot pooled over 6 arms {x0:.3f} (n {sum(r['n_bot'] for r in u0)}); D3_opp 53/480 = {53/480:.3f}")
x, y = np.array(pts).T
b, a = np.polyfit(x, y, 1)
print(f"OLS D3_opp = {a:.3f} + {b:.2f} x train_bot  (n {len(x)}, r {np.corrcoef(x, y)[0, 1]:.2f})")
print(f"slope through the init point: mean (D3-{53/480:.3f}) / (train-{x0:.3f}) = {np.mean((y - 53/480) / (x - x0)):.2f}")
