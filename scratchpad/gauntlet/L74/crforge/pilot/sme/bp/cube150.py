"""Episodes whose first detail has a FloatingCube row off by 150 (one axis) or a recorded IceWizard row 150 off.
python3 cube150.py RESULTS.jsonl [IWD.jsonl]"""
import json, sys
iw = {}
if len(sys.argv) > 2:
    for l in open(sys.argv[2]):
        d = json.loads(l)
        iw.setdefault(d['match'], []).append(d['R'])
for l in open(sys.argv[1]):
    r = json.loads(l)
    for e in r.get('episodes', []):
        det = e.get('detail') or []
        hit = [x for x in det if ('Cube' in str(x[2]) or 'IceWizard' in str(x[2])) and isinstance(x[3], list)
               and sorted(map(abs, x[3][:2])) == [0, 150]]
        if hit:
            near = [R for R in iw.get(r['match'], []) if 0 < e['start'] - R <= 40]
            print(r['match'][10:], 'onset', e['start'], 'frames', e['frames'], 'deploys R before', near, json.dumps(hit[:2])[:250])
