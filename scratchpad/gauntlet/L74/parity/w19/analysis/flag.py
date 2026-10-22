import json, sys, math
from collections import Counter, defaultdict
c = Counter(); err = defaultdict(list)
for f in sys.argv[1:]:
    for e in json.load(open(f)):
        tx, ty = e['tap']
        ly = ty if e['side'] == 0 else 32000 - ty
        zone = 'back' if ly < 3000 else 'river' if ly >= 14000 else 'mid'
        lags = [x for x in e.get('seen_lag') or [] if x is not None]
        lag = max(lags) if lags else None
        o = [((x - tx), (y - ty) * (1 if e['side'] == 0 else -1)) for x, y in e['live']]
        mid = min(o, key=lambda p: abs(p[0]))
        sides = sorted(p[0] for p in o if p is not mid)
        shape = 'SYM' if abs(sides[0] + sides[1]) <= 30 else 'shift'
        lb = 'lag?' if lag is None else 'lag<=1' if lag <= 1 else 'lag2-3' if lag <= 3 else 'lag4+'
        c[(zone, lb, shape)] += 1
        e_ = max(math.hypot(a[0] - b[0], a[1] - b[1]) for a, b in zip(e['live'], e['sim']))
        err[(zone, lb)].append(e_)
for k, v in sorted(c.items()):
    print(k, v)
for k, v in sorted(err.items()):
    v.sort(); print('max member error', k, 'n', len(v), 'median', round(v[len(v)//2]), 'share>30', round(sum(x > 30 for x in v) / len(v), 3))
