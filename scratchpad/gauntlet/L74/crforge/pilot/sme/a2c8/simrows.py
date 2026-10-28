"""crforge rows whose name contains SUB, ticks T0..T1: python3 simrows.py PLAN.json T0 T1 SUB  (env SME_LIB/SME_BUILD/SME_REPR)"""
import json, os, sys
sys.path.insert(0, '/workspace/pilot/sme')
from sme import run_batch
from sme_live import runnable
plan, t0, t1, sub = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), sys.argv[4]
o = run_batch([(runnable(json.load(open(plan))), t1 + 1, t0)], '/workspace/pilot/a2c8/work%d' % os.getpid())[0]
for s in o:
    rows = [r for k in s for r in (s[k] if isinstance(s[k], list) else []) if isinstance(r, list) and any(sub in str(c) for c in r)]
    print(s['t'], rows)
