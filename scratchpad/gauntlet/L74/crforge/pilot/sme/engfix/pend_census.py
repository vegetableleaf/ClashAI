# pend_census.py OUT -- ENG-FIX4: our-side cast_seen abilities that follow an own_press of the same card with no cast_seen
# between them (the press unresolved); with the reader's largest elixir drop in [t-6, t+6] (dev + FRESH1-6, r7 OFF inputs)
import json, sys
H = 'C:/Users/benpe/ClashBot/scratchpad/gauntlet/L74/crforge/pilot/sme/engfix/'
LIVE = 'C:/Users/benpe/ClashBot/scratchpad/gauntlet/L68/live_reader/'
out = open(sys.argv[1], 'w')
n = tot = 0
for s in ('dev', 'fresh1', 'fresh2', 'fresh3', 'fresh4', 'fresh5', 'fresh6'):
    for line in open(H + 'r7/%s_off.jsonl' % s):
        r = json.loads(line)
        my = r['my_side']
        ab = sorted((p for p in r['plays'] if p['side'] == my and p['kind'] == 'ability'), key=lambda p: p['tick'])
        el = {}
        for l in open(LIVE + r['match'] + '.jsonl', 'rb'):
            if b'"frame"' in l[:40]:
                d = json.loads(l)
                if d['tick'] is not None and d['tick'] not in el:
                    el[d['tick']] = d.get('elixir')
        for i, p in enumerate(ab):
            if p.get('source') != 'cast_seen':
                continue
            tot += 1
            prev = [q for q in ab[:i] if q['card'] == p['card']]
            if not prev or prev[-1].get('source') == 'cast_seen':
                continue
            w = [el[t] for t in sorted(el) if p['tick'] - 6 <= t <= p['tick'] + 6 and el[t] is not None]
            drop = max([a - b for a, b in zip(w, w[1:])] + [0])
            n += 1
            print(s, r['match'][10:], p['card'], 'cast', p['tick'], 'after', prev[-1].get('source'), prev[-1]['tick'], 'gap', p['tick'] - prev[-1]['tick'], 'max_drop', round(drop, 3), file=out)
print('unresolved-press casts', n, 'of cast_seen', tot, file=out)
out.close()
print(open(sys.argv[1]).read())
