"""Self-check of bp_rules.press_from_drop (SME_BP_PRESS). python -I test_press.py"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import bp_rules

sides = {'0': {'role': 'opp'}, '1': {'role': 'us'}}
el = {3481: 83117, 3483: 83831, 3485: 64545, 3487: 65259, 3649: 95000, 3651: 95357, 3653: 95714}
frames = {t: {'el': e} for t, e in el.items()}
cast = {'side': 1, 'kind': 'ability', 'card': 'IceWizard', 'tick': 3651, 'run_ticks': [3651, 3651], 'source': 'cast_seen'}
out = bp_rules.press_from_drop([cast], frames, sides)
assert out[0]['run_ticks'] == [3483, 3484] and out[0]['tick'] == 3484, out          # 094126: the drop 3483 -> 3485
play = {'side': 1, 'kind': 'play', 'card': 'Log', 'tick': 3484, 'run_ticks': [3484, 3484]}
assert bp_rules.press_from_drop([play, cast], frames, sides)[1] == cast             # a card play explains the drop
opp = dict(cast, side=0)
assert bp_rules.press_from_drop([opp], frames, sides)[0] == opp                     # the opponent's casts: untouched
own = dict(cast, source='own_press')
assert bp_rules.press_from_drop([own], frames, sides)[0] == own                     # tap-dated presses: untouched
far = dict(cast, tick=3851, run_ticks=[3851, 3851])
assert bp_rules.press_from_drop([far], frames, sides)[0] == far                     # beyond PRESS_BEFORE
print('ok')
