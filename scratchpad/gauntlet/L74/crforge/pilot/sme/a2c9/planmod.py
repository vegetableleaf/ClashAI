"""python3 planmod.py PLAN.json OUT.json IDX:NEWRUN ...  -- plan command IDX re-dated to NEWRUN (given = NEWRUN - 20)"""
import json, sys
plan = json.load(open(sys.argv[1]))
for a in sys.argv[3:]:
    i, n = map(int, a.split(':'))
    c = plan['cmds'][i]
    c['given'] += n - c['run']
    c['run'] = n
json.dump(plan, open(sys.argv[2], 'w'))
