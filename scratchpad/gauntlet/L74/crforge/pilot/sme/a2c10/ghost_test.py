"""A2c-10 self-check for SME_IWGHOST10 (laptop: needs the raw live log of 211239).
python -I ghost_test.py  -> 'ok N' or an AssertionError."""
import os
import sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
os.environ['SME_IWGHOST10'] = '1'
import mech_rules  # noqa: E402
import sme_live  # noqa: E402

LOG = os.path.join(HERE, '../../../../../L68/live_reader/live_play_20261026_211239.jsonl')
n = 0
# 1. 211239: side 1's hero IW played 4366 (valid target only over [4511, 4762], gone after 4910) gets one ghost press whose
#    window holds 4892, the press that makes the match exact; a hero with a cast in its life gets none.
plays = [dict(side=1, kind='play', card='IceWizard', deck_index=1, name='IceWizard', form=2, run_ticks=[4366, 4366], tick=4366,
              x=499, y=25499),
         dict(side=1, kind='play', card='IceWizard', deck_index=1, name='IceWizard', form=2, run_ticks=[5101, 5101], tick=5101,
              x=7499, y=31000),
         dict(side=1, kind='ability', card='IceWizard', deck_index=1, name='IceWizard', form=0, run_ticks=[5262, 5262], tick=5262,
              source='cast_seen')]
out = mech_rules.iw_ghosts(LOG, plays, 0)
g = [p for p in out if p.get('ghost')]
assert len(g) == 1 and g[0]['run_ticks'][0] == 4763 and g[0]['run_ticks'][0] <= 4892 <= g[0]['run_ticks'][1], g
n += 1
# 2. our own heroes are never ghosted
assert not [p for p in mech_rules.iw_ghosts(LOG, [dict(plays[0], side=0)], 0) if p.get('ghost')]
n += 1
# 3. the fitter: a ghost (kind skip) is tried only when its hero diverges, at R in [d - 4, d - 1] inside its window
plan = {'cmds': [{'kind': 'play', 'run': 4366, 'given': 4346, 'side': 1, 'card': 'IceWizard', '_src': {'lo': 4366, 'hi': 4366, 'tick': 4366, 'own': False}},
                 {'kind': 'skip', 'run': 4763, 'given': 4743, 'side': 1, 'unit': 'cmd0_0',
                  '_src': {'lo': 4763, 'hi': 4910, 'tick': 4763, 'own': False, 'ghost': 1}}]}
assert sme_live.variants_at(plan, 4894, 6000, frozenset()) == []
v = sme_live.variants_at(plan, 4894, 6000, {'cmd0'})
assert [c['run'] for i, c in v] == [4890, 4891, 4892, 4893] and all(i == 1 and c['kind'] == 'ability' for i, c in v), v
assert [c['run'] for i, c in sme_live.variants_at(plan, 4912, 6000, {'cmd0'})] == [4908, 4909, 4910]   # not past the window
n += 1
# 4. plan_from writes a ghost as kind skip, so an unfitted plan runs exactly as without it
rec = {'my_side': 0, 'sides': {k: {'deck': ['IceWizard'] * 8, 'levels': [16] * 8, 'word': 0, 'slot_flags': [0] * 8,
                                   'towers': {'king_level': 16, 'level': 16, 'group': 0}} for k in ('0', '1')},
       'deal': {'0': list(range(8)), '1': None}, 'plays': [plays[0], g[0]]}
c = sme_live.plan_from(rec, list(range(8)))['cmds']
assert c[1]['kind'] == 'skip' and c[1]['unit'] == 'cmd0_0' and c[1]['_src']['ghost'] == 1 and \
    'skip' not in [x['kind'] for x in sme_live.plan_from(dict(rec, plays=[plays[0]]), list(range(8)))['cmds']], c
n += 1
print('ok', n)
