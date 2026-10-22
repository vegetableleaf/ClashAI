"""Aggregate speeds.py: per (card, side, era) the mean live and SIM walk speed (mt/tick) over gaps where both walk, the
share of gaps where the SIM is >= 10 mt/tick faster / slower.   python spagg.py SPEEDS_JSONL [...]"""
import json, sys
from collections import defaultdict
agg = defaultdict(lambda: [0, 0, 0, 0, 0])
for f in sys.argv[1:]:
    for line in open(f):
        x = json.loads(line)
        era = 'L16' if x['match'][10:23] >= '20261019_1402' else 'pre'
        for card, own, vl, vs, n in x['rows']:
            a = agg[(card, 'own' if own else 'opp', era)]
            a[0] += n; a[1] += vl * n; a[2] += vs * n; a[3] += n * (vs - vl >= 10); a[4] += n * (vl - vs >= 10)
print('card | side | era | gaps | live mt/tick | SIM mt/tick | SIM/live | SIM faster >=10 | SIM slower >=10')
for k, a in sorted(agg.items(), key=lambda kv: -kv[1][0])[:45]:
    n = a[0]
    print(f'{k[0]} | {k[1]} | {k[2]} | {n} | {a[1]/n:.1f} | {a[2]/n:.1f} | {a[2]/a[1]:.3f} | {a[3]/n:.3f} | {a[4]/n:.3f}')
