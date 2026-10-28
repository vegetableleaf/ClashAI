"""Sum d2sample.py files (one per actor) of a run dir and print the share of main-thread samples inside each function
(inclusive) for the functions that matter to the obs / engine / policy split.
    python samp_sum.py DIR [N]"""
import json
import sys
from collections import Counter
from pathlib import Path

inc, leaf, n = Counter(), Counter(), 0
for p in Path(sys.argv[1]).glob('*.json'):
    d = json.loads(p.read_text())
    if d['samples'] < 1000:          # resource tracker / short-lived helpers
        continue
    n += d['samples']
    inc.update(d['inclusive'])
    leaf.update(d['leaf'])
N = int(sys.argv[2]) if len(sys.argv) > 2 else 45
print(f'samples {n} (10 ms each, main thread, actors with >= 1000 samples)')
print('-- inclusive')
for k, v in inc.most_common(N):
    print(f'{100 * v / n:6.1f}% {k}')
print('-- leaf')
for k, v in leaf.most_common(15):
    print(f'{100 * v / n:6.1f}% {k}')
