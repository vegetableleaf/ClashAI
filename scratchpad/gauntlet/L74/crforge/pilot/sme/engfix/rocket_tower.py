"""ENG-FIX (lead queue 2): our Rocket's crown-tower damage in live frames. For each own Rocket play whose point is within
2,000 of an opponent princess / king tower, the tower's hp drop between the last frame before and the first frame after
the rocket's landing (the first frame in [tick + 1, tick + 80] where the tower hp falls while no other own projectile /
area is within 3,000 of it is not required: drops are printed with every own projectile near, for reading).
    python -I rocket_tower.py LIVE_DIR INPUTS.jsonl..."""
import json, math, os, sys, collections
live = sys.argv[1]
TW = {(3500, 6500), (14500, 6500), (9000, 3000), (3500, 25500), (14500, 25500), (9000, 29000)}
drops = collections.Counter()
for f in sys.argv[2:]:
    for line in open(f):
        r = json.loads(line)
        my = r['my_side']
        rk = [p for p in r['plays'] if p['side'] == my and p['card'] == 'Rocket' and p.get('x') is not None]
        if not rk:
            continue
        fr = {}
        for l2 in open(os.path.join(live, r['match'] + '.jsonl'), 'rb'):
            if b'"frame"' in l2[:40]:
                d = json.loads(l2)
                if d['tick'] is not None and d['tick'] >= 0:
                    fr.setdefault(d['tick'], d['ents'])
        ts = sorted(fr)
        for p in rk:
            tw = [t for t in TW if math.hypot(t[0] - p['x'], t[1] - p['y']) <= 2000]
            for tx, ty in tw:
                hp = [(t, next((e[4] for e in fr[t] if e[0] != my and e[3] == -1 and (e[1], e[2]) == (tx, ty)), None))
                      for t in ts if p['tick'] - 4 <= t <= p['tick'] + 80]
                seq = [(t, h) for t, h in hp if h is not None]
                d = [(b[0], a[1] - b[1]) for a, b in zip(seq, seq[1:]) if a[1] > b[1]]
                print(r['match'][10:], p['tick'], (tx, ty), seq[0] if seq else None, d[:4])
                if d:
                    drops[d[0][1]] += 1
print('first drop after the play (hp):', drops.most_common(8))
