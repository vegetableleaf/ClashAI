"""Replay one live log through the wired live lethal rule (GenPilot.lethal_rocket) WITH the in-flight guard: my
confirmed plays (confirmed events: card, intended xy, confirm tick) feed GenPilot.past exactly as live_play's
record_play does; every logged decision snapshot is one call (no model).  python live_case.py <log> [t0 t1] [--mode ...]
Prints every decision in [t0, t1]: tick, enemy princess HP, the rule's choice."""
import json, os, sys
from types import SimpleNamespace
import numpy as np

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../..")))
from pipeline.dataset_gen import card_key
from pipeline.decision_options import DecisionOptions, enemy_princess_hps
from pipeline.e1_eval import allowed_slots
from pipeline.live_gen_v2 import GenPilot
from pipeline.live_mem import to_observe

log = sys.argv[1]
t0, t1 = (int(sys.argv[2]), int(sys.argv[3])) if len(sys.argv) > 3 and not sys.argv[2].startswith('--') else (0, 10 ** 9)
ev = [json.loads(l) for l in open(log) if l.strip().startswith('{')]
dec = [e for e in ev if e.get('event') == 'decision' and 'public' in e]
names = [None] * 8
for d in dec:
    for h in d['public']['own_hand']:
        if h['deck_index'] >= 0:
            names[h['deck_index']] = h['name']
gid = {card_key(n): i + 1 for i, n in enumerate(names)}
pilot = object.__new__(GenPilot)
pilot.decision_options = DecisionOptions(lethal_rocket='ot_behind', lethal_log='on')
pilot.grid, pilot.gid, pilot.past = 'lattice', gid, []
conf = sorted((e for e in ev if e.get('event') == 'confirmed'), key=lambda e: e['tick'])
ci = 0
for d in dec:
    p = d['public']
    while ci < len(conf) and conf[ci]['tick'] <= p['raw_tick']:     # record_play at the confirmation frame
        c = conf[ci]
        pilot.past.append((gid[card_key(c['name'])], 0, c['intended'][0], c['intended'][1], c['tick'] * 0.05))
        ci += 1
    side, hdi = p['observer_side'], [h['deck_index'] for h in p['own_hand']]
    me = dict(side=side, elixir_raw=int(p['own_elixir_raw'] * 1e4), next_deck_index=-1, hand_deck_indices=hdi)
    frame = dict(game_tick=p['raw_tick'], entities=p['raw_bodies'],
                 players=[me, dict(side=1 - side, elixir_raw=0, next_deck_index=-1, hand_deck_indices=[-1] * 4)])
    allowed = allowed_slots(np.array([h['card'] > 0 for h in p['own_hand']]), [h['cost'] for h in p['own_hand']],
                            int(p['model_own_elixir']))
    hit = pilot.lethal_rocket(frame, dict(names=names, hand_deck_indices=hdi,
                                          bs=SimpleNamespace(t_sec=p['model_tick'] * .05)), allowed)
    if t0 <= p['raw_tick'] <= t1:
        hps = enemy_princess_hps(to_observe(frame, side, names)['episode']['crown_towers'], side)
        print(p['raw_tick'], 'model_t %.2f' % (p['model_tick'] * .05), 'enemy', hps,
              'hand', [h['name'] for h in p['own_hand']], 'el', int(p['model_own_elixir']),
              '->', None if hit is None else (names[hdi[hit[0]]], hit[2]),
              '| logged', d['decision'].get('name'), d['decision'].get('play'))
