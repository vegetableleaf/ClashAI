"""ENG-SME: own_tap play points vs where the game put the body. For every own play (source own_tap) of a card that makes a
body, the first NEW own body of that card id (base / evo / hero form) seen within [tick + 1, tick + 8]; prints the
offset when it differs from the play point (FRESH2 110715@4503: X-Bow tap point x 2500, body at 1500).
    python -I own_point_census.py INPUTS.jsonl ..."""
import collections, json, os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'extract'))
import extract  # noqa: E402

cat, by_name = extract.load_catalog()
ids = lambda n: {(by_name.get(n) or {}).get(k) for k in ('card_id', 'evolution_form_id', 'hero_form_id')} - {None}  # noqa: E731
tot = collections.Counter()
for f in sys.argv[1:]:
    for line in open(f):
        r = json.loads(line)
        my = r['my_side']
        own = [p for p in r['plays'] if p['side'] == my and p['kind'] == 'play' and p.get('source') == 'own_tap' and p.get('x') is not None]
        if not own:
            continue
        fr, seen = [], set()
        for l2 in open(extract.LIVE / (r['match'] + '.jsonl'), 'rb'):
            if b'"frame"' not in l2[:40]:
                continue
            d = json.loads(l2); t = d['tick']
            if t is None or t < 0 or t in seen:
                continue
            seen.add(t); fr.append((t, {e[7]: e for e in d['ents'] if e[0] == my}))
        for p in own:
            dn = (by_name.get(p['name']) or {}).get('display_name') or p['name']
            cid = ids(p['name']) or ids(dn)
            before = set().union(*[set(b) for t, b in fr if p['tick'] - 6 <= t <= p['tick']]) if fr else set()
            new = {}
            for t, b in fr:
                if p['tick'] < t <= p['tick'] + 8:
                    for a, e in b.items():
                        if a not in before and e[3] in cid:
                            new.setdefault(a, e)
            new = list(new.values())
            if not new:
                tot['no_body'] += 1; continue
            e = new[0]
            dx, dy = e[1] - p['x'], e[2] - p['y']
            if len(new) > 1 or p['name'] in ('Skeletons',):
                tot['multi_body'] += 1; continue
            k = 'same' if max(abs(dx), abs(dy)) <= 1 else 'walked' if max(abs(dx), abs(dy)) < 500 else 'differs'
            tot[k] += 1
            if k == 'differs':
                print(r['match'][10:], p['name'], 'tick', p['tick'], 'play', (p['x'], p['y']), 'body', (e[1], e[2]), 'd', (dx, dy))
print(dict(tot))
