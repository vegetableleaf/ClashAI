"""iw_wincon presses: Tesla in hand or not, elixir at the decision, wincon named; clump presses: elixir."""
import json, re
from collections import Counter
from pathlib import Path
R = json.loads((Path(__file__).resolve().parent / 'press_rows.json').read_text())
for mark in ('CXXXVIII', 'CXXIV'):
    w = [r for r in R if r['mark'] == mark and r['kind'] == 'iw_wincon']
    c = [r for r in R if r['mark'] == mark and r['kind'] == 'iw_clump']
    tes = Counter(re.search(r'tesla_in_hand=(\w+)', r['why']).group(1) for r in w)
    el = sorted(r['elixir_at'] for r in w)
    elc = sorted(r['elixir_at'] for r in c)
    print(mark, 'wincon presses', len(w), 'tesla_in_hand', dict(tes), 'elixir med', round(el[len(el) // 2], 2),
          '<4:', sum(e < 4 for e in el), '| clump elixir med', round(elc[len(elc) // 2], 2), '<4:', sum(e < 4 for e in elc), '/', len(elc))
    print('   wincons:', Counter(r.get('wincon') for r in w).most_common(8))
