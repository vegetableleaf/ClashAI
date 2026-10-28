"""The replay set: every evo cast's match, plus whole no-evo matches (shuffled, seed 0) until >= 100 plain casts."""
import json, random, collections
meas = json.load(open('results/measure_out.json'))
evo_files = sorted({o['file'] for o in meas if o['kind'] == 'evo'})
by = collections.defaultdict(list)
for o in meas:
    by[o['file']].append(o)
others = sorted(f for f in by if f not in evo_files)
random.Random(0).shuffle(others)
plain_files, n = [], 0
for f in others:
    if n >= 100:
        break
    plain_files.append(f)
    n += sum(o['kind'] == 'plain' for o in by[f])
win = {f: [dict(kind=o['kind'], t0=o['t0'], tland=o['tland'], real=o['real'], decoy=o['decoy']) for o in by[f]]
       for f in evo_files + plain_files}
json.dump(win, open('replay/windows.json', 'w'), indent=0)
print('evo files', len(evo_files), 'plain files', len(plain_files), 'plain casts there', n,
      'plain casts in evo files', sum(o['kind'] == 'plain' for f in evo_files for o in by[f]))
