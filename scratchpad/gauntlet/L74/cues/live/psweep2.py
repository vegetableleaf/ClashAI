"""State-rule sweep with the edge+1500 target rule (psweep.py data)."""
import gzip, json, sys
sys.path.insert(0, '/workspace/rs0.1.35'); sys.path.insert(0, '/workspace/w_cue/cb')
import royalesim  # noqa
from pipeline.live_unit_state import load_table
C = load_table()['char']
rows = []
for p in sys.argv[1:]:
    for line in gzip.open(p, 'rt'):
        r = json.loads(line)
        if r[0] != 'err' and r[2] <= 250:
            rows.append(r)
A = [r for r in rows if r[0] <= 20 and r[1]]; B = [r for r in rows if not (r[0] <= 20 and r[1])]
ST = ('idle', 'moving', 'engaged', 'deploying', 'jumping', 'tunnelling', 'casting')
rad = lambda n: (C.get(n) or {}).get('collision_radius_milli') or 0
def edge(r):
    d = r[6]
    return None if d['td'] is None else d['td'] - rad(r[3]) - rad(d['tn'])
def kept(r):
    c, d = C.get(r[3]), r[6]
    if not d['tg']: return False
    if c is not None and not (c.get('range_milli') or c.get('sight_range_milli')): return False
    e = edge(r)
    R = max((c or {}).get('sight_range_milli') or 0, (c or {}).get('range_milli') or 0)
    return e is None or not R or e <= R + 1500
def live_state(r): return ST[r[4][1:8].index(1)] if 1 in r[4][1:8] else None
def rule(r, s2, use_prog):
    st = live_state(r)
    if r[6]['raw'] != 2: return st
    c = C.get(r[3]) or {}
    mover = c.get('kind') == 'troop' and (c.get('speed') or 0) > 0
    if not kept(r): return 'moving' if mover else 'idle'
    e = edge(r)
    if s2 is not None and mover and e is not None and e > (c.get('range_milli') or 0) + s2 and not (use_prog and r[6]['prog'] > 0):
        return 'moving'
    return 'engaged'
for nm, rs in (('A', A), ('B', B)):
    n = len(rs)
    print(nm, 'now %.4f' % (sum(live_state(r) == r[7]['st'] for r in rs) / n))
    for s2 in (None, 0, 500, 1000, 2000):
        for up in (False, True):
            print('  no-target->moving/idle, out-of-range s2=%s use_prog=%s: %.4f' % (s2, up, sum(rule(r, s2, up) == r[7]['st'] for r in rs) / n))
    print('  has_target with kept():  %.4f' % (sum(kept(r) == (r[5][10] > 0) for r in rs) / n))
