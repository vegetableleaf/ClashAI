import json, glob, sys
from collections import defaultdict
g = defaultdict(list)
for f in glob.glob(sys.argv[1] + '/*.json'):
    for k, v in json.load(open(f)).items():
        g[tuple(k.split('|'))] += v
cards = sorted({(k[0], k[1]) for k in g})
print('card | side | pre: n, median, >60 | post: n, median, >60')
for c in cards:
    row = []
    for era in ('pre', 'post'):
        v = sorted(g.get((c[0], c[1], era), []))
        row.append(f'{len(v)}, {v[len(v)//2]:.0f}, {sum(x > 60 for x in v)/len(v):.2f}' if len(v) >= 15 else f'{len(v)}')
    if any(',' in r for r in row):
        print(f'{c[0]} | {c[1]} | ' + ' | '.join(row))
