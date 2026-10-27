"""d5hs.py death5.jsonl -- delay-6 direct kills: U's attack / load timer at t-1 against its row's HitSpeed / LoadTime"""
import json, collections, sys
T = '/workspace/crforge_cache/tables/16.402.22/'
rows_c = {}
for f in ('characters.json', 'buildings.json'):
    for k, v in json.load(open(T + f))['rows'].items():
        rows_c[k] = v['columns']
def col(n, c):
    r = rows_c.get(n, {})
    while c not in r and r.get('Base'):
        r = rows_c.get(r['Base'].split('.')[-1], {}) if r.get('Base').split('.')[-1] != n else {}
    return r.get(c)
rows = [json.loads(l) for l in open(sys.argv[1])]
d = [x for x in rows if x['pre'] and x['clean'] and x['delay'] == 6 and x['cause'] == 'direct']
c = collections.Counter()
for x in d:
    a, ld = map(int, x['timers'].split('/')[:2])
    hs, lt = col(x['name'], 'HitSpeed'), col(x['name'], 'LoadTime')
    k = ('a+50-hs', None if hs is None else a + 50 - hs, 'ld', ld, x['out'])
    c[(None if hs is None else a + 50 - hs, x['out'])] += 1
    if x['out'] != 'crforge': print(x['name'], 'atk', a, 'load', ld, 'HitSpeed', hs, 'LoadTime', lt)
print(sorted(c.items(), key=lambda z: -z[1])[:30])
