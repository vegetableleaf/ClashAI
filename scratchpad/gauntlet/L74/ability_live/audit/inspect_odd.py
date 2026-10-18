"""List the presses whose truth is not 'ready' (no IW / spent / pending / no elixir / the IW body without the ability)."""
import json
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
R = json.loads((HERE / 'press_rows.json').read_text())
for r in R:
    if r.get('truth') not in ('ready', 'no_phase2'):
        print(r['mark'], r['log'][10:], r['tick'], r['truth'], 'nIW', r.get('n_own_iw'), 'hero', r.get('rule_hero_name'),
              'eff', r.get('effect_state'), (r.get('effect_tick') or 0) - r['tick'], 'cube', r.get('cube_tick') and
              r['cube_tick'] - r['tick'], 'frozen', r.get('n_frozen'), r.get('frozen_value'), '|', r['why'][:60])
print(Counter((r['mark'], r.get('truth')) for r in R if r.get('n_own_iw') == 2))
