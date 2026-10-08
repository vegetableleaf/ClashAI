"""Lethal-Rocket OPPORTUNITIES: continuous stretches >= 3 s where an enemy princess is alive at <= 497 HP (measured Rocket
tower damage, match 131352), Rocket is in my hand and I hold >= 6 elixir. Outcome per stretch: Rocket on the lethal
tower / Rocket elsewhere / no Rocket."""
import glob, json, sys
from collections import Counter

DMG, MIN_S = 497, 3.0
files = sorted(glob.glob(sys.argv[1] if len(sys.argv) > 1 else
                         'scratchpad/gauntlet/L68/live_reader/live_play_2026100[5-8]_*.jsonl'))
out, rows = Counter(), []
for f in files:
    ckpt, seq = '?', []
    for line in open(f):
        try:
            d = json.loads(line)
        except ValueError:
            continue
        e = d.get('event')
        if e == 'start':
            ckpt = str(d.get('ckpt', '?')).replace('\\', '/').split('/')[-1][:44]
        elif e == 'decision':
            pub = d['public']
            side = pub['observer_side']
            en = {t['lane']: t for t in pub['model_towers'] if t['side'] == 1 and t['kind'] == 'princess' and t['alive']}
            hp = {}
            for b in pub['raw_bodies']:
                if b.get('card_id') == -1 and b['side'] != side and b['max_hp'] < 6000:
                    for lane, t in en.items():
                        if abs(b['hp'] / b['max_hp'] - t['hp_frac']) < 1e-3:
                            hp[lane] = b['hp']
            kill = sorted(k for k, v in hp.items() if 0 < v <= DMG)
            hand = [c.get('name') for c in pub.get('own_hand', []) if isinstance(c, dict)]
            ok = bool(kill) and 'Rocket' in hand and float(pub['model_own_elixir'] or 0) >= 6
            seq.append(('D', int(d['tick']), ok, kill, hp, d['decision'].get('p_play')))
        elif e == 'play':
            xy = d['xy']
            xy = json.loads(xy) if isinstance(xy, str) else xy
            seq.append(('P', int(d['tick']), d.get('name'), xy))
    i = 0
    while i < len(seq):
        if seq[i][0] == 'D' and seq[i][2]:
            j, plays = i, []
            while j + 1 < len(seq) and (seq[j + 1][0] == 'P' or seq[j + 1][2]):
                j += 1
                if seq[j][0] == 'P':
                    plays.append(seq[j])
            t0, t1 = seq[i][1], seq[j][1]
            if (t1 - t0) / 20 >= MIN_S or any(p[2] == 'Rocket' for p in plays):
                kill, rk = seq[i][3], [p for p in plays if p[2] == 'Rocket']
                if rk:
                    lane = 'L' if rk[0][3][0] < 0.5 else 'R'
                    res = 'rocket_lethal' if lane in kill and rk[0][3][1] < 0.35 else 'rocket_elsewhere'
                else:
                    res = 'no_rocket'
                ph = 'OT' if t0 >= 3600 else 'reg'
                out[(ph, res)] += 1
                other = [p[2] for p in plays if p[2] != 'Rocket']
                rows.append((f.split('_', 2)[-1][:15], ckpt[-24:], ph, t0, round((t1 - t0) / 20, 1), seq[i][4], res,
                             'other_plays', len(other), other[:6]))
            i = j + 1
        else:
            i += 1
for k in sorted(out):
    print(k, out[k])
for r in rows:
    print(r)
