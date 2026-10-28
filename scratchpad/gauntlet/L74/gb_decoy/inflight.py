"""Every field of the two in-flight barrel rows of each evo cast: which ones differ between the real barrel and the decoy."""
import json, sys, collections
casts = [json.loads(l) for l in open('results/casts_clxiii.jsonl')]
meas = json.load(open('results/measure_out.json'))
evo = {(o['file'], o['t0']): o for o in meas if o['kind'] == 'evo'}
stat = collections.Counter()
for r in casts:
    o = evo.get((r['file'], r['t0']))
    if not o:
        continue
    lane = lambda x: 'L' if x < 0.5 else 'R'
    pr = [p for p in r['projs'] if lane(p['tgt_my'][0]) == o['real']][0]
    pd = [p for p in r['projs'] if lane(p['tgt_my'][0]) == o['decoy']][0]
    stat['real_gen_lower'] += pr['gen'] < pd['gen']
    stat['real_first_earlier'] += pr['first'] < pd['first']
    stat['same_first'] += pr['first'] == pd['first']
    stat['real_first_later'] += pr['first'] > pd['first']
    stat['real_last_later'] += pr['last'] > pd['last']
    stat['same_last'] += pr['last'] == pd['last']
    stat['n'] += 1
    print(r['file'], r['t0'], 'real', pr['gen'], pr['first'], pr['last'], pr['start'], pr['tgt'], '| decoy', pd['gen'], pd['first'], pd['last'], pd['start'], pd['tgt'])
print(dict(stat))
