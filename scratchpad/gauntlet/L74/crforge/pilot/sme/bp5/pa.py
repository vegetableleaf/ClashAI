"""pa.py MATCH T0 T1 WD -- crforge projectiles/areas born/gone per tick; game frame P/A lists"""
import json, sys, glob
m, t0, t1, wd = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), sys.argv[4]
prev = {}
for l in open(glob.glob(wd + "/live_play_*" + m + ".o.jsonl")[0]):
    o = json.loads(l); cur = {p[0]: p for p in o.get("PA", [])}
    if t0 <= o["t"] <= t1:
        b = [cur[i] for i in cur if i not in prev]; g = [prev[i] for i in prev if i not in cur]
        if b or g: print(o["t"], "born", b, "gone", g)
    prev = cur
for l in open(glob.glob("/workspace/pilot/sme_live/frames2/live_play_*" + m + ".jsonl")[0]):
    f = json.loads(l)
    if t0 <= f["t"] <= t1: print("F", f["t"], "P", f["P"], "A", f["A"])
