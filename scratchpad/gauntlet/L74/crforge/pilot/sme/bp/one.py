"""Why is frame t0 div? Diff vs sim t0 / t0+1 and step_read's reason. Env as the run (SME_TORN_STEP etc.).
    python3 one.py RUNDIR MATCH T0"""
import json, os, sys
sys.path.insert(0, '/workspace/pilot/sme')
from sme import run_batch, diff
from sme_live import load_frames, runnable, canon_live, sim_canon, fill_placeholder, step_read, HP_PH
run, m, t0 = sys.argv[1], sys.argv[2], int(sys.argv[3])
me = {json.loads(l)['match']: json.loads(l)['my_side'] for l in open('/workspace/pilot/inputs_v5/inputs_rngfree.jsonl')}[m]
plan = json.load(open(os.path.join(run, m, 'plan.json')))
frames = load_frames('/workspace/pilot/sme_live/frames2/%s.jsonl' % m)
o = run_batch([(runnable(plan), t0 + 4, t0 - 2)], '/workspace/pilot/bp/work/one_%d' % os.getpid())[0]
by = {s['t']: s for s in o}
for k in (0, 1, 2):
    r = canon_live(frames[t0], me)
    s = sim_canon(by[t0 + k], me)
    if HP_PH:
        r = fill_placeholder(r, s)
    d = diff(r, s)
    print('vs sim t0+%d: %d diffs' % (k, len(d)))
    for x in d[:14]:
        print('   ', x)
why = []
print('step_read', step_read(frames[t0], by[t0], by[t0 + 1], me, why), why)
ts = sorted(frames)
i = ts.index(t0)
print('neighbour frames', ts[i - 2:i + 3])
