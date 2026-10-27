"""Whole-match score of a run's plan with commands moved (A2c-BP2). Env as the run (bp2/env.sh; SNAP reclass as the run).
    python3 win.py RUNDIR MATCH [cmd_index:run | cmd_index:skip ...]
Prints the class counts, the first div frame and its diff, and the div episodes."""
import json, os, sys
sys.path.insert(0, '/workspace/pilot/sme')
from sme import run_batch
from sme_live import load_frames, runnable, analyse, episodes, SNAP
run, m = sys.argv[1], sys.argv[2]
me = {json.loads(l)['match']: json.loads(l)['my_side'] for l in open('/workspace/pilot/inputs_v5/inputs_rngfree.jsonl')}[m]
plan = json.load(open(os.path.join(run, m, 'plan.json')))
for a in sys.argv[3:]:
    i, r = a.split(':')
    if r == 'skip':
        plan['cmds'][int(i)]['kind'] = 'skip'
    else:
        plan['cmds'][int(i)].update(run=int(r), given=int(r) - 20)
frames = load_frames('/workspace/pilot/sme_live/frames2/%s.jsonl' % m)
wd = '/workspace/pilot/bp2/work/win_%d' % os.getpid()
o = run_batch([(runnable(plan), max(frames) + 3, 0)], wd)[0]
an = analyse(o, frames, me)
if SNAP:
    import bp_snap
    an = bp_snap.reclass(runnable(plan), frames, me, an, o, wd)
print(m, an['counts'], 'first', an['first'])
print('  diff', an['first_diff'] if an['first'] is None else analyse(o, frames, me, an['first'], an['first'])['first_diff'])
print('  episodes', episodes(an)[:12])
if os.environ.get('WIN_SHOW'):
    lo, hi = map(int, os.environ['WIN_SHOW'].split(','))
    for t in sorted(an['cls']):
        if lo <= t <= hi:
            print('   ', t, an['cls'][t], analyse(o, frames, me, t, t)['first_diff'] if an['cls'][t] != 'exact' else '')
