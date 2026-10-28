"""ENG-FIX (110715@4503): own building plays (X-Bow, Tesla) vs opponent bodies inside the tapped footprint. For every own
own_tap play of a building card: opponent ents within HALF (X-Bow 1500, Tesla 1000) of the tap on the last frame <= the run
tick, and the offset of the first new own body of the card in [tick + 1, tick + 8].
    python -I bld_block.py LIVE_DIR INPUTS.jsonl ..."""
import json, os, sys
HALF = {'Xbow': 1500, 'Tesla': 1000}
CID = {'Xbow': {27000008}, 'Tesla': {27000006, 27000007}}
live = sys.argv[1]
rows = []
for f in sys.argv[2:]:
    for line in open(f):
        r = json.loads(line)
        my = r['my_side']
        own = [p for p in r['plays'] if p['side'] == my and p['kind'] == 'play' and p.get('source') == 'own_tap' and p['card'] in HALF]
        if not own:
            continue
        fr = {}
        for l2 in open(os.path.join(live, r['match'] + '.jsonl'), 'rb'):
            if b'"frame"' not in l2[:40]:
                continue
            d = json.loads(l2)
            if d['tick'] is not None and d['tick'] >= 0 and d['tick'] not in fr:
                fr[d['tick']] = d['ents']
        ts = sorted(fr)
        for p in own:
            h = HALF[p['card']]
            t0 = max((t for t in ts if t <= p['tick']), default=None)
            inside = [e for e in fr.get(t0, []) if e[0] != my and abs(e[1] - p['x']) < h and abs(e[2] - p['y']) < h and e[6] != 12]
            before = {e[7] for t in ts if p['tick'] - 6 <= t <= p['tick'] for e in fr[t]}
            body = next(((e[1], e[2]) for t in ts if p['tick'] < t <= p['tick'] + 8 for e in fr[t]
                         if e[0] == my and e[7] not in before and e[3] in CID[p['card']]), None)
            off = None if body is None else (body[0] - p['x'], body[1] - p['y'])
            rows.append((r['match'][10:], p['card'], p['tick'], len(inside), off))
blocked = [r for r in rows if r[3]]
print('plays', len(rows), 'with opponent bodies inside the footprint', len(blocked),
      'moved (>= 500)', sum(1 for r in rows if r[4] and max(map(abs, r[4])) >= 500))
for r in rows:
    if r[3] or (r[4] and max(map(abs, r[4])) >= 500):
        print(*r)
