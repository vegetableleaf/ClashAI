"""Buildings / towers present per frame (changes only). python3 bld.py MATCH LO HI"""
import json, sys
m, lo, hi = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
prev = None
for l in open('/workspace/pilot/sme_live/frames2/%s.jsonl' % m):
    f = json.loads(l)
    if not lo <= f['t'] <= hi:
        continue
    b = sorted((e[0], e[1], e[2], e[3], e[5]) for e in f['E'] if e[3] == -1 or e[3] // 1000000 in (27,) or e[3] in (13000096, 13000098, 13000106))
    if b != prev:
        print(f['t'], b)
    prev = b
