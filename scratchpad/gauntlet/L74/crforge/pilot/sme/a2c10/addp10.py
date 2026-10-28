"""python3 addp10.py IN.json OUT.json SIDE UNIT RUN -- copy a plan with an ability press of UNIT (e.g. cmd64_0) at RUN,
appended to the command list."""
import json, sys
p = json.load(open(sys.argv[1]))
side, unit, R = int(sys.argv[3]), sys.argv[4], int(sys.argv[5])
c = {"kind": "ability", "given": R - 20, "run": R, "side": side, "unit": unit,
     "_src": {"lo": R, "hi": R, "tick": R, "source": "a2c10_probe", "own": False}}
p['cmds'].append(c)   # appended: units are named by command index (cmdN_k), so no index may shift
json.dump(p, open(sys.argv[2], 'w'))
print('appended as', len(p['cmds']) - 1)
