"""cls_down_split.py CLS_BASE_DIR CLS_ARM_DIR MOVED.json: split the down fights by how fin16's first global divergence (live vs
SIM) relates to fin15's on the same fight: SAME (kind, body, dt within 4 ticks: a divergence both engines already had; fin16
only changed what followed), EARLIER on fin16 (fin16 departs from live first), LATER on fin16."""
import json
import sys
from collections import Counter

sys.argv, (cb, ca, moved) = sys.argv[:1], sys.argv[1:4]
sys.argv += [moved, cb, ca, '/dev/null']
import importlib.util
from pathlib import Path
spec = importlib.util.spec_from_file_location('agg', Path(__file__).with_name('cls_down_agg.py'))
agg = importlib.util.module_from_spec(spec)
spec.loader.exec_module(agg)
cnt, ex = Counter(), {}
for k in agg.down:
    g, gb = (agg.A.get(k) or {}).get('first_global') or {}, (agg.B.get(k) or {}).get('first_global') or {}
    if not g or not gb:
        c = 'missing'
    elif g.get('kind') == gb.get('kind') and g.get('body') == gb.get('body') and abs(g['dt'] - gb['dt']) <= 4:
        c = 'same first divergence'
    elif g['dt'] < gb['dt']:
        c = 'fin16 earlier' + (' (a Skeletons body)' if 'Skeletons' in str(g.get('body')) else '')
    else:
        c = 'fin16 later'
    cnt[c] += 1
    ex.setdefault(c, k)
print(dict(cnt.most_common()))
print(ex)
