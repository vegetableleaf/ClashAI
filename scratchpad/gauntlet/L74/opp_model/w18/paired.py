"""W18: PAIRED per-cell difference of two SIM runs on the same seeds (O4-Ranked cells, w14/o4r_table.py definitions), with a
pair-bootstrap 95% CI, next to the Ranked target.  A = the reference run, B = the changed run (e.g. --tap-loss, --opp-tau).
    icebow/.venv/Scripts/python.exe -B scratchpad/gauntlet/L74/opp_model/w18/paired.py ROOT_A ROOT_B [--style]
Rows are matched on (seed, tag, learner_side); only matched rows count.  For a conditional cell (win | OT ...) each bootstrap
draw recomputes both arms' rate on the resampled pairs, so a change of the conditioning set is part of the difference."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE.parent / 'w14')]
import o4r_table as T  # noqa: E402


def key(j):
    return (j['seed'], j['tag'], j['learner_side'])


def arrays(rows, cell):
    sel, hit = next((s, h) for c, s, h in T.CELLS if c == cell)
    ins = {id(r) for r in sel(rows)}
    return np.array([id(r) in ins for r in rows], float), np.array([bool(hit(r)) for r in rows], float)


def main():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    (na, ra), = T.load_sim(args[0]).items()
    (nb, rb), = T.load_sim(args[1]).items()
    ib = {key(j): j for j in rb}
    pairs = [(j, ib[key(j)]) for j in ra if key(j) in ib]
    A = [T.sim_row(a, na) for a, _ in pairs]
    B = [T.sim_row(b, nb) for _, b in pairs]
    live = T.ranked_rows()
    n = len(pairs)
    print(f'{na} (A) vs {nb} (B): {n} matched games of {len(ra)} / {len(rb)}; identical outcomes '
          f'{sum(a["outcome"] == b["outcome"] and a["end_tick"] == b["end_tick"] for a, b in pairs)}')
    rng = np.random.default_rng(0)
    idx = rng.integers(0, n, size=(2000, n))
    for cell, *_ in T.CELLS:
        ia, ha = arrays(A, cell)
        ib_, hb = arrays(B, cell)
        pa, pb = (ia * ha).sum() / max(1, ia.sum()), (ib_ * hb).sum() / max(1, ib_.sum())
        da = (ia[idx] * ha[idx]).sum(1) / np.maximum(1, ia[idx].sum(1))
        db = (ib_[idx] * hb[idx]).sum(1) / np.maximum(1, ib_[idx].sum(1))
        lo, hi = np.percentile(db - da, [2.5, 97.5])
        sel, hit = next((s, h) for c, s, h in T.CELLS if c == cell)
        lv = sel(live)
        g = '*' if cell in T.GATE else ' '
        print(f'  {g} {cell:22s} A {100 * pa:5.1f}  B {100 * pb:5.1f}  B-A {100 * (pb - pa):+5.1f} [{100 * lo:+5.1f}, {100 * hi:+5.1f}]'
              f'   Ranked {100 * sum(map(hit, lv)) / max(1, len(lv)):5.1f}')
    if '--style' in sys.argv:
        for nm, raw in ((na, [a for a, _ in pairs]), (nb, [b for _, b in pairs])):
            d, cmp = T.style_dist(raw, 'ranked')
            import o3_score as O3
            print(f'  style {nm}: {d:.2f} | ' + ' '.join(f'{k} {cmp[k][3]:.2f}({cmp[k][4]:+.2f})' for k in O3.FEATS))


if __name__ == '__main__':
    main()
