"""ENG-FIX5: a record's plays of kind != play (abilities) near T, all fields. python ab_near.py INPUTS.jsonl MATCH T W"""
import json, sys
m, T, W = sys.argv[2], int(sys.argv[3]), int(sys.argv[4])
for l in open(sys.argv[1]):
    r = json.loads(l)
    if r['match'].endswith(m):
        for p in r['plays']:
            if abs(p['tick'] - T) <= W and p['kind'] != 'play':
                print(p)
