"""Body-position onsets of a run: magnitude, side (ours / opponent) and card. python3 pos_census.py RUNDIR"""
import collections, json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from agg_live import mech  # noqa: E402

mag, cards, sides, first = collections.Counter(), collections.Counter(), collections.Counter(), collections.Counter()
for l in open(os.path.join(sys.argv[1], 'results.jsonl')):
    r = json.loads(l)
    me = None
    for k, e in enumerate(r.get('episodes', [])):
        if e['detail'] is None or mech(e['detail'], False) != 'body position (movement / collision / targeting)':
            continue
        body = [x for x in e['detail'] if x[0][0] in 'TU' and isinstance(x[3], list)]
        m = max(abs(x[3][0]) + abs(x[3][1]) for x in body)
        b = '<=10' if m <= 10 else '<=100' if m <= 100 else '<=500' if m <= 500 else '>500'
        mag[b] += 1
        if k == 0:
            first[b] += 1
        x = max(body, key=lambda x: abs(x[3][0]) + abs(x[3][1]))
        cards[str(x[2]).split(':')[-1]] += 1
        sides[x[1][0]] += 1
print('largest |dx|+|dy| per onset:', dict(mag), 'as first true divergence:', dict(first))
print('side of the most-moved body:', dict(sides))
print('cards:', cards.most_common(15))
