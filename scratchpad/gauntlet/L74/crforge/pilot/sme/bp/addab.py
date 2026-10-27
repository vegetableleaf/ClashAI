"""Plan copy with one more ability command. python3 addab.py PLAN OUT SIDE UNIT RUN"""
import json, sys
p = json.load(open(sys.argv[1]))
side, unit, R = int(sys.argv[3]), sys.argv[4], int(sys.argv[5])
p['cmds'].append({'kind': 'ability', 'given': R - 20, 'run': R, 'side': side, 'unit': unit,
                  '_src': {'lo': R, 'hi': R, 'tick': R, 'source': 'probe', 'own': False}})
json.dump(p, open(sys.argv[2], 'w'))
