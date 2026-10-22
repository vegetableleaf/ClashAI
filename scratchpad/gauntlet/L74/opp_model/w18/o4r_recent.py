"""W18 O4-RECENT (owner 10-22): the O4-Ranked check against the MOST RECENT N live Ranked CLX matches instead of all 233.
    icebow/.venv/Scripts/python.exe -B scratchpad/gauntlet/L74/opp_model/w18/o4r_recent.py [--n 100] [--targets] ROOT [ROOT ...]
Live rows = diag12/recent/rows_ext.json (W13's anatomy rows rebuilt over every CLX Ranked log, 10-20 13:28 -> 10-21 14:32, the
switch to Mark CLXI), the last N by log time. Cells, SIM rows and the z rule are w14/o4r_table.py's.
TOLERANCE RULE (stated, owner-approved scale-up for the smaller n): each predeclared point tolerance is scaled by
sqrt(n_233 / n_recent) of THAT cell's live n, i.e. it stays the same multiple of the live standard error as W14's rule on 233
matches; |z| < 1.96 is unchanged (it widens by itself). Style bound unchanged (0.65, an effect size), measured against the
same N matches' opponents."""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE.parent / 'w14')]
import o4r_table as T  # noqa: E402

EXT = HERE.parent / 'diag12/recent/rows_ext.json'
TOL_233 = dict(T.TOL)


def recent_rows(n):
    rows = [r for r in json.load(open(EXT)) if r['sample'] == 'ranked']
    rows.sort(key=lambda r: r['key'])
    for r in rows:
        r['wincon_rev'] = r['wincon']
    return rows[-n:], rows


def scaled_tol(live_recent, live_233):
    out = {}
    for cell, tol in TOL_233.items():
        sel = next(s for c, s, _ in T.CELLS if c == cell)
        out[cell] = tol * math.sqrt(len(sel(live_233)) / max(1, len(sel(live_recent))))
    return out


def main():
    n = int(sys.argv[sys.argv.index('--n') + 1]) if '--n' in sys.argv else 100
    roots = [a for a in sys.argv[1:] if not a.startswith('--') and not a.isdigit()]
    live, allr = recent_rows(n)
    l233 = T.ranked_rows()
    T.TOL.clear()
    T.TOL.update(scaled_tol(live, l233))
    T.ranked_rows = lambda: live                     # the scorer's live set (also its live style reference)
    T._LIVE_STYLE.clear()
    print(f'O4-RECENT: the last {len(live)} of {len(allr)} CLX Ranked matches ({live[0]["key"][10:25]} .. {live[-1]["key"][10:25]}); '
          f'tolerances scaled by sqrt(n_233 / n_recent): ' + ', '.join(f'{k} {v:.1f}' for k, v in T.TOL.items()))
    if '--targets' in sys.argv:
        print('\n| cell | all 233 [95%] | recent ' + str(len(live)) + ' [95%] | tolerance (pp) |\n|---|---|---|---|')
        for cell, sel, hit in T.CELLS:
            a, b = sel(l233), sel(live)
            g = '* ' if cell in T.GATE else ''
            print(f'| {g}{cell} | {T.AN.fmt(sum(map(hit, a)), len(a))} | {T.AN.fmt(sum(map(hit, b)), len(b))} | '
                  f'{T.TOL[cell]:.1f} |' if cell in T.TOL else f'| {g}{cell} | {T.AN.fmt(sum(map(hit, a)), len(a))} | '
                  f'{T.AN.fmt(sum(map(hit, b)), len(b))} | z only |')
    for root in roots:
        for name, raw in sorted(T.load_sim(root).items()):
            T.table(name, raw, live, brief='--brief' in sys.argv)


if __name__ == '__main__':
    main()
