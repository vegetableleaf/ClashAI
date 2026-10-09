"""Live Log evidence (archive glob): (1) Log taps by model-frame y (enemy half y < 0.5) and how many were confirmed (hand
rotation) -- is the Log refused on the enemy half? (2) Log hits on ENEMY CROWN TOWERS: HP drop of an enemy princess in
the first snapshot after the tap whose drop is 30-80 HP (one Log at level 11-15 = 35-51), the cast xy, the tower, and
decision tick -> hit tick (upper bound: ~10-tick snapshots).  python log_timing.py "<glob>" """
import glob, json, sys
from collections import Counter
import numpy as np

files = sorted(glob.glob(sys.argv[1]))
taps, hits = Counter(), []
for f in files:
    ev = []
    for line in open(f):
        try:
            ev.append(json.loads(line))
        except ValueError:
            pass
    dec = [e for e in ev if e.get('event') == 'decision' and 'public' in e]
    if not dec:
        continue
    side = dec[0]['public']['observer_side']
    confs = [e for e in ev if e.get('event') in ('confirmed', 'unconfirmed')]
    for p in (e for e in ev if e.get('event') == 'play' and e.get('name') == 'Log'):
        xy = p['xy']
        c = next((c for c in confs if c['tick'] >= p['tick'] and c['name'] == 'Log'), None)
        half = 'enemy_half' if xy[1] < 0.5 else 'own_half'
        taps[(half, c['event'] if c else 'none')] += 1
        if c is None or c['event'] != 'confirmed':
            continue

        def towers(d):
            return {(b['x'], b['y']): b['hp'] for b in d['public']['raw_bodies']
                    if b.get('card_id') == -1 and b['side'] != side and b.get('kind') in (12, 13) and b['max_hp'] < 6000}
        before = next((d for d in reversed(dec) if d['tick'] <= p['tick']), None)
        if before is None:
            continue
        t0 = towers(before)
        prev = t0
        for d in dec:
            if not p['tick'] < d['tick'] <= p['tick'] + 120:
                continue
            t1 = towers(d)
            drop = [(k, prev[k] - t1[k]) for k in prev if k in t1 and 30 <= prev[k] - t1[k] <= 80]
            if drop:
                k, dmg = drop[0]
                tx, ty = (k[0], k[1]) if side == 0 else (18000 - k[0], 32000 - k[1])   # my frame, raw units
                hits.append(dict(file=f[-20:], tap=p['tick'], conf=c['tick'], hit=d['tick'], dmg=dmg,
                                 cast=(round(xy[0] * 18, 2), round(xy[1] * 32, 2)),
                                 tower=(tx / 1000, round(32 - ty / 1000, 2))))
                break
            prev = {k: t1.get(k, v) for k, v in prev.items()}
print('Log taps (half, confirm):', dict(taps))
print(f'Log hits on an enemy princess (drop 30-80 HP in one snapshot): {len(hits)}')
if hits:
    a = np.array([[h['conf'] - h['tap'], h['hit'] - h['conf'], h['hit'] - h['tap']] for h in hits])
    for j, nm in enumerate(('confirm-tap', 'hit-confirm', 'hit-tap')):
        print(f'  {nm}: min {a[:, j].min()} median {np.median(a[:, j]):.0f} max {a[:, j].max()}')
    print('  HP drops:', sorted(Counter(h['dmg'] for h in hits).items()))
    print('  cast (x, y board tiles; enemy princess y 6.5) / tower:',
          sorted(Counter((h['cast'], h['tower']) for h in hits).items())[:20])
