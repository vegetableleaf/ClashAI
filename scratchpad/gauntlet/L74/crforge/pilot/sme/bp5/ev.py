"""ev.py WD MATCH T ID [KINDS] -- probe events of one id at one tick"""
import json, sys, glob
wd, m, t, i = sys.argv[1], sys.argv[2], int(sys.argv[3]), int(sys.argv[4])
kinds = sys.argv[5].split(",") if len(sys.argv) > 5 else None
for l in open(glob.glob(wd + "/live_play_*" + m + ".o.jsonl")[0]):
    o = json.loads(l)
    if o["t"] == t:
        for e in o["ev"]:
            if e[1] == i and (kinds is None or e[0] in kinds): print(m, t, e)
