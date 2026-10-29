"""ENG-FIX5: the plan's commands in [T0, T1] (run tick) and the SIM's first row of each new id in that window.
python3 plays_near.py RUNDIR MATCH T0 T1"""
import json, os, sys
run, m, t0, t1 = sys.argv[1], sys.argv[2], int(sys.argv[3]), int(sys.argv[4])
p = json.load(open(os.path.join(run, m, 'plan.json')))
for i, c in enumerate(p['cmds']):
    if t0 <= c['run'] <= t1:
        print('cmd%d' % i, {k: v for k, v in c.items() if k != '_src'})
seen = set()
for l in open('/workspace/pilot/engfix5/work/p_%s/o.jsonl' % m[-6:]):
    o = json.loads(l)
    if o['t'] > t1 + 120:
        break
    for e in o['E']:
        if e[0] not in seen:
            seen.add(e[0])
            if o['t'] >= t0:
                print('t=%d new' % o['t'], e[:9])
