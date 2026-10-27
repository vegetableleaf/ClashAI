"""dos.py MATCH T0 T1 ID[,ID..] -- A2c-BP5 dossier from work/dos/<match>.o.jsonl: per tick C rows (+ game frame match) and probe events of the ids"""
import json, sys, glob
m, t0, t1, ids = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), [int(x) for x in sys.argv[4].split(",")]
wd = sys.argv[5] if len(sys.argv) > 5 else "/workspace/pilot/bp5/work/dos"
f = glob.glob(wd + "/live_play_*" + m + ".o.jsonl")[0]
fr = {}
for l in open("/workspace/pilot/sme_live/frames2/" + f.split("/")[-1].replace(".o.jsonl", ".jsonl")):
    x = json.loads(l)
    if t0 <= x["t"] <= t1: fr[x["t"]] = {(e[0], e[1], e[2]) for e in x["E"]}
for l in open(f):
    o = json.loads(l)
    if not t0 <= o["t"] <= t1: continue
    print("t", o["t"], "frame" if o["t"] in fr else "")
    for c in o["C"]:
        if c[0] in ids: print("   C", c, "EXACT" if o["t"] in fr and (c[2], c[3], c[4]) in fr[o["t"]] else "")
    order = [e[1] for e in o["ev"] if e[0] == "disp"]
    print("   visit order (disp):", [i for i in order if i in ids], "pos", {i: order.index(i) for i in ids if i in order})
    for e in o["ev"]:
        if e[1] in ids and e[0] != "push": print("   ", e)
