"""Does the GATED live lethal rule (GenPilot.lethal_rocket, the real phase / crown / hand / elixir gates) reach an
impossible card level on the low-level matches? Replays every logged decision (live_case.py's feeding: confirmed plays
-> past) with --lethal-rocket ot_behind --lethal-log on [--card-levels ...] and reports exceptions and fires.
  python level8_gate.py "<glob>" [NAME=LEVEL ...]"""
import glob, json, os, sys, traceback
from types import SimpleNamespace
from collections import Counter
import numpy as np

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../..")))
from pipeline.dataset_gen import card_key
from pipeline.decision_options import DecisionOptions
from pipeline.e1_eval import allowed_slots
from pipeline.live_gen_v2 import GenPilot

levels = sys.argv[2:] or None
tot, errs, fires = Counter(), Counter(), []
for f in sorted(glob.glob(sys.argv[1])):
    ev = [json.loads(l) for l in open(f) if l.strip().startswith('{')]
    dec = [e for e in ev if e.get('event') == 'decision' and 'public' in e]
    names = [None] * 8
    for d in dec:
        for h in d['public']['own_hand']:
            if h['deck_index'] >= 0:
                names[h['deck_index']] = h['name']
    gid = {card_key(n): i + 1 for i, n in enumerate(names) if n}
    p_ = object.__new__(GenPilot)
    p_.decision_options = DecisionOptions(lethal_rocket='ot_behind', lethal_log='on', card_levels=levels)
    p_.grid, p_.gid, p_.past = 'lattice', gid, []
    conf = sorted((e for e in ev if e.get('event') == 'confirmed'), key=lambda e: e['tick'])
    ci = 0
    for d in dec:
        p = d['public']
        while ci < len(conf) and conf[ci]['tick'] <= p['raw_tick']:
            c = conf[ci]
            if card_key(c['name']) in gid:
                p_.past.append((gid[card_key(c['name'])], 0, c['intended'][0], c['intended'][1], c['tick'] * .05))
            ci += 1
        side, hdi = p['observer_side'], [h['deck_index'] for h in p['own_hand']]
        me = dict(side=side, elixir_raw=int(p['own_elixir_raw'] * 1e4), next_deck_index=-1, hand_deck_indices=hdi)
        frame = dict(game_tick=p['raw_tick'], entities=p['raw_bodies'],
                     players=[me, dict(side=1 - side, elixir_raw=0, next_deck_index=-1, hand_deck_indices=[-1] * 4)])
        allowed = allowed_slots(np.array([h['card'] > 0 for h in p['own_hand']]), [h['cost'] for h in p['own_hand']],
                                int(p['model_own_elixir']))
        tot['decisions'] += 1
        try:
            h = p_.lethal_rocket(frame, dict(names=names, hand_deck_indices=hdi,
                                             bs=SimpleNamespace(t_sec=p['model_tick'] * .05)), allowed)
        except Exception as exc:                                 # noqa: BLE001 -- the question is whether it raises
            errs[(os.path.basename(f), repr(exc))] += 1
            continue
        if h is not None:
            fires.append((os.path.basename(f), p['raw_tick'], names[hdi[h[0]]], h[2]))
print(dict(tot), 'card_levels', levels)
print('exceptions:', sum(errs.values()), dict(errs))
print('fires:', len(fires))
for x in fires[:30]:
    print('  ', x)
