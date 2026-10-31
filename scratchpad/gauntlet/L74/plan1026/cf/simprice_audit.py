"""SIMPRICE step 1 (10-31): the Hero IW press's fork price from cf_credit's iw_pressed / iw_press samples (CF_DUMP jsonl).

Per sample dQ = Q(press) - Q(hold) (the K-mean return, +-1 = a win, so win probability = dQ / 2), whichever candidate the policy
took: iw_pressed = the policy pressed (alternative = hold), iw_press = it held a pressable button (alternative = press). Also the
audited terminal (continuation 0 to the match end), the horizon sweep (qh), the forks' accepted presses (ab_n: did the forced
press land / does the head re-press after a hold), the noise controls (cf_credit.reliability SNR, slope_audit), and splits by
what the freeze would hit (the head's freeze features, royale_env FREEZE_FEAT_N: target troops / elixir / win condition,
cube on my half), the phase and the head's P(press). CIs: 90% match-cluster bootstrap (as P4_AUDIT).

  python -B simprice_audit.py DUMP.jsonl [DUMP2 ...] [--from-update N] [--json OUT]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[5]))
from pipeline import cf_credit as CF  # noqa: E402

B = 44                       # e1_eval.ABILITY_FEAT_N: the freeze features follow (ability_features freeze)


def rows(paths, from_update):
    out = []
    for mi, (p, line) in enumerate((p, ln) for p in paths for ln in open(p, encoding='utf-8') if ln.strip()):
        r = json.loads(line)
        if r.get('update', 0) < from_update:
            continue
        for s in r['cf'].get('samples', []):
            if s['trigger'] not in ('iw_pressed', 'iw_press') or len(s['cands']) != 2:
                continue
            c0, c1 = s['cands']
            if any(q is None for c in (c0, c1) for q in c['q']):
                continue
            pr, ho = (c0, c1) if c0['ab_press'] else (c1, c0)
            f = c0.get('ab_feat') or []
            fz = f[B:B + 11] if len(f) >= B + 11 else [0.0] * 11
            t = int(s['tick'])
            out.append(dict(
                m=f"{mi}", trig=s['trigger'], tick=t, phase='1x' if t < 2400 else '2x' if t < 3600 else 'OT',
                dq=float(np.mean(pr['q']) - np.mean(ho['q'])),
                dt=(pr['q_end'] - ho['q_end']) if s.get('audit') and pr.get('q_end') is not None and ho.get('q_end') is not None
                else None,
                dh={h: float(np.mean(pr['qh'][h]) - np.mean(ho['qh'][h])) for h in (pr.get('qh') or {})
                    if None not in pr['qh'][h] and None not in ho['qh'][h]},
                n_press=pr.get('ab_n'), n_hold=ho.get('ab_n'), p=float(c0.get('ab_p', np.nan)),
                t0_hold=ho.get('ab_t0'), sig=(r.get('end_tick'), r.get('outcome'), tuple(int(x['tick']) for x in r['cf'].get('samples', []) if x['trigger'] in ('iw_pressed', 'iw_press'))),
                d300=None, d900=None, terminal=all(pr['terminal']) and all(ho['terminal']),
                tgt=fz[0] > 0.5, troops=round(fz[1] * 5), elixir=fz[2] * 10, wincon=fz[3] > 0.5,
                cube_elixir=fz[5] * 10, cube_mine=fz[8] > 0.5, marked=fz[9] > 0.5, s=s, upd=r.get('update', 0)))
    for x in out:
        x['d300'], x['d900'] = x['dh'].get('300'), x['dh'].get('900')
    return out


def ci(rs, key='dq', B_=2000, seed=0):
    v = [r[key] for r in rs if r[key] is not None]
    if not v:
        return None
    by = {}
    for r in rs:
        if r[key] is not None:
            by.setdefault(r['m'], []).append(r[key])
    g = list(by.values())
    rng = np.random.default_rng(seed)
    bs = []
    for _ in range(B_):
        pick = [g[i] for i in rng.integers(0, len(g), len(g))]
        bs.append(np.mean([x for gg in pick for x in gg]))
    return float(np.mean(v)), float(np.percentile(bs, 5)), float(np.percentile(bs, 95)), len(v)


def fmt(c):
    return 'n/a' if c is None else f"{c[0]:+.3f} [{c[1]:+.3f}, {c[2]:+.3f}] (n {c[3]})"


def table(rs, title):
    print(f"\n## {title}")
    print("| split | n | dQ main horizon (press - hold) | audited terminal | critic Q at 900 | critic Q at 300 |")
    print("|---|---|---|---|---|---|")
    groups = [('all', lambda r: True),
              ('policy pressed (iw_pressed)', lambda r: r['trig'] == 'iw_pressed'),
              ('policy held (iw_press)', lambda r: r['trig'] == 'iw_press'),
              ('freeze target: none', lambda r: not r['tgt']),
              ('target elixir 0 < e <= 3', lambda r: r['tgt'] and 0 < r['elixir'] <= 3),
              ('target elixir 3 < e <= 6', lambda r: r['tgt'] and 3 < r['elixir'] <= 6),
              ('target elixir > 6', lambda r: r['tgt'] and r['elixir'] > 6),
              ('win condition in the freeze', lambda r: r['wincon']),
              ('cube on my half', lambda r: r['cube_mine']),
              ('cube on the enemy half', lambda r: r['tgt'] and not r['cube_mine']),
              ('target already IW-marked', lambda r: r['marked']),
              ('1x', lambda r: r['phase'] == '1x'), ('2x', lambda r: r['phase'] == '2x'), ('OT', lambda r: r['phase'] == 'OT'),
              ('head P(press) < 0.02', lambda r: r['p'] < .02), ('head P(press) 0.02-0.2', lambda r: .02 <= r['p'] < .2),
              ('head P(press) >= 0.2', lambda r: r['p'] >= .2)]
    for name, f in groups:
        g = [r for r in rs if f(r)]
        if g:
            print(f"| {name} | {len(g)} | {fmt(ci(g))} | {fmt(ci(g, 'dt'))} | {fmt(ci(g, 'd900'))} | {fmt(ci(g, 'd300'))} |")


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument('dumps', nargs='+')
    ap.add_argument('--from-update', type=int, default=0)
    ap.add_argument('--json')
    ap.add_argument('--pair', help="another dump of the SAME real matches (same seed / policy), e.g. with cf_iw_block_ticks")
    a = ap.parse_args(argv)
    rs = rows(a.dumps, a.from_update)
    print(f"# SIMPRICE IW press audit: {len(rs)} samples, {len({r['m'] for r in rs})} matches, updates >= {a.from_update}")
    table(rs, 'Hero IW press: fork price by situation (90% match-cluster CI)')
    for trig in ('iw_pressed', 'iw_press'):
        g = [r for r in rs if r['trig'] == trig]
        if not g:
            continue
        hs = sorted({h for r in g for h in r['dh']}, key=int)
        sw = ', '.join(f"{h}: {fmt(ci([dict(r, x=r['dh'].get(h)) for r in g], 'x'))}" for h in hs)
        print(f"\n{trig} horizon sweep (ticks): {sw}")
        npress = [np.mean(r['n_press']) for r in g if r['n_press'] and None not in r['n_press']]
        nhold = [np.mean(r['n_hold']) for r in g if r['n_hold'] and None not in r['n_hold']]
        if npress and nhold:
            print(f"{trig} accepted presses per fork over the horizon: press branch {np.mean(npress):.2f}, hold branch "
                  f"{np.mean(nhold):.2f} (share of hold forks with a re-press {np.mean([x > 0 for x in nhold]):.2f})")
        t0 = [t for r in g for t in (r['t0_hold'] or []) if t is not None]
        nk = sum(len(r['t0_hold'] or []) for r in g)
        if nk:
            print(f"{trig} hold branch: first accepted press after the root in {len(t0)} / {nk} forks; ticks after root p10 / p50 "
                  f"{np.percentile(t0, 10) if t0 else float('nan'):.0f} / {np.percentile(t0, 50) if t0 else float('nan'):.0f}; "
                  f"within 200 ticks {sum(t <= 200 for t in t0)}")
        rel = CF.reliability([CF.sample_adv(r['s']['cands']) for r in g])
        sl = CF.slope_audit([r['s'] for r in g])
        print(f"{trig} reliability: SNR {rel['snr']}, factor {rel['factor']}, r_split {rel['r_split']} (n {rel['n']}); "
              f"critic slope (terminal on horizon) diffs {sl.get('diffs')} levels {sl.get('levels')}")
    if a.pair:                                        # SIMPRICE round 2: the same real matches with / without cf_iw_block_ticks
        rb = rows([a.pair], a.from_update)
        key = lambda r: (r['sig'], r['tick'], r['trig'])
        bk = {key(r): r for r in rb}
        pairs = [(r, bk[key(r)]) for r in rs if key(r) in bk]
        print(f"\n## paired with {a.pair}: {len(pairs)} identical roots (of {len(rs)} / {len(rb)})")
        for trig in ('iw_pressed', 'iw_press', None):
            g = [dict(x, dd=y['dq'] - x['dq'], m=x['m']) for x, y in pairs if trig is None or x['trig'] == trig]
            if g:
                print(f"{trig or 'all'}: dQ this run {fmt(ci(g))}, other run {fmt(ci([dict(y, m=x['m']) for x, y in pairs if trig is None or x['trig'] == trig]))}, "
                      f"other - this (paired) {fmt(ci(g, 'dd'))}")
    if a.json:
        Path(a.json).write_text(json.dumps([{k: v for k, v in r.items() if k != 's'} for r in rs]), encoding='utf-8')


if __name__ == '__main__':
    main(sys.argv[1:])


def snaps(paths, h='900'):
    """cf_diag snapshots at the h-tick sweep stop, press - hold per sample (K-mean): own / foe princess HP lost (princess units),
    own crowns conceded, own elixir (snap layout: cf_credit.snap)."""
    out = []
    for r in rows(paths, 0):
        pr, ho = (r['s']['cands'][0], r['s']['cands'][1]) if r['s']['cands'][0]['ab_press'] else (r['s']['cands'][1], r['s']['cands'][0])
        b = ((ho.get('dg') or {}).get(h) or {}).get('snap')
        a = ((pr.get('dg') or {}).get(h) or {}).get('snap')
        if not a or not b or None in a or None in b:
            continue
        m = lambda v, i: float(np.mean([x[i] for x in v]))
        out.append(dict(r, own=m(a, 0) - m(b, 0), foe=m(a, 4) - m(b, 4), crown=m(a, 3) - m(b, 3), elix=m(a, 8) - m(b, 8)))
    return out
