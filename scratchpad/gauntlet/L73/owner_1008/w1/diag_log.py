"""W1 diagnostic: Log-zone bodies the own_effects forecast made WORSE (new >= 1.5 tiles, base < 1.5). Usage: diag_log.py ROWS_PKL"""
import collections
import pickle
import sys

import numpy as np

from pipeline.obs_contract import _catalog_names

per = pickle.load(open(sys.argv[1], 'rb'))
R = [r for P in per for r in P if r['moving'] and r['cat'] == 'my_effect_hit' and r['how'] == 'Log']
bad = [r for r in R if r['new'] >= 1.5 and r['base'] < 1.5]
good = [r for r in R if r['new'] < 1.5 and r['base'] >= 1.5]
print('Log-zone moving bodies', len(R), 'made worse', len(bad), 'made better', len(good))
names = _catalog_names()
for lab, S in (('worse', bad), ('better', good)):
    print(lab, collections.Counter(names.get(r['dbg']['cid'], r['dbg']['cid']) for r in S).most_common(8))
    print(lab, 'ticks since Log confirm', np.percentile([min(f[0] for f in r['dbg']['fx'] if f[1] == 'Log') for r in S], [10, 50, 90]))
for r in bad[:25]:
    d = r['dbg']
    f = [(a, n, tuple(round(v, 1) for v in xy)) for a, n, xy in d['fx']]
    print(names.get(d['cid']), 'gap', d['gap'], 'prev', tuple(round(v, 2) for v in d['prev']), 'cur', tuple(round(v, 2) for v in d['cur']),
          'true', tuple(round(v, 2) for v in d['true']), 'base', tuple(round(v, 2) for v in d['b']), 'new', tuple(round(v, 2) for v in d['n']), f)
