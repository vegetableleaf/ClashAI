"""crforge rows whose name contains SUB, ticks T0..T1, with optional command re-dating:
python3 simk.py PLAN.json T0 T1 SUB [OLDRUN:NEWRUN ...]   (env SME_LIB/SME_BUILD/SME_REPR; sme8 code)
A command whose run is OLDRUN gets run NEWRUN and given NEWRUN-20 (the plan's lag)."""
import json, os, sys
sys.path.insert(0, os.environ.get('SME_CODE', '/workspace/pilot/sme8'))
from sme import run_batch
from sme_live import runnable
plan, t0, t1, sub = json.load(open(sys.argv[1])), int(sys.argv[2]), int(sys.argv[3]), sys.argv[4]
for a in sys.argv[5:]:
    o, n = map(int, a.split(':'))
    for c in plan['cmds']:
        if c['run'] == o:
            c['given'] += n - o
            c['run'] = n
print('keys', end=' ')
out = run_batch([(runnable(plan), t1 + 1, t0)], '/workspace/pilot/a2c9/work%d' % os.getpid())[0]
print(sorted(out[0].keys()))
for s in out:
    rows = [(k, r) for k in s for r in (s[k] if isinstance(s[k], list) else []) if isinstance(r, list) and any(sub in str(c) for c in r)]
    print(s['t'], s.get('E0', ''), rows)
