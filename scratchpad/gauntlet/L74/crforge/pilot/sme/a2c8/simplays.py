"""crforge play/ability outcomes in T0..T1 plus plan cmds there: python3 simplays.py PLAN.json T0 T1"""
import json, os, sys
sys.path.insert(0, '/workspace/pilot/sme')
from sme import run_batch
from sme_live import runnable
plan, t0, t1 = json.load(open(sys.argv[1])), int(sys.argv[2]), int(sys.argv[3])
print([{k: c.get(k) for k in ('kind', 'card', 'side', 'run', 'given', 'deck_index')} for c in plan['cmds'] if t0 <= c['run'] <= t1])
o = run_batch([(runnable(plan), t1 + 1, t0)], '/workspace/pilot/a2c8/workp%d' % os.getpid())[0]
for s in o:
    if s.get('plays'):
        print(s['t'], s['plays'])
    print(s['t'], 'S', s['S'])  if s['t'] in (t0, t1) else None
