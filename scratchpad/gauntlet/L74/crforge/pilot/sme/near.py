"""A2c-M: recorded rows vs crforge rows near a point, tick by tick.
python3 near.py PLAN.json FRAMES.jsonl T0 T1 X Y R [P|A|C|T ...]   (sim rows: [id,cls,name,side,x,y,hp,max,src,ax,ay,...])"""
import json, os, sys
sys.path.insert(0, '/workspace/pilot/sme')
from sme import run_batch
from sme_live import load_frames, runnable

plan_p, fr_p = sys.argv[1], sys.argv[2]
t0, t1, X, Y, R = map(int, sys.argv[3:8])
cls = set(sys.argv[8:]) or set('PACT')
fr = load_frames(fr_p)
o = {s['t']: s for s in run_batch([(runnable(json.load(open(plan_p))), t1 + 1, t0)], '/workspace/mech/work/near%d' % os.getpid())[0]}
near = lambda x, y: abs(x - X) + abs(y - Y) <= R  # noqa: E731
for t in range(t0, t1 + 1):
    if t in fr:
        f = fr[t]
        rows = [('E', e) for e in f['E'] if near(e[1], e[2])] + [('P', p) for p in f['P'] if near(p[1], p[2])] + \
               [('A', a) for a in f['A'] if near(a[1], a[2])]
        print('rec %d el=%s' % (t, f['el']), rows)
    if t in o:
        print('sim %d' % t, [e[:11] + e[12:13] for e in o[t]['E'] if e[1] in cls and near(e[4], e[5])])
