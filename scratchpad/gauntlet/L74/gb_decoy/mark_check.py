"""barrel_decoy.decoy_indices on every recorded cast's barrel rows (as the reader lists them): evo pairs marked with
the decoy = the landing-labelled decoy (GoblinDummy); plain casts never marked."""
import json, sys, collections
sys.path.insert(0, r'C:\Users\benpe\ClashBot')
from pipeline.barrel_decoy import decoy_indices
meas = {(o['file'], o['t0']): o for o in json.load(open('results/measure_out.json'))}
c = collections.Counter()
for l in open('results/casts_clxiii.jsonl'):
    r = json.loads(l)
    o = meas.get((r['file'], r['t0']))
    if not o:
        continue
    rows = [dict(side=1, card_id=28000004, x=0, y=0, target_x=p['tgt'][0], target_y=p['tgt'][1], generation_key=p['gen'])
            for p in r['projs']]
    got = decoy_indices(rows)
    if o['kind'] == 'plain':
        c['plain_marked'] += bool(got)
    else:
        lane = lambda x: 'L' if x < 0.5 else 'R'
        d = [lane(r['projs'][i]['tgt_my'][0]) for i in got]
        c['evo'] += 1
        c['evo_marked_decoy_correct'] += d == [o['decoy']]
print(dict(c))
