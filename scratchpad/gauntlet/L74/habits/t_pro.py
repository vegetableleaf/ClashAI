import json, collections
c = collections.defaultdict(collections.Counter); op = collections.defaultdict(collections.Counter); n = collections.Counter()
for l in open('pro_sides.jsonl'):
    r = json.loads(l); n[r['src'], r['icebow8']] += 1
    for t, who, card, ab, x, y in r['ev']:
        if y is None: continue
        if who == 'me' and card == 'x-bow': c[r['src']][round(y)] += 1
        if who == 'op' and card in ('golem', 'giant', 'pekka', 'mega-knight', 'lava-hound'): op[r['src']][round(y)] += 1
print(n)
for s in c: print(s, 'xbow Y', sorted(c[s].items(), key=lambda kv: -kv[1])[:8]); print(s, 'opp heavy Y', sorted(op[s].items(), key=lambda kv: -kv[1])[:8])
