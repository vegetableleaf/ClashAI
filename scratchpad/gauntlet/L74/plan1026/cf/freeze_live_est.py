"""FREEZE-LIVE step 2b: the SAME estimator on live and SIM rows.

Moment = a decision where the Hero Ice Wizard button was pressable: PRESSED (the head pressed) or HELD (it did not). Outcome = our
princess HP lost over the next h ticks, in princess units (1.0 = one princess tower, 4858 HP; lower = better): the sum over our
2 princess towers of the HP lost in (t, t + h]. Covariates (the head's own 55 'freeze' features, identical layout live / SIM):
f46 x 10 = elixir of the troops in the freeze target's 2.5 t, f45 = their count / 5 ... , plus tick, our elixir, princess HP already lost.
  live rows : freeze_live_parse.py (reader `frame` HP; chosen branch = what happened)
  SIM rows  : cf/data/spb_*.jsonl (pilot2.yaml pool, every decision with a >= 6-elixir freeze target; K 2 continuations, cf_diag
              snapshot at 300 / 900 ticks). Observational read = the CHOSEN branch only (what the policy did), exactly like live;
              paired read = press - hold in the SAME state (the fork), the causal estimand.
Three estimators for pressed - held on the chosen branches: raw; OLS-adjusted; stratified (target elixir bin x phase x our elixir bin).
CIs: 90% match-cluster bootstrap.  python -B freeze_live_est.py LIVE.jsonl [--json OUT]"""
from __future__ import annotations

import json
import random
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

CF = Path(__file__).resolve().parent / 'data'
H = {'300': 300, '900': 900}


def phase(t):
    return 0 if t < 2400 else 1 if t < 3600 else 2


# ------------------------------------------------------------------ rows
def live_rows(path):
    out = []
    for l in open(path):
        m = json.loads(l)
        f = m['feat']
        if not f or len(f) != 55 or f[46] * 10 + 1e-6 < 3.0:     # the two classes tabled below (target >= 3 elixir)
            continue
        lo = m['lost']
        if lo.get('0') is None:
            continue
        d = {h: (None if lo.get(h) is None else lo[h] - lo['0']) for h in ('150', '300', '450', '900')}
        out.append(dict(src='live', head=m['ckpt'], match=m['match'], pressed=m['kind'] == 'press', tick=m['tick'],
                        elixir=float(m['elixir'] or 0), lost0=lo['0'], f=f, d=d, conf='conf' in m))
    return out


def sim_rows(paths, head):
    out, ci = [], 0
    for p in paths:
        for l in open(p):
            j = json.loads(l); ci += 1
            for s in j['cf']['samples']:
                if s['trigger'] not in ('iw_pressed', 'iw_press'):
                    continue
                ch = next(c for c in s['cands'] if c['kind'] == 'chosen')
                alt = next((c for c in s['cands'] if c is not ch), None)
                ctx = s['ctx']
                lost0 = ctx['snap'][0]

                def dl(c, h):
                    sn = ((c or {}).get('dg') or {}).get(h, {}).get('snap')
                    if not sn or any(x is None for x in sn):
                        return None
                    return float(np.mean([x[0] for x in sn])) - lost0
                pressed = s['trigger'] == 'iw_pressed'
                d, pd = {}, {}
                for h in H:
                    a, b = dl(ch, h), dl(alt, h)
                    d[h] = a
                    pd[h] = None if a is None or b is None else (a - b if pressed else b - a)   # press - hold
                # clean pairs: continuation k where the HOLD branch never pressed (ab_n 0) and the PRESS branch did (ab_n >= 1): press vs never press
                pr_c, ho_c = (ch, alt) if pressed else (alt, ch)
                clean = {}
                for h in H:
                    sa = ((pr_c or {}).get('dg') or {}).get(h, {}).get('snap') or []
                    sb = ((ho_c or {}).get('dg') or {}).get(h, {}).get('snap') or []
                    vals = []
                    for k in range(min(len(sa), len(sb))):
                        if sa[k] is None or sb[k] is None:
                            continue
                        if (pr_c.get('ab_n') or [0] * 9)[k] >= 1 and (ho_c.get('ab_n') or [9] * 9)[k] == 0:
                            vals.append(sa[k][0] - sb[k][0])
                    clean[h] = float(np.mean(vals)) if vals else None
                out.append(dict(src='sim', head=head, match='%s#%d' % (Path(p).name, ci), pressed=pressed, tick=ctx['tick'],
                                elixir=float(ctx['snap'][8]), lost0=lost0, f=ch['ab_feat'], d=d, paired=pd, clean=clean,
                                terminal=ch.get('terminal')))
    return out


# ------------------------------------------------------------------ estimators
def feats(r):
    f = r['f']
    return [f[46] * 10, f[45], f[47], f[50] * 10, f[51], f[52], r['tick'] / 1000.0, r['elixir'] / 10.0, r['lost0']] + \
           [float(phase(r['tick']) == 1), float(phase(r['tick']) == 2)]


def boot(rows, stat, B=1000, seed=1):
    by = defaultdict(list)
    for r in rows:
        by[r['match']].append(r)
    ms = list(by)
    rnd = random.Random(seed)
    est = stat(rows)
    bs = []
    for _ in range(B):
        sel = [x for m in (ms[rnd.randrange(len(ms))] for _ in ms) for x in by[m]]
        v = stat(sel)
        if v is not None and np.isfinite(v):
            bs.append(v)
    bs.sort()
    if est is None or len(bs) < 50:
        return est, None, None
    return est, bs[int(.05 * len(bs))], bs[int(.95 * len(bs))]


def s_raw(h):
    def f(rows):
        a = [r['d'][h] for r in rows if r['pressed'] and r['d'][h] is not None]
        b = [r['d'][h] for r in rows if not r['pressed'] and r['d'][h] is not None]
        return float(np.mean(a) - np.mean(b)) if a and b else None
    return f


def s_ols(h):
    def f(rows):
        rr = [r for r in rows if r['d'][h] is not None]
        if sum(r['pressed'] for r in rr) < 3 or sum(not r['pressed'] for r in rr) < 3:
            return None
        X = np.array([[1.0, float(r['pressed'])] + feats(r) for r in rr])
        y = np.array([r['d'][h] for r in rr])
        beta = np.linalg.lstsq(X, y, rcond=1e-8)[0]
        return float(beta[1])
    return f


def stratum(r):
    te = r['f'][46] * 10
    return (0 if te < 8 else 1 if te < 10 else 2, phase(r['tick']), int(r['f'][52] > .5), int(r['elixir'] >= 6))


def s_strat(h):
    def f(rows):
        g = defaultdict(lambda: ([], []))
        for r in rows:
            if r['d'][h] is None:
                continue
            g[stratum(r)][0 if r['pressed'] else 1].append(r['d'][h])
        num = den = 0.0
        for a, b in g.values():
            if a and b:
                num += len(a) * (np.mean(a) - np.mean(b)); den += len(a)
        return num / den if den else None
    return f


def s_paired(h, key='paired'):
    def f(rows):
        v = [r[key][h] for r in rows if r[key][h] is not None]
        return float(np.mean(v)) if v else None
    return f


def fmt(e, lo, hi, scale=4858):
    if e is None:
        return 'n/a'
    if lo is None:
        return '%+.3f (%+.0f HP)' % (e, e * scale)
    return '%+.3f [%+.3f, %+.3f] (%+.0f HP)' % (e, lo, hi, e * scale)


def table(rows, name, hs=('300', '900')):
    print('\n== %s' % name)
    for cls_name, lo_, hi_ in ((' target >= 6 elixir', 6.0, 99.0), (' target 3-6 elixir', 3.0, 6.0)):
        sub = [r for r in rows if lo_ <= r['f'][46] * 10 + 1e-6 < hi_]
        npress = sum(r['pressed'] for r in sub)
        nheld = len(sub) - npress
        print(cls_name, ': pressed %d, held %d, matches %d' % (npress, nheld, len({r['match'] for r in sub})))
        if npress < 3 or nheld < 3:
            continue
        for h in hs:
            hh = [r for r in sub if r['d'][h] is not None]
            a = [r['d'][h] for r in hh if r['pressed']]
            b = [r['d'][h] for r in hh if not r['pressed']]
            print('   h=%s  lost: pressed %.3f (n %d)  held %.3f (n %d)' % (h, np.mean(a) if a else float('nan'), len(a),
                                                                      np.mean(b) if b else float('nan'), len(b)))
            for nm, st in (('raw', s_raw(h)), ('ols', s_ols(h)), ('strat', s_strat(h))):
                print('     %-6s pressed - held: %s' % (nm, fmt(*boot(hh, st))))


def paired_table(rows, name, hs=('300', '900')):
    print('\n== %s (paired fork: press - hold in the same state; + = more princess HP lost with the press)' % name)
    for who in (True, False):
        for cls_name, lo_, hi_ in ((' target >= 6', 6.0, 99.0), (' target 3-6', 3.0, 6.0)):
            sub = [r for r in rows if r['pressed'] == who and lo_ <= r['f'][46] * 10 + 1e-6 < hi_]
            if len(sub) < 5:
                continue
            for h in hs:
                hh = [r for r in sub if r['paired'][h] is not None]
                print('   %s moments, %s, h=%s: n %d  %s' % ('PRESSED' if who else 'HELD', cls_name, h, len(hh),
                                                         fmt(*boot(hh, s_paired(h)))))
                cc = [r for r in sub if r['clean'][h] is not None]
                if cc:
                    print('       clean pairs only (hold branch never presses; press branch presses): n %d  %s' % (
                        len(cc), fmt(*boot(cc, s_paired(h, 'clean')))))


def main():
    live = live_rows(sys.argv[1])
    heads = defaultdict(list)
    for r in live:
        heads[r['head']].append(r)
    print('live rows', len(live), {k: (len(v), sum(x['pressed'] for x in v), len({x['match'] for x in v})) for k, v in heads.items()})
    groups = {'CLXIII': [r for r in live if r['head'] == 'ICEBOW_Mark_CLXIII_NOLEAK.pt'],
              'CLXV': [r for r in live if r['head'] == 'ICEBOW_Mark_CLXV_LARGEBATCH.pt']}
    for g, rows in groups.items():
        table(rows, 'LIVE %s (observational, chosen branch)' % g, hs=('150', '300', '450', '900'))
    sims = {'CLXV': sim_rows([CF / 'spb_clxv2.jsonl', CF / 'spb_clxv3.jsonl'], 'CLXV'),
            'p2init': sim_rows([CF / 'spb_p2i.jsonl'], 'p2init')}
    for g, rows in sims.items():
        table(rows, 'SIM %s (observational, chosen branch, same estimator)' % g)
        paired_table(rows, 'SIM %s' % g)
    if '--json' in sys.argv:
        pass


if __name__ == '__main__':
    main()
