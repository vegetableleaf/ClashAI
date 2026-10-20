"""Evo Goblin Drill lives in live logs: each GoblinDrill_EV1 / _EV1_Dig body (by its reader address) -> first / last tick, first /
last point, hp at both ends, so a relocation (a second dig or a second building in one play) shows.  python evodrill.py LOG ..."""
import json, sys
for p in sys.argv[1:]:
    life = {}
    with open(p, 'rb') as f:
        for raw in f:
            if b'"frame"' not in raw[:40]:
                continue
            j = json.loads(raw)
            names = {u['address']: u['name'] for u in (j.get('phase2') or {}).get('units', [])}
            for e in j['ents']:
                n = names.get(e[7])
                if n and n.startswith('GoblinDrill_EV1'):
                    r = life.setdefault(e[7], dict(name=n, side=e[0], first=j['tick'], p0=(e[1], e[2]), hp0=e[4]))
                    r.update(last=j['tick'], p1=(e[1], e[2]), hp1=e[4], max=e[5])
    rows = sorted(life.values(), key=lambda r: r['first'])
    print(p[-22:-6])
    for r in rows:
        print('   ', r['name'], 'side', r['side'], r['first'], '->', r['last'], r['p0'], '->', r['p1'], 'hp', r['hp0'], '->', r['hp1'], '/', r['max'])
