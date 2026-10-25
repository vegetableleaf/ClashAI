"""Per-decision policy shift in SIM (skew_worker SKEW_MODE=real diag): the memory model with its real memory (m), the same
model with an EMPTY memory (e) and the base CLXIII (b) on the SAME rows. Usage: diag_shift.py DUMP_DIR [...]"""
import pickle
import sys
from pathlib import Path

import numpy as np


def kl(p, q):
    m = p > 0
    return float((p[m] * (np.log(p[m]) - np.log(np.maximum(q[m], 1e-12)))).sum())


def main():
    D = []
    for d in sys.argv[1:]:
        for f in sorted(Path(d).glob('*.pkl')):
            r = pickle.load(open(f, 'rb'))
            for x in r['diag']:
                x['match_t0'] = r['t'][0]
                x['win'] = r['row']['outcome'] == 'win'
            D += r['diag']
    print(f'{len(D)} learner decisions')
    t = np.array([x['t'] for x in D], float)
    for a, b in (('m', 'b'), ('e', 'b'), ('m', 'e')):
        pa, pb = np.array([x['p' + a] for x in D]), np.array([x['p' + b] for x in D])
        kc = np.array([kl(x['card' + a], x['card' + b]) for x in D])
        top = np.array([np.argmax(x['card' + a]) == np.argmax(x['card' + b]) for x in D])
        cell = np.array([x['cell' + a] == x['cell' + b] for x in D])
        kx = np.array([x[f'klcell_{a}{b}'] for x in D]) if f'klcell_{a}{b}' in D[0] else np.full(len(D), np.nan)
        print(f'{a} vs {b}: gate p mean {pa.mean():.3f} vs {pb.mean():.3f}; |dp| mean {np.abs(pa - pb).mean():.3f} '
              f'p90 {np.percentile(np.abs(pa - pb), 90):.3f}; p>=.35 share {(pa >= .35).mean():.3f} vs {(pb >= .35).mean():.3f}; '
              f'card KL {kc.mean():.3f} top-card same {top.mean():.3f}; top-card cell argmax same {cell.mean():.3f} cell KL {np.nanmean(kx):.3f}')
    for lo, hi in ((0, 200), (200, 1200), (1200, 2400), (2400, 3600), (3600, 99999)):
        m = (t >= lo) & (t < hi)
        if m.any():
            pm, pe, pb = (np.array([x['p' + k] for x, ok in zip(D, m) if ok]) for k in 'meb')
            print(f'tick [{lo}, {hi}): n {m.sum():5d}  gate p  mem {pm.mean():.3f}  empty {pe.mean():.3f}  base {pb.mean():.3f};'
                  f'  >= .35: {(pm >= .35).mean():.3f} / {(pe >= .35).mean():.3f} / {(pb >= .35).mean():.3f}')


if __name__ == '__main__':
    main()
