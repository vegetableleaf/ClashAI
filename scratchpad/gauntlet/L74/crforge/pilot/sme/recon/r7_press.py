"""RECON-7 (pod): does an ability press dated EARLIER than the generator's window heal a position-only record?
  python3 recon/r7_press.py PLAN.json FRAMES/MATCH.jsonl ME SIDE CARD D [--lo 45] [--hi 0]
Adds one ability press of SIDE's latest CARD play (unit 0,1,2) at every R in [D - lo, D - hi) to the plan, runs all variants on crforge, and prints per variant
the first divergence and the exact-frame count (sme_live.analyse).  Env: envR.sh."""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE); sys.path.insert(0, os.path.dirname(HERE))
import recon, sme_live  # noqa: E402
from sme import run_batch  # noqa: E402

a = sys.argv[1:]
plan = json.load(open(a[0])); frames = sme_live.load_frames(a[1])
me, side, card, d = int(a[2]), int(a[3]), a[4], int(a[5])
lo = int(a[a.index('--lo') + 1]) if '--lo' in a else 45
hi = int(a[a.index('--hi') + 1]) if '--hi' in a else 0
late = a[a.index('--late') + 1] if '--late' in a else None
end = max(frames)
plays = [i for i, c in enumerate(plan['cmds']) if c['kind'] == 'play' and c['card'] == card and c['side'] == side and c['run'] < d]
i = plays[-1]
vars_, jobs = [], []
base = recon.runnable(plan)
for R in range(d - lo, d - hi):
    for u in (0, 1, 2):
        c = {'kind': 'ability', 'given': R - 20, 'run': R, 'side': side, 'unit': 'cmd%d_%d' % (i, u),
             '_src': {'lo': R, 'hi': R, 'tick': R, 'source': 'recon_add', 'own': side == me}}
        if late:
            if u:
                continue
            c = {'kind': 'ability', 'given': R - 20, 'run': R, 'side': side, 'late_unit': late, 'card': card, '_src': c['_src']}
        p = recon.apply_edit(plan, {'op': 'add', 'pos': next(iter(recon.add_positions(plan, R))), 'cmd': c})
        if p is not None:
            vars_.append((R, u)); jobs.append((recon.runnable(p), end + 3, 0))
outs = run_batch(jobs, os.environ.get('R7_WORK', '/tmp/r7press_%d' % os.getpid()))
o0 = run_batch([(base, end + 3, 0)], os.environ.get('R7_WORK', '/tmp/r7press_%d' % os.getpid()) + 'b')[0]
an0 = sme_live.analyse(o0, frames, me)
print('base: first', an0['first'], 'counts', an0['counts'])
res = []
for (R, u), o in zip(vars_, outs):
    if o is None:
        continue
    an = sme_live.analyse(o, frames, me)
    res.append((an['first'] if an['first'] is not None else 10 ** 9, an['counts'].get('exact', 0), R, u, an['counts']))
res.sort(reverse=True)
for r in res[:8]:
    print('press R', r[2], 'unit', r[3], 'first_div', r[0], 'counts', r[4])
