"""pa9.py TRACE.o.jsonl PLAN.json T0 T1 -- projectiles / areas born or gone per tick (AimRun4+ traces) and plan commands in [T0-40, T1]"""
import json, sys
f, plan, t0, t1 = sys.argv[1], sys.argv[2], int(sys.argv[3]), int(sys.argv[4])
for i, c in enumerate(json.load(open(plan))['cmds']):
    if t0 - 40 <= c.get('run', -1) <= t1: print('cmd', i, {k: v for k, v in c.items() if k != '_src'})
prev = None
for l in open(f):
    o = json.loads(l)
    cur = {p[0]: p for p in o.get('PA', [])}
    if prev is not None and t0 <= o['t'] <= t1:
        b = [cur[i] for i in cur if i not in prev]; g = [prev[i] for i in prev if i not in cur]
        if b or g: print(o['t'], 'born', b, 'gone', g)
    if o['t'] > t1: break
    prev = cur
