"""Owner 2026-10-08 23:xx: "the model cast rocket on a fallen tower". Find live Rockets aimed within 3 tiles of an enemy
princess position whose tower was already dead at the decision, with the decision path (why / lethal fields)."""
import glob, json, sys

files = sorted(glob.glob(sys.argv[1] if len(sys.argv) > 1 else
                         'scratchpad/gauntlet/L68/live_reader/live_play_20261008_2*.jsonl'))
PRINCESS = {'L': (3.5 / 18, 6.5 / 32), 'R': (14.5 / 18, 6.5 / 32)}   # enemy princess centres, model frame (x/18, y/32)
n_rk = n_dead = 0
for f in files:
    last = None
    for line in open(f, encoding='utf-8', errors='replace'):
        try:
            d = json.loads(line)
        except ValueError:
            continue
        e = d.get('event')
        if e == 'decision':
            last = d
        elif e == 'play' and d.get('name') == 'Rocket' and last is not None:
            n_rk += 1
            xy = d['xy'] if isinstance(d['xy'], list) else json.loads(d['xy'])
            towers = {t['lane']: t for t in last['public']['model_towers'] if t['side'] == 1 and t['kind'] == 'princess'}
            for lane, (cx, cy) in PRINCESS.items():
                dist = (((xy[0] - cx) * 18) ** 2 + ((xy[1] - cy) * 32) ** 2) ** 0.5
                t = towers.get(lane)
                if dist <= 3.0 and (t is None or not t['alive']):
                    n_dead += 1
                    dec = last['decision']
                    enemies = [(round(b['x'], 2), round(b['y'], 2)) for b in last['public']['model_bodies'] if b['side'] == 1
                               and ((b['x'] - xy[0]) * 18) ** 2 + ((b['y'] - xy[1]) * 32) ** 2 <= 4.0]
                    print(f.split('_', 2)[-1], 'tick', d['tick'], 'xy', [round(v, 3) for v in xy], 'dead lane', lane,
                          'dist', round(dist, 1), '| why', dec.get('why'), 'lethal', dec.get('lethal_rocket'),
                          '| enemy bodies within 2 t of impact:', len(enemies), '| towers',
                          {k: (round(v['hp_frac'], 2), v['alive']) for k, v in towers.items()})
print('rockets', n_rk, 'aimed at a dead princess position', n_dead)
