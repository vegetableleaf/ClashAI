import json, sys
from collections import Counter, defaultdict
c = defaultdict(Counter)
for f in sys.argv[1:]:
    for e in json.load(open(f)):
        tx, ty = e['tap']
        ly = ty if e['side'] == 0 else 32000 - ty
        if not 3000 <= ly < 14000:
            continue
        o = [((x - tx), (y - ty) * (1 if e['side'] == 0 else -1)) for x, y in e['live']]
        mid = min(o, key=lambda p: abs(p[0]))
        sides = sorted(p[0] for p in o if p is not mid)
        shape = 'SYM' if abs(sides[0] + sides[1]) <= 30 else 'shift'
        c[e['match'][10:21]][shape] += 1
for k in sorted(c):
    print(k, dict(c[k]))
