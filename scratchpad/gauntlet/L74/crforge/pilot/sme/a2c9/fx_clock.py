"""A2c-9T item 3 (222712@4183): does an area's first sighting date it like its later sightings?
    python -I fx_clock.py INPUTS.jsonl [CARD_ID ...]
For each reader fx row group (one gen id), v = tick * 50 + remaining ms is constant while the frame label is right
(remaining falls 50 ms a tick). Per gen: the first sighting's v against the mode of the later ones (>= 2 later rows that
agree). Prints counts by card and every gen whose first sighting is off, and whether an extracted play is dated from it."""
import collections, json, sys
LIVE = r'C:\Users\benpe\ClashBot\scratchpad\gauntlet\L68\live_reader\%s.jsonl'
recs = [json.loads(l) for l in open(sys.argv[1])]
only = {int(c) for c in sys.argv[2:]}
tab, odd = collections.Counter(), []
for r in recs:
    g = collections.defaultdict(list)
    for line in open(LIVE % r['match'], 'rb'):
        if b'"frame"' not in line[:40]:
            continue
        d = json.loads(line)
        t = d['tick']
        if t is None or t < 0:
            continue
        for e in d['fx']:
            if not only or e[3] in only:
                if e[4] is not None: g[e[7]].append((t, e[3], e[4], e[0], e[1], e[2]))
    for gen, rows in g.items():
        rows = sorted(set(rows))
        if len(rows) < 3 or rows[0][2] <= 0:
            continue
        v = [t * 50 + rem for t, c, rem, *_ in rows if rem > 0]
        rest = collections.Counter(v[1:4])
        mode, n = rest.most_common(1)[0]
        if n < 2:
            tab[(rows[0][1], 'rest_split')] += 1
            continue
        k = 'agree' if v[0] == mode else 'first_off_%+d' % ((v[0] - mode) // 50)
        tab[(rows[0][1], k)] += 1
        if k != 'agree':
            t0 = rows[0][0]
            made_first, made_rest = t0, t0 + (mode - v[0]) // 50   # shift of the made tick the rest implies
            hit = [p for p in r['plays'] if p['kind'] == 'play' and p.get('dated') == 'fx_made' and p['side'] == rows[0][3]
                   and abs(p['x'] - rows[0][4]) + abs(p['y'] - rows[0][5]) <= 600 and abs(p['tick'] - t0) <= 3]
            odd.append((r['match'][10:], gen, rows[0][1], [x[:3] for x in rows[:4]], k,
                        [(p['card'], p['tick']) for p in hit]))
for k, v in sorted(tab.items()):
    print(k, v)
for o in odd:
    print(o)
