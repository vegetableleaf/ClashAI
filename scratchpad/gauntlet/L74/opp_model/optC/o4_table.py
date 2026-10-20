"""W7 O4 table (laptop): each SIM config (opp_eval.sh rows) vs live CLX at our tower 4858 (n = 138), per crown cell:
SIM % [Wilson 95%], live % [95%], SIM - live (pp), two-proportion z; plus o3_score's style distance. Overall and for the
archetypes with live n >= 30 (hog, weak_other, other).
    icebow/.venv/Scripts/python.exe -I scratchpad/gauntlet/L74/opp_model/optC/o4_table.py ROOT [ROOT ...] [--only SUBSTR]
ROOT = a pulled out/NAME dir or its parent (every NAME_SEED/D3/matches.jsonl below it = config NAME, seeds pooled)."""
from __future__ import annotations

import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE.parent), str(HERE.parents[1] / 'human')]
import analyze as AN  # noqa: E402
import crowns as C  # noqa: E402
import o3_score as O3  # noqa: E402
import opp_behaviour as OB  # noqa: E402

CELLS = ('win', 'lose_princess', 'take_princess', 'both', 'ot_share', 'reg_loss')
ARCH = ('hog', 'weak_other', 'other')


def z2(a, b):
    """Two-proportion z (pooled) for (k, n) pairs; nan when undefined."""
    (k1, n1), (k2, n2) = a, b
    if not n1 or not n2:
        return float('nan')
    p = (k1 + k2) / (n1 + n2)
    se = math.sqrt(p * (1 - p) * (1 / n1 + 1 / n2))
    return (k1 / n1 - k2 / n2) / se if se else float('nan')


def sim_recs(rows):
    return [C.live_rec(dict(falls=O3.sim_falls(r), end=int(r['end_tick']),
                            win=1.0 if r['outcome'] == 'win' else 0.0 if r['outcome'] == 'loss' else 0.5), off=0) for r in rows]


def block(title, st, lt):
    print(f'    {title}: n SIM {st["n"]} / live {lt["n"]}')
    worst = 0.0
    for k in CELLS:
        z = z2(st[k], lt[k])
        worst = max(worst, abs(z)) if not math.isnan(z) else worst
        print(f'      {k:14s} SIM {C.pct(*st[k]):24s} live {C.pct(*lt[k]):24s} '
              f'{100 * (st[k][0] / max(1, st[k][1]) - lt[k][0] / max(1, lt[k][1])):+6.1f} pp  z {z:+5.2f}'
              f'{"  <-- |z| >= 1.96" if abs(z) >= 1.96 else ""}')
    if lt.get('giveback') and st.get('giveback'):
        print(f'      {"giveback":14s} SIM {C.pct(*st["giveback"]):24s} live {C.pct(*lt["giveback"]):24s} '
              f'z {z2(st["giveback"], lt["giveback"]):+5.2f}')
    return worst


def main():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    only = sys.argv[sys.argv.index('--only') + 1] if '--only' in sys.argv else None
    if only:
        args.remove(only)
    live = AN.load_live()
    L13 = [r for r in live if r['tro'] >= 12950 and r['m'] in ('CXXXVIII', 'CLIII', 'CLIX', 'CLX', 'CLX_T16')]
    lf = [OB.features(dict(src='live', id=r['log'], seen=r['seen'], res=0, end=r['end'], t0=r['t0'], side=r['side'],
                           plays=r['plays'], mine=r['mine'])) for r in L13]
    T16 = [r for r in live if r['m'] == 'CLX_T16']
    lt_all = C.crown_stats([r['rec'] for r in T16])
    for root in args:
        for name, rows in sorted(O3.load(root).items()):
            if only and only not in name:
                continue
            b = O3.behaviour(rows)
            cmp = OB.compare(lf, [f for _, f in b]) if b else None
            ds = [cmp[k][4] for k in O3.FEATS if cmp and not math.isnan(cmp[k][4])]
            dist = math.sqrt(sum(d * d for d in ds) / len(ds)) if ds else float('nan')
            if '--brief' in sys.argv:          # one line: SIM % per cell (live CLX@4858 in the header)
                st = C.crown_stats(sim_recs(rows))
                print(f'{name:44s} n {len(rows):4d} dist {dist:.2f} ' + ' '.join(
                    f'{k} {100 * st[k][0] / max(1, st[k][1]):5.1f}' for k in CELLS))
                if '--feats' in sys.argv and cmp:          # style features: SIM mean (d vs live 13k)
                    print('      ' + ' '.join(f'{k} {cmp[k][3]:.2f}({cmp[k][4]:+.2f})' for k in O3.FEATS))
                continue
            print(f'\n== {name}: {len(rows)} rows, style distance {dist:.2f} (live 13k n={len(lf)})')
            worst = block('all archetypes', C.crown_stats(sim_recs(rows)), lt_all)
            for a in ARCH:
                sr = [r for r in rows if AN.arch2(r.get('opp_deck') or []) == a]
                lr = [r['rec'] for r in T16 if r['a'] == a]
                if sr and lr:
                    block(a, C.crown_stats(sim_recs(sr)), C.crown_stats(lr))
            print(f'    max |z| over the overall cells: {worst:.2f}')


if __name__ == '__main__':
    main()
