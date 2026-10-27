"""Torn-read check: for each object of a recorded frame, which simulated ticks (T-2..T+2) hold it exactly.
python3 tornck.py SIM.jsonl REC_OR_P3.jsonl T [p3]"""
import json, sys
from sme import load_frames, canon_rec, canon_sim
p3 = len(sys.argv) > 4
rec = load_frames(sys.argv[2]) if p3 else load_frames(sys.argv[2], key='f')
sim = {}
for l in open(sys.argv[1]):
    o = json.loads(l); sim[o['t']] = o
t = int(sys.argv[3])
r = canon_rec(rec[t], not p3)
cs = {k: canon_sim(sim[t + k], not p3) for k in range(-2, 3) if t + k in sim}
from collections import Counter
hits = Counter()
for kind in ('T', 'U', 'P', 'A'):
    for x in r[kind]:
        ks = tuple(k for k, c in cs.items() if x in c[kind])
        hits[ks] += 1
        if not ks: print('  in no sim tick:', kind, x)
for k in ('S0', 'S1'):
    if k in r:
        ks = tuple(kk for kk, c in cs.items() if c.get(k) == r[k]); hits[('S', ks)] += 1
print('frame', t, 'objects by the sim ticks (offsets) that hold them:', dict(hits))
for k, c in cs.items():
    for kind in ('T', 'U', 'P', 'A'):
        miss = [x for x in c[kind] if x not in r[kind]]
        if k in (0, 1) and miss: print('  sim%+d has, rec lacks:' % k, kind, miss[:6])
