"""Why a frame is not a step read (round 4.1 debugging): python3 step_why.py RUNDIR LIST  (run env)"""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sme import run_batch  # noqa: E402
from sme_live import load_frames, runnable, step_read  # noqa: E402
ME = {json.loads(l)['match']: json.loads(l)['my_side'] for l in open('/workspace/pilot/inputs_v2/inputs_rngfree.jsonl')}
run, lst = sys.argv[1:3]
for line in open(lst):
    m, t0 = line.split()[:2]
    t0 = int(t0)
    plan = json.load(open(os.path.join(run, m, 'plan.json')))
    f = load_frames(os.path.join('/workspace/pilot/sme_live/frames2', m + '.jsonl'))[t0]
    o = run_batch([(runnable(plan), t0 + 4, max(0, t0 - 3))], os.path.join(run, m, 'steptest'))[0]
    by = {s['t']: s for s in o}
    why = []
    print(m[10:], t0, step_read(f, by[t0], by[t0 + 1], ME[m], why), why, flush=True)
