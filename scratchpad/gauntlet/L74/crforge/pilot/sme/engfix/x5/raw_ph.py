"""ENG-FIX5: the phase2 / phase3 / ents_state parts of one tick of a live log (keys + short reprs).
python raw_ph.py LOG TICK"""
import json, sys
for line in open(sys.argv[1], 'rb'):
    if b'"frame"' not in line[:40]:
        continue
    d = json.loads(line)
    if d['tick'] == int(sys.argv[2]):
        for k in ('ents_state', 'phase2', 'phase3'):
            v = d.get(k)
            print('==', k, type(v).__name__)
            if isinstance(v, dict):
                for kk, vv in v.items():
                    if isinstance(vv, list):
                        print('  ', kk, 'list', len(vv))
                        for x in vv:
                            print('     ', json.dumps(x)[:300])
                    else:
                        print('  ', kk, json.dumps(vv)[:300])
            else:
                print('  ', json.dumps(v)[:600])
        break
