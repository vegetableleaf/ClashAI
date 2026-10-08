"""Sanity: my dead-reckoning forecast vs the model_bodies the live model actually received (play decisions, recorded matches)."""
import numpy as np
from common import *
ds = []
for g in ('STACK_ALOFF', 'STACK_RA', 'STACK_ALON', 'R1e'):
    for m in load(g):
        F = m['frames']
        if not F: continue
        s = m['side']; idx = {t: i for i, (t, el, en) in enumerate(F)}
        for d in m['dec']:
            if not d['play'] or d['t'] not in idx or not d.get('mb'): continue
            i = idx[d['t']]; k = i - 1
            while k > 0 and F[k][0] >= d['t']: k -= 1
            if F[k][0] >= d['t']: continue
            prev = {e[6]: e for e in F[k][2]}; g_ = d['t'] - F[k][0]
            mb = [(b[2] * 18, (1 - b[3]) * 32) for b in d['mb']]
            for e in F[i][2]:
                if e[0] == s or e[6] not in prev: continue
                p = prev[e[6]]
                fx, fy = own(s, e[1] + (e[1] - p[1]) / g_ * 26, e[2] + (e[2] - p[2]) / g_ * 26)
                ds.append(min(((fx - x) ** 2 + (fy - y) ** 2) ** .5 for x, y in mb) if mb else 99)
ds = np.array(ds)
print('n', len(ds), 'median nn dist %.3f tiles; share <=0.25 tile %.2f' % (np.median(ds), np.mean(ds <= 0.25)))
