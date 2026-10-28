"""ramord9.py ORDER_ROWS TRACEDIR -- A2c-9R lead 4: clean order-census events where a RamRider mount ('Ram') moved earlier in the tick
than the pushed body B, after a river-jump landing (lander_k <= 200). For each: Ram id, the Ram's landing tick (last tick in state
JUMPING), B's id and first tick in the trace, B's holder index vs the Ram's. If B was born before the landing and the game still
follows crforge (Ram first), 'the Ram is re-appended to the list at landing' is contradicted for that event."""
import glob, json, sys
rows_p, td = sys.argv[1], sys.argv[2]
ev = []
for l in open(rows_p):
    if '"Ram"' not in l: continue
    x = json.loads(l)
    if 'Ram' in x['movers'] and x['clean'] and x['pre'] and x['lander_k'] is not None and x['lander_k'] <= 200: ev.append(x)
for m in sorted({x['m'] for x in ev}):
    born, land, idx, st = {}, {}, {}, {}
    for l in open(glob.glob(td + '/live_play_' + m + '.o.jsonl')[0]):
        o = json.loads(l)
        for k, c in enumerate(o['C']):
            born.setdefault(c[0], o['t'])
            if c[1] == 'Ram':
                if st.get(c[0]) is not None and st[c[0]] != c[7]: land.setdefault(c[0], []).append((o['t'], st[c[0]], c[7]))
                st[c[0]] = c[7]
            idx[(o['t'], c[0])] = k
    rams = [i for i in st]
    for x in [y for y in ev if y['m'] == m]:
        r = rams[0] if len(rams) == 1 else rams
        print(m, x['t'], 'B', x['id'], x['name'], 'born', born.get(x['id']), 'idx', idx.get((x['t'], x['id'])), '| Ram', r,
              'idx', [idx.get((x['t'], q)) for q in rams], 'born', [born.get(q) for q in rams], 'states', {q: land.get(q, [])[:6] for q in rams},
              'k', x['lander_k'], x['out'])
