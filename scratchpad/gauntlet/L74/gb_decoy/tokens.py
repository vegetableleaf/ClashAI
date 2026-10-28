"""At each played decision during an evo cast's flight: how many enemy goblin-barrel (card 42) tokens the model saw, and
are they identical apart from their mirrored x / target x?"""
import json, collections
casts = [json.loads(l) for l in open('results/casts_clxiii.jsonl')]
meas = {(o['file'], o['t0']): o for o in json.load(open('results/measure_out.json'))}
c = collections.Counter()
ex = None
for r in casts:
    o = meas.get((r['file'], r['t0']))
    if not o or o['kind'] not in ('evo', 'plain'):
        continue
    for d in r['resp']:
        if d['ev'] != 'decision' or d['tick'] > o['tland']:
            continue
        gb = [t for t in d['mp'] if int(t[0]) == 42 and t[1] == 1.0]
        c[o['kind'], len(gb)] += 1
        if o['kind'] == 'evo' and len(gb) == 2:
            a, b = gb
            same = abs(a[4] + b[4] - 1) < 1e-3 and abs(a[5] - b[5]) < 1e-6 and abs(a[3] - b[3]) < 1e-3 and abs(a[6] - b[6]) < 0.02 and a[7] == b[7]
            c['evo_pair_mirror_only'] += same
            ex = ex or (a, b)
print(dict(c)); print('example', ex)
