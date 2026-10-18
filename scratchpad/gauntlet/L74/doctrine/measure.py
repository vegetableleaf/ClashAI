"""L74/doctrine: measure the owner's 10-18 "keep both princess towers" claim on pro replays, live matches and SIM rows.
    icebow/.venv/Scripts/python.exe -X utf8 measure.py > measure.out      (idle priority; reads only local files)
Clock: HF / crawl2 / SIM ticks = game clock (regulation ends at 3600, overtime at 6000); live game_tick = clock + LIVE_OFF
(live regulation-end frames sit at 3676-3681). Positions: the X-Bow player's own frame (own king y 29, river 16).
Exact vs inferred: live crown timelines are exact (tower HP frames). Pros / SIM have final crowns + length only, so the
overtime-start state and 'ever lost / ever took' are exact; 'who fell first' is bounded, plus a pocket-deploy estimate
whose error is measured on the live matches. Style metrics use the same play-based code for pros and live."""
from __future__ import annotations

import bisect
import glob
import json
import math
import random
import sys
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'habits'))
import hablib as H  # noqa: E402
import live_tables as LT  # noqa: E402

import polars as pl  # noqa: E402

LIVE_OFF = 78
REG, OT_END = 3600, 6000
CUE = 'rlarm_gae_cue_ab2_u0065_grafted.pt'
LT.MARKS[CUE] = 'cue_ab2'
ANYWHERE = {'miner', 'goblin_drill', 'mirror'}
SIM_DIR = Path('C:/Users/benpe/pod_backup_weekend/stepd/clIII_fin13/eval')
Z = 1.959964


# ---------------------------------------------------------------- statistics
def wilson(k, n):
    if n == 0:
        return (float('nan'),) * 3
    p = k / n
    d = 1 + Z * Z / n
    c = (p + Z * Z / (2 * n)) / d
    h = Z * math.sqrt(p * (1 - p) / n + Z * Z / (4 * n * n)) / d
    return p, c - h, c + h


def newcombe(k1, n1, k2, n2):
    """95% CI of p1 - p2 (Newcombe hybrid score interval)."""
    p1, l1, u1 = wilson(k1, n1)
    p2, l2, u2 = wilson(k2, n2)
    d = p1 - p2
    return d, d - math.sqrt((p1 - l1) ** 2 + (u2 - p2) ** 2), d + math.sqrt((u1 - p1) ** 2 + (p2 - l2) ** 2)


def fmt_p(rows, f=lambda r: r['win']):
    k, n = sum(f(r) for r in rows), len(rows)
    if n == 0:
        return '   n=0'
    p, lo, hi = wilson(k, n)
    return f'{100 * p:5.1f}% [{100 * lo:4.1f}, {100 * hi:4.1f}] n={n}'


def boot_mean(vals, B=2000, seed=0):
    vals = [v for v in vals if v is not None]
    if not vals:
        return float('nan'), float('nan'), float('nan')
    rng = random.Random(seed)
    m = sum(vals) / len(vals)
    bs = sorted(sum(rng.choice(vals) for _ in vals) / len(vals) for _ in range(B if len(vals) < 3000 else 400))
    return m, bs[int(.025 * len(bs))], bs[int(.975 * len(bs)) - 1]


def fmt_m(vals, d=2):
    m, lo, hi = boot_mean(vals)
    n = len([v for v in vals if v is not None])
    return f'{m:.{d}f} [{lo:.{d}f}, {hi:.{d}f}] n={n}'


# ---------------------------------------------------------------- crown records (one per match, X-Bow side's view)
def rec_final(group, key, win, c, oc, cls, tb=False):
    """Final-state record. cls: 'pre' (ended before regulation end), 'reg', 'ot' (sudden-death crown), 'otend' (tiebreak/draw).
    tb: drop the tiebreak crown (a full overtime with unequal crowns = the winner got one tower from the tiebreak)."""
    ot = None if cls in ('pre', 'reg') else min(c, oc)
    if tb and cls == 'otend' and c != oc:
        c, oc = (c - 1, oc) if win == 1.0 else (c, oc - 1)
    first = 'none' if c == 0 and oc == 0 else 'took' if oc == 0 else 'lost' if c == 0 else 'amb'
    r11 = 'no' if min(c, oc) == 0 else 'yes' if (c, oc) == (1, 1) or ot == 1 else 'amb'
    return dict(group=group, key=key, win=win, c=c, oc=oc, cls=cls, ot=ot, first=first, r11=r11,
                ever_lost=oc >= 1, ever_took=c >= 1)


def hf_cls(dur, c, oc):
    if dur is None:
        return None
    if dur < 184.3:
        return 'pre'
    if dur <= 185.6 and c != oc:
        return 'reg'
    return 'ot' if dur < 305 else 'otend'


def tick_cls(end, c, oc, last_play=None):
    """SIM end_tick, or (crawl2) the last play tick: a play after 3600 proves overtime; else regulation unless tied."""
    if last_play is not None:
        if last_play > REG:
            return 'otend' if c == oc else 'ot'
        return 'otend' if c == oc else ('pre' if max(c, oc) == 3 else 'reg')
    if end < REG - 10:
        return 'pre'
    if end <= REG + 1:
        return 'reg'
    return 'ot' if end < OT_END else 'otend'


# ---------------------------------------------------------------- pocket evidence (who lost a princess first, from plays)
def pocket_first(own, opp):
    """First tick each side deployed a troop / building into the other's half (needs that princess down): own pocket
    y < 16 (own troops normally >= 17.5), opponent pocket y > 16 (theirs normally <= 14.5). -> (t_own_ev, t_opp_ev)."""
    def first(plays, test):
        ts = [p['tick'] for p in plays if p['y'] is not None and p['card'] not in ANYWHERE
              and H.kind(p['card']) in ('troop', 'building') and test(p['y'])]
        return min(ts) if ts else None
    return first(own, lambda y: y < 16.0), first(opp, lambda y: y > 16.0)


def est_first(t_own, t_opp):
    """Estimated first crown from pocket evidence: the side whose pocket deploy comes first took the first tower."""
    if t_own is None and t_opp is None:
        return None
    if t_opp is None or (t_own is not None and t_own < t_opp):
        return 'took'
    return 'lost'


# ---------------------------------------------------------------- loaders
def norm_ev(ev, who):
    return [dict(tick=e[0], card=H.norm(e[2]), x=e[4], y=e[5]) for e in ev if e[1] == who and not e[3]]


def load_pros():
    """HF X-Bow sides (Path of Legend) + crawl2 icebow players, deduped on the first 12 plays."""
    scan = pl.read_parquet(HERE / 'pro_scan.parquet').filter(pl.col('xbow'))
    hp = {}
    for r in scan.iter_rows(named=True):
        hp.setdefault((r['replay_tag'], tuple(sorted(r['deck'])), r['crowns'], r['opp_crowns']), []).append(r)
    out, seen, dup = [], set(), 0
    for line in open(HERE.parent / 'habits/pro_sides.jsonl', encoding='utf-8'):
        r = json.loads(line)
        mode = r['mode'].split('/')[0]
        if mode != 'pathOfLegend' or len(r['ev']) < 6:
            continue
        sig = tuple((e[0], e[1], e[2]) for e in r['ev'][:12])
        if sig in seen:
            dup += 1
            continue
        seen.add(sig)
        own, opp = norm_ev(r['ev'], 'me'), norm_ev(r['ev'], 'op')
        c, oc = r['crowns'], r['opp_crowns']
        if r['src'] == 'hf':
            cls = hf_cls(r['dur'], c, oc)
            s = hp.get((r['tag'], tuple(r['deck']), c, oc), [None])[0]
        else:
            cls = tick_cls(None, c, oc, last_play=max(e[0] for e in r['ev']))
            s = None
        if cls is None:
            continue
        g = 'pro_icebow8' if r['icebow8'] else 'pro_xbow_other'
        m = dict(src=r['src'], group=g, key=r['src'] + ':' + r['tag'], win=r['win'], own=own, opp=opp, c=c, oc=oc,
                 cls=cls, dur=r['dur'], scan=s, opp_deck=r.get('opp_deck'))
        out.append(m)
    print(f'pros: {len(out)} X-Bow sides kept (Path of Legend, >= 6 plays), {dup} duplicates dropped;',
          Counter((m['group'], m['src']) for m in out))
    return out


def load_live():
    ms = LT.load()
    keep = []
    for m in ms:
        fr = m['frames']
        if not fr:
            continue
        # princess / king fall = first frame after which the tower stays missing or <= 0 for the rest of the match
        fall = {}
        for who in ('own', 'opp'):
            for s in 'KLR':
                alive = [t for t, T, *_ in fr if T.get((who, s), 0) > 0]
                if alive and alive[-1] < fr[-1][0]:
                    nxt = [t for t, *_ in fr if t > alive[-1]]
                    fall[(who, s)] = nxt[0] - LIVE_OFF
                elif not alive:
                    fall[(who, s)] = fr[0][0] - LIVE_OFF
        m['fall'] = fall
        m['end'] = fr[-1][0] - LIVE_OFF
        m['start_T'] = fr[0][1]
        m['end_T'] = fr[-1][1]
        for q in m['own'] + m['opp']:
            q['tick'] -= LIVE_OFF
        keep.append(m)
    print('live:', Counter(m['group'] for m in keep))
    return keep


def live_rec(m, tb=False):
    f = m['fall']
    def crowns(who):
        if (who, 'K') in f:
            return 3
        return sum((who, s) in f for s in 'LR')
    c, oc = crowns('opp'), crowns('own')
    end = m['end']
    cls = 'pre' if end < REG - 10 else 'reg' if end <= REG + 15 and c != oc else 'ot' if end < OT_END - 5 else 'otend'
    r = rec_final(m['group'], m['key'], m['win'], c, oc, cls)
    if tb and cls == 'otend':                    # the tiebreak tower (falls at the overtime buzzer) is not a fall in play
        f = {k: t for k, t in f.items() if t < OT_END - 10}
        c, oc = crowns('opp'), crowns('own')
        r.update(c=c, oc=oc, ever_lost=oc >= 1, ever_took=c >= 1)
    pf = sorted([(t, 'lost') for (w, s), t in f.items() if w == 'own' and s in 'LR'] +
                [(t, 'took') for (w, s), t in f.items() if w == 'opp' and s in 'LR'])
    r['first'] = pf[0][1] if pf else ('none' if not f else 'king')
    # exact state at clock t: princesses down by then (only for matches still running at t)
    def state(t):
        if end <= t:
            return None
        return (sum(1 for (w, s), tt in f.items() if w == 'opp' and s in 'LR' and tt <= t),
                sum(1 for (w, s), tt in f.items() if w == 'own' and s in 'LR' and tt <= t))
    r['s60'], r['s120'], r['s180'] = state(1200), state(2400), state(REG)
    seq, a, b = [(0, 0)], 0, 0
    for t, w in pf:
        a, b = (a + 1, b) if w == 'took' else (a, b + 1)
        seq.append((a, b))
    r['reached'] = set(seq)
    r['r11'] = 'yes' if (1, 1) in r['reached'] else 'no'
    r['ot'] = r['s180'][0] if r['s180'] and r['s180'][0] == r['s180'][1] else None
    r['result_check'] = (c > oc) == (m['win'] == 1.0) if c != oc else None
    return r


def load_sim():
    """CLIII promotion-eval rows on fin13 (vs generated opponents): (group, key, win, crowns, opp crowns, end class)."""
    rows = []
    for f in sorted(glob.glob(str(SIM_DIR / '*_fin13/D3/*/matches.jsonl'))):
        for line in open(f):
            j = json.loads(line)
            c, oc = j['crowns_for'], j['crowns_against']
            win = 1.0 if j['outcome'] == 'win' else 0.0 if j['outcome'] == 'loss' else 0.5
            rows.append(('sim_CLIII', j['tag'] + ':' + str(j['seed']), win, c, oc, tick_cls(j['end_tick'], c, oc)))
    return rows


def baseline():
    """Non-X-Bow sides of Path of Legend games with no X-Bow on either side: the deck-neutral reference."""
    d = pl.read_parquet(HERE / 'pro_scan.parquet').filter((pl.col('battle_type') == 'pathOfLegend') & ~pl.col('xbow')
                                                          & ~pl.col('opp_xbow') & pl.col('dur').is_not_null())
    return [('pro_nonxbow', r['replay_tag'] + r['side'], r['win'], r['crowns'], r['opp_crowns'],
             hf_cls(r['dur'], r['crowns'], r['opp_crowns']))
            for r in d.select('replay_tag', 'side', 'win', 'crowns', 'opp_crowns', 'dur').iter_rows(named=True)]


# ---------------------------------------------------------------- section 1: crown-state tables
def crown_tables(groups, title):
    print(f'\n## {title}')
    hdr = f"  {'group':16s} {'P(win) all':28s} {'OT start 0-0':28s} {'OT start 1-1':28s} {'1-1 minus 0-0 (pp)':22s}"
    print(hdr)
    for g, rs in groups.items():
        o0 = [r for r in rs if r['ot'] == 0]
        o1 = [r for r in rs if r['ot'] == 1]
        d = newcombe(sum(r['win'] for r in o1), len(o1), sum(r['win'] for r in o0), len(o0)) if o0 and o1 else (float('nan'),) * 3
        print(f'  {g:16s} {fmt_p(rs):28s} {fmt_p(o0):28s} {fmt_p(o1):28s} {100 * d[0]:+5.1f} [{100 * d[1]:+5.1f}, {100 * d[2]:+5.1f}]')
    print(f"\n  {'group':16s} {'P(win | ever lost a princess)':32s} {'P(win | ever took one)':32s} {'P(lose a princess at all)':28s}")
    for g, rs in groups.items():
        el = [r for r in rs if r['ever_lost']]
        et = [r for r in rs if r['ever_took']]
        print(f'  {g:16s} {fmt_p(el):32s} {fmt_p(et):32s} {fmt_p(rs, lambda r: r["ever_lost"]):28s}')


def first_tables(groups, title, est=None):
    """P(win | lost first) / P(win | took first). Exact where 'first' is known; else bounds over the ambiguous matches
    (both sides ended with >= 1 crown) and, when est is given, the pocket-evidence estimate."""
    print(f'\n## {title}')
    for g, rs in groups.items():
        known = Counter(r['first'] for r in rs)
        amb = [r for r in rs if r['first'] == 'amb']
        lf = [r for r in rs if r['first'] == 'lost']
        tf = [r for r in rs if r['first'] == 'took']
        if not amb:
            d = newcombe(sum(r['win'] for r in tf), len(tf), sum(r['win'] for r in lf), len(lf))
            print(f'  {g:16s} lost first {fmt_p(lf)} | took first {fmt_p(tf)} | took-lost {100 * d[0]:+.1f} pp '
                  f'[{100 * d[1]:+.1f}, {100 * d[2]:+.1f}] | no princess fell {known["none"]}, king first {known["king"]}')
            continue
        aw = sum(r['win'] for r in amb)
        al = len(amb) - aw
        lw, ln = sum(r['win'] for r in lf), len(lf)
        tw, tn = sum(r['win'] for r in tf), len(tf)
        lo_lf, hi_lf = lw / (ln + al) if ln + al else 0, (lw + aw) / (ln + aw) if ln + aw else 0
        lo_tf, hi_tf = tw / (tn + al) if tn + al else 0, (tw + aw) / (tn + aw) if tn + aw else 0
        print(f'  {g:16s} known lost-first n={ln} (wins {lw:g}), took-first n={tn} (wins {tw:g}), ambiguous n={len(amb)} '
              f'(wins {aw:g}) -> bounds P(win | lost first) [{100 * lo_lf:.1f}, {100 * hi_lf:.1f}]%, '
              f'P(win | took first) [{100 * lo_tf:.1f}, {100 * hi_tf:.1f}]%')


def trade_tables(groups, title):
    """How often both sides take a princess, and how often a 1-0 lead is given back (live exact; pros / SIM: upper bound =
    every ambiguous match counted as took-first-then-lost-one)."""
    print(f'\n## {title}')
    for g, rs in groups.items():
        both = fmt_p(rs, lambda r: r['c'] >= 1 and r['oc'] >= 1)
        if 'reached' in rs[0]:
            tf = [r for r in rs if (1, 0) in r['reached']]
            gb = fmt_p(tf, lambda r: (1, 1) in r['reached'])
        else:
            tn = sum(r['first'] == 'took' for r in rs)
            na = sum(r['first'] == 'amb' for r in rs)
            gb = f'<= {100 * na / max(1, tn + na):.1f}% (bound; took-first n={tn}, ambiguous n={na})'
        print(f'  {g:16s} both sides took a princess {both:30s} | gave a 1-0 lead back (reached 1-1 after 1-0) {gb}')


TANKS = {'golem', 'giant', 'lava-hound', 'electro-giant', 'pekka', 'mega-knight', 'royal-giant', 'goblin-giant', 'elixir-golem',
         'giant-skeleton', 'rune-giant', 'balloon', 'three-musketeers'}
BRIDGE = {'hog-rider', 'ram-rider', 'battle-ram', 'royal-hogs', 'wall-breakers', 'bandit', 'elite-barbarians', 'miner',
          'goblin-drill', 'skeleton-barrel', 'royal-recruits', 'graveyard', 'goblin-barrel'}


def archetype(deck):
    d = set(deck or [])
    return 'siege' if d & {'x-bow', 'mortar'} else 'beatdown' if d & TANKS else 'bridge/bait' if d & BRIDGE else 'other'


def strat_ot(pros, recs, B=1000):
    """P(win | OT starts 1-1) - P(win | OT starts 0-0) for pro X-Bow sides, Mantel-Haenszel weighted within opponent archetype
    (so a matchup mix that reaches 1-1 more often cannot fake the gap); match bootstrap 95% CI."""
    rows = [(archetype(m.get('opp_deck')), r['ot'], r['win']) for m, r in zip(pros, recs) if r['ot'] in (0, 1)]
    def rd(rs):
        cell = defaultdict(lambda: [0, 0, 0, 0])            # wins1, n1, wins0, n0
        for a, o, w in rs:
            c = cell[a]
            if o == 1:
                c[0] += w; c[1] += 1
            else:
                c[2] += w; c[3] += 1
        num = den = 0.0
        for w1, n1, w0, n0 in cell.values():
            if n1 and n0:
                wt = n1 * n0 / (n1 + n0)
                num += wt * (w1 / n1 - w0 / n0)
                den += wt
        return num / den if den else float('nan'), cell
    est, cell = rd(rows)
    rng = random.Random(1)
    bs = sorted(rd([rng.choice(rows) for _ in rows])[0] for _ in range(B))
    print('\n## OVERTIME 1-1 vs 0-0, pro X-Bow sides, adjusted for opponent archetype (Mantel-Haenszel; 95% bootstrap CI)')
    for a, (w1, n1, w0, n0) in sorted(cell.items()):
        print(f'  {a:12s} 1-1: {100 * w1 / max(1, n1):5.1f}% n={n1:4d} | 0-0: {100 * w0 / max(1, n0):5.1f}% n={n0:5d}')
    print(f'  adjusted 1-1 minus 0-0: {100 * est:+.1f} pp [{100 * bs[int(.025 * B)]:+.1f}, {100 * bs[int(.975 * B) - 1]:+.1f}]')


def own_arch_ot():
    """Is the overtime 1-1 penalty X-Bow-specific? The same gap for every own-deck archetype (Path of Legend, mirrors of the
    same archetype dropped so the two sides do not cancel)."""
    d = pl.read_parquet(HERE / 'pro_scan.parquet').filter((pl.col('battle_type') == 'pathOfLegend') & pl.col('dur').is_not_null())
    d = d.join(d.select('replay_tag', 'side', pl.col('deck').alias('opp_deck_l')), on='replay_tag').filter(
        pl.col('side') != pl.col('side_right'))
    def arch(deck):
        s = set(deck)
        return 'x-bow' if 'x-bow' in s else 'mortar' if 'mortar' in s else archetype(deck)
    cell = defaultdict(lambda: [0, 0, 0, 0])
    for r in d.select('deck', 'opp_deck_l', 'win', 'crowns', 'opp_crowns', 'dur').iter_rows(named=True):
        cls = hf_cls(r['dur'], r['crowns'], r['opp_crowns'])
        if cls in ('pre', 'reg'):
            continue
        a, b = arch(r['deck']), arch(r['opp_deck_l'])
        o = min(r['crowns'], r['opp_crowns'])
        if a == b or o > 1:
            continue
        c = cell[a]
        c[0 if o == 1 else 2] += r['win']
        c[1 if o == 1 else 3] += 1
    print('\n## Is the OT 1-1 penalty X-Bow-specific? P(win | OT 1-1) - P(win | OT 0-0) by OWN deck archetype '
          '(pros, Path of Legend, same-archetype mirrors dropped)')
    for a, (w1, n1, w0, n0) in sorted(cell.items(), key=lambda x: -x[1][3]):
        dd = newcombe(w1, n1, w0, n0)
        print(f'  {a:12s} 1-1 {100 * w1 / max(1, n1):5.1f}% n={n1:6d} | 0-0 {100 * w0 / max(1, n0):5.1f}% n={n0:6d} | '
              f'{100 * dd[0]:+5.1f} pp [{100 * dd[1]:+5.1f}, {100 * dd[2]:+5.1f}]')


def reached_tables(groups, title):
    print(f'\n## {title}')
    for g, rs in groups.items():
        y = [r for r in rs if r['r11'] == 'yes']
        n_ = [r for r in rs if r['r11'] == 'no']
        a = [r for r in rs if r['r11'] == 'amb']
        yw, aw = sum(r['win'] for r in y), sum(r['win'] for r in a)
        bnd = (f' -> bounds P(win | reached 1-1) [{100 * yw / max(1, len(y) + len(a) - aw):.1f}, '
               f'{100 * (yw + aw) / max(1, len(y) + aw):.1f}]%') if a else ''
        print(f'  {g:16s} reached 1-1 {fmt_p(y)} | never 1-1 {fmt_p(n_)} | ambiguous n={len(a)} wins {aw:g}{bnd}')


def live_state_tables(recs):
    print('\n## LIVE exact: P(win | crown state at clock t), state = (we took, we lost) princesses; matches still running at t')
    by = defaultdict(list)
    for r in recs:
        by[r['group']].append(r)   # live groups
    for key, lab in (('s60', '60 s'), ('s120', '120 s (double elixir)'), ('s180', '180 s (overtime start)')):
        print(f'  -- at {lab}')
        for g, rs in by.items():
            cells = Counter(r[key] for r in rs if r[key] is not None)
            parts = []
            for st in ((0, 0), (1, 0), (0, 1), (1, 1)):
                sub = [r for r in rs if r[key] == st]
                if sub:
                    p, lo, hi = wilson(sum(r['win'] for r in sub), len(sub))
                    parts.append(f'{st[0]}-{st[1]}: {100 * p:.0f}% [{100 * lo:.0f},{100 * hi:.0f}] n={len(sub)}')
            other = sum(v for k, v in cells.items() if k not in ((0, 0), (1, 0), (0, 1), (1, 1)))
            print(f'    {g:10s} ' + ' | '.join(parts) + (f' | other n={other}' if other else ''))
    print('\n  P(win | crown state reached at ANY point):')
    for g, rs in by.items():
        parts = []
        for st in ((1, 0), (0, 1), (1, 1)):
            sub = [r for r in rs if st in r['reached']]
            if sub:
                p, lo, hi = wilson(sum(r['win'] for r in sub), len(sub))
                parts.append(f'{st[0]}-{st[1]}: {100 * p:.0f}% [{100 * lo:.0f},{100 * hi:.0f}] n={len(sub)}')
        n00 = [r for r in rs if r['reached'] == {(0, 0)}]
        parts.append('no princess fell: ' + fmt_p(n00))
        print(f'    {g:10s} ' + ' | '.join(parts))
    print('\n  trade order among matches that reached 1-1:')
    for g, rs in by.items():
        a = [r for r in rs if (1, 0) in r['reached'] and (1, 1) in r['reached']]
        b = [r for r in rs if (0, 1) in r['reached'] and (1, 1) in r['reached']]
        print(f'    {g:10s} took first then traded (1-0 -> 1-1): {fmt_p(a)} | lost first then traded back (0-1 -> 1-1): {fmt_p(b)}')


# ---------------------------------------------------------------- section 2: style metrics (plays only, same for pros and live)
def is_def(q):
    return q['y'] is not None and q['y'] >= 15.0 and not H.is_bridge_xbow(q)


def is_off(q):
    return q['y'] is not None and (H.is_bridge_xbow(q) or q['y'] < 15.0)


def defence_episodes(m):
    """Opponent troop plays clustered with gaps <= 5 s = one push; value = their elixir. Our defensive plays (own half, not a
    bridge X-Bow) from 2 s before its first play to 8 s after its last are the answer; each of our plays answers one push."""
    opp = sorted([p for p in m['opp'] if H.kind(p['card']) == 'troop'], key=lambda p: p['tick'])
    eps = []
    for p in opp:
        if eps and p['tick'] - eps[-1]['t1'] <= 100:
            eps[-1]['t1'] = p['tick']
            eps[-1]['v'] += H.cost(p['card'])
        else:
            eps.append(dict(t0=p['tick'], t1=p['tick'], v=H.cost(p['card']), ours=[]))
    starts = [e['t0'] for e in eps]
    for q in m['own']:
        if not is_def(q):
            continue
        i = bisect.bisect_right(starts, q['tick'] + 40) - 1
        if i >= 0 and q['tick'] <= eps[i]['t1'] + 160:
            eps[i]['ours'].append(q)
    out = []
    for e in eps:
        sp = sum(H.cost(q['card']) for q in e['ours'])
        cheap = bool(e['ours']) and all(H.cost(q['card']) <= H.CHEAP_COST for q in e['ours'])
        out.append(dict(key=m['key'], v=e['v'], spend=sp, trade=e['v'] - sp, answered=bool(e['ours']), cheap=cheap,
                        band='heavy>=10' if e['v'] >= 10 else 'mid5-9' if e['v'] >= 5 else 'light<5',
                        rocket=any(q['card'] == 'rocket' for q in e['ours'])))
    return out


def match_style(m):
    own = m['own']
    early = [q for q in own if 0 <= q['tick'] < 1200]
    off_early = sum(H.cost(q['card']) for q in early if is_off(q))
    fb = [q['tick'] for q in own if H.is_bridge_xbow(q)]
    rk = H.rocket_uses(m)
    last = max([q['tick'] for q in own + m['opp']] or [0])
    mins = max(1.0, (m.get('end') or m.get('dur_clock') or last) / 1200)
    return dict(key=m['key'], off_early=off_early, early_spend=sum(H.cost(q['card']) for q in early),
                any_off_early=off_early > 0, first_bridge_s=(min(fb) / 20) if fb else None,
                bridge_pm=len(fb) / mins, rockets_pm=len(rk) / mins,
                rocket_tower_pm=sum(r['aim'] == 'tower' for r in rk) / mins,
                rocket_tower=sum(r['aim'] == 'tower' for r in rk), mins=mins)


def princess_max_hp(scan_rows):
    by = defaultdict(Counter)
    for s in scan_rows:
        for k in ('own_princess_left', 'own_princess_right'):
            if s[k]:
                by[s['tower_lv']][s[k]] += 1
    return {lv: c.most_common(1)[0][0] for lv, c in by.items()}   # untouched towers are the mode


def style_tables(pros, live):
    print('\n## STYLE (plays only, identical code for pros and live). Groups: pros icebow8 (exact deck), pros other X-Bow decks, '
          'live Marks')
    groups = defaultdict(list)
    for m in pros + live:
        groups[m['group']].append(m)
    for m in pros:
        m['dur_clock'] = (m['dur'] - 4.5) * 20 if m['dur'] else None
    order = ['pro_icebow8', 'pro_xbow_other', 'CLIII', 'CXXXVIII', 'cue_ab2', 'CXXIV']
    eps = {g: [e for m in groups[g] for e in defence_episodes(m)] for g in order}
    st = {g: [match_style(m) for m in groups[g]] for g in order}
    print('\n  Defence episodes (opponent troop pushes; our answers on our half):')
    print(f"  {'group':15s} {'band':10s} {'n':>6s}  {'elixir trade (their - ours)':30s} {'positive-trade share':26s} "
          f"{'cheap-only share (answered)':28s} {'unanswered':24s} {'Rocket in answer':22s}")
    for g in order:
        for b in ('all', 'mid5-9', 'heavy>=10'):
            es = [e for e in eps[g] if b == 'all' or e['band'] == b]
            if not es:
                continue
            ci = H.boot_ci(es, lambda s: sum(e['trade'] for e in s) / len(s))
            pos = H.boot_ci(es, lambda s: sum(e['trade'] > 0 for e in s) / len(s))
            ans = [e for e in es if e['answered']]
            ch = H.boot_ci(ans, lambda s: sum(e['cheap'] for e in s) / len(s))
            un = H.boot_ci(es, lambda s: sum(not e['answered'] for e in s) / len(s))
            rk = H.boot_ci(ans, lambda s: sum(e['rocket'] for e in s) / len(s))
            mt = sum(e['trade'] for e in es) / len(es)
            print(f"  {g:15s} {b:10s} {len(es):6d}  {mt:+5.2f} [{ci[0]:+.2f}, {ci[1]:+.2f}]{'':9s}"
                  f"{100 * sum(e['trade'] > 0 for e in es) / len(es):5.1f}% [{100 * pos[0]:.1f}, {100 * pos[1]:.1f}]{'':5s}"
                  f"{100 * sum(e['cheap'] for e in ans) / max(1, len(ans)):5.1f}% [{100 * ch[0]:.1f}, {100 * ch[1]:.1f}]{'':7s}"
                  f"{100 * sum(not e['answered'] for e in es) / len(es):5.1f}% [{100 * un[0]:.1f}, {100 * un[1]:.1f}]   "
                  f"{100 * sum(e['rocket'] for e in ans) / max(1, len(ans)):5.1f}% [{100 * rk[0]:.1f}, {100 * rk[1]:.1f}]")
    print('\n  Per match (mean [95% CI] n):')
    for lab, f, d in (('early offensive spend, first 60 s (elixir)', 'off_early', 2),
                      ('total spend, first 60 s (elixir)', 'early_spend', 2),
                      ('first bridge X-Bow (clock s)', 'first_bridge_s', 1),
                      ('bridge X-Bows per minute', 'bridge_pm', 3),
                      ('Rockets per minute (all aims)', 'rockets_pm', 3),
                      ('Rockets at a tower per minute', 'rocket_tower_pm', 3),
                      ('Rockets at a tower per match', 'rocket_tower', 2)):
        print(f'  {lab}')
        for g in order:
            print(f'    {g:15s} ' + fmt_m([s[f] for s in st[g]], d))
        if f == 'off_early':
            print('    share of matches with any offensive spend in the first 60 s:')
            for g in order:
                print(f'      {g:15s} ' + fmt_p(st[g], lambda s: s['any_off_early']))
    print('\n  Does early aggression go with losing? P(win) split by the match\'s own early play (association only: the '
          'opponent deck drives both)')
    for g in order:
        ws = [m['win'] for m in groups[g]]
        a = [w for w, s in zip(ws, st[g]) if s['first_bridge_s'] is not None and s['first_bridge_s'] < 60]
        b = [w for w, s in zip(ws, st[g]) if s['first_bridge_s'] is None or s['first_bridge_s'] >= 60]
        dd = newcombe(sum(a), len(a), sum(b), len(b)) if a and b else (float('nan'),) * 3
        print(f'    {g:15s} first bridge X-Bow < 60 s: {fmt_p([dict(win=w) for w in a])} | later / none: '
              f'{fmt_p([dict(win=w) for w in b])} | diff {100 * dd[0]:+.1f} pp [{100 * dd[1]:+.1f}, {100 * dd[2]:+.1f}]')
    # own princess damage: live frames vs pro final HP (HF only); as a share of one full princess tower
    print('\n  Own princess-tower HP lost, in princess-tower units (1.0 = one tower) per match and per minute:')
    scan_rows = [m['scan'] for m in pros if m.get('scan') and m['scan']['tower_lv'] == 16]
    mx = princess_max_hp(scan_rows)
    print('    full princess HP by tower level (max seen):', dict(sorted(mx.items())))
    for g in order:
        tot, pm = [], []
        for m in groups[g]:
            if g.startswith('pro'):
                s = m.get('scan')
                if not s or not m['dur'] or s['tower_lv'] != 16:
                    continue
                full = mx[s['tower_lv']]
                lost = (2 * full - (s['own_princess_left'] or 0) - (s['own_princess_right'] or 0)) / full
                mins = (m['dur'] - 4.5) / 60
            else:
                T0, T1 = m['start_T'], m['end_T']
                full = max(T0.get(('own', 'L'), 0), T0.get(('own', 'R'), 0))
                if full <= 0:
                    continue
                lost = sum(max(0, T0.get(('own', s), 0) - T1.get(('own', s), 0)) for s in 'LR') / full
                mins = m['end'] / 1200
            tot.append(lost)
            pm.append(lost / max(mins, 0.5))
        print(f'    {g:15s} per match {fmt_m(tot, 3)} | per minute {fmt_m(pm, 3)}')
    print('\n  X-Bow tower damage (LIVE only: needs frames; pros have no frames). Per bridge X-Bow: life (s) and enemy tower '
          'HP lost during its life:')
    for g in order[2:]:
        rows = [r for m in groups[g] for r in H.xbow_events(dict(m, frames=[(t - LIVE_OFF, *rest) for t, *rest in m['frames']]))
                if r.get('life_s') is not None]
        if rows:
            print(f"    {g:15s} life {fmt_m([r['life_s'] for r in rows], 1)} | tower dmg {fmt_m([r['dmg'] for r in rows], 0)}"
                  f" | own tower HP taken {fmt_m([r['taken'] for r in rows], 0)}")
    return eps, st


# ---------------------------------------------------------------- main
def main():
    pros = load_pros()
    live = load_live()
    lrec = [live_rec(m) for m in live]
    chk = [r['result_check'] for r in lrec if r['result_check'] is not None]
    print(f'live crown timeline vs logged result: {sum(chk)}/{len(chk)} agree (unequal-crown matches)')
    precs = [rec_final(m['group'], m['key'], m['win'], m['c'], m['oc'], m['cls']) for m in pros]
    for m, r in zip(pros, precs):
        m['rec'] = r
    sim = load_sim()
    base = baseline()

    # validity of the crawl2 overtime rule (play after 3600) on HF, where the length is known
    hf = [m for m in pros if m['src'] == 'hf' and m['cls'] in ('ot', 'otend')]
    miss = sum(1 for m in hf if max([q['tick'] for q in m['own'] + m['opp']] or [0]) <= REG)
    print(f'crawl2 overtime rule check on HF overtime games: {miss}/{len(hf)} have no play after 3600 (would be missed)')

    # pocket-evidence validity: false positives (evidence with no such tower down) on pros, ordering on live
    fp_own = sum(1 for m in pros if m['c'] == 0 and pocket_first(m['own'], m['opp'])[0] is not None)
    fp_opp = sum(1 for m in pros if m['oc'] == 0 and pocket_first(m['own'], m['opp'])[1] is not None)
    print(f"pocket evidence false positives on pros: own pocket with 0 crowns {fp_own}/{sum(m['c'] == 0 for m in pros)}, "
          f"opponent pocket with 0 opp crowns {fp_opp}/{sum(m['oc'] == 0 for m in pros)}")
    ok = tot = noev = 0
    lag = defaultdict(list)
    for m, r in zip(live, lrec):
        t_own, t_opp = pocket_first(m['own'], m['opp'])
        for who, tev in (('opp', t_own), ('own', t_opp)):
            falls = [t for (w, s), t in m['fall'].items() if w == who and s in 'LR']
            if falls and tev is not None:
                lag[who].append((tev - min(falls)) / 20)
        if r['c'] >= 1 and r['oc'] >= 1 and r['first'] in ('took', 'lost'):
            e = est_first(t_own, t_opp)
            if e is None:
                noev += 1
            else:
                tot += 1
                ok += e == r['first']
    def pct(xs, q):
        xs = sorted(xs)
        return xs[min(len(xs) - 1, int(q * len(xs)))] if xs else float('nan')
    print(f'pocket estimate vs exact first crown on LIVE matches where both sides lost a princess: {ok}/{tot} correct '
          f'({100 * ok / max(1, tot):.1f}%), {noev} without evidence')
    for who, xs in lag.items():
        neg = sum(x < 0 for x in xs)
        print(f'  live lag pocket deploy - tower fall ({who} princess): median {pct(xs, .5):.1f} s, p90 {pct(xs, .9):.1f} s, '
              f'before the fall (impossible = reader position noise) {neg}/{len(xs)}')
    order = ['pro_icebow8', 'pro_xbow_other', 'pro_all_xbow', 'pro_nonxbow', 'sim_CLIII', 'live_CLIII', 'live_CXXXVIII',
             'live_cue_ab2', 'live_CXXIV']

    def build(tb):
        g = defaultdict(list)
        pr = [rec_final(m['group'], m['key'], m['win'], m['c'], m['oc'], m['cls'], tb) for m in pros]
        for r in pr:
            g[r['group']].append(r)
        g['pro_all_xbow'] = pr
        for t in sim + base:
            g[t[0]].append(rec_final(*t, tb=tb))
        for m in live:
            g['live_' + m['group']].append(live_rec(m, tb))
        return {k: g[k] for k in order if g.get(k)}
    G = build(False)
    print('\n  match-end class shares:', {g: dict(Counter(r['cls'] for r in rs)) for g, rs in G.items()})
    crown_tables(G, 'CROWN STATE (exact for every source): overall, overtime-start state, ever lost / ever took a princess '
                    '(tiebreak tower COUNTED as a crown)')
    strat_ot(pros, precs)
    own_arch_ot()
    T = build(True)
    print('\n# From here on the tiebreak tower (destroyed at the overtime buzzer) is NOT counted as a princess lost / taken.')
    crown_tables({k: v for k, v in T.items()}, 'CROWN STATE, tiebreak crown removed')
    first_tables(T, 'FIRST PRINCESS IN PLAY: lost first vs took first (live exact; pros / SIM bounded: both sides ended with '
                    'a crown = order unknown)')
    trade_tables(T, 'CROWN TRADES: both sides took a princess; a 1-0 lead given back')
    reached_tables(T, 'REACHED 1-1 at any point (live exact; pros / SIM: yes when final 1-1 or overtime started 1-1)')
    live_state_tables([r for k, v in T.items() if k.startswith('live_') for r in v])
    style_tables(pros, live)


if __name__ == '__main__':
    main()
