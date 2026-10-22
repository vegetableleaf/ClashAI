import json, sys, math
from collections import Counter
ex = json.load(open(sys.argv[1]))
c = Counter()
rows = []
for e in ex:
    tx, ty = e['tap']
    lo = [(round(x - tx), round(y - ty)) for x, y in e['live']]
    so = [(round(x - tx), round(y - ty)) for x, y in e['sim']]
    err = max(math.hypot(a[0]-b[0], a[1]-b[1]) for a, b in zip(lo, so))
    rows.append((err, e['side'], (tx, ty), sorted(lo), sorted(so)))
rows.sort(key=lambda r: -r[0])
for r in rows[:25]:
    print(round(r[0]), 'side', r[1], 'tap', r[2], 'live', r[3], 'sim', r[4])
print('--- small error examples')
for r in rows[-5:]:
    print(round(r[0]), 'side', r[1], 'tap', r[2], 'live', r[3], 'sim', r[4])
