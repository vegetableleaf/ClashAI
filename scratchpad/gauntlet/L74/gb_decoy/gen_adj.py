"""Evo pairs: generation key gap decoy - real, and first-seen tick gap (results/casts_clxiii.jsonl)."""
import json, collections
meas = {(o['file'], o['t0']): o for o in json.load(open('results/measure_out.json'))}
c = collections.Counter()
for l in open('results/casts_clxiii.jsonl'):
    r = json.loads(l)
    if len(r['projs']) == 2:
        a, b = sorted(r['projs'], key=lambda p: p['gen'])
        c['pairs'] += 1
        c[('gen_gap', b['gen'] - a['gen'])] += 1
        c[('first_gap', b['first'] - a['first'])] += 1
print(dict(c))
