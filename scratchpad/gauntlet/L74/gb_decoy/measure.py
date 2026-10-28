"""Per opponent Goblin Barrel cast (CLXIII live): real / decoy lanes, our response plays and their lanes."""
import json, collections, sys

ANSWERS = {'Log', 'Knight', 'IceWizard', 'Skeletons', 'Tornado', 'Tesla'}
rows = [json.loads(l) for l in open(sys.argv[1])]
WIN = int(sys.argv[2]) if len(sys.argv) > 2 else 40


def lane(x):
    return 'L' if x < 0.5 else 'R'


def classify(r):
    """-> (kind, real_lane, decoy_lane, land_tick) or None."""
    ps, ls = r['projs'], r['lands']
    if any(p['tgt_my'][1] <= 0.5 for p in ps):
        return None                                   # a barrel aimed on its own half
    if len(ps) == 1:
        return ('plain', lane(ps[0]['tgt_my'][0]), None, ps[0]['last'])
    if len(ps) != 2 or abs(ps[0]['tgt_my'][0] + ps[1]['tgt_my'][0] - 1) > 0.02:
        return ('odd', None, None, None)
    score = []
    for p, L in zip(ps, ls):
        real = sum(e['name'] == 'BarrelGoblin' and e['maxhp'] > 200 for e in L)
        fake = sum(e['name'] == 'GoblinDummy' or e['maxhp'] < 200 for e in L)
        score.append(real - fake)
    if score[0] == score[1]:
        return ('evo_unlabelled', None, None, None)
    real, decoy = (ps[0], ps[1]) if score[0] > score[1] else (ps[1], ps[0])
    if lane(real['tgt_my'][0]) == lane(decoy['tgt_my'][0]):
        return ('evo_same_lane', lane(real['tgt_my'][0]), lane(decoy['tgt_my'][0]), max(real['last'], decoy['last']))
    return ('evo', lane(real['tgt_my'][0]), lane(decoy['tgt_my'][0]), max(real['last'], decoy['last']))


out = []
tab = collections.Counter()
for r in rows:
    if 'CLXIII' not in r['ckpt']:
        continue
    c = classify(r)
    if c is None:
        continue
    kind, rl, dl, tland = c
    tab[kind] += 1
    if kind not in ('plain', 'evo'):
        continue
    plays = [x for x in r['resp'] if x['ev'] == 'play' and x['tick'] >= r['t0'] - 2 and x['tick'] <= tland + WIN]
    ans = [x for x in plays if x['name'] in ANSWERS and x['xy'] and x['xy'][1] > 0.5]
    first = ans[0] if ans else None
    out.append(dict(file=r['file'], t0=r['t0'], tland=tland, kind=kind, real=rl, decoy=dl, bl=r['opts']['barrel_lane'],
                    first=None if first is None else (first['name'], lane(first['xy'][0]), first['tick'] - r['t0'], first['tick'] - tland,
                                                      first.get('why')),
                    ans=[(x['name'], lane(x['xy'][0]), x['tick'] - r['t0'], x['tick'] - tland) for x in ans],
                    plays=[(x['name'], [round(v, 3) for v in x['xy']], x['tick'] - r['t0']) for x in plays]))
print(dict(tab))
for kind in ('plain', 'evo'):
    rs = [o for o in out if o['kind'] == kind]
    first = [o for o in rs if o['first']]
    right = sum(o['first'][1] == o['real'] for o in first)
    print(f'\n{kind}: casts {len(rs)}, with an answer on my half within land+{WIN}: {len(first)}; first answer in the REAL lane {right}, other lane {len(first) - right}')
    # in flight vs after landing
    for when, f in (('in flight (before land)', lambda o: o['first'][3] < 0), ('after land', lambda o: o['first'][3] >= 0)):
        sub = [o for o in first if f(o)]
        print(f'   {when}: {len(sub)}, real lane {sum(o["first"][1] == o["real"] for o in sub)}')
    by = collections.Counter((o['first'][0], o['first'][1] == o['real']) for o in first)
    print('   by card (card, real lane):', sorted(by.items()))
    allans = [a for o in rs for a in o['ans']]
    ra = sum(1 for o in rs for a in o['ans'] if a[1] == o['real'])
    print(f'   all answers in window: {len(allans)}, real lane {ra}')
json.dump(out, open('results/measure_out.json', 'w'), indent=0)
for o in out:
    if o['kind'] == 'evo':
        print(o['file'], o['t0'], 'land', o['tland'] - o['t0'], 'real', o['real'], 'bl', o['bl'], 'first', o['first'], 'ans', o['ans'])
