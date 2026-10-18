"""'ready' screenshot readings: blue/grey fraction bands by phase-2 truth, per model (is the false 'ready' separable?)."""
import json
from collections import Counter
from pathlib import Path
B = json.loads((Path(__file__).resolve().parent / 'button_rows.json').read_text())
for mark in ('CXXXVIII', 'CXXIV'):
    c = Counter()
    for b in B.values():
        if b['mark'] == mark:
            for t, truth, bl, gr in b['ready_reads']:
                band = 'genuine-like (0.38<=blue<=0.44)' if 0.38 <= bl <= 0.44 else ('floor-like (blue>0.48)' if bl > 0.48 else 'other')
                c[(truth, band)] += 1
    print(mark, dict(sorted(c.items())))
