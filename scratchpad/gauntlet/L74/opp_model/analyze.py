"""L74/opp_model analysis (W3, 10-20): J11 SIM->live predictiveness, J9 crown-path realism, J10 opponent play realism,
the Stage-2 post-mortem numbers and the live-data audit.  Single process, laptop, local files only.

    icebow/.venv/Scripts/python.exe -I scratchpad/gauntlet/L74/opp_model/analyze.py > scratchpad/gauntlet/L74/opp_model/analyze.out
Needs out/live_matches.jsonl.gz (live_table.py).  Every proportion: Wilson 95% CI; differences: Newcombe or paired normal CI."""
from __future__ import annotations

import gzip
import json
import math
import random
import sys
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
import orjson

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE), str(HERE.parents[0] / 'human'), str(HERE.parents[0] / 'weekend')]
import crowns as C  # noqa: E402
import sim_sets as S  # noqa: E402
import opp_behaviour as OB  # noqa: E402
import archetypes as A  # noqa: E402

MARKS = {'ICEBOW Mark CXII: PLAINIW': 'CXII', 'ICEBOW Mark CXVII: GAE': 'CXVII', 'ICEBOW Mark CXXIV: LONGER': 'CXXIV',
         'ICEBOW Mark CXXXVIII: CUES': 'CXXXVIII', 'ICEBOW Mark CLIII: LEVELS': 'CLIII', 'ICEBOW Mark CLIX: PRESS': 'CLIX',
         'ICEBOW Mark CLX: PARITY': 'CLX'}
ORDER = list(MARKS.values()) + ['CLX_T16']   # CLX_T16 = CLX after our tower level-up (own princess 4858), see j11
ARCH = ('royal_giant_monk', 'royal_giant', 'lava_hound', 'golem', 'pekka_bridge', 'hyperbait', 'hog', 'weak_other', 'other')
P = C.pct


def arch2(names):
    """weekend/archetypes.classify (owner's six + weak_other + other), with Hog Rider decks split out of the rest (the Stage-2
    gate's 13k loss cell).  Live: cards SEEN in the match; SIM: the opponent's full deck."""
    a = A.classify(names)
    if a in ('weak_other', 'other') and 'hogrider' in {A.canon(n) for n in names}:
        return 'hog'
    return a


def own_hp(r):
    return max([v for k, v in r['tower_maxhp'].items() if k.startswith('own_P')] or [0])


def load_live():
    rows = [orjson.loads(l) for l in gzip.open(HERE / 'out/live_matches.jsonl.gz')]
    out = []
    for r in rows:
        if r['deck'] != 'icebow' or r['tro'] is None or r['tro'] < 10000 or r['res'] not in ('WIN', 'LOSS', 'DRAW'):
            continue
        r['m'] = MARKS.get(r['mark'])
        if r['m'] == 'CLX' and own_hp(r) == 4858:
            r['m'] = 'CLX_T16'
        r['a'] = arch2(r['seen'])
        r['rec'] = C.live_rec(r)
        out.append(r)
    return out


def sec(t):
    print('\n' + '=' * 110 + '\n## ' + t + '\n' + '=' * 110)


# ------------------------------------------------------------------------------------------------ J11 live side
# NOTE: fit_logit is NOT used for any verdict: null_beta.py shows its trophy slope is the random-walk artefact (kept for that test)
def fit_logit(rows, B=300, seed=0):
    """P(win) = sigmoid(theta_mark + beta * (trophies - 13000) / 1000), one theta per Mark, one common beta (Newton-Raphson).
    -> {mark: (p at 13,000, lo, hi)}, beta (lo, hi): percentile CIs from a match bootstrap (B draws)."""
    ms = sorted({r['m'] for r in rows}, key=ORDER.index)
    X = np.zeros((len(rows), len(ms) + 1))
    for i, r in enumerate(rows):
        X[i, ms.index(r['m'])] = 1.0
        X[i, -1] = (r['tro'] - 13000) / 1000
    y = np.array([r['win'] == 1.0 for r in rows], float)

    def newton(X, y):
        w = np.zeros(X.shape[1])
        for _ in range(50):
            p = 1 / (1 + np.exp(-X @ w))
            g = X.T @ (y - p)
            H = X.T @ (X * (p * (1 - p))[:, None]) + 1e-6 * np.eye(X.shape[1])
            step = np.linalg.solve(H, g)
            w += step
            if np.abs(step).max() < 1e-9:
                break
        return w
    w0 = newton(X, y)
    rng = np.random.default_rng(seed)
    bs = []
    for _ in range(B):
        idx = rng.integers(0, len(y), len(y))
        bs.append(newton(X[idx], y[idx]))
    bs = np.array(bs)
    sig = lambda z: 1 / (1 + np.exp(-z))  # noqa: E731
    th = {m: (sig(w0[k]), *np.percentile(sig(bs[:, k]), [2.5, 97.5])) for k, m in enumerate(ms)}
    return th, (w0[-1], *np.percentile(bs[:, -1], [2.5, 97.5])), ms, w0, bs


def strat_diff(ra, rb, width=100):
    """Win-rate difference b - a within trophy bins (Mantel-Haenszel-style weights nA nB / (nA + nB)); bins both cover only."""
    def bins(rs):
        d = defaultdict(list)
        for r in rs:
            d[int(r['tro'] // width)].append(r['win'] == 1.0)
        return d
    A_, B_ = bins(ra), bins(rb)
    num = den = var = 0.0
    na = nb = 0
    for k in set(A_) & set(B_):
        a, b = A_[k], B_[k]
        w = len(a) * len(b) / (len(a) + len(b))
        pa, pb = sum(a) / len(a), sum(b) / len(b)
        num += w * (pb - pa)
        den += w
        var += w * w * (pa * (1 - pa) / len(a) + pb * (1 - pb) / len(b))
        na += len(a)
        nb += len(b)
    if den == 0:
        return None
    d = num / den
    h = 1.96 * math.sqrt(var) / den
    return d, d - h, d + h, na, nb


def spearman(x, y):
    def rk(v):
        o = sorted(range(len(v)), key=lambda i: v[i])
        r = [0.0] * len(v)
        for j, i in enumerate(o):
            r[i] = j
        return r
    rx, ry = rk(x), rk(y)
    n = len(x)
    return 1 - 6 * sum((a - b) ** 2 for a, b in zip(rx, ry)) / (n * (n * n - 1))


def kendall(x, y):
    c = d = 0
    for i in range(len(x)):
        for j in range(i + 1, len(x)):
            s = (x[i] - x[j]) * (y[i] - y[j])
            c += s > 0
            d += s < 0
    return (c - d) / max(1, c + d), c, d


def j11(live):
    sec('J11. SIM -> live predictiveness')
    rows = [r for r in live if r['m']]
    print('\n### Live record per Mark (icebow main account, graded ladder matches, trophies before the match >= 10,000).')
    print('    CLX is split at 10-19 14:02, when OUR princess tower max HP went 4424 -> 4858 (one tower level up; every earlier match: 4424)')
    print(f"  {'Mark':9s} {'dates':31s} {'win':28s} {'trophies p10 / p50 / p90':26s} {'trophies first -> last':22s} own princess HP")
    for m in ORDER:
        rs = sorted([r for r in rows if r['m'] == m], key=lambda r: r['ts'])
        t = sorted(r['tro'] for r in rs)
        print(f"  {m:9s} {rs[0]['ts']}..{rs[-1]['ts']} {P(sum(r['win'] == 1 for r in rs), len(rs)):28s} "
              f"{t[len(t) // 10]} / {t[len(t) // 2]} / {t[9 * len(t) // 10]:<12d} {rs[0]['tro']} -> {rs[-1]['tro'] + rs[-1]['tro_d']:<12d} "
              f"{dict(Counter(own_hp(r) for r in rs))}")
    print('\n### Live win rate per trophy band (250-trophy bins; n >= 8 shown)')
    bands = sorted({int(r['tro'] // 250) * 250 for r in rows})
    print('  band     ' + ''.join(f'{m:>15s}' for m in ORDER))
    for b in bands:
        cells = []
        for m in ORDER:
            rs = [r for r in rows if r['m'] == m and b <= r['tro'] < b + 250]
            cells.append(f"{100 * sum(r['win'] == 1 for r in rs) / len(rs):5.1f}% n={len(rs):<4d}" if len(rs) >= 8 else '-')
        print(f'  {b:5d}+  ' + ''.join(f'{c:>15s}' for c in cells))
    print('\n### Tower level, all icebow matches >= 12,000: win rate by the opponent princess max HP relative to ours')
    for lab, f in (('opponent tower HIGHER', lambda o, p: p > o), ('equal', lambda o, p: p == o), ('opponent tower LOWER', lambda o, p: p < o)):
        rs = [r for r in live if r['tro'] >= 12000 and f(own_hp(r), max([v for k, v in r['tower_maxhp'].items() if k.startswith('opp_P')] or [0]))]
        print(f'  {lab:22s} {P(sum(r["win"] == 1 for r in rs), len(rs))}')
    a_, b_ = [r for r in rows if r['m'] == 'CLX_T16'], [r for r in rows if r['m'] == 'CLX']
    d = C.newcombe(sum(r['win'] == 1 for r in a_), len(a_), sum(r['win'] == 1 for r in b_), len(b_))
    print(f'  same model (CLX), own tower 4858 - 4424: {100 * d[0]:+.1f} pp [{100 * d[1]:+.1f}, {100 * d[2]:+.1f}] '
          f'(also +700 trophies higher, which makes opponents no easier)')

    print('\n### Shared bands at the same own tower level (4424), where every Mark in the row dwelled (no trophy model)')
    BANDS = (((12000, 12500), ('CXII', 'CXVII', 'CXXIV')), ((13000, 13250), ('CXXXVIII', 'CLIII', 'CLIX', 'CLX')))
    band_rate = {}
    for (lo, hi), ms in BANDS:
        for m in ms:
            rs = [r for r in rows if r['m'] == m and lo <= r['tro'] < hi]
            band_rate[m] = (sum(r['win'] == 1 for r in rs), len(rs))
            print(f'  {lo}-{hi - 1} {m:9s} {P(*band_rate[m])}')
    ab = [r for r in rows if r['m'] in ('CXII', 'CXVII') and '20261014_225700' <= r['ts'] <= '20261015_090500']
    ka = [r for r in ab if r['m'] == 'CXVII']
    kb = [r for r in ab if r['m'] == 'CXII']
    d = C.newcombe(sum(r['win'] == 1 for r in ka), len(ka), sum(r['win'] == 1 for r in kb), len(kb))
    print(f'\n### Interleaved live A/B (blocks of 5, 10-14 22:57 .. 10-15 09:04): CXVII {P(sum(r["win"] == 1 for r in ka), len(ka))}'
          f' vs CXII {P(sum(r["win"] == 1 for r in kb), len(kb))}: CXVII - CXII {100 * d[0]:+.1f} pp [{100 * d[1]:+.1f}, {100 * d[2]:+.1f}]')

    print('\n### SIM evals per Mark (wins / 960 per seed block)')
    sim = {k: R for k in S.SETS if (R := S.rows(k))}
    for (m, ctx, blk), R in sorted(sim.items(), key=lambda kv: (kv[0][1], ORDER.index(kv[0][0]) if kv[0][0] in ORDER else 99)):
        print(f'  {ctx:14s} {blk:6s} {m:12s} {P(sum(r["outcome"] == "win" for r in R), len(R))}')
    print('\n### Paired SIM deltas between Marks inside one context (same seed / census / side / deck), pp [95% CI] n_pairs')
    links = [('rt35_live', 'CXII', 'CXVII'), ('rt35_live', 'CXVII', 'CXXIV'), ('rt35_live', 'CXXIV', 'CXXXVIII'),
             ('rt35_std', 'CXII', 'CXVII'), ('rt35_std', 'CXVII', 'CXXIV'),
             ('f36_fact', 'CXXIV', 'CXXXVIII'), ('f36_fact', 'CXXXVIII', 'CLIII'), ('f36_fact', 'CLIII', 'CLIX'),
             ('fin13', 'CLIII', 'CLX'), ('fin13_l16', 'CLIII', 'CLX'),
             ('s2_e4T3', 'CXXIV', 'CXXXVIII'), ('s2_gen10', 'CXXIV', 'CXXXVIII'), ('s2_gen20', 'CXXIV', 'CXXXVIII'),
             ('s2_gen40', 'CXXIV', 'CXXXVIII'), ('s2_expl', 'CXXIV', 'CXXXVIII')]
    simd = {}
    for ctx, a, b in links:
        out = []
        for blk in ('std', 'fresh'):
            ra, rb = sim.get((a, ctx, blk)), sim.get((b, ctx, blk))
            if ra and rb:
                out.append((blk, S.paired(rb, ra)))
        ra = sum((sim.get((a, ctx, bl)) or [] for bl in ('std', 'fresh')), [])
        rb = sum((sim.get((b, ctx, bl)) or [] for bl in ('std', 'fresh')), [])
        simd[(ctx, a, b)] = pooled = S.paired(rb, ra)
        txt = '  '.join(f'{bl} {100 * x[0]:+.2f} [{100 * x[1]:+.2f}, {100 * x[2]:+.2f}] n={x[3]}' for bl, x in out if x)
        print(f'  {ctx:10s} {b:9s} - {a:9s}: {txt}  | pooled {100 * pooled[0]:+.2f} [{100 * pooled[1]:+.2f}, {100 * pooled[2]:+.2f}]')

    print('\n### Predicted (SIM paired delta) vs observed (live, shared band, own tower 4424) for each promotion link')
    pts = []
    for ctx, a, b in (('rt35_live', 'CXII', 'CXVII'), ('rt35_live', 'CXVII', 'CXXIV'), ('f36_fact', 'CXXXVIII', 'CLIII'),
                      ('f36_fact', 'CLIII', 'CLIX'), ('fin13', 'CLIII', 'CLX')):
        d = C.newcombe(*band_rate[b], *band_rate[a])
        s_ = simd[(ctx, a, b)][0]
        pts.append((s_, d[0], (d[2] - d[1]) / 3.92))
        print(f'  {b:9s} - {a:9s} SIM {ctx:9s} {100 * s_:+5.2f} | live {100 * d[0]:+5.1f} [{100 * d[1]:+5.1f}, {100 * d[2]:+5.1f}]')
    print('  (CXXIV -> CXXXVIII has no shared dwelling band: CXXXVIII passed 12.5-12.75k in 30 matches while climbing; raw overall '
          '51.5% vs 48.1%, not comparable: it played 680 trophies higher)')
    s, l_, se = (np.array(x) for x in zip(*pts))
    wt = 1 / se ** 2
    b_ = (wt * s * l_).sum() / (wt * s * s).sum()
    h = 1.96 / math.sqrt((wt * s * s).sum())
    print(f'  calibration through the origin (live = slope x SIM, weights 1/var(live)): slope {b_:+.2f} [{b_ - h:+.2f}, {b_ + h:+.2f}] over '
          f'{len(pts)} links -- 1.00 = SIM gains show up live in full, 0 = not at all')
    print(f'  pooled 13k chain: SIM predicts CLX - CXXXVIII = {100 * (simd[("f36_fact", "CXXXVIII", "CLIII")][0] + simd[("fin13", "CLIII", "CLX")][0]):+.1f} pp; '
          f'live (13,000-13,249, own 4424) {100 * C.newcombe(*band_rate["CLX"], *band_rate["CXXXVIII"])[0]:+.1f} '
          f'[{100 * C.newcombe(*band_rate["CLX"], *band_rate["CXXXVIII"])[1]:+.1f}, {100 * C.newcombe(*band_rate["CLX"], *band_rate["CXXXVIII"])[2]:+.1f}]')
    print('\n### Rank agreement (SIM pooled win in one context vs the live shared-band win rate)')
    for ctx, ms in (('rt35_live', ('CXII', 'CXVII', 'CXXIV')), ('f36_fact', ('CXXXVIII', 'CLIII', 'CLIX'))):
        sw = [sum(r['outcome'] == 'win' for bl in ('std', 'fresh') for r in sim.get((m, ctx, bl), [])) /
              sum(len(sim.get((m, ctx, bl), [])) for bl in ('std', 'fresh')) for m in ms]
        lw = [band_rate[m][0] / band_rate[m][1] for m in ms]
        kt = kendall(sw, lw)
        print(f'  {ctx:10s} {ms}: SIM ' + ', '.join(f'{100 * x:.1f}' for x in sw) + ' | live ' + ', '.join(f'{100 * x:.1f}' for x in lw) +
              f' | Kendall tau {kt[0]:+.2f} ({kt[1]} concordant / {kt[2]} discordant); P(tau = +1 by chance) = 1/6')
    print('\n### Absolute calibration: SIM pooled win minus the live overall win of the same Mark (live at own tower 4424;'
          ' CLX_T16 compared with the all-16 SIM), in promotion order')
    for ctx, ms in (('rt35_live', ('CXII', 'CXVII', 'CXXIV', 'CXXXVIII')), ('rt35_std', ('CXII', 'CXVII', 'CXXIV')),
                    ('f36_fact', ('CXXIV', 'CXXXVIII', 'CLIII', 'CLIX')), ('fin13', ('CLIII', 'CLX')),
                    ('fin13_l16', ('CLIII', 'CLX'))):
        cells = []
        for m in ms:
            R = [r for bl in ('std', 'fresh') for r in sim.get((m, ctx, bl), [])]
            lm = 'CLX_T16' if (ctx == 'fin13_l16' and m == 'CLX') else m
            L = [r for r in rows if r['m'] == lm]
            sw, lw = sum(r['outcome'] == 'win' for r in R) / len(R), sum(r['win'] == 1 for r in L) / len(L)
            cells.append(f'{m} SIM {100 * sw:.1f} - live {100 * lw:.1f} = {100 * (sw - lw):+.1f}')
        print(f'  {ctx:10s} ' + ' | '.join(cells))
    n80 = lambda d: math.ceil(2 * (1.96 + 0.8416) ** 2 * 0.25 / d ** 2)  # noqa: E731
    print(f'\n### Power: matches PER ARM for 80% power, two-sided 5%, near 50%: 3 pp {n80(.03)}, 5 pp {n80(.05)}, 8 pp {n80(.08)}, '
          f'10 pp {n80(.10)}  (largest Mark sample here: 385)')
    return sim


# ------------------------------------------------------------------------------------------------ J9 crown realism
def j9(live, sim):
    sec('J9. Crown-path realism, SIM vs live, per opponent archetype')
    hdr = ['P(win)', 'P(opp takes a princess)', 'P(we take one)', 'both took one', 'OT share', 'OT starts 1-1', 'P(win|OT 1-1)',
           'P(win|OT 0-0)', 'P(win|lost a princess)', 'regulation loss', 'gave a 1-0 lead back']
    groups = {}
    l13 = [r for r in live if r['tro'] >= 12950 and r['m'] in ('CXXXVIII', 'CLIII', 'CLIX', 'CLX', 'CLX_T16')]
    groups['LIVE 13k: CXXXVIII>=12,950 + CLIII + CLIX + CLX'] = [(r['a'], r['rec']) for r in l13]
    groups['LIVE 13k, own tower 4424 (all four Marks)'] = [(r['a'], r['rec']) for r in l13 if own_hp(r) == 4424]
    groups['LIVE 13k, own tower 4858 (CLX after the level-up)'] = [(r['a'], r['rec']) for r in l13 if own_hp(r) == 4858]
    groups['LIVE 13k: CLX only (both tower levels)'] = [(r['a'], r['rec']) for r in l13 if r['m'] in ('CLX', 'CLX_T16')]
    groups['LIVE 13k: CXXXVIII >= 12,950 only'] = [(r['a'], r['rec']) for r in l13 if r['m'] == 'CXXXVIII']
    groups['LIVE 12k: CXII + CXVII + CXXIV (12,000-12,949)'] = [(r['a'], r['rec']) for r in live
                                                               if 12000 <= r['tro'] < 12950 and r['m'] in ('CXII', 'CXVII', 'CXXIV')]

    def simg(m, ctx, blks=('std', 'fresh')):
        return [(arch2(r['opp_deck'] or []), C.sim_rec(r)) for bl in blks for r in sim.get((m, ctx, bl), [])]
    groups['SIM CLX fin13 live-levels'] = simg('CLX', 'fin13')
    groups['SIM CLX fin13 L16'] = simg('CLX', 'fin13_l16')
    groups['SIM CLIII fin13 live-levels'] = simg('CLIII', 'fin13')
    groups['SIM CLIII fin13 L16'] = simg('CLIII', 'fin13_l16')
    groups['SIM CXXXVIII f36 (E4 T .1)'] = simg('CXXXVIII', 'f36_fact')
    for ctx, lab in (('s2_e4T3', 'E4 T .3'), ('s2_gen10', 'pro-imitation gen_v32 d10'), ('s2_gen40', 'pro-imitation d40'),
                     ('s2_expl', 'exploiter 862bfe92')):
        groups[f'SIM CXXXVIII f36 vs {lab}'] = simg('CXXXVIII', ctx, ('std',))
    groups['SIM live levels, f36: CXXXVIII + CLIII + CLIX'] = sum((simg(m, 'f36_fact') for m in ('CXXXVIII', 'CLIII', 'CLIX')), [])
    print('\n### ALL archetypes')
    print('  ' + ' | '.join(['group'] + hdr))
    for g, rs in groups.items():
        print('  ' + ' | '.join([g] + C.fmt_stats(C.crown_stats([x for _, x in rs]))))
    print('\n### Like-for-like: the SAME learner vs SIM opponents and vs live opponents (SIM rows with telemetry = exact crown order)')
    print('  ' + ' | '.join(['group'] + hdr))
    lfl = {}
    lfl['LIVE CXII, all (12.0-12.3k)'] = [x for a, x in [(r['a'], r['rec']) for r in live if r['m'] == 'CXII']]
    lfl['SIM CXII vs E4 T .1, CAL pool (ECON_r1, exact)'] = [C.sim_rec(r) for r in sim.get(('CXII', 'tel_cal_e4', 'std'), [])]
    lfl['LIVE CXXIV vs Hog decks (12k)'] = [r['rec'] for r in live if r['m'] == 'CXXIV' and r['a'] == 'hog']
    for ctx, lab in (('tel_hog_e4', 'E4 T .1'), ('tel_hog_e4u65', 'Stage-2 Phase C E4-init exploiter u65'),
                     ('tel_hog_il65', 'Stage-2 Phase C imitation-init exploiter u65')):
        lfl[f'SIM CXXIV vs {lab}, Hog pool (exact)'] = [C.sim_rec(r) for r in sim.get(('CXXIV', ctx, 'std'), [])]
    lfl['LIVE CXXXVIII vs Hog decks (13k, >= 12,950)'] = [r['rec'] for r in live if r['m'] == 'CXXXVIII' and r['a'] == 'hog'
                                                          and r['tro'] >= 12950]
    lfl['SIM CXXXVIII vs E4 T .1, Hog decks of the live pool'] = [C.sim_rec(r) for bl in ('std', 'fresh')
                                                                 for r in sim.get(('CXXXVIII', 'f36_fact', bl), []) if arch2(r['opp_deck'] or []) == 'hog']
    for ctx, lab in (('c_hog13k_e4u65', 'Stage-2 E4-init exploiter u65'), ('c_hog13k_il65', 'Stage-2 imitation-init exploiter u65')):
        lfl[f'SIM CXXXVIII vs {lab}, Hog pool, 13k levels'] = [C.sim_rec(r) for r in sim.get(('CXXXVIII', ctx, 'std'), [])]
    for g, rs in lfl.items():
        print('  ' + ' | '.join([g] + C.fmt_stats(C.crown_stats(rs))))
    print('\n### Deck mix: share of matches per archetype (live = cards seen; SIM = full opponent deck)')
    print('  ' + 'group'.ljust(52) + ''.join(f'{a[:10]:>11s}' for a in ARCH))
    for g in ('LIVE 13k: CXXXVIII>=12,950 + CLIII + CLIX + CLX', 'LIVE 12k: CXII + CXVII + CXXIV (12,000-12,949)', 'SIM CLX fin13 live-levels',
              'SIM CXXXVIII f36 (E4 T .1)'):
        c = Counter(a for a, _ in groups[g])
        n = sum(c.values())
        print('  ' + g[:51].ljust(52) + ''.join(f'{100 * c[a] / n:10.1f}%' for a in ARCH))
    print('\n### Per archetype: LIVE 13k (pooled 4 Marks) vs SIM CLX fin13 live-levels (SIMlv) vs SIM CLX fin13 all-16 (SIM16)'
          ' [P(opp takes a princess) | P(win) | P(win|OT 1-1) | gave 1-0 back]')
    for a in ARCH:
        cells = []
        for g in ('LIVE 13k: CXXXVIII>=12,950 + CLIII + CLIX + CLX', 'SIM CLX fin13 live-levels', 'SIM CLX fin13 L16'):
            st = C.crown_stats([x for aa, x in groups[g] if aa == a])
            if st['n'] == 0:
                cells.append('n=0')
                continue
            gb = P(*st['giveback']) if st['giveback'] else f"<={100 * st['giveback_bound']:.0f}%"
            cells.append(f"lose-princess {P(*st['lose_princess'])}; win {P(*st['win'])}; OT1-1 win {P(*st['win_ot11'])}; giveback {gb}")
        print(f'  {a}\n     LIVE  {cells[0]}\n     SIM11 {cells[1]}\n     SIM16 {cells[2]}')
    # matched comparisons: live before our tower level-up (own 4424 = L15-like) vs the SIM with live levels (learner tower 15, opponent
    # levels from the live profile: f36_fact), and live after it (own 4858, opponents mostly 4858) vs the all-16 SIM
    pairs = (('SIM live levels, f36: CXXXVIII + CLIII + CLIX', 'LIVE 13k, own tower 4424 (all four Marks)'),
             ('SIM CLX fin13 L16', 'LIVE 13k, own tower 4858 (CLX after the level-up)'))
    for fld, lab in (('ever_lost', 'P(opp takes a princess in play)'), ('win', 'P(win)'), ('both', 'both sides took a princess'),
                     ('ot', 'OT share')):
        f = {'ever_lost': lambda x: x['ever_lost'], 'win': lambda x: x['win'] == 1.0,
             'both': lambda x: x['c'] >= 1 and x['oc'] >= 1, 'ot': lambda x: x['cls'] in ('ot', 'otend')}[fld]
        print(f'\n### Gap table, {lab}: SIM minus matched LIVE, pp [Newcombe 95%]  '
              f'(A) live-levels SIM vs live own-4424 13k | (B) all-16 SIM CLX vs live own-4858 13k')
        for a in ARCH + ('ALL',):
            out = []
            for gs, gl in pairs:
                L = [x for aa, x in groups[gl] if a == 'ALL' or aa == a]
                Sx = [x for aa, x in groups[gs] if a == 'ALL' or aa == a]
                if len(L) >= 5 and Sx:
                    d = C.newcombe(sum(map(f, Sx)), len(Sx), sum(map(f, L)), len(L))
                    out.append(f'SIM {100 * sum(map(f, Sx)) / len(Sx):5.1f} live {100 * sum(map(f, L)) / len(L):5.1f} (n {len(L):3d}) '
                               f'gap {100 * d[0]:+6.1f} [{100 * d[1]:+6.1f}, {100 * d[2]:+6.1f}]')
                else:
                    out.append(f'live n={len(L)}: too few'.ljust(62))
            print(f'  {a:17s} (A) {out[0]:62s} | (B) {out[1]}')
    return groups


# ------------------------------------------------------------------------------------------------ J10 opponent play realism
def j10(live):
    sec('J10. Opponent play realism (human/opp_behaviour.py features, one detector on both sides)')
    def ob(r):
        return dict(src='live', id=r['log'], seen=r['seen'], res=1 if r['win'] == 1 else 0, end=r['end'], t0=r['t0'], side=r['side'],
                    plays=r['plays'], mine=r['mine'])
    L13 = [ob(r) for r in live if r['tro'] >= 12950 and r['m'] in ('CXXXVIII', 'CLIII', 'CLIX', 'CLX', 'CLX_T16')]
    L12 = [ob(r) for r in live if 12000 <= r['tro'] < 12950]
    sims = {'E4 T .1, CAL pool, learner r1 (ECON_r1)': 'sim_ECON_r1',
            'E4 T .1, Hog pool, learner CXXIV (T_e4base)': 'sim_T_e4base',
            'gen_v32_s0 pro imitation d10 (S_v32_d10_r0)': 'sim_S_v32_d10_r0',
            'gen_v32_s0 d20 + 20-tick reaction (S_v32_d20_r20)': 'sim_S_v32_d20_r20',
            'E4 d30 + 20-tick reaction (T_e4_d30_r20)': 'sim_T_e4_d30_r20',
            'Stage-2 Phase C imitation+RL exploiter u65 (T_il_u0065)': 'sim_T_il_u0065'}
    SM = {k: OB.load(v) for k, v in sims.items()}
    FL13 = [(m, OB.features(m)) for m in L13]
    FL12 = [(m, OB.features(m)) for m in L12]
    print(f'\n  live 13k n={len(L13)}, live 12k n={len(L12)}; SIM sets: ' + ', '.join(f'{k} n={len(v)}' for k, v in SM.items()))
    print('\n### Distance (RMS Cohen d over 13 features; floor = the value two samples of one population give) vs LIVE 13k')
    print('  ' + 'SIM set'.ljust(58) + 'ALL'.rjust(14) + ''.join(f'{a[:10]:>14s}' for a in ARCH))
    for k, ms in SM.items():
        FS = [(m, OB.features(m)) for m in ms]
        cells = []
        for a in ('ALL',) + ARCH:
            Lf = [f for m, f in FL13 if a == 'ALL' or arch2(m['seen']) == a]
            Sf = [f for m, f in FS if a == 'ALL' or arch2(m['seen']) == a]
            if len(Lf) >= 10 and len(Sf) >= 10:
                d, fl = OB.distance(OB.compare(Lf, Sf), len(Lf), len(Sf))
                cells.append(f'{d:.2f}/{fl:.2f}')
            else:
                cells.append('-')
        print('  ' + k[:57].ljust(58) + ''.join(f'{c:>14s}' for c in cells))
    Lf12 = [f for _, f in FL12]
    Lf13 = [f for _, f in FL13]
    d, fl = OB.distance(OB.compare(Lf12, Lf13), len(Lf12), len(Lf13))
    print(f'  {"LIVE 12k vs LIVE 13k (how much the human population itself moves)":58s}{d:.2f}/{fl:.2f}')
    print('\n### Feature means, ALL matches: LIVE 13k | LIVE 12k | each SIM set (Cohen d vs LIVE 13k)')
    cm = {k: OB.compare(Lf13, [OB.features(m) for m in ms]) for k, ms in SM.items()}
    c12 = OB.compare(Lf13, Lf12)
    print('  feature       live13k   live12k(d)     ' + ''.join(f'{k.split("(")[-1][:-1][:14]:>20s}' for k in SM))
    for f in OB.FEATS:
        print(f'  {f:12s} {c12[f][1]:8.2f}  {c12[f][3]:7.2f}({c12[f][4]:+.2f}) ' +
              ''.join(f'{cm[k][f][3]:12.2f}({cm[k][f][4]:+5.2f})' for k in SM))
    # per-archetype detail for the eval-default opponent (E4) vs live 13k on the three biggest gaps
    print('\n### Per archetype, LIVE 13k vs E4 (ECON_r1): ppm_2x | react_3s | push_max | our_half | first_tick  (live / SIM)')
    FS = [(m, OB.features(m)) for m in SM['E4 T .1, CAL pool, learner r1 (ECON_r1)']]
    for a in ARCH:
        Lf = [f for m, f in FL13 if arch2(m['seen']) == a]
        Sf = [f for m, f in FS if arch2(m['seen']) == a]
        if len(Lf) < 10 or len(Sf) < 10:
            print(f'  {a:17s} live n={len(Lf)} SIM n={len(Sf)}: too few')
            continue
        c = OB.compare(Lf, Sf)
        print(f'  {a:17s} live n={len(Lf):4d} SIM n={len(Sf):4d}: ' +
              ' | '.join(f'{f} {c[f][1]:.2f}/{c[f][3]:.2f} (d {c[f][4]:+.2f})' for f in ('ppm_2x', 'react_3s', 'push_max', 'our_half', 'first_tick')))


# ------------------------------------------------------------------------------------------------ Stage-2 post-mortem numbers
def stage2(sim):
    sec('Stage-2 post-mortem numbers')
    for run in ('stepd_ctrl', 'stepd_ctrl_nos2'):
        agg = defaultdict(lambda: [0, 0])
        for l in open(S.B / f'stepd/{run}/train_log.jsonl', encoding='utf-8'):
            j = json.loads(l)
            if j.get('type') != 'update':
                continue
            for k, v in (j.get('league') or {}).get('by_opp', {}).items():
                a = agg[(j['update'] // 26, k)]
                a[0] += v['W']
                a[1] += v['n']
        print(f'\n  {run}: training win rate by opponent bucket, per block of 26 updates (exploiter_league = the Stage-2 s2_all_il_sA opponent)')
        for k in sorted({k for _, k in agg}):
            print(f'    {k:18s} ' + '  '.join(f'u{b * 26:03d}+ {P(*agg[(b, k)]):24s}' for b in range(5) if agg[(b, k)][1]))
    for blk in ('std', 'fresh'):
        d = S.paired(sim[('CTRL', 'fin13', blk)], sim[('CLX', 'fin13', blk)])
        print(f'  SIM fin13 {blk}: CTRL (with Stage-2 opponents) - CLX (without) {100 * d[0]:+.2f} [{100 * d[1]:+.2f}, {100 * d[2]:+.2f}] n={d[3]}')
    for m in ('CTRL', 'CLX', 'CLIII'):
        recs = [(arch2(r['opp_deck'] or []), C.sim_rec(r)) for bl in ('std', 'fresh') for r in sim[(m, 'fin13', bl)]]
        st = C.crown_stats([x for _, x in recs])
        print(f'  SIM fin13 {m:6s} ' + ' | '.join(f'{k} {P(*st[k])}' for k in ('win', 'lose_princess', 'take_princess', 'both', 'win_ot11')))
    print('\n  Per archetype, SIM fin13 pooled: CTRL - CLX win (paired, pp)')
    ctrl = sim[('CTRL', 'fin13', 'std')] + sim[('CTRL', 'fin13', 'fresh')]
    clx = sim[('CLX', 'fin13', 'std')] + sim[('CLX', 'fin13', 'fresh')]
    for a in ARCH:
        ra = [r for r in ctrl if arch2(r['opp_deck'] or []) == a]
        rb = [r for r in clx if arch2(r['opp_deck'] or []) == a]
        d = S.paired(ra, rb)
        if d:
            print(f'    {a:17s} {100 * d[0]:+6.2f} [{100 * d[1]:+6.2f}, {100 * d[2]:+6.2f}] n={d[3]}')


# ------------------------------------------------------------------------------------------------ data audit
def audit(live):
    sec('Data audit: live opponent action sequences usable for an opponent model')
    all_rows = [orjson.loads(l) for l in gzip.open(HERE / 'out/live_matches.jsonl.gz')]
    ice = [r for r in live]
    print(f'  graded live matches in the table: {len(all_rows)} (icebow main account >= 10k trophies: {len(ice)})')
    for lo, hi, lab in ((12000, 12950, '12k band 12,000-12,949'), (12950, 99999, '13k band >= 12,950'), (12000, 99999, 'all >= 12,000')):
        rs = [r for r in ice if lo <= r['tro'] < hi]
        fr = sum(r['ts'] >= '20261015_172600' for r in rs)
        print(f'\n  {lab}: {len(rs)} matches; with 2-tick frame events (spells visible to the PublicObserver path) {fr}; '
              f'detected opponent plays {sum(len(r["plays"]) for r in rs)} ({sum(len(r["plays"]) for r in rs) / max(1, len(rs)):.1f}/match)')
        c = Counter(r['a'] for r in rs)
        print('    ' + ', '.join(f'{a} {c[a]} ({sum(len(r["plays"]) for r in rs if r["a"] == a)} plays)' for a in ARCH))
        lv = Counter()
        for r in rs:
            hp = [v for k, v in r['tower_maxhp'].items() if k.startswith('opp_P')]
            lv[max(hp) if hp else None] += 1
        print('    opponent princess max HP (tower level proxy): ' + ', '.join(f'{k}: {v}' for k, v in lv.most_common(6)))
    rs = [r for r in ice if r['tro'] >= 12950]
    kinds = Counter()
    for r in rs:
        for p in r['plays']:
            kinds[(OB.catalog()[0].get(p[1]) or ('?',))[0]] += 1
    print(f'\n  13k detected plays by card type (PlayDetector; bodiless spells invisible): {dict(kinds)}')
    nd = Counter(min(8, len(r['seen'])) for r in rs)
    print('  distinct opponent cards seen per 13k match (bodies + detected plays; deck = 8): ' +
          ', '.join(f'{k}: {nd[k]}' for k in sorted(nd)) + f' -> >= 7 seen in {100 * sum(v for k, v in nd.items() if k >= 7) / len(rs):.0f}%')
    gaps = [p[6] for r in rs for p in r['plays']]
    print(f'  first-sighting reader gap > 12 ticks (position unreliable): {100 * sum(g > 12 for g in gaps) / max(1, len(gaps)):.1f}% of plays')


def main():
    random.seed(0)
    live = load_live()
    sim = j11(live)
    j9(live, sim)
    j10(live)
    stage2(sim)
    audit(live)


if __name__ == '__main__':
    main()
