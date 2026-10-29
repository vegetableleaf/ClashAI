"""OPP-SIEGE2 task 1a: lock rate of on-time answers by their offset from the HUMAN spot (live median dx, dy per card;
dx lane-mirrored toward the centre, dy toward the opponent; tiles from the X-Bow), live vs SIM sources.
python place_off.py SRC [SRC ...]   (out/siege_b_<SRC>.json; live is always included)"""
import json, math, sys, statistics as st
from collections import defaultdict

BINS = ((0, 1.5), (1.5, 3), (3, 99))


def on(rs):
    for r in rs:
        if r['cls'] == 'answer_ontime' and r['kind'] != 'spell':
            yield r, (r['ax'] - r['xx']) * (1 if r['xx'] < 9 else -1), r['ay'] - r['xy']


src = {n: json.load(open(f'out/siege_b_{n}.json'))['xbows'] for n in ['live'] + sys.argv[1:]}
by = defaultdict(list)
for r, dx, dy in on(src['live']):
    by[r['card']].append((dx, dy))
spot = {c: (st.median(a for a, _ in v), st.median(b for _, b in v)) for c, v in by.items() if len(v) >= 20}
print('human spots (live median dx, dy; n):', {c: (*spot[c], len(by[c])) for c in sorted(spot, key=lambda c: -len(by[c]))})
fmt = lambda s: f"{sum(s)/len(s):.2f} n{len(s)}" if s else '-'
for n, rs in src.items():
    pool = defaultdict(list)
    per = defaultdict(lambda: defaultdict(list))
    for r, dx, dy in on(rs):
        if r['card'] not in spot:
            continue
        d = math.hypot(dx - spot[r['card']][0], dy - spot[r['card']][1])
        b = next(i for i, (lo, hi) in enumerate(BINS) if lo <= d < hi)
        pool[b].append(r['locked'])
        per[r['card']][b].append(r['locked'])
    print(f"{n:8s} pooled lock by offset 0-1.5 / 1.5-3 / >3 tiles: " + ' | '.join(fmt(pool[b]) for b in range(3)))
    for c in sorted(spot, key=lambda c: -len(by[c]))[:8]:
        print(f"   {c:14s} " + ' | '.join(fmt(per[c][b]) for b in range(3)))
