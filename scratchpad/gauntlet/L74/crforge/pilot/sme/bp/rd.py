"""Reader detail rows of bodies of given cards in a tick range. python3 rd.py MATCH LO HI CARD[,CARD]"""
import json, sys
m, lo, hi, cards = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), {int(c) for c in sys.argv[4].split(',')}
for l in open('/workspace/pilot/bp/rdet/%s.jsonl' % m):
    f = json.loads(l)
    if lo <= f['t'] <= hi:
        for r in f['G']:
            if r[3] in cards:
                print(f['t'], r)
