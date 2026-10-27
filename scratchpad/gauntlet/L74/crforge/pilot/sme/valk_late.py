"""Hero Valkyrie casts where crforge's first ValkyrieHero_AEO comes after R+2: the enemies around her at R+2 and at
the sim's first AEO line (row, side, distance, hp), to see what crforge waited for.
    python3 valk_late.py RUNDIR [N]"""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sme import run_batch  # noqa: E402
from sme_live import load_frames, runnable  # noqa: E402

run = sys.argv[1]
N = int(sys.argv[2]) if len(sys.argv) > 2 else 8
shown = 0
for l in open(os.path.join(run, 'results.jsonl')):
    m = json.loads(l)['match']
    p = os.path.join(run, m, 'plan.json')
    if not os.path.exists(p) or shown >= N:
        continue
    plan = json.load(open(p))
    cards = {'cmd%d_0' % i: c.get('card') for i, c in enumerate(plan['cmds'])}
    abil = [c for c in plan['cmds'] if c['kind'] == 'ability' and cards.get(c['unit']) == 'Valkyrie']
    if not abil:
        continue
    frames = load_frames(os.path.join('/workspace/pilot/sme_live/frames2', m + '.jsonl'))
    o = run_batch([(runnable(plan), max(frames) + 3, 0)], os.path.join(run, m, 'valkl'))[0]
    if o is None:
        continue
    by = {x['t']: x for x in o}
    for c in abil:
        R, side = c['run'], c['side']
        a_s = next((x['t'] for x in o if x['t'] > R and any(e[2] == 'ValkyrieHero_AEO' and e[3] == side for e in x['E'])), None)
        a_r = next((t for t in sorted(frames) if t >= R and any(a[3] == 203000011 and a[0] == side for a in frames[t]['A'])), None)
        if a_s is None or a_s - R <= 2 or a_r is None or a_r - R > 3:
            continue
        shown += 1
        for t in (R + 2, a_s):
            s = by[t]
            v = next((e for e in s['E'] if e[1] == 'C' and e[2] == 'ValkyrieHero' and e[3] == side), None)
            if not v:
                continue
            near = sorted(((abs(e[4] - v[4]) + abs(e[5] - v[5]), e[1] + ':' + e[2], e[6], e[11] if len(e) > 11 else '')
                           for e in s['E'] if e[3] != side and e[1] in 'CT'), key=lambda z: z[0])[:4]
            print(m, 'R', R, 'game area R+%d' % (a_r - R), 'sim area R+%d' % (a_s - R), '| at', t, 'valk buffs', v[11] if len(v) > 11 else '',
                  'nearest enemies (dist, row, hp, buffs):', near)
        if shown >= N:
            break
