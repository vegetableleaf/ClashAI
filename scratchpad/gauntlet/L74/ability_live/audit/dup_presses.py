"""IW bodies (log, generation) with more than one press: each press's truth, effect, cube."""
import json
from collections import defaultdict
from pathlib import Path
R = json.loads((Path(__file__).resolve().parent / 'press_rows.json').read_text())
g = defaultdict(list)
for r in R:
    if r.get('iw_gen'):
        g[(r['mark'], r['log'], r['iw_gen'])].append(r)
for k, rs in g.items():
    if len(rs) > 1:
        print(k[0], k[1][10:], k[2], [(r['tick'], r['truth'], r.get('n_own_iw'), r.get('effect_state'), r.get('cube_tick'), r['why'][:9]) for r in rs])
