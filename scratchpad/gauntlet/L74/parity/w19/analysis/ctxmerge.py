import json, glob, sys
from collections import defaultdict
g = defaultdict(lambda: defaultdict(list))
for f in glob.glob(sys.argv[1] + '/*.json'):
    for k, v in json.load(open(f)).items():
        for e, xs in v.items():
            g[k][e] += xs
rate = lambda xs: f'{sum(xs)/len(xs):.3f} ({len(xs)})' if xs else '-'
tot = {e: sum(len(v[e]) for k, v in g.items() if k.startswith('dist ')) for e in ('pre', 'L16')}
for k in sorted(g):
    v = g[k]
    print(f"{k} | {rate(v['pre'])} | {rate(v['L16'])} | {len(v['pre'])/max(1, tot['pre']):.2f} -> {len(v['L16'])/max(1, tot['L16']):.2f}")
