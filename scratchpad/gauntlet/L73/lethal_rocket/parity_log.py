"""OFFLINE PARITY: feed logged live decisions through the wired live rule (GenPilot.lethal_rocket, live_gen_v2) with
--lethal-rocket ot.  python parity_log.py <live_play_*.jsonl glob> [--first-only]
Per decision the logged public snapshot gives the reader frame's bodies (raw_bodies = the frame's entities, towers
included, absolute HP), my hand (own_hand deck indices / names / costs), my model-board elixir and model tick. Not
logged: the full player block (only what to_observe reads is rebuilt: side, hand, elixir). No model is run: the rule
does not read the model. Reports every decision where the rule fires and the first one per match."""
import glob, json, os, sys
from types import SimpleNamespace
import numpy as np

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../..")))
from pipeline.decision_options import DecisionOptions, phase_index
from pipeline.e1_eval import allowed_slots
from pipeline.live_gen_v2 import GenPilot

pilot = object.__new__(GenPilot)
pilot.decision_options, pilot.grid = DecisionOptions(lethal_rocket='ot'), 'lattice'
files = sorted(glob.glob(sys.argv[1]))
first_only = '--first-only' in sys.argv
tot = dict(matches=0, fired_matches=0, fires=0, reg_fires=0)
for f in files:
    dec = []
    for line in open(f):
        try:
            d = json.loads(line)
        except ValueError:
            continue
        if d.get('event') == 'decision' and 'public' in d:
            dec.append(d)
    if not dec:
        continue
    tot['matches'] += 1
    names = [None] * 8
    for d in dec:
        for h in d['public']['own_hand']:
            if h['deck_index'] >= 0:
                names[h['deck_index']] = h['name']
    fires = []
    for d in dec:
        p = d['public']
        side = p['observer_side']
        hdi = [h['deck_index'] for h in p['own_hand']]
        me = dict(side=side, elixir_raw=int(p['own_elixir_raw'] * 1e4), next_deck_index=-1, hand_deck_indices=hdi)
        foe = dict(side=1 - side, elixir_raw=0, next_deck_index=-1, hand_deck_indices=[-1] * 4)
        frame = dict(game_tick=p['raw_tick'], players=[me, foe], entities=p['raw_bodies'])
        t = p['model_tick'] * 0.05
        info = dict(names=names, hand_deck_indices=hdi, bs=SimpleNamespace(t_sec=t))
        allowed = allowed_slots(np.array([h['card'] > 0 for h in p['own_hand']]), [h['cost'] for h in p['own_hand']],
                                int(p['model_own_elixir']))
        hit = pilot.lethal_rocket(frame, info, allowed)
        if hit is not None:
            fires.append((d['tick'], round(t, 2), hit[2], d['decision'].get('name'), d['decision'].get('play'),
                          round(d['decision']['p_play'], 3)))
            tot['reg_fires'] += phase_index([t])[0] != 2
    tot['fires'] += len(fires)
    tot['fired_matches'] += bool(fires)
    if fires:
        print(os.path.basename(f), 'side', dec[0]['public']['observer_side'], 'fires', len(fires))
        for x in fires[:1] if first_only else fires:
            print('   tick %d model_t %.2f target %s | logged: %s play=%s p=%.3f' % (x[0], x[1], x[2], x[3], x[4], x[5]))
print(tot)
