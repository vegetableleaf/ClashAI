"""W1: does the live Log push the bodies it rolls over, and when? Per confirmed Log, each enemy ground body inside the
corridor (|dX| <= 1.95 + 0.6 tiles): its displacement along the roll axis (own frame, + = away from me) per 2-tick
frame, aligned on the tick the roll centre (tap + 0.2 * (t - conf - 8.33) tiles) first comes within 1.2 tiles of it.
Usage: log_probe.py PKL_DIR"""
import collections
import pickle
import sys

import numpy as np

from pipeline.extrapolate import _row
from q3_own_effects import GROUPS, own, raw_of

D = sys.argv[1].rstrip('/') + '/'
prof = collections.defaultdict(list)
n_body = 0
for g in GROUPS:
    for m in pickle.load(open(D + f'live_{g}.pkl', 'rb')):
        F, s = m['frames'], m['side']
        if not F:
            continue
        T = np.array([f[0] for f in F])
        for c in m['conf']:
            if c['name'] != 'Log':
                continue
            cx, cy = own(s, *raw_of(s, c['xy']))
            i0, i1 = np.searchsorted(T, c['t'] - 10), np.searchsorted(T, c['t'] + 80)
            tr = collections.defaultdict(dict)
            for j in range(i0, min(i1, len(F))):
                for e in F[j][2]:
                    if e[0] != s and e[3] >= 0:
                        tr[(e[6], e[3])][F[j][0]] = own(s, e[1], e[2])
            for (ad, cid), pts in tr.items():
                row = _row({'card_id': cid}) or {}
                if row.get('kind') != 'troop' or (row.get('flying_height') or 0) > 0:
                    continue
                ts = sorted(pts)
                hit = next((t for t in ts if t >= c['t'] + 8.33 and abs(pts[t][0] - cx) <= 2.55
                            and abs(pts[t][1] - (cy + 0.2 * (t - c['t'] - 8.33))) <= 1.2
                            and 0.2 * (t - c['t'] - 8.33) <= 10.1), None)
                if hit is None:
                    continue
                n_body += 1
                for a, b in zip(ts, ts[1:]):
                    if b - a == 2:
                        prof[(b - hit) // 2 * 2].append((pts[b][1] - pts[a][1]) / 2 * 1000)
print('ground bodies the roll reached:', n_body)
for k in sorted(prof):
    if -12 <= k <= 20:
        v = np.array(prof[k])
        print('tick %+3d vs reach: n %4d  along-axis step median %+6.0f  mean %+6.0f  share > +40: %.2f' % (
            k, len(v), np.median(v), v.mean(), np.mean(v > 40)))
