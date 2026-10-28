"""fdiff9.py TRACE.o.jsonl FRAMES.jsonl T0 T1 -- per recorded frame: sim characters (AimRun C rows) with no exact recorded body (side, x, y)
and recorded bodies with no exact sim character; nearest counterpart for each."""
import json, sys
f, fr, t0, t1 = sys.argv[1], sys.argv[2], int(sys.argv[3]), int(sys.argv[4])
sim = {}
for l in open(f):
    o = json.loads(l)
    if t0 <= o['t'] <= t1: sim[o['t']] = o['C']
    if o['t'] > t1: break
for l in open(fr):
    x = json.loads(l)
    if not t0 <= x['t'] <= t1 or x['t'] not in sim: continue
    rec = [(e[0], e[1], e[2], e[3]) for e in x['E']]
    rs = {(e[0], e[1], e[2]) for e in rec}
    ss = {(c[2], c[3], c[4]) for c in sim[x['t']]}
    so = [c[:5] for c in sim[x['t']] if (c[2], c[3], c[4]) not in rs]
    ro = [e for e in rec if (e[0], e[1], e[2]) not in ss]
    print(x['t'], 'sim_only', so, 'rec_only', ro)
