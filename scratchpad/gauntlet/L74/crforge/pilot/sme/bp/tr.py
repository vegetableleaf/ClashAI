"""Tick-by-tick trace, reader vs crforge, of the objects near a point (A2c-BP2). Env as the run (bp2/env.sh).
    python3 tr.py RUNDIR MATCH LO HI X Y RADIUS [cmd_index:run ...]
Prints the plan's commands in [LO-60, HI], then per tick the sim rows (cls name side x y hp) within RADIUS of (X, Y)
and our elixir, and on recorded ticks the reader rows (U/T side x y card hp, P, A) and our elixir. Our side only."""
import json, math, os, sys
sys.path.insert(0, '/workspace/pilot/sme')
from sme import run_batch
from sme_live import load_frames, runnable, repr_rows
run, m, lo, hi, X, Y, R = sys.argv[1], sys.argv[2], *map(int, sys.argv[3:8])
me = {json.loads(l)['match']: json.loads(l)['my_side'] for l in open('/workspace/pilot/inputs_v5/inputs_rngfree.jsonl')}[m]
plan = json.load(open(os.path.join(run, m, 'plan.json')))
for a in sys.argv[8:]:
    i, r = map(int, a.split(':'))
    plan['cmds'][i].update(run=r, given=r - 20)
    print('cmd', i, '->', {k: v for k, v in plan['cmds'][i].items() if k != '_src'})
frames = load_frames('/workspace/pilot/sme_live/frames2/%s.jsonl' % m)
for i, c in enumerate(plan['cmds']):
    if lo - 60 <= c['run'] <= hi:
        print('cmd%d' % i, {k: v for k, v in c.items() if k not in ('_src',)})
o = run_batch([(runnable(plan), hi + 2, lo)], '/workspace/pilot/bp2/work/tr_%d' % os.getpid())[0]
near = lambda x, y: math.hypot(x - X, y - Y) <= R  # noqa: E731
for s in o:
    t = s['t']
    if t > hi:
        break
    rows = sorted((e[1], e[2], e[3], e[4], e[5], e[6]) for e in repr_rows(s) if near(e[4], e[5]))
    print('%5d sim el=%d' % (t, s['S'][me][0]), ' '.join('%s:%s/%d(%d,%d)%d' % r for r in rows))
    if t in frames:
        f = frames[t]
        rr = sorted([('U', e[0], e[1], e[2], e[3], e[4]) for e in f['E'] if near(e[1], e[2])] +
                    [('P', e[0], e[1], e[2], e[3], '') for e in f['P'] if near(e[1], e[2])] +
                    [('A', e[0], e[1], e[2], e[3], '') for e in f['A'] if near(e[1], e[2])])
        print('%5d REC el=%d' % (t, f['el']), ' '.join('%s/%d(%d,%d)c%s:%s' % r for r in rr))
