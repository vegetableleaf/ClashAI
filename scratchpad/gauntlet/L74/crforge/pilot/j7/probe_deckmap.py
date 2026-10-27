"""A2b-2b probe: is fin_run's catalogue -> internal card mapping (fights' H-DECKMAP rule) right for a J7 match?
    PYTHONPATH=<tree> python probe_deckmap.py PLAN.json
Prints, per side, the public deck / hand and the save's hand + queue after the tick-0 reset, the mapping, and what the save
names each internal id (when it carries card records)."""
import json, sys
from scratchpad.gauntlet.L74.crforge.pilot.j7 import fin_run as R

plan = json.load(open(sys.argv[1]))
eng = R.engine(plan['match']); b = eng.b
decks = [[eng.ids[n] for n in plan['display'][s]] for s in (0, 1)]
forms = [[{1: 1, 2: 2}.get(f, 0) for f in plan['slots'][s]] for s in (0, 1)]
b.reset(1, decks, 0, 0, None, None, [], forms=forms, levels=plan['levels'], tower_levels=[16, 16])
sv = json.loads(b.save()); pub = json.loads(b.state_json())
print('save keys', sorted(sv)[:40])
print('player save keys', sorted(sv['players'][0]))
for t in (0, 1):
    pp, sp = pub['players'][t], sv['players'][t]
    print('side', t, 'deck', [(c, eng.cat[c]['name']) for c in pp['deck']], 'hand', pp['hand'], 'next', pp.get('next_card'))
    print('   save hand', sp['hand'], 'queue', sp['queue'])
    mono = dict(zip(sorted(pp['deck']), sorted(sp['hand'] + sp['queue'])))
    mono.update(dict(zip(pp['hand'] + ([pp['next_card']] if pp.get('next_card') is not None else []), sp['hand'] + sp['queue'][:1])))
    print('   map', {eng.cat[c]['name']: v for c, v in mono.items()})
print('save decks', sv['decks'], 'forms', sv['forms'], 'deck_levels', sv['deck_levels'])
print('input decks', decks)
for k in ('cards', 'card_records', 'records'):
    if k in sv:
        recs = sv[k]
        print(k, len(recs), [(i, r.get('name') if isinstance(r, dict) else r) for i, r in enumerate(recs)][:60])
