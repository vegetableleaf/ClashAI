"""born9.py TRACE.o.jsonl T0 T1 -- crforge characters born / gone / state change per tick (any AimRun trace), with name, side, xy"""
import json, sys
f, t0, t1 = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
prev = None
for l in open(f):
    o = json.loads(l)
    cur = {c[0]: c for c in o["C"]}
    if prev is not None and t0 <= o["t"] <= t1:
        b = [cur[i][:5] + cur[i][7:9] for i in cur if i not in prev]
        g = [prev[i][:5] + prev[i][7:9] for i in prev if i not in cur]
        st = [(i, cur[i][1], prev[i][7], cur[i][7]) for i in cur if i in prev and prev[i][7] != cur[i][7]]
        if b or g or st: print(o["t"], "born", b, "gone", g, "state", st)
    if o["t"] > t1: break
    prev = cur
