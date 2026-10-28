"""P6-MACRO: episodes (mine.py) -> cell-matched win / tower-margin lifts with match-cluster bootstrap CIs -> LIBRARY.json.

    python -B stats.py --ep EP_DIR [--B 1000] [--out-dir DIR]        (EP_DIR holds pro.jsonl.gz, live.jsonl.gz, hf/*.jsonl.gz)

Estimator (per macro x source, and 'human' = pro + hf with the source inside the cell):
  cell = (phase, crown diff, princess-HP margin band, own elixir band, opponent archetype, own archetype [, source]
  [, the macro's extra key xc: attacking unit (king_redirect), failures so far (rocket_cycle), answer context (def_xbow_hard),
  siege card (siege_answer)]).
  lift = sum_c nT_c * (mean_T,c - mean_C,c) / sum_c nT_c over cells holding both treated and control episodes (the effect
  on the treated, exact stratification); coverage = treated share inside such cells.
  CI = Poisson(1) bootstrap over matches (cid: both sides of a match and all its episodes move together), 95% percentile.
  Outcomes: win (match result) and net PRINCESS margin change n200 / n400 / n600 / n1200 / nend (princess units).
  Diagnosis rows: lift_well (treated AND well-executed vs control) / lift_failed (treated AND not well vs control); 'well' is
  measured after the start, so lift_well is biased upward by construction (it conditions on success) -- a diagnosis tool,
  not the macro's value.
Horizon for forks: the shortest of 10 / 20 / 30 / 60 s / end whose margin lift reaches 80% of the largest margin lift with
a CI low > 0 ('measured'); otherwise the macro's doctrinal default ('default', the reason given). Association only."""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import math
from collections import defaultdict
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
OUTS = ('win', 'n200', 'n400', 'n600', 'n1200', 'nend')
HOR = {'n200': 200, 'n400': 400, 'n600': 600, 'n1200': 1200, 'nend': 'end'}
CELL = ('ph', 'cr', 'hm', 'el', 'oa', 'wa')
MIN_T = 30                      # fewer treated episodes than this in a source -> 'thin' (b)


def load(ep_dir):
    ep = Path(ep_dir)
    files = [(p, 'pro') for p in [ep / 'pro.jsonl.gz'] if p.exists()] + [(p, 'live') for p in [ep / 'live.jsonl.gz']
                                                                           if p.exists()]
    files += [(p, 'hf') for p in sorted((ep / 'hf').glob('*.jsonl.gz'))]
    eps, sides = defaultdict(list), []
    for p, src in files:
        for line in gzip.open(p, 'rt', encoding='utf-8'):
            e = json.loads(line)
            (sides.append(e) if e['macro'] == '_side' else eps[e['macro']].append(e))
    return eps, sides


def att(cell, tr, y, w):
    """Weighted exact-stratification ATT. cell: int array, tr: 0/1, y: float, w: weights. -> (lift, coverage)."""
    nc = cell.max() + 1
    nT = np.bincount(cell, weights=w * tr, minlength=nc)
    nC = np.bincount(cell, weights=w * (1 - tr), minlength=nc)
    sT = np.bincount(cell, weights=w * tr * y, minlength=nc)
    sC = np.bincount(cell, weights=w * (1 - tr) * y, minlength=nc)
    ok = (nT > 0) & (nC > 0)
    if not ok.any():
        return float('nan'), 0.0
    d = sT[ok] / nT[ok] - sC[ok] / nC[ok]
    return float((nT[ok] * d).sum() / nT[ok].sum()), float(nT[ok].sum() / max(nT.sum(), 1e-9))


def estimate(rows, B, seed=0, with_src=False):
    """rows: episode dicts of one macro. -> dict of point estimates + CIs for every outcome (+ diagnosis lifts)."""
    keys = CELL + (('src',) if with_src else ())
    cmap, cid = {}, {}
    cell = np.array([cmap.setdefault(tuple(r[k] for k in keys) + (r.get('xc'),), len(cmap)) for r in rows])
    cl = np.array([cid.setdefault(r['cid'], len(cid)) for r in rows])
    tr = np.array([r['tr'] for r in rows], float)
    well = np.array([-1 if r['well'] is None else r['well'] for r in rows])
    Y = {o: np.array([r[o] for r in rows], float) for o in OUTS}
    one = np.ones(len(rows))
    res = dict(n=len(rows), matches=len(cid), n_tr=int(tr.sum()), tr_rate=round(float(tr.mean()), 4),
               win_tr_raw=round(float(Y['win'][tr == 1].mean()), 4) if tr.any() else None,
               win_ctl_raw=round(float(Y['win'][tr == 0].mean()), 4) if (tr == 0).any() else None)
    wd = well >= 0
    if (wd & (tr == 1)).any():
        res['well_rate_tr'] = round(float(well[wd & (tr == 1)].mean()), 4)
    if (wd & (tr == 0)).any():
        res['well_rate_ctl'] = round(float(well[wd & (tr == 0)].mean()), 4)
    rng = np.random.default_rng(seed)
    W = rng.poisson(1.0, size=(B, len(cid))).astype(float)
    variants = {'': (tr, one)}
    if (wd & (tr == 1)).sum() >= MIN_T:
        variants['well_'] = (tr, (~((tr == 1) & (well == 0))).astype(float))      # drop failed attempts
        variants['failed_'] = (tr, (~((tr == 1) & (well == 1))).astype(float))    # drop well-executed ones
    if wd.sum() >= MIN_T and (tr == 1).sum() >= MIN_T:
        variants['succ_'] = None                                                 # success-rate lift (well as outcome)
    for pre, v in variants.items():
        outs = OUTS if pre == '' else ('win',)
        if v is None:
            m = wd
            t_, y_, c_, w0 = tr[m], well[m].astype(float), cell[m], np.ones(m.sum())
            pt, cov = att(c_, t_, y_, w0)
            bs = [att(c_, t_, y_, W[b][cl[m]])[0] for b in range(B)]
            bs = np.sort([x for x in bs if not math.isnan(x)])
            res['lift_success'] = dict(est=round(pt, 4), ci=_ci(bs), cov=round(cov, 3))
            continue
        t_, keep = v
        for o in outs:
            pt, cov = att(cell, t_, Y[o], keep)
            bs = np.sort([x for x in (att(cell, t_, Y[o], keep * W[b][cl])[0] for b in range(B)) if not math.isnan(x)])
            res['%slift_%s' % (pre, o)] = dict(est=round(pt, 4), ci=_ci(bs), cov=round(cov, 3))
    return res


def _ci(bs):
    if len(bs) < 20:
        return [None, None]
    return [round(float(bs[int(.025 * len(bs))]), 4), round(float(bs[int(.975 * len(bs)) - 1]), 4)]


def horizon(res, default):
    lifts = {o: res.get('lift_' + o) for o in HOR}
    pos = {o: v for o, v in lifts.items() if v and v['est'] == v['est'] and v['ci'][0] is not None and v['ci'][0] > 0}
    if not pos:
        return default[0], 'default: ' + default[1]
    mx = max(v['est'] for v in pos.values())
    for o in HOR:
        if o in pos and pos[o]['est'] >= 0.8 * mx:
            return HOR[o], 'measured (margin lift %s reaches 80%% of the max %.3f)' % (o, mx)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--ep', required=True)
    ap.add_argument('--B', type=int, default=1000)
    ap.add_argument('--out-dir', default=str(HERE))
    ap.add_argument('--only', default='')
    a = ap.parse_args(argv)
    spec = json.load(open(HERE / 'spec.json', encoding='utf-8'))
    eps, sides = load(a.ep)
    out = dict(kind='p6_macro_library_v1', ep_dir=a.ep, B=a.B, cell=list(CELL), macros=[], extras=[], data={})
    srcs = sorted({s['src'] for s in sides})
    out['data'] = {s: dict(sides=sum(x['src'] == s for x in sides),
                           xbow_sides=sum(x['src'] == s and 'x_bow' in x['deck8'] for x in sides),
                           icebow8_sides=sum(x['src'] == s and len(x['deck8']) == 8 for x in sides)) for s in srcs}
    todo = []
    for sp in spec['macros']:          # + refinements: the same macro on a narrower start condition (spec "refine")
        todo.append((sp, eps.get(sp['id'], [])))
        for rf in sp.get('refine', []):
            def ok(r, w=rf['where']):
                return all((r.get(k) if k in r else (r.get('x') or {}).get(k)) in (v if isinstance(v, list) else [v])
                           for k, v in w.items())
            todo.append((dict(sp, id=sp['id'] + '|' + rf['suffix'], refine_of=sp['id'], start_condition=rf['start']),
                         [r for r in eps.get(sp['id'], []) if ok(r)]))
    for sp, rows in todo:
        mid = sp['id']
        if a.only and mid.split('|')[0] not in a.only.split(','):
            continue
        ent = dict(sp, sources={})
        ent.pop('refine', None)
        for s in srcs:
            rs = [r for r in rows if r['src'] == s]
            if not rs or not any(r['tr'] for r in rs) or all(r['tr'] for r in rs):
                ent['sources'][s] = dict(n=len(rs), n_tr=sum(r['tr'] for r in rs), note='no treated / no control episodes')
                continue
            ent['sources'][s] = estimate(rs, a.B if len(rs) < 200000 else max(200, a.B // 4))
            print(mid, s, json.dumps({k: v for k, v in ent['sources'][s].items() if k in ('n', 'n_tr', 'lift_win', 'lift_n600')}),
                  flush=True)
        hum = [r for r in rows if r['src'] in ('pro', 'hf')]
        if hum and any(r['tr'] for r in hum) and not all(r['tr'] for r in hum):
            ent['sources']['human'] = estimate(hum, a.B if len(hum) < 200000 else max(200, a.B // 4), with_src=True)
        prim = ent['sources'].get(sp.get('primary', 'human')) or {}
        ent['horizon_ticks'], ent['horizon_basis'] = horizon(prim, sp['default_horizon']) if prim.get('lift_win') else (
            sp['default_horizon'][0], 'default: ' + sp['default_horizon'][1])
        lw = prim.get('lift_win')
        pos = lambda k: (prim.get(k) or {}).get('ci', [None])[0] is not None and prim[k]['ci'][0] > 0  # noqa: E731
        ent['status'] = ('thin' if not lw or prim.get('n_tr', 0) < MIN_T else
                         'win_lift' if pos('lift_win') else
                         'win_negative' if lw['ci'][1] is not None and lw['ci'][1] < 0 else
                         'margin_lift' if any(pos('lift_' + o) for o in HOR) else
                         'success_lift' if pos('lift_success') else 'no_lift')
        out['macros'].append(ent)
    out['extras'] = extras(sides, a.B)
    body = json.dumps(out, indent=1, sort_keys=False)
    p = Path(a.out_dir) / 'LIBRARY.json'
    p.write_text(body, encoding='utf-8')
    print('LIBRARY.json sha256', hashlib.sha256(body.encode()).hexdigest(), flush=True)


def extras(sides, B, min_n=200):
    """Mined two-card icebow8 sequences (A then B within 5 s; same / other lane; B offensive / defensive): units = player-sides
    whose deck holds both cards; treated = used >= once; cell = (opp archetype, own archetype, source); outcome = win.
    Kept when the CI low > 0 AND it survives Bonferroni over every tested pair (|est| / bootstrap SE > z_(1 - 0.025 / m))."""
    keys = defaultdict(int)
    for s in sides:
        for k in s['pairs']:
            keys[k] += 1
    cand = [k for k, v in keys.items() if v >= min_n]
    res = []
    from statistics import NormalDist
    z = NormalDist().inv_cdf(1 - 0.025 / max(len(cand), 1))
    for k in sorted(cand):
        a_, b_ = k.split(':')[0].split('>')
        rows = [dict(cid=s['cid'], ph='-', cr=0, hm='0', el='-', oa=s['oa'], wa=s['wa'], src=s['src'], tr=int(s['pairs'].get(k, 0) > 0),
                     well=None, win=s['win'], **{o: 0.0 for o in OUTS[1:]}) for s in sides if {a_, b_} <= set(s['deck8'])]
        nt = sum(r['tr'] for r in rows)
        if nt < min_n or len(rows) - nt < min_n:
            continue
        e = estimate_win(rows, B)
        e.update(pair=k, n=len(rows), n_tr=nt)
        e['bonferroni'] = bool(e['se'] and abs(e['est']) / e['se'] > z)
        res.append(e)
    res.sort(key=lambda e: -(e['ci'][0] or -9))
    return dict(tested=len(cand), z_bonferroni=round(z, 3), pairs=res)


def estimate_win(rows, B, seed=1):
    keys = ('oa', 'wa', 'src')
    cmap, cid = {}, {}
    cell = np.array([cmap.setdefault(tuple(r[k] for k in keys), len(cmap)) for r in rows])
    cl = np.array([cid.setdefault(r['cid'], len(cid)) for r in rows])
    tr = np.array([r['tr'] for r in rows], float)
    y = np.array([r['win'] for r in rows], float)
    pt, cov = att(cell, tr, y, np.ones(len(rows)))
    W = np.random.default_rng(seed).poisson(1.0, size=(min(B, 400), len(cid))).astype(float)
    bs = np.sort([x for x in (att(cell, tr, y, W[b][cl])[0] for b in range(len(W))) if not math.isnan(x)])
    return dict(est=round(pt, 4), ci=_ci(bs), se=round(float(bs.std()), 4) if len(bs) else None, cov=round(cov, 3))


if __name__ == '__main__':
    main()
