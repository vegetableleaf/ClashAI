"""W1 offline score: the live 26-tick look-ahead (pipeline.extrapolate, the live prev rule) with and without own_effects
on the recorded live matches (owner_1008 live_*.pkl), against the real positions 26 ticks later.

Categories as q3.forecast_rows (owner_1008/q3.py): my_effect_hit = an enemy body inside the zone of my Log (|dX| <= 2.5,
-1 <= dY <= 11 tiles of the tap) / Tornado (5.5 tiles) confirmed in the last 40 ticks, or within 6 tiles of my hero Ice
Wizard after an ability confirmed in the last 40 ticks. DIFFERENCE from q3: the velocity comes from the frame the live
pilot uses (the newest frame <= t - 10, GenPilot.row), not the immediately previous frame, so the baseline is the live one.
own_effects inputs = what GenPilot hands extrapolate live: my confirmed plays (card, intended xy -> raw, confirm tick) and
my confirmed ability presses (confirm tick). Usage: python q3_own_effects.py PKL_DIR [OUT_PKL]
"""
import pickle
import sys
from collections import defaultdict

import numpy as np

from pipeline.extrapolate import extrapolate

H = 26
GROUPS = ('R1e', 'R1e_late', 'STACK_ALON', 'STACK_ALOFF', 'STACK_RA')
HERO = (26000023, 203000023)
CATS = ('no_recent_play', 'my_other_play', 'my_effect_elsewhere', 'my_effect_hit')


def own(side, x, y):
    return ((18000 - x) / 1000, (32000 - y) / 1000) if side == 1 else (x / 1000, y / 1000)


def raw_of(side, xy):
    """model-frame xy (live_play my_frame_xy inverse) -> raw engine units."""
    x, y = xy[0] * 18000, (1 - xy[1]) * 32000
    return (18000 - x, 32000 - y) if side == 1 else (x, y)


def frame(t, ents):
    return {"game_tick": t, "entities": [dict(side=e[0], x=float(e[1]), y=float(e[2]), card_id=e[3], hp=e[4], kind=e[5],
                                              address=e[6]) for e in ents], "players": []}


def boot(units, stat, B=300, seed=0):
    rng = np.random.default_rng(seed)
    n = len(units)
    v = [stat([units[i] for i in rng.integers(0, n, n)]) for _ in range(B)]
    v = [x for x in v if x == x]
    return stat(units), np.percentile(v, 2.5), np.percentile(v, 97.5)


def share(key):
    def f(U):
        v = [r[key] >= 1.5 for R in U for r in R]
        return float(np.mean(v)) if v else float('nan')
    return f


def rows(m):
    s, F = m['side'], m['frames']
    if not F:
        return []
    ticks = np.array([f[0] for f in F])
    idx = {t: i for i, (t, _, _) in enumerate(F)}
    conf = [(c['t'], c['name'], c['xy']) for c in m['conf']]
    abil = [a['t'] for a in m['abc']]
    out = []
    for d in m['dec']:
        t = d['t']
        if t not in idx:
            continue
        i = idx[t]
        k = int(np.searchsorted(ticks, t - 10, side='right')) - 1      # GenPilot.row: newest frame <= t - 10
        if k < 0:
            continue
        j = int(np.argmin(abs(ticks - (t + H))))
        if abs(ticks[j] - (t + H)) > 2:
            continue
        cur, prev = frame(t, F[i][2]), frame(F[k][0], F[k][2])
        fx = [dict(card=n, x=raw_of(s, xy)[0], y=raw_of(s, xy)[1], tick=tc) for tc, n, xy in conf if 0 <= t - tc <= 150]
        fx += [dict(card='IceWizard', ability=True, tick=ta, x=0, y=0) for ta in abil if 0 <= t - ta <= 150]
        base = {e['address']: e for e in extrapolate(cur, prev, H, s)['entities']}
        new = {e['address']: e for e in extrapolate(cur, prev, H, s, own_effects=fx)['entities']} if fx else base
        fut = {e[6]: e for e in F[j][2] if e[0] != s}
        pv = {e[6]: e for e in F[k][2] if e[0] != s}
        hero = [e for e in F[i][2] if e[0] == s and e[3] in HERO]
        recent = [c for c in conf if 0 <= t - c[0] <= 40]
        rec_eff = [(c[0], c[1], own(s, *raw_of(s, c[2]))) for c in recent if c[1] in ('Log', 'Tornado')]
        rec_ab = [a for a in abil if 0 <= t - a <= 40]
        second = bool(d['play']) and any(0 <= t - c[0] <= 4 for c in conf)
        for e in F[i][2]:
            if e[0] == s or e[3] < 0 or e[6] not in pv or e[6] not in fut or pv[e[6]][3] != e[3]:
                continue
            r = fut[e[6]]
            X, Y = own(s, e[1], e[2])
            how = set()
            for _, nm, (cx, cy) in rec_eff:
                if nm == 'Tornado' and np.hypot(X - cx, Y - cy) <= 5.5:
                    how.add('Tornado')
                if nm == 'Log' and abs(X - cx) <= 2.5 and cy - 1 <= Y <= cy + 11:
                    how.add('Log')
            if rec_ab and hero:
                hx, hy = own(s, hero[0][1], hero[0][2])
                if np.hypot(X - hx, Y - hy) <= 6:
                    how.add('ability')
            cat = ('my_effect_hit' if how else ('my_effect_elsewhere' if (rec_eff or rec_ab) else
                                                ('my_other_play' if recent else 'no_recent_play')))
            err = lambda q: float(np.hypot(q['x'] - r[1], q['y'] - r[2]) / 1000)       # noqa: E731
            out.append(dict(cat=cat, how='+'.join(sorted(how)), second=second, moving=(e[1], e[2]) != (pv[e[6]][1], pv[e[6]][2]),
                            base=err(base[e[6]]), new=err(new[e[6]]), changed=base[e[6]] != new[e[6]],
                            dbg=dict(t=t, cid=e[3], cur=own(s, e[1], e[2]), prev=own(s, pv[e[6]][1], pv[e[6]][2]), gap=t - F[k][0],
                                     true=own(s, r[1], r[2]), b=own(s, base[e[6]]['x'], base[e[6]]['y']),
                                     n=own(s, new[e[6]]['x'], new[e[6]]['y']),
                                     fx=[(t - c[0], c[1], c[2]) for c in rec_eff])))
    return out


if __name__ == '__main__':
    D = sys.argv[1].rstrip('/') + '/'
    per = []
    for g in GROUPS:
        for m in pickle.load(open(D + f'live_{g}.pkl', 'rb')):
            if m['frames']:
                per.append(rows(m))
    print('matches with frames', len(per))
    print('enemy bodies that MOVED between the two frames; share of 26-tick forecasts off by >= 1.5 tiles [95% CI, matches resampled]')
    print('%-22s %7s  %-20s %-20s %s' % ('category', 'n', 'dead reckoning', '+ own_effects', 'median err base -> new | share changed'))
    sel = {c: (lambda r, c=c: r['cat'] == c) for c in CATS}
    for h in ('Log', 'Tornado', 'ability', 'Log+Tornado', 'Tornado+ability', 'Log+ability'):
        sel['  hit by ' + h] = (lambda r, h=h: r['cat'] == 'my_effect_hit' and r['how'] == h)
    sel['  hit, SECOND play'] = lambda r: r['cat'] == 'my_effect_hit' and r['second']
    sel['other, SECOND play'] = lambda r: r['cat'] == 'my_other_play' and r['second']
    sel['ALL moving'] = lambda r: True
    for name, f in sel.items():
        u = [[r for r in R if r['moving'] and f(r)] for R in per]
        n = sum(len(R) for R in u)
        if not n:
            continue
        a, b = boot(u, share('base')), boot(u, share('new'))
        flat = [r for R in u for r in R]
        print('%-22s %7d  %.2f [%.2f, %.2f]   %.2f [%.2f, %.2f]   %.2f -> %.2f | %.2f' % (
            name, n, *a, *b, np.median([r['base'] for r in flat]), np.median([r['new'] for r in flat]),
            np.mean([r['changed'] for r in flat])))
    if len(sys.argv) > 2:
        pickle.dump(per, open(sys.argv[2], 'wb'))
