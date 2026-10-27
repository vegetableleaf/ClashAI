"""Inspect a live match around a tick: recorded vs simulated objects with names.
    python3 insp_live.py RUNDIR MATCH [TICK] [--span 6] [--all]
Re-runs RUNDIR/MATCH/plan.json; TICK defaults to the result's first divergence. Prints, per frame in [TICK-span, TICK],
the diff and (with --all) every non-tower object on both sides with its name."""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sme import diff, run_batch, card_name  # noqa: E402
from sme_live import load_frames, canon_live, sim_canon, runnable  # noqa: E402

run, m = sys.argv[1], sys.argv[2]
args = sys.argv[3:]
show_all = '--all' in args
span = int(args[args.index('--span') + 1]) if '--span' in args else 6
res = json.load(open(os.path.join(run, m, 'result.json')))
t0 = int(args[0]) if args and args[0].isdigit() else res['first_div']
plan = json.load(open(os.path.join(run, m, 'plan.json')))
frames = load_frames(os.path.join('/workspace/pilot/sme_live/frames', m + '.jsonl'))
me = res.get('my_side', 1 if plan['decks'][1][4] == 'Xbow' else 0)
o = run_batch([(runnable(plan), t0 + 3, max(0, t0 - span - 2))], os.path.join(run, m, 'insp'))[0]
by = {x['t']: x for x in o}
print('cmds near:', [(i, c.get('card', c.get('unit')), c['side'], c['run'], c.get('x'), c.get('y'))
                     for i, c in enumerate(plan['cmds']) if t0 - 150 <= c['run'] <= t0])
for t in range(t0 - span, t0 + 1):
    if t not in frames or t not in by:
        continue
    d = diff(canon_live(frames[t], me), sim_canon(by[t], me))
    print('t', t, 'ndiff', len(d))
    for x in d:
        print('   ', x)
    if show_all or t == t0:
        f = frames[t]
        print('   REC  E', [(e[0], e[1], e[2], card_name(e[3]) if e[3] != -1 else 'T', e[4]) for e in f['E'] if e[3] != -1])
        print('   REC  P', [(p[0], p[1], p[2], card_name(p[3]) if p[3] != -1 else 'shot') for p in f['P']])
        print('   REC  A', [(a[0], a[1], a[2], card_name(a[3])) for a in f['A']])
        print('   SIM   ', [(e[3], e[4], e[5], e[1] + ':' + e[2], e[6]) for e in by[t]['E'] if e[1] != 'T'])
