"""python3 mv10.py IN.json OUT.json CMD:RUN [CMD:RUN ...] -- copy a plan with command CMD run at RUN (given RUN - 20)."""
import json, sys
p = json.load(open(sys.argv[1]))
for a in sys.argv[3:]:
    i, r = map(int, a.split(':'))
    p['cmds'][i]['run'], p['cmds'][i]['given'] = r, r - 20
json.dump(p, open(sys.argv[2], 'w'))
