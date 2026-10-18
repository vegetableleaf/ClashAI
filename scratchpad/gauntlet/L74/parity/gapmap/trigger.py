"""Step-d trigger arithmetic on FIN12_stamped per-fight rows (rows.py output) + the live census.

Per card: n, matches, raw p (mean aK), match-bootstrap lower CI (same as fights.boot_ci: B 2000, seed 0), noise ceiling c,
miss mass n(1-p), noise floor sum(1-ceil), excess = mass - floor.
Projection model: the bootstrap lower bound is reproduced by a Wilson lower bound at an EFFECTIVE n, m = n / f (f = the
design effect: fractional aK lowers it, match clustering raises it), f fitted per card; f held fixed as p and n change.
p_need(n') = the p whose Wilson lower bound at n'/f is GOAL.  ponytail: Wilson + fixed f; a resample check is in --check.
usage: python trigger.py ROWS.tsv CENSUS.json [--rate MATCHES_PER_DAY] > TRIGGER.txt ; python trigger.py --selftest"""
import json, math, random, sys
from collections import defaultdict

GOAL_CARD, GOAL_ALL, GOAL_N, Z = .95, .975, 30, 1.959964
TIER_B, TIER_SHARE = .003, .90


def boot_ci(items, f, B=2000, seed=0):
    by = defaultdict(list)
    for k, v in items:
        by[k].append(v)
    keys, rng, out = sorted(by), random.Random(seed), []
    for _ in range(B):
        v = f([x for k in rng.choices(keys, k=len(keys)) for x in by[k]])
        if v is not None:
            out.append(v)
    out.sort()
    return (out[int(.025*len(out))], out[max(0, int(.975*len(out))-1)]) if out else (None, None)


def wilson_lo(p, m):
    if m <= 0:
        return 0.
    d = 1 + Z*Z/m
    return (p + Z*Z/(2*m) - Z*math.sqrt(max(p*(1-p), 0)/m + Z*Z/(4*m*m)))/d


def fit_f(p, n, lo):
    """design effect f such that wilson_lo(p, n/f) == lo (bisection on log f)."""
    if lo is None or p >= 1 or lo >= p:
        return None
    a, b = math.log(.05), math.log(50.)
    for _ in range(80):
        mid = (a+b)/2
        if wilson_lo(p, n/math.exp(mid)) > lo:
            a = mid
        else:
            b = mid
    return math.exp((a+b)/2)


def p_need(n, f, goal):
    """smallest p with wilson_lo(p, n/f) >= goal (1.0+ = unreachable at this n)."""
    if wilson_lo(1., n/f) < goal:
        return None
    a, b = goal, 1.
    for _ in range(60):
        mid = (a+b)/2
        if wilson_lo(mid, n/f) >= goal:
            b = mid
        else:
            a = mid
    return b


def n_need(p, f, goal):
    """fights needed at agreement p for wilson_lo >= goal (None if p <= goal)."""
    if p <= goal:
        return None
    lo, hi = 1., 1e7
    if wilson_lo(p, hi/f) < goal:
        return None
    for _ in range(80):
        mid = math.sqrt(lo*hi)
        if wilson_lo(p, mid/f) >= goal:
            hi = mid
        else:
            lo = mid
    return hi


def load(path):
    rows = []
    for ln in open(path, encoding='utf-8'):
        c = ln.rstrip('\n').split('\t')
        if c[3] != '1' or c[4] == '':
            continue
        rows.append(dict(stem=c[0], t0=int(c[1]), card=c[2], aK=float(c[4]), a0=int(c[5]),
                         ceil=float(c[6]) if c[6] else None, blk=c[10]))
    return rows


def card_stats(rows):
    mean = lambda xs: sum(xs)/len(xs) if xs else None
    by = defaultdict(list)
    for r in rows:
        by[r['card']].append(r)
    out = {}
    for card, xs in list(by.items()) + [('OVERALL', rows)]:
        items = [(x['stem'], x['aK']) for x in xs]
        p = mean([v for _, v in items])
        lo, hi = boot_ci(items, mean)
        cs = [x['ceil'] for x in xs if x['ceil'] is not None]
        out[card] = dict(n=len(xs), matches=len({x['stem'] for x in xs}), p=p, lo=lo, hi=hi,
                         ceil=mean(cs) if cs else None, mass=sum(1-x['aK'] for x in xs),
                         floor=sum(1-(x['ceil'] if x['ceil'] is not None else 1.) for x in xs))
    return out


def main(rows_path, census_path, per_day):
    rows = load(rows_path)
    M = len({r['stem'] for r in rows})
    S = card_stats(rows)
    cen = json.load(open(census_path, encoding='utf-8'))
    tot = sum(cen['plays'].values())
    share = {k: v/tot for k, v in cen['plays'].items()}
    tierB = [k for k in share if k.startswith('own ') or share[k] >= TIER_B]
    sB = sum(share[k] for k in tierB)
    fs = sorted(s['f'] for s in [dict(f=fit_f(v['p'], v['n'], v['lo'])) for k, v in S.items() if k != 'OVERALL'
                                  and k in tierB and v['n'] >= GOAL_N] if s['f'])
    f_pool = fs[len(fs)//2] if fs else 1.
    days = (0, 1, 3, 7)
    o = S['OVERALL']
    fo = fit_f(o['p'], o['n'], o['lo'])
    L = [f"cohort: {len(rows)} strict fights in {M} matches; accrual {per_day} matches/day (stamped share ~100%)",
         f"OVERALL raw {o['p']:.4f} lower CI {o['lo']:.4f} (goal {GOAL_ALL}); ceiling {o['ceil']:.4f}; design effect f {fo:.2f}",
         'OVERALL raw needed for lower CI >= 0.975: ' + ', '.join(
             f"{d}d (n {round(o['n']*(M+d*per_day)/M)}) {p_need(o['n']*(M+d*per_day)/M, fo, GOAL_ALL):.4f}" for d in days),
         f"  = share of the EXCESS miss mass (above the noise floor) that must be removed: " + ', '.join(
             f"{d}d {(p_need(o['n']*(M+d*per_day)/M, fo, GOAL_ALL)-o['p'])/(o['ceil']-o['p']):.0%}" for d in days),
         f"tier B: {len(tierB)} cards = {sB:.4f} of live plays; 90% needs {TIER_SHARE*sB:.4f} of plays on MEETING cards",
         f"pooled design effect (median over tier-B cards with misses, n >= 30): {f_pool:.2f}", '',
         'card | share | n | /match | raw p | lower CI | ceiling | f | p_need now | +1d | +3d | +7d | days to meet at this p | limit']
    res = []
    for k in sorted(tierB, key=lambda k: -share[k]):
        v = S.get(k)
        if share[k] < .0002 and k.startswith('own '):
            continue                                          # the bait account's stray own plays (<0.02%)
        if not v:
            res.append(dict(card=k, share=share[k], limit='not in strict cohort', meets=False))
            L.append(f"{k} | {share[k]:.4f} | 0 | - | - | - | - | - | - | - | - | - | never (no strict fights) | not in cohort"); continue
        f = fit_f(v['p'], v['n'], v['lo']) or f_pool
        rate = v['n']/M
        need = [p_need(max(v['n'] + d*per_day*rate, 1), f, GOAL_CARD) for d in days]
        meets = v['n'] >= GOAL_N and v['lo'] >= GOAL_CARD
        if v['p'] >= 1:                                       # the bootstrap gives [1, 1]: meets at n >= 30 while it stays perfect
            nn = GOAL_N
        else:
            nn = n_need(v['p'], f, GOAL_CARD)
            nn = max(nn, GOAL_N) if nn else None
        dd = None if nn is None else max(0., (nn - v['n'])/(rate*per_day))
        c = v['ceil'] or 1.
        if meets:
            lim = 'MEETS'
        elif v['p'] >= 1:
            lim = 'data (n < 30, perfect so far)'
        elif dd is not None and dd <= 7:
            lim = f'data ({dd:.1f} d)'
        elif need[3] is None or need[3] > c:
            lim = 'noise: p_need(+7d) above its ceiling' if need[3] is not None else 'n too small'
        else:
            lim = 'error'
        fmt = lambda x: '-' if x is None else f"{x:.3f}"
        res.append(dict(card=k, share=share[k], n=v['n'], rate=rate, p=v['p'], lo=v['lo'], ceil=v['ceil'], f=f, need=need,
                        days=dd, limit=lim, meets=meets, mass=v['mass'], floor=v['floor']))
        L.append(f"{k} | {share[k]:.4f} | {v['n']} | {rate:.3f} | {v['p']:.3f} | {v['lo']:.3f} | {fmt(v['ceil'])} | {f:.2f} | "
                 + ' | '.join(fmt(x) for x in need) + f" | {'-' if dd is None else f'{dd:.1f}'} | {lim}")
    meet_now = sum(r['share'] for r in res if r['meets'])
    L += ['', f"meeting now: {meet_now:.4f} of plays = {meet_now/sB:.3f} of tier B (need {TIER_SHARE})"]
    # data-only accrual: cards that meet by day d at their CURRENT agreement
    for d in (1, 3, 7):
        s = sum(r['share'] for r in res if r['meets'] or (r.get('days') is not None and r['days'] <= d))
        L.append(f"  + data accrual alone at today's agreement, after {d} d: {s/sB:.3f} of tier B")
    # minimal set by share (largest first) among the non-meeting cards
    need_share, acc, pick = TIER_SHARE*sB - meet_now, 0., []
    for r in sorted((r for r in res if not r['meets']), key=lambda r: -r['share']):
        if acc >= need_share:
            break
        acc += r['share']; pick.append(r)
    L += ['', f"MINIMAL SET by live share (gap {need_share:.4f} of plays): {len(pick)} cards, {acc:.4f}",
          '  ' + ', '.join(f"{r['card']} ({r['share']:.4f}, {r['limit']})" for r in pick)]
    json.dump(dict(M=M, per_day=per_day, overall=o, f_overall=fo, f_pool=f_pool, tierB_share=sB, meet_now=meet_now, cards=res,
                   stats=S), open(rows_path.rsplit('/', 1)[0] + '/trigger.json' if '/' in rows_path else 'trigger.json', 'w'),
              indent=1, default=str)
    print('\n'.join(L))


def selftest():
    assert abs(wilson_lo(.5, 100) - .4038) < 1e-3
    f = fit_f(.9, 400, .87)
    assert abs(wilson_lo(.9, 400/f) - .87) < 1e-6
    pn = p_need(400, f, .95)
    assert abs(wilson_lo(pn, 400/f) - .95) < 1e-6 and pn > .95
    nn = n_need(.97, f, .95)
    assert abs(wilson_lo(.97, nn/f) - .95) < 1e-4
    assert n_need(.95, f, .95) is None
    print('TRIGGER_SELFTEST_OK')


if __name__ == '__main__':
    if sys.argv[1:2] == ['--selftest']:
        selftest()
    else:
        rate = float(sys.argv[sys.argv.index('--rate')+1]) if '--rate' in sys.argv else 240.
        main(sys.argv[1], sys.argv[2], rate)
