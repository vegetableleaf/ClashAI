"""Hero Ice Golem death: crforge makes both IceGolemiteHero_Death_Aeo (slow) and, through the inherited OnDeathAction
IceGolemiteDeathExplosion, IceGolemiteDeathArea (33 base damage). Does the game deal that damage?
For each sim line where an IceGolemiteDeathArea appears next to an IceGolemiteHero_Death_Aeo (a hero death) and for a
plain Ice Golem death (DeathArea with no hero Death_Aeo), take the enemy bodies within 2,000 whose sim hp drops at the
next lines by the death damage; check the recorded hp of the body at the same point over the next 4 ticks.
    python3 golem_check.py RUNDIR"""
import collections, json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sme import run_batch  # noqa: E402
from sme_live import load_frames, runnable  # noqa: E402

run = sys.argv[1]
res = collections.Counter()
ex = []
for l in open(os.path.join(run, 'results.jsonl')):
    m = json.loads(l)['match']
    p = os.path.join(run, m, 'plan.json')
    if not os.path.exists(p):
        continue
    plan = json.load(open(p))
    if not any(c.get('card') == 'IceGolemite' for c in plan['cmds']):
        continue
    frames = load_frames(os.path.join('/workspace/pilot/sme_live/frames', m + '.jsonl'))
    o = run_batch([(runnable(plan), max(frames) + 3, 0)], os.path.join(run, m, 'golem'))[0]
    if o is None:
        continue
    by = {x['t']: x for x in o}
    seen = set()
    for x in o:
        t = x['t']
        for a in x['E']:
            if a[1] != 'A' or a[2] != 'IceGolemiteDeathArea' or a[0] in seen:
                continue
            seen.add(a[0])
            hero = any(b[1] == 'A' and b[2] == 'IceGolemiteHero_Death_Aeo' and abs(b[4] - a[4]) + abs(b[5] - a[5]) < 200
                       for b in x['E'])
            prev, nxt = by.get(t - 1), by.get(t + 1)
            if not prev or not nxt:
                continue
            for e in prev['E']:
                if e[1] != 'C' or e[3] == a[3] or e[6] <= 0 or abs(e[4] - a[4]) + abs(e[5] - a[5]) > 2800:
                    continue
                after = next((f for f in nxt['E'] if f[0] == e[0]), None)
                if not after or after[6] >= e[6]:
                    continue
                drop = e[6] - after[6]
                # recorded: the body at the sim point at t-1, its hp over t..t+4
                rows = []
                for k in range(-1, 5):
                    fr = frames.get(t + k)
                    if fr:
                        q = [g for g in fr['E'] if g[0] == e[3] and abs(g[1] - e[4]) + abs(g[2] - e[5]) < 120 and g[3] != -1]
                        if q:
                            rows.append((k, q[0][4]))
                if len(rows) < 2:
                    continue
                rdrop = rows[0][1] - min(h for _, h in rows) if rows[0][0] <= 0 else None
                key = ('hero' if hero else 'plain', 'rec dropped by the sim drop' if rdrop == drop else
                       'rec no drop' if rdrop == 0 else 'rec other drop' if rdrop is not None else 'no rec before')
                res[key] += 1
                if len(ex) < 8 and hero:
                    ex.append((m, t, e[2], drop, rows))
for k, v in sorted(res.items()):
    print(v, k)
for x in ex:
    print(x)
