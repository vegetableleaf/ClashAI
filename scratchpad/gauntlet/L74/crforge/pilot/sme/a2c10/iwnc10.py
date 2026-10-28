"""A2c-10: hero Ice Wizard plays with no press in the plan (never cast), per side, and whether the match's first div
falls on that IW's life. python3 iwnc10.py RUNDIR"""
import json, os, sys
from collections import Counter
run = sys.argv[1]
c = Counter()
for l in open(os.path.join(run, 'results.jsonl')):
    r = json.loads(l)
    pp = os.path.join(run, r['match'], 'plan.json')
    if not os.path.exists(pp):
        continue
    cmds = json.load(open(pp))['cmds']
    pressed = {k['unit'] for k in cmds if k['kind'] == 'ability'}
    hero = {k['side'] for k in cmds if k['kind'] == 'ability' and cmds[int(k['unit'][3:].split('_')[0])].get('card') == 'IceWizard'}
    for i, k in enumerate(cmds):
        if k.get('card') != 'IceWizard' or k['side'] not in hero:
            continue
        nxt = next((q['run'] for q in cmds[i + 1:] if q.get('card') == 'IceWizard' and q['side'] == k['side']), 10 ** 6)
        fd = r.get('first_div')
        key = ('own' if (k.get('_src') or {}).get('own') else 'opp', 'pressed' if 'cmd%d_0' % i in pressed else 'never',
               'fd_in_life' if fd is not None and k['run'] <= fd < nxt else '-')
        c[key] += 1
        if key[1] == 'never' and key[2] == 'fd_in_life':
            print(r['match'][-6:], i, k['side'], k['run'], 'fd', fd, (r.get('first_detail') or [[None, None, None]])[0][2])
for k in sorted(c):
    print(k, c[k])
