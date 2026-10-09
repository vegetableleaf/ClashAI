"""Which live decisions make lethal_rocket_target's tower-level rule read an impossible card level (verifier: level 8
in 2,978 of 152,711 decisions, 10-08/09)?  python level8_scan.py "<glob>"
Per decision: to_observe(raw_bodies) crown rows, the row lethal_rocket_target uses (``mine`` = my FIRST crown row with a
max_hp), its type / max HP / position, the level it maps to; plus tick, phase and whether the gated lethal rule could be
reached (OT, or regulation while behind on crowns)."""
import glob, json, os, sys
from collections import Counter

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../..")))
from pipeline.body_identity import level_of_factor
from pipeline.decision_options import crowns_behind
from pipeline.live_mem import to_observe

tot, bad, ex = Counter(), Counter(), {}
for f in sorted(glob.glob(sys.argv[1])):
    for line in open(f):
        if '"decision"' not in line:
            continue
        try:
            d = json.loads(line)
        except ValueError:
            continue
        if d.get('event') != 'decision' or 'public' not in d:
            continue
        p = d['public']
        side = p['observer_side']
        me = dict(side=side, elixir_raw=0, next_deck_index=-1, hand_deck_indices=[h['deck_index'] for h in p['own_hand']])
        frame = dict(game_tick=p['raw_tick'], entities=p['raw_bodies'],
                     players=[me, dict(side=1 - side, elixir_raw=0, next_deck_index=-1, hand_deck_indices=[-1] * 4)])
        towers = to_observe(frame, side, [None] * 8)['episode']['crown_towers']
        mine = next((t for t in towers if int(t['side']) == side and t.get('max_hp')), None)
        tot['decisions'] += 1
        if mine is None:
            tot['no_my_tower'] += 1
            continue
        level = level_of_factor(float(mine['max_hp']) / (4824.0 if mine.get('type') == 'king' else 3052.0))
        tot[f'level_{level}'] += 1
        if level is not None and level < 9:
            ot = p['model_tick'] >= 3600
            behind = crowns_behind(towers, side)
            key = (mine['type'], mine['max_hp'], mine['x'], mine['y'], 'OT' if ot else ('reg_behind' if behind else 'reg'))
            bad[key] += 1
            ex.setdefault(key, (os.path.basename(f), p['raw_tick'],
                                sorted((t['side'], t['type'], t['x'], t['y'], t['hp'], t['max_hp']) for t in towers)))
print(dict(tot))
for k, n in bad.most_common(20):
    print(n, k, '| e.g.', ex[k][0], 'tick', ex[k][1], ex[k][2])
