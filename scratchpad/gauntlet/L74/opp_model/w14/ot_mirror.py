"""W14 round 4b input: nextround/ot_states.json MIRRORED for opponent training. In W14's runs the LEARNER is the
opponent-to-be, so the learner must start from the live opponent's 3:00 state and the icebow side from CLX's:
own' = opp reversed into the opponent's own frame, opp' = own reversed (rl_royale.draw_ot_start reverses opp again).
Elixir stays CLX's (the opponent's is not observed live), as W15's rule for the non-learner side.
    python scratchpad/gauntlet/L74/opp_model/w14/ot_mirror.py -> w14/ot_states_mirror.json"""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
d = json.loads((HERE.parents[1] / 'nextround/ot_states.json').read_text(encoding='utf-8'))
for s in d['states']:
    s['own'], s['opp'] = list(s['opp'])[::-1], list(s['own'])[::-1]
d['source'] += ' + w14/ot_mirror.py (own <-> opp, each reversed: the learner is the opponent-to-be)'
d['summary'] = {k: v for k, v in d['summary'].items() if k in ('n', 'elixir_median', 'elixir_mean')}
(HERE / 'ot_states_mirror.json').write_text(json.dumps(d), encoding='utf-8')
behind = sum(min(s['own']) < min(s['opp']) - .1 for s in d['states']) / len(d['states'])
print(len(d['states']), 'states; learner (opponent) behind by > 0.1 at 3:00:', round(behind, 3))
