import json, sys, collections
sys.path.insert(0, '/workspace/pilot/a2c6')
T = '/workspace/crforge_cache/tables/16.402.22/'
cost = {}
for f in ('spells_characters', 'spells_buildings', 'spells_other'):
    for n, r in json.load(open(T + f + '.json'))['rows'].items():
        if r['columns'].get('ManaCost') is not None: cost.setdefault(n, r['columns']['ManaCost'])
c = collections.Counter(); out = []
for l in open(sys.argv[1]):
    r = json.loads(l); me = r['my_side']
    fr = {f['t']: f for f in map(json.loads, open('/workspace/pilot/sme_live/frames2/%s.jsonl' % r['match']))}
    ts = sorted(fr)
    own = [p for p in r['plays'] if p['side'] == me]
    for p in own:
        if p['kind'] != 'play' or p.get('source') != 'own_tap': continue
        R = p['tick']; k = cost.get(p['card'])
        if k is None: c['nocost'] += 1; continue
        pairs = []
        for a, b in zip(ts, ts[1:]):
            if not (R - 15 <= b <= R + 15): continue
            d = fr[a]['el'] - fr[b]['el']
            best = min((d + rg * (b - a) for rg in (178, 357, 537)), key=lambda x: abs(x - round(x / 10000) * 10000))
            if best >= 9000: pairs.append((a, b, round(best / 10000)))
        hit = [x for x in pairs if x[2] >= k]
        if not hit: c['no drop'] += 1; continue
        a, b, n = min(hit, key=lambda x: min(abs(x[0] - R), abs(x[1] - 1 - R)))
        if a <= R <= b - 1: c['inside'] += 1
        else:
            c['outside'] += 1; out.append((r['match'][-15:], p['card'], R, (a, b - 1), n, k))
print(dict(c))
for o in out: print(*o)
