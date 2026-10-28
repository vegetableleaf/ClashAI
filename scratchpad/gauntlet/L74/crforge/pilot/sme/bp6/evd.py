"""evd.py O.jsonl T0 T1 [ID,...] -- A2c-BP6 dossier: replan / disp / vg / vs / vchk events in a tick range (optionally some ids)"""
import json, sys
f, t0, t1 = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
ids = set(int(x) for x in sys.argv[4].split(',')) if len(sys.argv) > 4 else None
for l in open(f):
    o = json.loads(l)
    if o['t'] < t0: continue
    if o['t'] > t1: break
    for e in o['ev']:
        if e[0] in ('replan', 'disp', 'vg', 'vs', 'vchk') and (ids is None or e[1] in ids):
            if e[0] == 'replan': e = e[:12] + ['R', e[12]]
            print(o['t'], e)
