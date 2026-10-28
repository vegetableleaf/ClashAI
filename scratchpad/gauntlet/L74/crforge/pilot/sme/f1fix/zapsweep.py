"""SME-F1FIX (pod): 000420's fitted plan with one opponent Zap added at (X, Y) for each run tick R in [R0, R1]; per R the
whole-match sme_live.analyse counts and first div (R = none: the plan as fitted). Source the runF env first (envF.sh).
    python3 zapsweep.py PLAN.json FRAMES.jsonl SIDE X Y R0 R1 LEVEL"""
import copy, json, os, sys
sys.path.insert(0, os.environ['SME_CODE'])
import sme_live
from sme import run_batch
plan, frames, me = json.load(open(sys.argv[1])), sme_live.load_frames(sys.argv[2]), int(sys.argv[3])
x, y, r0, r1, lv = map(int, sys.argv[4:9])
jobs, labels = [], []
for R in [None] + list(range(r0, r1 + 1)):
    p = copy.deepcopy(plan)
    if R is not None:
        p['cmds'].append({'kind': 'play', 'given': R - 20, 'run': R, 'side': 1 - me, 'card': 'Zap', 'level': lv, 'x': x, 'y': y,
                          '_src': {'lo': R, 'hi': R, 'tick': R, 'source': 'f1fix_probe', 'own': False}})
    jobs.append((sme_live.runnable(p), max(frames) + 3, 0)); labels.append(R)
outs = run_batch(jobs, '/workspace/pilot/f1fix/work%d' % os.getpid())
for R, o in zip(labels, outs):
    an = sme_live.analyse(o, frames, me)
    late = sum(1 for t, c in an['cls'].items() if c == 'div' and t >= 3519)
    print('R', R, 'first', an['first'], 'counts', an['counts'], 'div at >= 3519:', late)
