"""Positions of chosen sim bodies at every in-step point of step T (SnapRun2; A2c-BP2). Env as the run (bp2/env.sh).
    python3 instep.py RUNDIR MATCH T ID[,ID...]
Prints a line per in-step state where any chosen body's (x, y, hp) changed."""
import json, os, sys
sys.path.insert(0, '/workspace/pilot/sme')
import bp_snap
from sme_live import runnable
run, m, T, ids = sys.argv[1], sys.argv[2], int(sys.argv[3]), {int(i) for i in sys.argv[4].split(',')}
plan = runnable(json.load(open(os.path.join(run, m, 'plan.json'))))
snaps = bp_snap.snapshots(plan, [T], T + 2, '/workspace/pilot/bp2/work/instep_%d' % os.getpid())[T]
prev = None
for s in snaps:
    cur = {e[0]: tuple(e[4:7]) for e in s['E'] if e[0] in ids}
    if cur != prev:
        print(s.get('k'), s.get('ev'), cur)
    prev = cur
