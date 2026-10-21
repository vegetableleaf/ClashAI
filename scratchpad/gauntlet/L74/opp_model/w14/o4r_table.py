"""W14 O4-Ranked table (laptop): each SIM opponent config vs ICEBOW Mark CLX's 233 RANKED matches (clx_ranked/rows.json,
W13's definitions), per crown cell: SIM %, Ranked % [Wilson 95%], SIM - Ranked (pp) [Newcombe 95%], two-proportion z.
Plus the opponent's play-style distance (o3_score's 9 features) vs the live RANKED opponents and vs W7's live 13k ladder set.
    icebow/.venv/Scripts/python.exe -B scratchpad/gauntlet/L74/opp_model/w14/o4r_table.py ROOT [ROOT ...] [--brief] [--only S]
ROOT = a pulled out/NAME dir or its parent: every NAME_SEED/D3/**/matches.jsonl below it = config NAME, seed blocks pooled.
SIM rows -> clx_ranked/sim.py row() (the exact W13 crown-path code), so the SIM side matches CLX_RANKED.md T11 by construction.
Gate cells (pass = |z| < 1.96 each): GATE below.  BEAT = W13's tank / bridge-spam win conditions (report.py BEAT)."""
from __future__ import annotations

import glob
import json
import math
import sys
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
L74 = HERE.parents[1]
sys.path[:0] = [str(L74 / 'clx_ranked'), str(HERE.parent), str(L74 / 'human')]
import sim as SR  # noqa: E402  (clx_ranked/sim.py; imports anatomy = idle priority)

AN = SR.AN
BEAT = {'giant', 'electro_giant', 'royal_hogs', 'battle_ram', 'pekka', 'golem', 'goblin_giant', 'lava_hound', 'royal_giant',
        'elixir_golem', 'rune_giant', 'giant_skeleton', 'three_musketeers', 'boss_bandit'}       # = clx_ranked/report.py BEAT
DRAIN_S = 299.25                                                                                # report.py: OT decided before it
ALL = lambda x: x  # noqa: E731
WIN = lambda r: r['win'] == 1  # noqa: E731
CELLS = (  # (name, row selector, hit) -- the same functions on live Ranked rows and SIM rows
    ('win', ALL, WIN),
    ('win_vs_BEAT', lambda x: [r for r in x if r['wincon'] in BEAT], WIN),
    ('win_vs_rest', lambda x: [r for r in x if r['wincon'] not in BEAT], WIN),
    ('ot_share', ALL, lambda r: r['ot']),
    ('win_given_OT', lambda x: [r for r in x if r['ot']], WIN),
    ('win_OT_pre_drain', lambda x: [r for r in x if r['ot'] and r['end_s'] < DRAIN_S], WIN),
    ('win_at_drain', lambda x: [r for r in x if r['ot'] and r['end_s'] >= DRAIN_S], WIN),
    ('lost_first_princess', ALL, lambda r: r['first'] == 'own'),
    ('opp_takes_princess', ALL, lambda r: r['their_cr'] >= 1),
    ('clx_takes_princess', ALL, lambda r: r['our_cr'] >= 1),
    ('both_took_one', ALL, lambda r: r['our_cr'] >= 1 and r['their_cr'] >= 1),
    ('reg_loss', ALL, lambda r: r['win'] == 0 and not r['ot']),
    ('loss_tiebreak_drain', ALL, lambda r: r['path'] == 'L_tiebreak_drain'),
)
GATE = ('win', 'win_vs_BEAT', 'win_vs_rest', 'ot_share', 'win_given_OT', 'win_OT_pre_drain', 'lost_first_princess',
        'opp_takes_princess', 'both_took_one', 'reg_loss')
BRIEF = ('win', 'win_vs_BEAT', 'win_vs_rest', 'ot_share', 'win_given_OT', 'win_OT_pre_drain', 'opp_takes_princess',
         'both_took_one')


def ranked_rows():
    return [r for r in json.load(open(L74 / 'clx_ranked/rows.json')) if r['sample'] == 'ranked']


def wilson(k, n):
    return AN.wilson(k, n)


def newcombe(k1, n1, k2, n2):
    p1, l1, u1 = wilson(k1, n1)
    p2, l2, u2 = wilson(k2, n2)
    d = p1 - p2
    return d, d - math.sqrt((p1 - l1) ** 2 + (u2 - p2) ** 2), d + math.sqrt((u1 - p1) ** 2 + (p2 - l2) ** 2)


def z2(k1, n1, k2, n2):
    if not n1 or not n2:
        return float('nan')
    p = (k1 + k2) / (n1 + n2)
    se = math.sqrt(p * (1 - p) * (1 / n1 + 1 / n2))
    return (k1 / n1 - k2 / n2) / se if se else float('nan')


def load_sim(root):
    """{config NAME: [raw json rows]} for every NAME_SEED/D3 under root: D3/matches.jsonl (the merged file) when present, else
    the per-worker D3/*/matches.jsonl (fin15 gap.py writes both once a block finishes; never read both)."""
    cfg = defaultdict(list)
    for d in sorted(set(glob.glob(str(Path(root) / '**' / 'D3'), recursive=True))):
        d = Path(d)
        merged = d / 'matches.jsonl'
        files = [merged] if merged.exists() else sorted(d.glob('*/matches.jsonl'))
        name = d.parent.name.rsplit('_', 1)[0]
        for p in files:
            for line in open(p, encoding='utf-8'):
                cfg[name].append(json.loads(line))
    return cfg


_LIVE_STYLE = {}


def live_style(which):
    """Live opponent style features: 'ranked' = the 233 Ranked logs (live_table.cached, the shared per-log cache);
    '13k' = W7's reference (analyze.load_live, >= 12,950 trophies, CXXXVIII..CLX)."""
    if which in _LIVE_STYLE:
        return _LIVE_STYLE[which]
    import opp_behaviour as OB
    if which == 'ranked':
        import live_table as LT
        ms = []
        for r in ranked_rows():
            d = LT.cached(LT.LOGS / r['key'])
            if d and d.get('start'):
                ms.append(dict(src='live', id=r['key'], seen=d['seen'], res=0, end=d['end'], t0=d['t0'], side=d['side'],
                               plays=d['plays'], mine=d['mine']))
    else:
        import analyze as A7
        ms = [dict(src='live', id=r['log'], seen=r['seen'], res=0, end=r['end'], t0=r['t0'], side=r['side'], plays=r['plays'],
                   mine=r['mine']) for r in A7.load_live()
              if r['tro'] >= 12950 and r['m'] in ('CXXXVIII', 'CLIII', 'CLIX', 'CLX', 'CLX_T16')]
    _LIVE_STYLE[which] = [OB.features(m) for m in ms]
    return _LIVE_STYLE[which]


def style_dist(raw, which):
    import o3_score as O3
    import opp_behaviour as OB
    b = O3.behaviour(raw)
    if not b:
        return float('nan'), None
    cmp = OB.compare(live_style(which), [f for _, f in b])
    ds = [cmp[k][4] for k in O3.FEATS if not math.isnan(cmp[k][4])]
    return (math.sqrt(sum(d * d for d in ds) / len(ds)) if ds else float('nan')), cmp


def table(name, raw, live, brief=False, feats=False):
    sim = [SR.row(j, name) for j in raw]
    out = {}
    worst, fails = 0.0, []
    for cell, sel, hit in CELLS:
        a, b = sel(sim), sel(live)
        k1, n1, k2, n2 = sum(map(hit, a)), len(a), sum(map(hit, b)), len(b)
        z = z2(k1, n1, k2, n2)
        out[cell] = (k1, n1, k2, n2, z)
        if cell in GATE and not math.isnan(z):
            worst = max(worst, abs(z))
            if abs(z) >= 1.96:
                fails.append(cell)
    dr, cmp = style_dist(raw, 'ranked')
    d13, _ = style_dist(raw, '13k')
    if brief:
        print(f'{name:40s} n {len(sim):4d} style R {dr:.2f} / 13k {d13:.2f} | ' + ' '.join(
            f'{c} {100 * out[c][0] / max(1, out[c][1]):5.1f}' for c in BRIEF) + f' | gate fails {len(fails)}: {",".join(fails)}')
        if feats and cmp:
            import o3_score as O3
            print('      ' + ' '.join(f'{k} {cmp[k][3]:.2f}({cmp[k][4]:+.2f})' for k in O3.FEATS))
        return out, fails, dr
    print(f'\n== {name}: {len(sim)} SIM games vs {len(live)} Ranked; style distance vs Ranked {dr:.2f}, vs 13k ladder {d13:.2f}')
    for cell, *_ in CELLS:
        k1, n1, k2, n2, z = out[cell]
        d, lo, hi = newcombe(k1, n1, k2, n2)
        g = '*' if cell in GATE else ' '
        print(f'  {g} {cell:22s} SIM {AN.fmt(k1, n1):28s} Ranked {AN.fmt(k2, n2):28s} {100 * d:+6.1f} [{100 * lo:+6.1f}, '
              f'{100 * hi:+6.1f}] z {z:+5.2f}{"  <-- FAIL" if g == "*" and abs(z) >= 1.96 else ""}')
    print(f'  gate (* cells): {len(GATE) - len(fails)} of {len(GATE)} pass, max |z| {worst:.2f}; fails: {fails or "none"}')
    return out, fails, dr


W12 = 'C:/Users/benpe/pod_backup_weekend/tonight1020/clx_fin15/w12_clx_fin15'


def check():
    """--check: the table must reproduce CLX_RANKED.md T11 on W12's R6 u20 rows (SIM side; Ranked side = rows.json)."""
    (name, raw), = load_sim(W12).items()
    sim = [SR.row(j, name) for j in raw]
    live = ranked_rows()
    got = {c: round(100 * sum(map(h, sel(x))) / len(sel(x)), 1) for c, sel, h in CELLS for x in (sim,)}
    want = dict(win=64.0, win_vs_BEAT=57.5, win_OT_pre_drain=77.5, lost_first_princess=34.6, reg_loss=19.5)
    assert len(sim) == 1920 and len(live) == 233, (len(sim), len(live))
    assert all(got[k] == v for k, v in want.items()), (got, want)
    print('CHECK OK', want)


def main():
    if '--check' in sys.argv:
        return check()
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    only = sys.argv[sys.argv.index('--only') + 1] if '--only' in sys.argv else None
    if only:
        args.remove(only)
    live = ranked_rows()
    print(f'Ranked reference: {len(live)} CLX matches (clx_ranked/rows.json); gate cells: {", ".join(GATE)}')
    for root in args:
        for name, raw in sorted(load_sim(root).items()):
            if only and only not in name:
                continue
            table(name, raw, live, brief='--brief' in sys.argv, feats='--feats' in sys.argv)


if __name__ == '__main__':
    main()
