"""ENG-FIX: run a plan once (runH/envF env) and print the sim's U / T / P rows near a point over [LO, HI].
    python3 diag_near.py PLAN.json TICKS LO HI X Y R"""
import json, math, os, sys
sys.path.insert(0, os.environ.get('SME_CODE', '/workspace/pilot/f1fix/sme11f'))
import sme_live  # noqa: E402
from sme import run_batch  # noqa: E402
plan, ticks, lo, hi, X, Y, R = sys.argv[1], *map(int, sys.argv[2:8])
o = run_batch([(sme_live.runnable(json.load(open(plan))), ticks, 0)], '/tmp/diagN_%d' % os.getpid())[0]
for x in o:
    if lo <= x['t'] <= hi:
        print(x['t'], [k for k in x if k != 't'])
        for k in x:
            if isinstance(x[k], list):
                for u in x[k]:
                    s = json.dumps(u)
                    xy = [v for v in (u if isinstance(u, list) else u.values()) if isinstance(v, int)]
                    if any(math.hypot(a - X, b - Y) <= R for a, b in zip(xy, xy[1:])):
                        print('  ', k, s[:300])
