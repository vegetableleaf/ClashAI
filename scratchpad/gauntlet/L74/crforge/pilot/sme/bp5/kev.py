"""kev.py WD MATCH T0 T1 IDS -- per tick, the events (in order) that involve the ids (hit/rm/replan/disp/prop), compact"""
import json, sys, glob
wd, m, t0, t1 = sys.argv[1], sys.argv[2], int(sys.argv[3]), int(sys.argv[4]); ids = {int(i) for i in sys.argv[5].split(",")}
for l in open(glob.glob(wd + "/live_play_*" + m + ".o.jsonl")[0]):
    o = json.loads(l)
    if t0 <= o["t"] <= t1:
        ev = [(k, e) for k, e in enumerate(o["ev"]) if e[0] != "push" and (e[1] in ids or (e[0] == "hit" and e[2] in ids))]
        print(o["t"], len(o["ev"]), [(k, e[:7]) for k, e in ev])
        print("    C", [c for c in o["C"] if c[0] in ids])
