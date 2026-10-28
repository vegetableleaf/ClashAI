"""python3 cmp1.py PLAN.json FRAMES.jsonl SIDE T S0 [S1 ..]  -- frame T against sim lines S0, S1.. (full diff)"""
import json, os, sys
sys.path.insert(0, os.environ.get('SME_CODE', '/workspace/pilot/sme8'))
import sme_live
from sme import run_batch, diff
plan, frames, me, t = json.load(open(sys.argv[1])), sme_live.load_frames(sys.argv[2]), int(sys.argv[3]), int(sys.argv[4])
ss = [int(x) for x in sys.argv[5:]]
o = {x['t']: x for x in run_batch([(sme_live.runnable(plan), max(ss) + 1, min(ss))], '/workspace/pilot/a2c9/work%d' % os.getpid())[0]}
for s in ss:
    r, c = sme_live.canon_live(frames[t], me), sme_live.sim_canon(o[s], me)
    if sme_live.HP_PH:
        r = sme_live.fill_placeholder(r, c)
    print('frame', t, 'vs sim', s, json.dumps(diff(r, c)))
