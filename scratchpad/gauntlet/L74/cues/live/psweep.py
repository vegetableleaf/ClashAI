"""Sweeps of the live-only rules on pcollect.py output (rows with debug fields): target drop, shield-hp, engaged."""
import collections
import gzip
import json
import sys

sys.path.insert(0, '/workspace/rs0.1.35')
sys.path.insert(0, '/workspace/w_cue/cb')
import royalesim  # noqa: F401,E402
from pipeline.live_unit_state import load_table  # noqa: E402

T = load_table()
C = T['char']
rows = []
for p in sys.argv[1:]:
    for line in gzip.open(p, 'rt'):
        r = json.loads(line)
        if r[0] != 'err' and r[2] <= 250:
            rows.append(r)
A = [r for r in rows if r[0] <= 20 and r[1]]
B = [r for r in rows if not (r[0] <= 20 and r[1])]
print('rows A %d B %d' % (len(A), len(B)))


def rad(n):
    return (C.get(n) or {}).get('collision_radius_milli') or 0


def reach(n):
    c = C.get(n) or {}
    return max(c.get('sight_range_milli') or 0, c.get('range_milli') or 0)


def keep_centre(r, s):
    d = r[6]
    if not d['tg']:
        return False
    if d['td'] is None:
        return True
    R = reach(r[3])
    return not (R and d['td'] > R + s)


def keep_edge(r, s):
    d = r[6]
    if not d['tg']:
        return False
    if d['td'] is None:
        return True
    R = reach(r[3])
    return not (R and d['td'] - rad(r[3]) - rad(d['tn']) > R + s)


def keep_edge_na(r, s):     # + a table unit with no attack (no range and no sight) never holds a target
    c = C.get(r[3])
    if c is not None and not (c.get('range_milli') or c.get('sight_range_milli')):
        return False
    return keep_edge(r, s)


def score(rs, f):
    return sum(f(r) == (r[5][10] > 0) for r in rs) / max(1, len(rs))


print('\n== has_target agreement (A / B) by drop rule ==')
for s in (0, 1000, 1500, 2000, 3000, 4000):
    print('centre +%-5d %.4f / %.4f' % (s, score(A, lambda r: keep_centre(r, s)), score(B, lambda r: keep_centre(r, s))))
for s in (-500, 0, 500, 1000, 1500, 2500):
    print('edge   %+-5d %.4f / %.4f   +no-attack-drop %.4f / %.4f' % (
        s, score(A, lambda r: keep_edge(r, s)), score(B, lambda r: keep_edge(r, s)),
        score(A, lambda r: keep_edge_na(r, s)), score(B, lambda r: keep_edge_na(r, s))))
print('raw (no drop)  %.4f / %.4f' % (score(A, lambda r: r[6]['tg']), score(B, lambda r: r[6]['tg'])))
bad = collections.Counter((r[3], r[6]['tg'], r[5][10] > 0) for r in A if keep_edge_na(r, 1000) != (r[5][10] > 0))
print('A misses under edge+1000+no-attack (name, live raw tg, sim tg):', bad.most_common(12))

print('\n== shielded on shield-hp cards: live buff rule vs + (hp >= max_hp) ==')
SH = {n for n, c in C.items() if (c.get('shield_hitpoints') or 0) > 0}
for nm, rs in (('A', A), ('B', B)):
    s_rows = [r for r in rs if r[3] in SH]
    base = sum((r[4][20] > 0) == (r[5][20] > 0) for r in s_rows)
    der = sum(((r[4][20] > 0) or r[6]['hp'] >= r[6]['mhp'] > 0) == (r[5][20] > 0) for r in s_rows)
    allr = sum(((r[4][20] > 0) or (r[3] in SH and r[6]['hp'] >= r[6]['mhp'] > 0)) == (r[5][20] > 0) for r in rs)
    print('%s: shield-card rows %d: buff rule %.4f, +hp==max %.4f; all rows with the derived rule %.4f' % (
        nm, len(s_rows), base / max(1, len(s_rows)), der / max(1, len(s_rows)), allr / max(1, len(rs))))
    print('   sim hp==max on shield rows when sim shielded:', collections.Counter(
        (r[5][20] > 0, r[7]['hp'] >= r[7]['mhp']) for r in s_rows).most_common())

print('\n== state disagreements (A): (live raw, live has_target, prog>0) -> sim state ==')
ST = ('idle', 'moving', 'engaged', 'deploying', 'jumping', 'tunnelling', 'casting')
for nm, rs in (('A', A), ('B', B)):
    c = collections.Counter((r[6]['raw'], r[4][10] > 0, r[6]['prog'] > 0, r[7]['st'], C.get(r[3], {}).get('kind'))
                            for r in rs if r[4][1:8] != r[5][1:8])
    print(nm, sum(c.values()), c.most_common(14))
    # candidate: raw 2 with no target and no progress -> a troop reads 'moving' (building 'idle')
    def st_rule(r):
        raw = r[6]['raw']
        if raw == 2 and not r[4][10] and r[6]['prog'] <= 0:
            return 'moving' if C.get(r[3], {}).get('kind') == 'troop' and (C.get(r[3], {}).get('speed') or 0) > 0 else 'idle'
        return ST[r[4][1:8].index(1)] if 1 in r[4][1:8] else None
    agree0 = sum(r[4][1:8] == r[5][1:8] for r in rs) / max(1, len(rs))
    agree1 = sum(st_rule(r) == r[7]['st'] for r in rs) / max(1, len(rs))
    print('   state agreement now %.4f, with raw-2-no-target rule %.4f' % (agree0, agree1))
