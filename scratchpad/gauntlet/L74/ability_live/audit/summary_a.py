"""Quick per-model counts from inventory.json (presses, deploys, confirm / unconfirm, why split, iw_press mode)."""
import json, re
from collections import Counter, defaultdict
from pathlib import Path

inv = json.loads(Path(__file__).with_name('inventory.json').read_text())
by = defaultdict(Counter)
modes = Counter()
for m in inv:
    k = m.get('mark')
    if m['frames'] < 500:
        continue
    modes[(k, m.get('iw_press'), m.get('pstar'))] += 1
    c = by[k]
    c['matches'] += 1
    for e in m['events']:
        ev = e['event']
        if ev == 'confirmed':
            c['iw_deploys'] += 1
        elif ev.startswith('ability'):
            c[ev] += 1
            if ev == 'ability':
                c['why_' + e['why'].split()[0]] += 1
                c['src_' + ('head' if 'head' in e['why'] else 'rule')] += 1
print(modes)
for k, c in by.items():
    print(k, dict(c))
