import json, sys
from collections import Counter, defaultdict
c = defaultdict(Counter)
for f in sys.argv[1:]:
    for e in json.load(open(f)):
        if e['match'][10:23] < '20261019_1356':
            continue
        tx, ty = e['tap']
        ly = ty if e['side'] == 0 else 32000 - ty
        if not 3000 <= ly < 14000:
            continue
        ox = tx if e['side'] == 0 else 18000 - tx
        o = [((x - tx), (y - ty) * (1 if e['side'] == 0 else -1)) for x, y in e['live']]
        mid = min(o, key=lambda p: abs(p[0]))
        sides = sorted(p[0] for p in o if p is not mid)
        s = sides[0] + sides[1]
        shape = 'SYM' if abs(s) <= 30 else ('S+' if s > 0 else 'S-')
        c[('ownx', ox)][shape] += 1
        c[('owny', ly)][shape] += 1
        c[('tickpar', e['tick'] % 2)][shape] += 1
        c[('xyx', round(e['xy'][0], 4))][shape] += 1
for k in sorted(c):
    print(k, dict(c[k]))
