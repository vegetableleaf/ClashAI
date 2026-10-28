"""python raw10.py LIVE_LOG T0 T1 -- raw non-frame events and frame elixir / projectiles / areas in [T0, T1]."""
import json, sys
f, t0, t1 = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
for l in open(f, 'rb'):
    j = json.loads(l)
    t = j.get('tick')
    if j.get('event') != 'frame':
        if t is None or t0 <= t <= t1: print('EV', json.dumps(j)[:400])
        continue
    if t0 <= t <= t1:
        print(t, 'el', j.get('elixir'), 'proj', j.get('proj'), 'fx', [x[:6] for x in j.get('fx', [])])
