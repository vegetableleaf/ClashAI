"""Every-frame counterfactual of the live lethal rule (after the verifier's L73 v4 counterfactual): the wired GenPilot
(--lethal-rocket ot_behind --lethal-log on) sees the recorded reader FRAMES. Before T0 it decides (= snapshots) only on
frames with no play pending, my confirmed plays feeding ``past`` as live_play's record_play; from T0 to T1 it decides
on EVERY frame, never acting (as if every lethal decision were held), hand / allowed slots from the decision at HAND_TICK
(default T0). Model board = raw + LA for LA in (24, 26).
  python replay_frames.py <log> T0 T1 [HAND_TICK]"""
import json, os, sys
from types import SimpleNamespace
import numpy as np

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../..")))
from pipeline.dataset_gen import card_key
from pipeline.decision_options import DecisionOptions, enemy_princess_hps
from pipeline.e1_eval import allowed_slots
from pipeline.live_gen_v2 import GenPilot
from pipeline.live_mem import to_observe

F, T0, T1 = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
HT = int(sys.argv[4]) if len(sys.argv) > 4 else T0
KEYS = ('side', 'x', 'y', 'card_id', 'hp', 'max_hp', 'kind', 'address')
ev = [json.loads(l) for l in open(F) if l.strip().startswith('{')]
dec = [e for e in ev if e.get('event') == 'decision' and 'public' in e]
names = [None] * 8
for d in dec:
    for h in d['public']['own_hand']:
        if h['deck_index'] >= 0:
            names[h['deck_index']] = h['name']
gid = {card_key(n): i + 1 for i, n in enumerate(names) if n}
dh = min(dec, key=lambda d: abs(d['public']['raw_tick'] - HT))['public']
side, hdi = dh['observer_side'], [h['deck_index'] for h in dh['own_hand']]
allowed = allowed_slots(np.array([h['card'] > 0 for h in dh['own_hand']]), [h['cost'] for h in dh['own_hand']], 8)
print(f'{os.path.basename(F)}: hand {[names[i] for i in hdi]} (decision {dh["raw_tick"]}); my confirmed spells',
      [(e['tick'], e['name']) for e in ev if e.get('event') == 'confirmed' and e['name'] in ('Rocket', 'Log')
       and T0 - 200 < e['tick'] <= T1])
for LA in (24, 26):
    p = object.__new__(GenPilot)
    p.decision_options = DecisionOptions(lethal_rocket='ot_behind', lethal_log='on')
    p.grid, p.gid, p.past = 'lattice', gid, []
    pending, fires = False, []
    for e in ev:
        k, t = e.get('event'), e.get('tick', 0)
        if t > T1:
            break
        if k == 'play' and t < T0:
            pending = True
        elif k in ('confirmed', 'unconfirmed') and t < T0:
            pending = False
            if k == 'confirmed':
                p.past.append((gid[card_key(e['name'])], 0, e['intended'][0], e['intended'][1], t * .05))
        elif k == 'frame' and (not pending or t >= T0):
            frame = dict(game_tick=t, entities=[dict(zip(KEYS, r)) for r in e['ents']],
                         players=[dict(side=side, elixir_raw=80000, next_deck_index=-1, hand_deck_indices=hdi),
                                  dict(side=1 - side, elixir_raw=0, next_deck_index=-1, hand_deck_indices=[-1] * 4)])
            p._lethal_snapshot(frame, names=names)
            if t >= T0:
                h = p.lethal_rocket(frame, dict(names=names, hand_deck_indices=hdi, bs=SimpleNamespace(t_sec=(t + LA) * .05)),
                                    allowed)
                hps = enemy_princess_hps(to_observe(frame, side, names)['episode']['crown_towers'], side)
                fires.append((t, hps, None if h is None else (names[hdi[h[0]]], h[2]['lane'], h[2]['hp'])))
    print(f'LA {LA}: frames {len(fires)}; fires at', [(t, f) for t, _, f in fires if f] or 'none')
    print('   tower HP by frame:', [(t, hps) for t, hps, _ in fires][::3])
