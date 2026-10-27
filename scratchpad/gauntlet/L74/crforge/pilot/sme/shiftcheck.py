"""diff of recorded frame T against sim frames T-3..T+3: python3 shiftcheck.py SIM.jsonl T"""
import json, sys
from sme import load_frames, canon_rec, canon_sim, diff
rec = load_frames("data/rec.jsonl", key="f")
sim = {}
for l in open(sys.argv[1]):
    o = json.loads(l); sim[o["t"]] = o
t = int(sys.argv[2])
for k in range(-3, 4):
    d = diff(canon_rec(rec[t]), canon_sim(sim[t + k]))
    print(k, len(d), d[:4])
