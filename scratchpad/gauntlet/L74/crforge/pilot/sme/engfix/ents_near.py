"""ENG-FIX: reader rows (ents with phase-2 name, proj, fx) within R units of a point over a tick range.
    python -I ents_near.py LOG LO HI X Y R"""
import json, math, sys
path, lo, hi, X, Y, R = sys.argv[1], *map(int, sys.argv[2:7])
for line in open(path, 'rb'):
    if b'"frame"' not in line[:40]:
        continue
    d = json.loads(line)
    t = d['tick']
    if t is None or not lo <= t <= hi:
        continue
    nm = {u.get('address'): (u.get('name'), [b.get('name') for b in u.get('buffs') or [] if isinstance(b, dict)]) for u in (d.get('phase2') or {}).get('units', [])}
    print(t, 'el', d.get('elixir'))
    for e in d['ents']:
        if math.hypot(e[1] - X, e[2] - Y) <= R:
            print('  E', e[:7], nm.get(e[7]))
    for p in d['proj']:
        if math.hypot(p[1] - X, p[2] - Y) <= R or (p[4] is not None and math.hypot(p[4] - X, p[5] - Y) <= R):
            print('  P', p[:6], p[8:])
    for a in d['fx']:
        if math.hypot(a[1] - X, a[2] - Y) <= R:
            print('  A', a[:6])
