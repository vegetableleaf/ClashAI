"""torn_mixed check details for a frame. python3 mixck.py RUN MATCH T0"""
import json, os, sys
sys.path.insert(0, '/workspace/pilot/sme')
from sme import run_batch
from sme_live import load_frames, runnable, canon_live, sim_canon
run, m, t = sys.argv[1], sys.argv[2], int(sys.argv[3])
me = {json.loads(l)['match']: json.loads(l)['my_side'] for l in open('/workspace/pilot/inputs_v5/inputs_rngfree.jsonl')}[m]
plan = json.load(open(os.path.join(run, m, 'plan.json')))
frames = load_frames('/workspace/pilot/sme_live/frames2/%s.jsonl' % m)
o = run_batch([(runnable(plan), t + 3, t - 1)], '/workspace/pilot/bp/work/mix_%d' % os.getpid())[0]
by = {s['t']: s for s in o}
r, a, b = canon_live(frames[t], me), sim_canon(by[t], me), sim_canon(by[t + 1], me)
for k in 'TUPA':
    for x in r[k]:
        if not (x in a[k] or x in b[k]):
            print('not held', k, x)
for k in r:
    if k.startswith('S'):
        print(k, r[k], a.get(k), b.get(k))
