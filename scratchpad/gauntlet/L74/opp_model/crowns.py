"""Crown-path records, one definition for live rows (exact tower-fall timeline) and SIM eval rows (final crowns + end tick),
reusing doctrine/measure.py (rec_final, tick_cls, wilson, newcombe) so the numbers match DOCTRINE_MEASURED.md's method.
Clock ticks: 20 / s, regulation ends 3600, overtime ends 6000; a fall at >= 5990 is the tiebreak tower (not in play)."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'doctrine'))
import measure as M  # noqa: E402

REG, OT_END, LIVE_OFF = 3600, 6000, 78
wilson, newcombe = M.wilson, M.newcombe


def _crowns(f, who):
    return 3 if who + '_K' in f else sum(1 for k in f if k.startswith(who + '_P'))


def live_rec(r, off=LIVE_OFF):
    """Live row (live_table.py) -> dict: c / oc = princess-or-king crowns we took / lost IN PLAY (tiebreak tower removed),
    c_all / oc_all incl. the tiebreak, cls (pre / reg / ot / otend), ot = crowns each at OT start when tied, reached = set of
    (ours, theirs) states passed through, first = 'took' / 'lost' / 'none'."""
    f = r['falls']
    end = r['end'] - off
    c_all, oc_all = _crowns(f, 'opp'), _crowns(f, 'own')
    cls = 'pre' if end < REG - 10 else 'reg' if end <= REG + 15 and c_all != oc_all else 'ot' if end < OT_END - 5 else 'otend'
    fp = {k: t for k, t in f.items() if t < OT_END - 10}
    c, oc = _crowns(fp, 'opp'), _crowns(fp, 'own')
    pf = sorted([(t, 'lost') for k, t in fp.items() if k.startswith('own_P')] +
                [(t, 'took') for k, t in fp.items() if k.startswith('opp_P')])
    seq, a, b = [(0, 0)], 0, 0
    for _, w in pf:
        a, b = (a + 1, b) if w == 'took' else (a, b + 1)
        seq.append((a, b))
    s180 = None
    if end > REG:
        s180 = (sum(1 for k, t in fp.items() if k.startswith('opp_P') and t <= REG),
                sum(1 for k, t in fp.items() if k.startswith('own_P') and t <= REG))
    ot = s180[0] if s180 and s180[0] == s180[1] and cls in ('ot', 'otend') else None
    return dict(win=r['win'], c=c, oc=oc, c_all=c_all, oc_all=oc_all, cls=cls, ot=ot, reached=set(seq),
                first=pf[0][1] if pf else 'none', ever_lost=oc >= 1, ever_took=c >= 1, exact=True)


def sim_rec(r):
    """SIM eval row -> the same fields; order (first / reached) is unknown when both sides took a crown ('amb'), unless the row
    carries the behaviour telemetry's tower frames (sim_sets.tel_falls): then the record is exact, as live."""
    if r.get('falls') is not None:
        x = live_rec(dict(falls=r['falls'], end=r['end_tick'], win=1.0 if r['outcome'] == 'win' else 0.0 if r['outcome'] == 'loss' else 0.5), off=0)
        return x
    c, oc = r['crowns_for'], r['crowns_against']
    win = 1.0 if r['outcome'] == 'win' else 0.0 if r['outcome'] == 'loss' else 0.5
    cls = M.tick_cls(r['end_tick'], c, oc)
    x = M.rec_final('sim', None, win, c, oc, cls, tb=True)
    reached = None if x['first'] == 'amb' else {(0, 0), (min(x['c'], 1), min(x['oc'], 1))}
    return dict(win=win, c=x['c'], oc=x['oc'], c_all=c, oc_all=oc, cls=cls, ot=x['ot'], reached=reached, first=x['first'],
                ever_lost=x['ever_lost'], ever_took=x['ever_took'], exact=False)


def pct(k, n):
    if n == 0:
        return 'n=0'
    p, lo, hi = wilson(k, n)
    return f'{100 * p:.1f}% [{100 * lo:.1f}, {100 * hi:.1f}] n={n}'


def crown_stats(recs):
    """The J9 crown-path numbers for one group of records (live exact; SIM give-back is an upper bound)."""
    n = len(recs)
    out = dict(n=n)
    out['win'] = (sum(r['win'] == 1.0 for r in recs), n)
    out['lose_princess'] = (sum(r['ever_lost'] for r in recs), n)
    out['take_princess'] = (sum(r['ever_took'] for r in recs), n)
    out['both'] = (sum(r['c'] >= 1 and r['oc'] >= 1 for r in recs), n)
    ot = [r for r in recs if r['cls'] in ('ot', 'otend')]
    out['ot_share'] = (len(ot), n)
    o11 = [r for r in recs if r['ot'] == 1]
    o00 = [r for r in recs if r['ot'] == 0]
    out['ot11_share'] = (len(o11), n)
    out['win_ot11'] = (sum(r['win'] == 1.0 for r in o11), len(o11))
    out['win_ot00'] = (sum(r['win'] == 1.0 for r in o00), len(o00))
    el = [r for r in recs if r['ever_lost']]
    out['win_lost'] = (sum(r['win'] == 1.0 for r in el), len(el))
    reg = [r for r in recs if r['cls'] in ('pre', 'reg')]
    out['reg_loss'] = (sum(r['win'] == 0.0 for r in reg), n)
    if recs and recs[0]['exact']:
        led = [r for r in recs if (1, 0) in r['reached']]
        out['giveback'] = (sum((1, 1) in r['reached'] for r in led), len(led))
        out['giveback_bound'] = None
    else:
        tf = sum(r['first'] == 'took' for r in recs)
        amb = sum(r['first'] == 'amb' for r in recs)
        out['giveback'] = None
        out['giveback_bound'] = amb / max(1, tf + amb)
    return out


FIELDS = ('win', 'lose_princess', 'take_princess', 'both', 'ot_share', 'ot11_share', 'win_ot11', 'win_ot00', 'win_lost', 'reg_loss')


def fmt_stats(s):
    cells = [pct(*s[k]) for k in FIELDS]
    cells.append(pct(*s['giveback']) if s['giveback'] else f"<= {100 * s['giveback_bound']:.1f}% (bound)")
    return cells
