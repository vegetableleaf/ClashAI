"""sweep9n.py PLAN.json FRAMES.jsonl ME CMD LO HI -- A2c-9N over-fit probe: the plan with command CMD run at every R in
[LO, HI] (given = R - 20), whole match each; prints R, first div, exact / div counts and the frames that are exact in the
base but div at R (worse) and the reverse (better). Base = the plan as given."""
import json, os, sys
sys.path.insert(0, os.environ.get('SME_CODE', '/workspace/pilot/sme9'))
import sme_live
from sme import run_batch
plan, frames, me, ci, lo, hi = json.load(open(sys.argv[1])), sme_live.load_frames(sys.argv[2]), int(sys.argv[3]), \
    int(sys.argv[4]), int(sys.argv[5]), int(sys.argv[6])
end = max(frames)


def at(R):
    p = json.loads(json.dumps(plan))
    if R is not None:
        p['cmds'][ci]['given'] += R - p['cmds'][ci]['run']
        p['cmds'][ci]['run'] = R
    return sme_live.runnable(p)


Rs = [None] + list(range(lo, hi + 1))
outs = run_batch([(at(R), end + 3, 0) for R in Rs], '/workspace/pilot/a2c9n/work%d' % os.getpid())
base = None
for R, o in zip(Rs, outs):
    if o is None:
        print(R, 'failed'); continue
    an = sme_live.analyse(o, frames, me)
    cls = an['cls']
    if base is None:
        base = cls
    worse = sorted(t for t in cls if base.get(t) != 'div' and cls[t] == 'div')
    better = sorted(t for t in cls if base.get(t) == 'div' and cls[t] != 'div')
    print(json.dumps({'R': R if R is not None else 'base', 'first': an['first'], 'exact': an['counts'].get('exact', 0),
                      'div': an['counts'].get('div', 0), 'worse': len(worse), 'worse_first': worse[:3],
                      'better': len(better)}), flush=True)
