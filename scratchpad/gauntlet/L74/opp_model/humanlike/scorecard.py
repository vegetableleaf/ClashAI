"""Opponent human-likeness scorecard (plan1026 Pillar 2): levels A (per decision), B (closed-loop behaviour), D (outcome parity),
coverage H.  Level C (match discriminator) is a later ticket; its thresholds are already in THRESHOLDS.json.

    icebow/.venv/Scripts/python.exe -I scratchpad/gauntlet/L74/opp_model/humanlike/scorecard.py repro
    icebow/.venv/Scripts/python.exe -I scratchpad/gauntlet/L74/opp_model/humanlike/scorecard.py score NAME=PATH [NAME=PATH ...] [--json out.json]
    icebow/.venv/Scripts/python.exe -I scratchpad/gauntlet/L74/opp_model/humanlike/scorecard.py selftest

PATH = a root holding NAME_SEED/D3/matches.jsonl (rows with o3_plays; fin15 gap.py output) or `ob:SIMNAME` = a human/data/sim_SIMNAME.json.gz
(opp_behaviour telemetry, has positions).  Reuses opp_behaviour (features / Cohen d), o3_score (SIM rows -> plays), o4r_table (Ranked rows),
analyze (live 13k set, arch2).  Refuses to run unless THRESHOLDS.json hashes to the sha logged in HUMANLIKE.md.
Public-information rule: live opponents enter ONLY through detected plays (opp_behaviour); no hand / deck-order / elixir is read from live
(live `opp_el` is the public counter the reader already shows)."""
from __future__ import annotations

import hashlib
import json
import math
import random
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
L74 = HERE.parents[1]
ROOT = HERE.parents[4]
O = L74 / 'opp_model'
sys.path[:0] = [str(O), str(O / 'w14'), str(O / 'diag12'), str(L74 / 'human'), str(ROOT)]
PB = Path.home() / 'pod_backup_weekend'
Z90 = 1.645                                                      # TOST: 90% CI inside the margin


# ------------------------------------------------------------------ thresholds (pre-registered)
def load_thresholds():
    raw = (HERE / 'THRESHOLDS.json').read_bytes().replace(b'\r\n', b'\n')       # git may turn LF into CRLF on checkout
    sha = hashlib.sha256(raw).hexdigest()
    logged = re.findall(r'\|\s*`([0-9a-f]{64})`', (HERE / 'HUMANLIKE.md').read_text(encoding='utf-8'))
    if not logged or logged[-1] != sha:
        raise SystemExit(f'THRESHOLDS.json sha {sha} != last sha logged in HUMANLIKE.md ({logged[-1] if logged else None}): refusing to score')
    return json.loads(raw), sha


# ------------------------------------------------------------------ per-match stats
def extra_stats(plays):
    """Stats from the opponent play list alone (tick, key, ...), identical code for live and SIM."""
    ts = sorted(p[0] for p in plays)
    gaps = [(b - a) / 20 for a, b in zip(ts, ts[1:])]
    keys = [p[1] for p in sorted(plays, key=lambda p: p[0])]
    nan = float('nan')
    q = lambda xs, f: sorted(xs)[min(len(xs) - 1, int(f * len(xs)))] if xs else nan      # noqa: E731
    c = Counter(keys)
    ent = -sum(v / len(keys) * math.log(v / len(keys)) for v in c.values()) if keys else nan
    return dict(gap_p10=q(gaps, .1), gap_p50=q(gaps, .5), gap_p90=q(gaps, .9), card_entropy=ent,
                top_card_share=max(c.values()) / len(keys) if keys else nan,
                repeat_rate=sum(a == b for a, b in zip(keys, keys[1:])) / (len(keys) - 1) if len(keys) > 1 else nan)


# signature stats: (archetype label of analyze.arch2) -> {stat: card keys}; per match: plays per minute of those cards and first tick
SIG = {'hog': ('hogrider',), 'hyperbait': ('goblin_barrel', 'goblin_gang', 'princess', 'skeleton_barrel'),
       'golem': ('golem', 'elixir_golem', 'golemite'), 'lava_hound': ('lava_hound',), 'pekka_bridge': ('pekka', 'battle_ram', 'bandit', 'royal_ghost'),
       'royal_giant': ('royal_giant',), 'royal_giant_monk': ('royal_giant', 'monk')}
SIG_STATS = ('sig_per_min', 'sig_first_s')


def sig_stats(arch, plays, end):
    ks = {k.replace('_', '').replace('-', '') for k in SIG.get(arch, ())}
    hit = sorted(p[0] for p in plays if p[1].replace('_', '').replace('-', '') in ks)
    mins = max(end, 1) / 20 / 60
    return dict(sig_per_min=len(hit) / mins, sig_first_s=hit[0] / 20 if hit else float('nan'))


def match_row(arch, m, positions):
    import opp_behaviour as OB
    f = OB.features(m)
    f.update(extra_stats(m['plays']))
    f.update(sig_stats(arch, m['plays'], m['end']))
    f['_arch'], f['_pos'] = arch, positions
    return f


# ------------------------------------------------------------------ sources
def live_ref(which):
    """[(arch, feature row)] of live matches. '13k' = O3's reference (>= 12,950 trophies, CXXXVIII..CLX), '12k' = all >= 10k main-account matches
    (opp_behaviour live.json.gz), 'ranked' = the 233 Ranked logs."""
    import analyze as AN
    import opp_behaviour as OB
    if which == '13k':
        return [match_row(r['a'], dict(src='live', id=r['log'], seen=r['seen'], res=0, end=r['end'], t0=r['t0'], side=r['side'], plays=r['plays'],
                                       mine=r['mine']), True)
                for r in AN.load_live() if r['tro'] >= 12950 and r['m'] in ('CXXXVIII', 'CLIII', 'CLIX', 'CLX', 'CLX_T16')]
    if which == '12k':
        return [match_row(AN.arch2(m['seen']), m, True) for m in OB.load('live')]
    import o4r_table as T
    import live_table as LT
    out = []
    for r in T.ranked_rows():
        d = LT.cached(LT.LOGS / r['key'])
        if d and d.get('start'):
            out.append(match_row(r['arch'], dict(src='live', id=r['key'], seen=d['seen'], res=0, end=d['end'], t0=d['t0'], side=d['side'],
                                                 plays=d['plays'], mine=d['mine']), True))
    return out


def sim_rows(path):
    """-> (feature rows, raw rows or None).  Positions exist only on `ob:` sources."""
    import analyze as AN
    import opp_behaviour as OB
    import o3_score as O3
    from pipeline.opp_elixir_count import card_cost
    if path.startswith('ob:'):
        ms = OB.load('sim_' + path[3:])
        return [match_row(AN.arch2(m.get('deck') or m['seen']), m, True) for m in ms], None
    import o4r_table as T
    raw = [j for rows in T.load_sim(path).values() for j in rows]
    out = []
    for r, (arch, f) in zip([j for j in raw if j.get('o3_plays')], O3.behaviour([j for j in raw if j.get('o3_plays')])):
        pl = r['o3_plays']
        m = dict(plays=[[int(t), c.replace('-', '_'), card_cost(c.replace('-', '_')) or 0.0, 0.0, 0.0, 1, 99, None] for t, c in pl['opp'] if O3.visible(c)],
                 mine=[int(t) - 26 for t, _ in pl['learner']], end=int(r['end_tick']), t0=0, seen=[])
        out.append(match_row(arch, m, False))
    return out, raw


# ------------------------------------------------------------------ level B
CORE9 = ['ppm_1x', 'ppm_2x', 'first_tick', 'react_s', 'react_3s', 'react_lift', 'push_mean', 'push_max', 'spell_share']       # = O3.FEATS
POS4 = ['own_half', 'bridge', 'our_half', 'opp_el']
EXTRA = ['gap_p10', 'gap_p50', 'gap_p90', 'card_entropy', 'top_card_share', 'repeat_rate']


def _ms(xs):
    xs = [x for x in xs if not math.isnan(x)]
    n = len(xs)
    if n < 2:
        return n, float('nan'), float('nan')
    mu = sum(xs) / n
    return n, mu, math.sqrt(sum((x - mu) ** 2 for x in xs) / (n - 1))


def cohen(L, S, keys, nmin=5):
    """{k: (nL, muL, sdL, nS, muS, sdS, d, se_d)}; d = (muS - muL) / pooled SD, the opp_behaviour.compare formula."""
    out = {}
    for k in keys:
        nl, ml, sl = _ms([x[k] for x in L])
        ns, ms_, ss = _ms([x[k] for x in S])
        d = se = float('nan')
        if nl >= nmin and ns >= nmin:
            sp = math.sqrt(((nl - 1) * sl ** 2 + (ns - 1) * ss ** 2) / (nl + ns - 2))
            if sp > 0:
                d = (ms_ - ml) / sp
                se = math.sqrt(1 / nl + 1 / ns + d * d / (2 * (nl + ns)))
        out[k] = (nl, ml, sl, ns, ms_, ss, d, se)
    return out


def rms(c, keys):
    ds = [c[k][6] for k in keys if not math.isnan(c[k][6])]
    return math.sqrt(sum(d * d for d in ds) / len(ds)) if ds else float('nan')


def level_b(L, S, th, feats=None):
    """L live feature rows, S model rows -> dict.  feats default = CORE9 (+ POS4 when both sides have positions) + EXTRA.
    pass = RMS d (CORE) <= b_live_rms_d_max AND every stat TOST-inside b_live_per_stat_abs_d_max AND B3 spread ratios inside the range."""
    B = th['B']
    pos = all(x['_pos'] for x in S) and all(x['_pos'] for x in L)
    core = CORE9 + (POS4 if pos else [])
    feats = feats or core + EXTRA
    core = [k for k in core if k in feats]
    c = cohen(L, S, feats, B['min_n_per_side_for_a_stat'])
    marg = B['b_live_per_stat_abs_d_max']
    tost = {k: (abs(v[6]) + Z90 * v[7] < marg) if not math.isnan(v[6]) else False for k, v in c.items()}
    r_core = rms(c, core)
    r9 = rms(c, CORE9)
    spread = {k: (c[k][5] / c[k][2] if c[k][2] else float('nan')) for k in B['b3_stats'] if k in c}
    lo, hi = B['b3_spread_ratio_range']
    b3 = {k: (lo <= v <= hi) for k, v in spread.items()}
    floor = math.sqrt(1 / max(1, len(L)) + 1 / max(1, len(S)))
    return dict(n_live=len(L), n_sim=len(S), rms_core=r_core, rms9=r9, floor=floor, stats=c, tost=tost, spread=spread, b3=b3, positions=pos,
                pass_rms=bool(r_core <= B['b_live_rms_d_max']), pass_tost=all(tost.values()), pass_b3=all(b3.values()) if b3 else False,
                passed=bool(r_core <= B['b_live_rms_d_max'] and all(tost.values()) and b3 and all(b3.values())))


def sig_table(L, S):
    """per-archetype signature stats d (SIG labels only)."""
    out = {}
    for a in SIG:
        la, sa = [x for x in L if x['_arch'] == a], [x for x in S if x['_arch'] == a]
        out[a] = (len(la), len(sa), cohen(la, sa, list(SIG_STATS)))
    return out


def per_arch(L, S, th):
    out = {}
    for a in sorted({x['_arch'] for x in L} | {x['_arch'] for x in S}):
        la, sa = [x for x in L if x['_arch'] == a], [x for x in S if x['_arch'] == a]
        if len(la) >= 5 and len(sa) >= 5:
            out[a] = level_b(la, sa, th, feats=CORE9)
        else:
            out[a] = None
    return out


# ------------------------------------------------------------------ level D (pooled version for baselines; the real test needs the sealed block)
def newcombe(k1, n1, k2, n2):
    import o4r_table as T
    return T.newcombe(k1, n1, k2, n2)


def level_d(raw, th, live_rows=None):
    """SIM win rate of the learner vs the live win rate it had against the same opponents.  live_rows = o4r_table.ranked_rows()."""
    import o4r_table as T
    D = th['D']
    live_rows = live_rows or T.ranked_rows()
    sim = [T.sim_row(j, 'x') for j in raw]
    kS, nS = sum(r['win'] == 1 for r in sim), len(sim)
    kL, nL = sum(r['win'] == 1 for r in live_rows), len(live_rows)
    d, lo, hi = newcombe(kS, nS, kL, nL)
    m = D['mean_pred_vs_live_pp_max'] / 100
    out = dict(sim_win=kS / nS, live_win=kL / nL, n_sim=nS, n_live=nL, diff_pp=100 * d, ci_pp=(100 * lo, 100 * hi),
               tost_equiv=bool(lo > -m and hi < m), enough_live=bool(nL >= D['min_sealed_matches']), arch={})
    for a in sorted({r['arch'] for r in live_rows}):
        s_, l_ = [r for r in sim if r['arch'] == a], [r for r in live_rows if r['arch'] == a]
        if s_ and l_:
            out['arch'][a] = (len(s_), len(l_), 100 * (sum(r['win'] == 1 for r in s_) / len(s_) - sum(r['win'] == 1 for r in l_) / len(l_)))
    out['passed'] = bool(out['tost_equiv'] and out['enough_live'])
    return out


# ------------------------------------------------------------------ level A (metrics on a prediction dump; no baseline has one)
def level_a(p_true, top1, p_top, correct_top, gaps_rescaled, th, ceiling=None):
    """p_true: model probability of the human's card per decision; top1: argmax==human (0/1); p_top / correct_top: confidence of the
    argmax and whether right (ECE); gaps_rescaled: time-rescaled gaps between plays (should be Exp(1))."""
    A = th['A']
    nll = -sum(math.log(max(p, 1e-12)) for p in p_true) / len(p_true)
    agree = sum(top1) / len(top1)
    bins = defaultdict(list)
    for p, c in zip(p_top, correct_top):
        bins[min(9, int(p * 10))].append((p, c))
    ece = sum(len(v) * abs(sum(p for p, _ in v) / len(v) - sum(c for _, c in v) / len(v)) for v in bins.values()) / len(p_top)
    g = sorted(gaps_rescaled)
    n = len(g)
    ks = max(max((i + 1) / n - (1 - math.exp(-x)), (1 - math.exp(-x)) - i / n) for i, x in enumerate(g)) if n else float('nan')
    return dict(nll=nll, agreement=agree, ece_pp=100 * ece, ks=ks, n=len(p_true), n_gaps=n,
                pass_agreement=bool(agree >= A['agreement_card_min']), pass_ece=bool(len(p_true) >= A['ece_min_decisions'] and 100 * ece <= A['ece_card_pp_max']),
                pass_ks=bool(n >= A['timing_min_gaps_per_archetype'] and ks <= A['timing_rescaled_gap_ks_max']))


def ceiling():
    j = L74.parent / 'L67' / 'agreement_ceiling3.out'
    first = json.loads([ln for ln in j.read_text().splitlines() if ln.startswith('{')][0])
    return dict(card=first['same_card_pct'], cell=first['same_cell_pct'], pairs=(first['card_pairs'], first['cell_pairs']))


# ------------------------------------------------------------------ coverage H
def coverage(arch_pass, th):
    """H = sum_c w_c pass_c over cells = (live arch label) x (band).  arch_pass: {arch: bool}.  The model is not band-conditioned, so a
    cell's pass = its archetype's pass (stated).  Head-deck cells are not built yet (need HF side counts): they fold into archetypes."""
    import analyze as AN
    bands = th['H']['bands_trophies']
    cnt = Counter()
    for r in AN.load_live():
        if r['tro'] >= 12000:
            b = next(i for i, (lo, hi) in enumerate(bands) if lo <= r['tro'] < hi)
            cnt[(b, r['a'])] += 1
    tot = sum(cnt.values())
    h = sum(n / tot for (b, a), n in cnt.items() if arch_pass.get(a))
    return dict(H=h, cells=len(cnt), live_n=tot, cell_share={f'{bands[b][0]}-{bands[b][1]}|{a}': n / tot for (b, a), n in sorted(cnt.items())})


# ------------------------------------------------------------------ printing
def f2(x):
    return '-' if x is None or (isinstance(x, float) and math.isnan(x)) else f'{x:.2f}'


def report(name, path, refs, th):
    S, raw = sim_rows(path)
    print(f'\n### {name}  ({len(S)} model matches with plays{"" if raw is None else f", {len(raw)} raw rows"}; positions: {S[0]["_pos"] if S else None})')
    res = {}
    for rn, L in refs.items():
        b = level_b(L, S, th)
        res[rn] = b
        print(f'B vs {rn:6s} n_live {b["n_live"]:4d}  RMS d (core{"13" if b["positions"] else "9"}) {f2(b["rms_core"])}  RMS d CORE9 {f2(b["rms9"])}  floor {f2(b["floor"])} '
              f'| RMS<=.10 {b["pass_rms"]}  TOST<.20 all {b["pass_tost"]}  B3 {b["pass_b3"]}  => B {"PASS" if b["passed"] else "FAIL"}')
    pr = per_arch(refs['13k'], S, th)
    arch_pass = {a: bool(v and v['passed']) for a, v in pr.items()}
    print('per-archetype CORE9 RMS d vs 13k: ' + ', '.join(f'{a} {f2(v["rms9"])} (n {v["n_sim"]}/{v["n_live"]})' if v else f'{a} n/a' for a, v in pr.items()))
    sg = sig_table(refs['13k'], S)
    print('signature stats d (SIM-live): ' + '; '.join(f'{a}: ' + ' '.join(f'{k} {f2(c[6])}' for k, c in v[2].items()) + f' (n {v[1]}/{v[0]})'
                                                  for a, v in sg.items() if v[1] >= 5))
    out = dict(name=name, B=res, arch_pass=arch_pass)
    if raw is not None:
        try:
            d = level_d(raw, th)
            out['D'] = d
            print(f'D (pooled, Ranked-233, NOT the sealed block): SIM win {100 * d["sim_win"]:.1f}% (n {d["n_sim"]}) vs live {100 * d["live_win"]:.1f}% (n {d["n_live"]}): '
                  f'{d["diff_pp"]:+.1f} pp [{d["ci_pp"][0]:+.1f}, {d["ci_pp"][1]:+.1f}]  enough_live(>=1500) {d["enough_live"]}  => D {"PASS" if d["passed"] else "FAIL"}')
        except Exception as e:                                                  # noqa: BLE001
            print('D: not computable:', repr(e)[:120])
    cov = coverage(arch_pass, th)
    print(f'H (B-only, A/C/D absent => H_ABC = 0): H_B {cov["H"]:.3f} over {cov["cells"]} cells (live n {cov["live_n"]}); H_ABC 0.000 (A, C not scored)')
    out['H_B'] = cov['H']
    return out


# ------------------------------------------------------------------ reproduction + self-test
def repro(th):
    refs = {k: live_ref(k) for k in ('13k', '12k')}
    ranked = live_ref('ranked')
    rows = []
    n13 = len(refs['13k'])
    b = level_b(refs['13k'], refs['12k'], th)
    rows.append(('human floor sqrt(1/n+1/n), n=748', 0.05, math.sqrt(2 / n13)))
    rows.append(('12k vs 13k humans, 13 stats (opp_behaviour feature set)', 0.10, rms(cohen(refs['13k'], refs['12k'], CORE9 + POS4), CORE9 + POS4)))
    rows.append(('12k vs 13k humans, CORE9 (no positions)', None, b['rms9']))
    s, _ = sim_rows('ob:ECON_r1')
    c = cohen(refs['13k'], s, CORE9 + POS4)
    rows.append(('E4 (ECON_r1, 960) vs 13k, 13 stats', 0.93, rms(c, CORE9 + POS4)))
    rows.append(('E4 (ECON_r1) vs 13k, CORE9 (the form every o3 row set uses)', None, rms(c, CORE9)))
    import o4r_table as T
    for lab, ref, path, which in [('O2b (o3_liveoppB T.1 d40, 480) vs 13k', 0.65, PB / 'o3/48148/o3_liveoppB_T0.1_d40_r0', '13k'),
                                  ('gen_v32_s0 (o3_gen_s0 T.1 d40, 480) vs 13k', 0.79, PB / 'o3/48148/o3_gen_s0_T0.1_d40_r0', '13k'),
                                  ('I u40 (w14F_Iu40, 2880) vs Ranked-233', 0.78, PB / 'w14/o4/w14F_Iu40', 'ranked'),
                                  ('B u20 (w14O4_Bu20, 1920) vs Ranked-233', 0.53, PB / 'w14/o4/w14O4_Bu20', 'ranked')]:
        S, _ = sim_rows(str(path))
        L = refs['13k'] if which == '13k' else ranked
        rows.append((lab, ref, rms(cohen(L, S, CORE9), CORE9)))
        # cross-check against the gate's own code path (o4r_table.style_dist)
        raw = [j for r in T.load_sim(path).values() for j in r]
        rows.append(('   same set via o4r_table.style_dist', ref, T.style_dist(raw, which)[0]))
    cl = ceiling()
    rows.append(('human-human card agreement ceiling (saved L67 run)', 43.7, cl['card']))
    rows.append(('human-human cell agreement ceiling (saved L67 run)', 27.5, cl['cell']))
    print('| quantity | reference | scorecard | match |\n|---|---|---|---|')
    ok = True
    for lab, ref, got in rows:
        m = '' if ref is None else ('OK' if abs(got - ref) <= (0.5 if ref > 5 else 0.015 if ref < 0.2 else 0.025) else 'MISMATCH')
        ok &= m != 'MISMATCH'
        print(f'| {lab} | {"-" if ref is None else ref} | {got:.3f} | {m} |')
    print('REPRO', 'OK' if ok else 'FAILED')
    return ok


def selftest(th):
    """Instrument controls (pattern 8).  Humans vs humans must pass RMS and B3 (and TOST in most random splits); a planted speed bug and a
    planted spread collapse must fail; level A passes a calibrated model with Exp(1) gaps and fails a miscalibrated / constant-gap one."""
    L12 = live_ref('12k')
    feats = CORE9 + EXTRA
    npass = Counter()
    nsp = 20
    for seed in range(nsp):
        idx = list(range(len(L12)))
        random.Random(seed).shuffle(idx)
        h = len(idx) // 2
        r = level_b([L12[i] for i in idx[:h]], [L12[i] for i in idx[h:]], th, feats=feats)
        npass['rms'] += r['pass_rms']; npass['tost'] += r['pass_tost']; npass['b3'] += r['pass_b3']; npass['all'] += r['passed']
    print(f'human control: {nsp} random halves of the 12k live set (n ~960/side): RMS<=.10 {npass["rms"]}/{nsp}, TOST all stats {npass["tost"]}/{nsp}, '
          f'B3 {npass["b3"]}/{nsp}, full B pass {npass["all"]}/{nsp}')
    idx = list(range(len(L12)))
    random.Random(0).shuffle(idx)
    A_, B_ = [L12[i] for i in idx[::2]], [L12[i] for i in idx[1::2]]
    bad1 = [dict(x, ppm_2x=x['ppm_2x'] * 1.3, react_3s=x['react_3s'] * 1.5) for x in B_]                       # planted: busier + faster answers
    mu = sum(x['push_mean'] for x in B_) / len(B_)
    bad2 = [dict(x, push_mean=mu + 0.3 * (x['push_mean'] - mu)) for x in B_]                                  # planted: right mean, collapsed spread
    r1, r2 = level_b(A_, bad1, th, feats=feats), level_b(A_, bad2, th, feats=feats)
    print(f'planted speed bug: RMS {f2(r1["rms9"])} passed={r1["passed"]}; planted spread collapse: passed={r2["passed"]} (push_mean ratio {f2(r2["spread"]["push_mean"])})')
    rng = random.Random(0)
    n = 300000
    ps = [rng.random() for _ in range(n)]
    g = [rng.expovariate(1.0) for _ in range(6000)]
    th0 = dict(th, A=dict(th['A'], agreement_card_min=0.0))
    good = level_a([0.5] * n, [1] * n, ps, [1 if rng.random() < p else 0 for p in ps], g, th0)
    bad = level_a([0.5] * n, [1] * n, ps, [0] * n, [1.0] * 6000, th0)
    print(f'level A calibrated: ECE {good["ece_pp"]:.2f} pp KS {good["ks"]:.3f} pass_ece {good["pass_ece"]} pass_ks {good["pass_ks"]}; '
          f'miscalibrated/constant gaps: ECE {bad["ece_pp"]:.1f} KS {bad["ks"]:.2f} pass_ece {bad["pass_ece"]} pass_ks {bad["pass_ks"]}')
    # human full-pass rate is REPORTED, not asserted: B3's [0.9, 1.1] band false-fails humans ~15-25% at n~960/side (see HUMANLIKE.md)
    good_ok = (npass['rms'] == nsp and not r1['passed'] and not r2['pass_b3'] and good['pass_ece'] and good['pass_ks']
               and not bad['pass_ece'] and not bad['pass_ks'])
    print('SELFTEST', 'OK' if good_ok else 'FAILED')
    return good_ok


def main():
    th, sha = load_thresholds()
    cmd = sys.argv[1] if len(sys.argv) > 1 else 'repro'
    print(f'THRESHOLDS.json sha256 {sha} (matches HUMANLIKE.md)')
    if cmd == 'repro':
        sys.exit(0 if repro(th) else 1)
    if cmd == 'selftest':
        sys.exit(0 if selftest(th) else 1)
    if cmd == 'score':
        specs = [a.split('=', 1) for a in sys.argv[2:] if '=' in a and not a.startswith('--')]
        refs = {'13k': live_ref('13k'), 'ranked': live_ref('ranked')}
        allr = [report(n, p, refs, th) for n, p in specs]
        if '--json' in sys.argv:
            def clean(o):
                if isinstance(o, dict):
                    return {str(k): clean(v) for k, v in o.items()}
                if isinstance(o, (list, tuple)):
                    return [clean(v) for v in o]
                return None if isinstance(o, float) and math.isnan(o) else o
            Path(sys.argv[sys.argv.index('--json') + 1]).write_text(json.dumps(clean(allr), indent=1))


if __name__ == '__main__':
    main()
