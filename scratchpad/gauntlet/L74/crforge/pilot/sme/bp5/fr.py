"""fr.py MATCH T0 T1 X Y RAD -- recorded bodies (side,x,y,hp,type) within RAD of (X,Y) per frame (positions only)"""
import json, sys, glob
m, t0, t1, X, Y, R = sys.argv[1], *map(int, sys.argv[2:7])
for l in open(glob.glob("/workspace/pilot/sme_live/frames2/live_play_*" + m + ".jsonl")[0]):
    f = json.loads(l)
    if t0 <= f["t"] <= t1:
        print(f["t"], [e[:3] + e[4:6] for e in f["E"] if abs(e[1] - X) + abs(e[2] - Y) <= R])
