import json, sys
from collections import Counter
c = Counter(); ex = Counter()
for f in sys.argv[1:]:
    for e in json.load(open(f)):
        if e['match'][10:23] < '20261019_1356':
            continue
        tx, ty = e['tap']
        ly = ty if e['side'] == 0 else 32000 - ty
        if not 3000 <= ly < 14000:
            continue
        o = [((x - tx), (y - ty) * (1 if e['side'] == 0 else -1)) for x, y in e['live']]
        mid = min(o, key=lambda p: abs(p[0]))
        sides = sorted(p[0] for p in o if p is not mid)
        s = sides[0] + sides[1]
        shape = 'SYM' if abs(s) <= 30 else ('shift+' if s > 0 else 'shift-')
        so = [((x - tx), (y - ty) * (1 if e['side'] == 0 else -1)) for x, y in e['sim']]
        smid = min(so, key=lambda p: abs(p[0])); ss = sorted(p[0] for p in so if p is not smid)
        sshape = 'SYM' if abs(ss[0] + ss[1]) <= 30 else ('shift+' if ss[0] + ss[1] > 0 else 'shift-')
        c[(e['side'], 'own-left' if (tx < 9000) == (e['side'] == 0) else 'own-right', shape, 'sim ' + sshape)] += 1
        ex[(shape, tuple(sorted((round(a), round(b)) for a, b in o)))] += 1
for k, v in sorted(c.items()):
    print(k, v)
print([x for x in ex.most_common(8)])
