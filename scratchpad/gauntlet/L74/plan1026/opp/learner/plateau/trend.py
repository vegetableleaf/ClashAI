"""OLS slope (pp per 100 updates, +- se) of D3 opponent win and of the training win vs the CLXIII partner, per arm."""
import re, os, numpy as np
from curves import run, H

LOG = r"C:/Users/benpe/ClashBot/scratchpad/gauntlet/L74/plan1026/opp/learner/out/lead_d3.log"
d3 = {}
for l in open(LOG, encoding="utf-8"):
    m = re.search(r"Z (oplc_\S+?)_u(\d{4})(?:_635)? (?:\[[^\]]+\] )?CLXIII W (\d+) / 480", l)
    if m:
        d3.setdefault(m.group(1), {})[int(m.group(2))] = 100 * (1 - int(m.group(3)) / 480)


def ols(x, y):
    x, y = np.asarray(x, float), np.asarray(y, float)
    if len(x) < 3:
        return float("nan"), float("nan")
    b, a = np.polyfit(x, y, 1)
    r = y - (a + b * x)
    se = np.sqrt(r @ r / (len(x) - 2) / ((x - x.mean()) @ (x - x.mean())))
    return 100 * b, 100 * se


for name, pts in sorted(d3.items()):
    u = sorted(pts)
    s, se = ols(u, [pts[k] for k in u])
    line = f"{name:28s} D3 u{u[0]}-u{u[-1]} n{len(u)}: {s:+.1f} +- {se:.1f} pp/100u"
    try:
        rows, _ = run(name)
        late = [r for r in rows if r["u"] >= 40]
        ts, tse = ols([r["u"] for r in late], [100 * r["wr_bot"] for r in late])
        line += f" | train vs partner u40-u{rows[-1]['u']}: {ts:+.1f} +- {tse:.1f} pp/100u"
    except FileNotFoundError:
        line += " | train log not on disk"
    print(line)
