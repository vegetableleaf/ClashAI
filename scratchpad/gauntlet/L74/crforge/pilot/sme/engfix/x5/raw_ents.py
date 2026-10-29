"""ENG-FIX5: raw reader 'ents' rows (all fields) of one tick of a live log. python raw_ents.py LOG TICK"""
import json, sys
for line in open(sys.argv[1], 'rb'):
    if b'"frame"' not in line[:40]:
        continue
    d = json.loads(line)
    if d['tick'] == int(sys.argv[2]):
        print([k for k in d if k not in ('ents',)])
        for k, e in enumerate(d['ents']):
            print(k, e)
        break
