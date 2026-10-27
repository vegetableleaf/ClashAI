"""River crossings by ground bodies (reader generation crossing y = 16000 near a bridge, |x - 3500| or |x - 14500| <= 1500)
in clean stretches: per match, crossings before the first divergence of a run (or all, for an exact match).
python3 crossings.py RUNDIR"""
import json, os, sys
res = {json.loads(l)['match']: json.loads(l) for l in open(os.path.join(sys.argv[1], 'results.jsonl'))}
flags = {json.loads(l)['match']: json.loads(l)['flags'] for l in open('/workspace/pilot/inputs/inputs_rngfree.jsonl')}
tot = clean = 0
for m, r in res.items():
    if 'error' in r or flags.get(m):
        continue
    fd = r.get('first_div') or 10 ** 9
    last = {}
    for l in open('/workspace/pilot/bp/rdet/%s.jsonl' % m):
        f = json.loads(l)
        for g in f['G']:
            if g[3] == -1 or g[5] is None:
                continue
            gen, y, x = g[5], g[2], g[1]
            if gen in last and (last[gen][1] - 16000) * (y - 16000) < 0 and min(abs(x - 3500), abs(x - 14500)) <= 1500:
                tot += 1
                clean += f['t'] < fd
            last[gen] = (x, y)
print('bridge crossings (unflagged matches):', tot, '| before the first divergence:', clean)
