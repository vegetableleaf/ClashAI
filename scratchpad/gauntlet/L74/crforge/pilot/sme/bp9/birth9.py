"""birth9.py TRACEDIR RUNDIR M:ID,ID,... -- A2c-9R: birth tick, side, name of the given ids (first trace tick they appear) and the plan
commands run in [birth-2, birth]."""
import glob, json, sys
td, rd = sys.argv[1], sys.argv[2]
for a in sys.argv[3:]:
    m, ids = a.split(':'); ids = [int(i) for i in ids.split(',')]
    born = {}
    for l in open(glob.glob(td + '/live_play_' + m + '.o.jsonl')[0]):
        o = json.loads(l)
        for c in o['C']:
            if c[0] in ids and c[0] not in born: born[c[0]] = (o['t'], c[1], c[2])
        if len(born) == len(ids): break
    p = json.load(open(rd + '/live_play_' + m + '/plan.json'))
    print(m, born)
    ts = {b[0] for b in born.values()}
    for i, c in enumerate(p['cmds']):
        if any(t - 3 <= c.get('run', -9) <= t for t in ts): print('   cmd', i, c.get('kind'), c.get('run'), c.get('side'), c.get('card', c.get('unit')), (c.get('_src') or {}).get('source'))
