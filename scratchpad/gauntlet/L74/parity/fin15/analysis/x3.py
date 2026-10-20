"""Live 2x -> 3x switch tick: for each log, frames in 2340..2480 below the cap with no deduction; fit e(t) = e0 + 0.0178 * (t - t0)
before the switch and + 0.0357 after; report the switch tick that minimises the squared error."""
import json, sys, glob
from collections import Counter
res = Counter()
for p in sorted(glob.glob(sys.argv[1]))[:int(sys.argv[2])]:
    fr = []
    with open(p, 'rb') as f:
        for raw in f:
            if b'"frame"' in raw[:40]:
                j = json.loads(raw)
                t = j['tick']
                if t > 4880:
                    break
                if j.get('elixir') is not None and 4740 <= t:
                    fr.append((t, j['elixir']))
    if len(fr) < 20:
        continue
    runs, cur = [], [fr[0]]
    for a, b in zip(fr, fr[1:]):
        if b[1] < a[1] - 1e-6 or b[1] >= 9.99:
            runs.append(cur); cur = [b]
        else:
            cur.append(b)
    runs.append(cur)
    r = max(runs, key=len)
    if len(r) < 20 or r[0][0] > 4780 or r[-1][0] < 4820:
        continue
    best = None
    t0, e0 = r[0]
    for s in range(4780, 4821):
        model = lambda t: e0 + 0.0357 * (min(t, s) - t0) + 0.0537 * max(0, t - s)
        err = sum((e - model(t)) ** 2 for t, e in r)
        if best is None or err < best[0]:
            best = (err, s)
    res[best[1]] += 1
print('live switch tick (last 2x step INTO this tick):', sorted(res.items()))
