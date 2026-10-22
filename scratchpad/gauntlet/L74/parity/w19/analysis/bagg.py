"""Aggregate births.py: per card (side) the birth tick SIM - live of paired new bodies, live-only / SIM-only bodies.
  python bagg.py BIRTHS_JSONL [...]"""
import json, sys
from collections import Counter, defaultdict
dt = defaultdict(Counter); only = defaultdict(Counter)
for f in sys.argv[1:]:
    for line in open(f):
        x = json.loads(line)
        for card, own, d, o, anchor, n in x['rows']:
            k = ('own ' if own else 'opp ') + card
            if d is None:
                only[k][o] += n
            else:
                dt[k][d] += n
rows = []
for k in set(dt) | set(only):
    c = dt[k]; n = sum(c.values())
    off = sum(v for d, v in c.items() if abs(d) > 2)
    rows.append((off + only[k]['L'] + only[k]['S'], k, n, off, only[k]['L'], only[k]['S'], c))
rows.sort(reverse=True)
print('card | paired births | |SIM-live| > 2 ticks | live only | SIM only | top SIM-live offsets')
for bad, k, n, off, lo, so, c in rows[:40]:
    print(f'{k} | {n} | {off} | {lo} | {so} | {[x for x in c.most_common(6)]}')
