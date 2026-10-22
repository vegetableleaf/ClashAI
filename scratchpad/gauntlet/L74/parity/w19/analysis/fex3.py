import json, sys
from collections import Counter
ex = json.load(open(sys.argv[1]))
c = Counter()
for e in ex:
    tx, ty = e['tap']
    if not ((e['side'] == 1 and ty == 17500) or (e['side'] == 0 and ty == 14500)):
        continue
    lo = [(x - tx, y - ty) for x, y in e['live']]
    mid = [p for p in lo if abs(p[0]) < 200]
    clamp = 'CLAMP' if mid and abs(mid[0][1]) < 200 else 'free'
    queued = 'queued' if (e.get('elixir') or 0) < 1 else 'elixir ok'
    lag = e['first'] - e['tick']
    c[(clamp, queued, 'lag<=25' if lag <= 25 else 'lag>25', round(e['xy'][1], 4))] += 1
for k, v in sorted(c.items(), key=lambda kv: (kv[0][3], kv[0][0])):
    print(v, k)
