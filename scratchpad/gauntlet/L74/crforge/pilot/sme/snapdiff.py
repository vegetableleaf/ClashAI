"""A2c-M: diff of recorded frame t against crforge's line t, each in-step state of step t+1 (SnapRun / SnapRun2 per
env SME_SNAP_*), and line t+1.  python3 snapdiff.py PLAN.json FRAMES.jsonl ME T"""
import json, sys
sys.path.insert(0, '/workspace/pilot/sme')
import bp_snap
from sme import run_batch, diff
from sme_live import load_frames, runnable, canon_live, sim_canon, fill_placeholder, HP_PH

plan_p, fr_p, me, t = sys.argv[1], sys.argv[2], int(sys.argv[3]), int(sys.argv[4])
plan = runnable(json.load(open(plan_p)))
f = load_frames(fr_p)[t]
o = {s['t']: s for s in run_batch([(plan, t + 3, t - 1)], '/workspace/mech/work/sd')[0]}
states = [('line t', o[t])] + [('%s#%d' % (s['ev'], s['k']), s) for s in bp_snap.snapshots(plan, [t + 1], t + 3, '/workspace/mech/work/sd')[t + 1]] + [('line t+1', o[t + 1])]
for name, s in states:
    sc = sim_canon(s, me)
    rc = canon_live(f, me)
    if HP_PH:
        rc = fill_placeholder(rc, sc)
    d = diff(rc, sc)
    print('%-18s el=%s %d diffs' % (name, s['S'][me][0], len(d)), d[:6])
print('rec el', f['el'])
