"""born.py MATCH T0 T1 -- crforge characters born / gone per tick (AimRun dossier) and recorded bodies count per side/type per frame"""
import json, sys, glob
m, t0, t1 = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
prev = None
for l in open(glob.glob("/workspace/pilot/bp5/work/dos/live_play_*" + m + ".o.jsonl")[0]):
    o = json.loads(l)
    cur = {c[0]: c for c in o["C"]}
    if prev is not None and t0 <= o["t"] <= t1:
        b = [cur[i][:5] + cur[i][7:8] for i in cur if i not in prev]; g = [prev[i][:5] + prev[i][7:8] for i in prev if i not in cur]
        st = [(i, prev[i][7], cur[i][7]) for i in cur if i in prev and prev[i][7] != cur[i][7]]
        if b or g or st: print(o["t"], "born", b, "gone", g, "state", st)
    prev = cur
for l in open(glob.glob("/workspace/pilot/sme_live/frames2/live_play_*" + m + ".jsonl")[0]):
    f = json.loads(l)
    if t0 <= f["t"] <= t1: print("F", f["t"], "B", f["B"], "n1", sorted((e[3], e[5]) for e in f["E"] if e[0] == 1))
