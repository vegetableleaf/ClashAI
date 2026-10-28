"""A2c-9Z: why a Zap point is (in)consistent with its buff group. python -I zap_why.py LOG.jsonl C X Y [level]"""
import math, os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'extract'))
import extract, mech_rules  # noqa: E402
life, stats = extract.table_shims(extract.TABLES)
p, c, x, y = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), int(sys.argv[4])
g = next(g for g in mech_rules.zap_groups(p) if g['c'] == c)
v = 1 - g['s']
rad = lambda b: (stats(b['name']) or {}).get('collision_radius_milli') or 500  # noqa: E731
for lab, B in (('HIT', g['hits'].values()), ('PRE', [b for a, b in g['pre'].items() if b['side'] == v and a not in g['post']]),
               ('REST', [b for a, b in g['post'].items() if b['side'] == v and a not in g['hits']])):
    for b in B:
        d = math.hypot(b['x'] - x, b['y'] - y)
        print(lab, b['name'], b['x'], b['y'], b['hp'], b.get('drop'), 'dist', int(d), 'reach', 2500 + rad(b), 'COVERED' if d <= 2500 + rad(b) else '')
