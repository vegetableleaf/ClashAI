"""python3 chk.py PLAN.json FRAMES.jsonl SIDE [T0 T1]  -- sme_live.analyse on a plan; div runs + details in T0..T1"""
import json, os, sys
sys.path.insert(0, os.environ.get('SME_CODE', '/workspace/pilot/sme8'))
import sme_live
from sme import run_batch
plan, frames, side = json.load(open(sys.argv[1])), sme_live.load_frames(sys.argv[2]), int(sys.argv[3])
t0, t1 = (int(sys.argv[4]), int(sys.argv[5])) if len(sys.argv) > 5 else (0, 0)
o = run_batch([(sme_live.runnable(plan), max(frames) + 3, 0)], '/workspace/pilot/a2c10/work%d' % os.getpid())[0]
an = sme_live.analyse(o, frames, side)
by = {x['t']: x for x in o}
print(json.dumps({k: an[k] for k in ('frames', 'counts', 'first')}))
div = sorted(t for t, c in an['cls'].items() if c == 'div')
runs, s = [], None
for a, b in zip(div, div[1:] + [None]):
    s = a if s is None else s
    if b is None or any(t in frames and t not in div for t in range(a + 1, b)):
        runs.append((s, a)); s = None
print('div runs', runs[:30])
for t in div:
    if t0 <= t <= t1:
        print(t, json.dumps(sme_live.describe_first(by, frames, side, t))[:600])
