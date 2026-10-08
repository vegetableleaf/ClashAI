"""How often was a LETHAL Rocket available live (an enemy princess at <= ROCKET_TOWER_DMG HP, Rocket in hand, enough
elixir) and what did the bot do?  Measured Rocket tower damage: 497 (match 131352, tick 4304: 1092 -> 595)."""
import glob, json, sys
from collections import Counter

DMG = 497
files = sorted(glob.glob(sys.argv[1] if len(sys.argv) > 1 else
                         'scratchpad/gauntlet/L68/live_reader/live_play_2026100[5-8]_*.jsonl'))
tally, cases = Counter(), []
for f in files:
    ckpt, opp, decs = '?', None, []
    for line in open(f):
        try:
            d = json.loads(line)
        except ValueError:
            continue
        e = d.get('event')
        if e == 'start':
            ckpt = str(d.get('ckpt', '?')).replace('\\', '/').split('/')[-1][:40]
        elif e == 'decision':
            pub = d['public']
            side = pub['observer_side']
            # enemy princesses in the MODEL frame: model_towers lane L/R; absolute hp from raw (towers card_id -1)
            en = {t['lane']: t for t in pub['model_towers'] if t['side'] == 1 and t['kind'] == 'princess'}
            raw = [b for b in pub['raw_bodies'] if b.get('card_id') == -1 and b['side'] != side and b['max_hp'] < 6000]
            hp = {}
            for b in raw:                       # match raw princess to model lane by hp fraction
                for lane, t in en.items():
                    if t['alive'] and abs(b['hp'] / b['max_hp'] - t['hp_frac']) < 1e-3:
                        hp[lane] = b['hp']
            hand = [c.get('name') if isinstance(c, dict) else c for c in pub.get('own_hand', [])]
            decs.append((int(d['tick']), hp, 'Rocket' in str(hand), float(pub['model_own_elixir'] or 0), d['decision']))
        elif e == 'play' and d.get('name') == 'Rocket':
            decs.append((int(d['tick']), 'PLAY', d['xy']))
    # lethal windows: decisions where some enemy princess <= DMG
    lethal = [x for x in decs if x[1] != 'PLAY' and any(v <= DMG for v in x[1].values())]
    if not lethal:
        continue
    plays = [x for x in decs if x[1] == 'PLAY' and x[0] >= lethal[0][0]]
    for t, _, xy in plays:
        xy = json.loads(xy) if isinstance(xy, str) else xy
        at = [x for x in lethal if x[0] <= t]
        if not at or t - at[-1][0] > 40:
            continue
        hp = at[-1][1]
        lane = 'L' if xy[0] < 0.5 else 'R'
        killable = [k for k, v in hp.items() if v <= DMG]
        tally['rocket_in_lethal_window'] += 1
        tally['hit_lethal_tower' if lane in killable and xy[1] < 0.35 else 'missed_lethal_tower'] += 1
        cases.append((f.split('_', 2)[-1], ckpt, t, hp, lane, round(xy[1], 3)))
    afford = [x for x in lethal if x[2] and x[3] >= 6]
    tally['matches_with_lethal_window'] += 1
    tally['lethal_affordable_decisions'] += len(afford)
    if afford:
        tally['matches_lethal_affordable'] += 1
        first = afford[0][0]
        took = [c for c in cases if c[0] == f.split('_', 2)[-1] and c[2] >= first]
        cases.append((f.split('_', 2)[-1], ckpt, 'affordable_from', first, 'ot' if first >= 3600 else 'reg',
                      'span_s', round((afford[-1][0] - first) / 20, 1), 'rockets_after', len(took)))
print(dict(tally))
for c in cases:
    print(c)
