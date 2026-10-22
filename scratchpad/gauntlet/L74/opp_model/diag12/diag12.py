"""W18 DIAG_12: why does the best opponent (W14 I u40, 4ff9fe93) fail 6 of the 12 O4-Ranked checks?  Laptop, light CPU, idle.
    icebow/.venv/Scripts/python.exe -B scratchpad/gauntlet/L74/opp_model/diag12/diag12.py [SECTION ...] > diag12/diag12.out
Sections (default all): defs phase state both wincon intensity tank xbow exec lock style
Inputs (read-only):
  live  = clx_ranked/rows.json (W13's 233 CLX Ranked rows) + invlib.live_matches (habits/cache pickles of the same logs)
  SIM   = pod_backup_weekend/w14/o4/w14F_Iu40 (2,880 games: CLX vs I u40, blocks 741200 + 742000-746000)
  SIMp  = pod_backup_weekend/w14/o3/w14c_Iu40_pos (block 741200 again WITH deploy positions + tower / X-Bow traces)
Definitions are the O4-Ranked scorer's (w14/o4r_table.py -> clx_ranked/sim.py row(); live rows from clx_ranked/anatomy.py).
Public information only: opponent plays / bodies / towers as seen on screen; never the opponent's hand, deck order or elixir."""
from __future__ import annotations

import ctypes
import json
import math
import statistics as st
import sys
from collections import Counter, defaultdict
from pathlib import Path

try:
    ctypes.windll.kernel32.SetPriorityClass(ctypes.windll.kernel32.GetCurrentProcess(), 0x40)   # IDLE: shared laptop
except Exception:  # noqa: BLE001
    pass

HERE = Path(__file__).resolve().parent
OPP = HERE.parent
L74 = OPP.parent
sys.path[:0] = [str(OPP / 'w14'), str(L74 / 'clx_ranked'), str(L74 / 'investment'), str(OPP), str(L74 / 'human')]
import o4r_table as T  # noqa: E402
import pocket as PK  # noqa: E402

AN, H = T.AN, T.AN.H
BK = Path('C:/Users/benpe/pod_backup_weekend/w14')
SIM_ROOT, POS_ROOT = BK / 'o4/w14F_Iu40', BK / 'o3/w14c_Iu40_pos'
POS_OTHERS = {'E u40': BK / 'o3/w14c_Eu40_pos', 'B u20': BK / 'o3/w14c_Bu20_pos', 'R6 u20': BK / 'o3/w14p_R6u20_pos'}
REG, TPS = 3600, 20
TANKS = {'giant', 'electro_giant', 'golem', 'goblin_giant', 'lava_hound', 'royal_giant', 'elixir_golem', 'rune_giant',
         'giant_skeleton', 'pekka', 'royal_hogs', 'battle_ram', 'three_musketeers', 'boss_bandit'}
fmt, wil = AN.fmt, AN.wilson


def pct(k, n):
    return f'{100 * k / n:5.1f}' if n else '  n/a'


def h(t):
    print(f'\n## {t}', flush=True)


def nc(k1, n1, k2, n2):
    d, lo, hi = T.newcombe(k1, n1, k2, n2)
    return f'{100 * d:+5.1f} [{100 * lo:+5.1f}, {100 * hi:+5.1f}]'


# ------------------------------------------------------------------------------------------------------------------ data
_C = {}


def live_rows():
    if 'lr' not in _C:
        _C['lr'] = T.ranked_rows()
    return _C['lr']


def sim_raw(root=SIM_ROOT):
    k = ('raw', str(root))
    if k not in _C:
        (name, raw), = T.load_sim(root).items()
        _C[k] = raw
    return _C[k]


def sim_rows(root=SIM_ROOT):
    k = ('rows', str(root))
    if k not in _C:
        _C[k] = [T.sim_row(j, 'sim') for j in sim_raw(root)]
    return _C[k]


def live_matches():
    """invlib live match dicts for the 233 Ranked rows (frames, own / opp plays with positions), keyed by log name."""
    if 'lm' not in _C:
        import invlib as I
        keep, _, _ = PK.A.load()
        rk = {n: v for n, v in keep.items() if v['sample'] == 'ranked'}
        sub = HERE / '_index_ranked.json'
        json.dump({n: dict(mark=v['mark'], result=v['result'], tro=v['tro']) for n, v in rk.items()}, open(sub, 'w'))
        try:
            _C['lm'] = {m['key']: m for m in I.live_matches({'CLX'}, index=sub)}
        finally:
            sub.unlink()
    return _C['lm']


# --------------------------------------------------------------------------------------------- (iv) definitions + noise
def sec_defs():
    h('D1 (iv) live OT label vs the SIM rule: a match whose crowns were UNEQUAL at 3:00 ended in regulation')
    lr = live_rows()
    bad = [r for r in lr if r['ot'] and tuple(r['reg_cr'])[0] != tuple(r['reg_cr'])[1]]
    print(f'live rows labelled OT (end > 3610) with unequal crowns at 3:00: {len(bad)} of {sum(r["ot"] for r in lr)} '
          f'(end_s {[r["end_s"] for r in bad]}; results {[r["win"] for r in bad]}); the SIM ends such a match at tick 3600')
    sr = sim_rows()
    se = Counter()
    for j in sim_raw():
        e = j['end_tick']
        se['reg_end<3600'] += e < REG
        se['==3600'] += e == REG
        se['3601-3610'] += REG < e <= REG + 10
        se['>3610'] += e > REG + 10
    print('SIM end_tick classes:', dict(se), '| SIM outcomes', dict(Counter(j['outcome'] for j in sim_raw())))
    fixed = [dict(r, ot=r['ot'] and tuple(r['reg_cr'])[0] == tuple(r['reg_cr'])[1]) for r in lr]
    print('cells with the live OT label made SIM-consistent (ot := crowns level at 3:00 and end > 3610):')
    for cell in ('ot_share', 'win_given_OT', 'win_OT_pre_drain', 'reg_loss'):
        sel, hit = next((s, f) for c, s, f in T.CELLS if c == cell)
        a, b, c = sel(sr), sel(lr), sel(fixed)
        k1, n1, k2, n2, k3, n3 = sum(map(hit, a)), len(a), sum(map(hit, b)), len(b), sum(map(hit, c)), len(c)
        print(f'  {cell:18s} SIM {pct(k1, n1)} | live as scored {pct(k2, n2)} (n {n2}) -> SIM-consistent {pct(k3, n3)} (n {n3}); '
              f'z {T.z2(k1, n1, k2, n2):+.2f} -> {T.z2(k1, n1, k3, n3):+.2f}')

    h('D2 (iv) live sampling noise: Ranked n, Wilson CI, and how far the SIM point sits outside it')
    for cell in T.GATE:
        sel, hit = next((s, f) for c, s, f in T.CELLS if c == cell)
        a, b = sel(sr), sel(lr)
        k1, n1, k2, n2 = sum(map(hit, a)), len(a), sum(map(hit, b)), len(b)
        p, lo, hi = wil(k2, n2)
        q = k1 / n1
        out = 'inside' if lo <= q <= hi else f'outside by {100 * (q - hi if q > hi else lo - q):.1f} pp'
        tol = T.TOL.get(cell)
        need = f'; pass needs SIM in [{100 * p - tol:.1f}, {100 * p + tol:.1f}] and |z| < 1.96' if tol else ''
        print(f'  {cell:20s} SIM {100 * q:5.1f} (n {n1:4d}) | Ranked {fmt(k2, n2)} -> SIM {out}{need}')

    h('D3 (iv) the live target is not stationary: Ranked cells by time block (rank climb, W13 1)')
    blocks = (('10-20 13:28-17:59', lambda r: r['key'] < 'live_play_20261020_180000'),
              ('10-20 18:00-21:59', lambda r: 'live_play_20261020_180000' <= r['key'] < 'live_play_20261020_220000'),
              ('10-20 22:00-10-21', lambda r: r['key'] >= 'live_play_20261020_220000'))
    for lab, f in blocks:
        y = [r for r in lr if f(r)]
        cells = []
        for cell in ('win', 'win_vs_BEAT', 'win_given_OT', 'win_OT_pre_drain', 'both_took_one', 'reg_loss'):
            sel, hit = next((s, g) for c, s, g in T.CELLS if c == cell)
            a = sel(y)
            cells.append(f'{cell} {pct(sum(map(hit, a)), len(a))} (n {len(a)})')
        print(f'  {lab:18s} n {len(y):3d}: ' + ' | '.join(cells))


# --------------------------------------------------------------------------------------------------- phase decomposition
def split(rows):
    n = len(rows)
    c = Counter()
    for r in rows:
        c['reg_W'] += r['win'] == 1 and not r['ot']
        c['reg_L'] += r['win'] == 0 and not r['ot']
        c['ot_W'] += r['win'] == 1 and r['ot']
        c['ot_L'] += r['win'] == 0 and r['ot']
        c['draw'] += r['win'] == .5
    return n, c


def sec_phase():
    h('P1 where the CLX win comes from: regulation vs overtime, share of ALL matches (SIM I u40 2,880 vs Ranked 233)')
    for lab, f in (('all', lambda r: True), ('vs BEAT', lambda r: r['wincon_rev'] in T.BEAT),
                   ('vs rest', lambda r: r['wincon_rev'] not in T.BEAT)):
        a, b = [r for r in sim_rows() if f(r)], [r for r in live_rows() if f(r)]
        (na, ca), (nb, cb) = split(a), split(b)
        print(f'  {lab:8s} SIM n {na:4d}: ' + ' '.join(f'{k} {pct(ca[k], na)}' for k in ('reg_W', 'reg_L', 'ot_W', 'ot_L')) +
              f' | Ranked n {nb:3d}: ' + ' '.join(f'{k} {pct(cb[k], nb)}' for k in ('reg_W', 'reg_L', 'ot_W', 'ot_L')) +
              ' | SIM - Ranked: ' + ' '.join(f'{k} {nc(ca[k], na, cb[k], nb)}' for k in ('reg_L', 'ot_L')))
    h('P2 regulation losses by the phase of the decisive fall (share of all matches)')
    for nm, rows in (('SIM', sim_rows()), ('Ranked', live_rows())):
        c = Counter(r['path'] for r in rows if r['win'] == 0 and not r['ot'])
        print(f'  {nm:6s} ' + ' '.join(f'{k} {pct(v, len(rows))}' for k, v in sorted(c.items())))
    h('P3 every crown path, share of the BEAT / rest matches (SIM vs Ranked)')
    for lab, f in (('vs BEAT', lambda r: r['wincon_rev'] in T.BEAT), ('vs rest', lambda r: r['wincon_rev'] not in T.BEAT)):
        for nm, rows in (('SIM', sim_rows()), ('Ranked', live_rows())):
            y = [r for r in rows if f(r)]
            c = Counter(r['path'] for r in y)
            print(f'  {lab:8s} {nm:6s} n {len(y):4d}: ' + ' '.join(f'{k} {pct(v, len(y))}' for k, v in sorted(c.items())))
    h('P4 0-0 overtimes vs BEAT: the 3:00 state (Ranked: all 0-0 OTs; SIM: the pos rows of block 741200)')
    lr = [r for r in live_rows() if r['ot'] and tuple(r['reg_cr']) == (0, 0) and r['wincon_rev'] in T.BEAT]
    sr = []
    for j in sim_raw(POS_ROOT):
        s = sim_state300(j)
        r = T.sim_row(j, 'p')
        if s and j['end_tick'] > REG + 10 and s['cr'] == (0, 0) and r['wincon_rev'] in T.BEAT:
            sr.append((state_class(s['own_min'], s['opp_min']), j['outcome'] == 'win'))
    for cls in ('behind', 'level', 'ahead'):
        a = [r for r in lr if state_class(r['reg_own_min'], r['reg_opp_min']) == cls]
        b = [w for c_, w in sr if c_ == cls]
        print(f'  {cls:6s} Ranked share {pct(len(a), len(lr))} (n {len(lr)}) win {fmt(sum(r["win"] == 1 for r in a), len(a))} | '
              f'SIM share {pct(len(b), len(sr))} (n {len(sr)}) win {fmt(sum(b), len(b))}')


# ----------------------------------------------------------------------------------------------- 3:00 state (positions)
def sim_state300(j):
    """Lowest standing princess HP (fraction) per side at clock 3590 from o3_trace, plus crowns then; None without a trace."""
    tr = j.get('o3_trace')
    if not tr or not tr.get('snaps'):
        return None
    me = int(j['learner_side'])
    towers = {int(u): v for u, v in tr['towers'].items()}
    snap = None
    for t, tw, xb in tr['snaps']:
        if t > REG - 10:
            break
        snap = tw
    if snap is None:
        return None
    hp = {u: 0 for u in towers}
    hp.update({int(u): x for u, x in snap})
    pm = next(v[2] for v in towers.values() if v[1] in (1, 2))
    own = [hp[u] / pm for u, v in towers.items() if v[0] == me and v[1] in (1, 2) and hp[u] > 0]
    opp = [hp[u] / pm for u, v in towers.items() if v[0] != me and v[1] in (1, 2) and hp[u] > 0]
    oc = sum(1 for u, v in towers.items() if v[0] != me and v[1] in (1, 2) and hp[u] <= 0)
    tc = sum(1 for u, v in towers.items() if v[0] == me and v[1] in (1, 2) and hp[u] <= 0)
    return dict(own_min=min(own) if own else 0.0, opp_min=min(opp) if opp else 0.0, cr=(oc, tc))


def state_class(own_min, opp_min):
    d = own_min - opp_min        # > 0: our weakest princess is healthier = we are AHEAD in the tiebreak / the OT race
    return 'behind' if d < -.1 else 'ahead' if d > .1 else 'level'


def sec_state():
    h('S1 the 0-0 overtime is decided by the 3:00 state (W13 T3b): SIM pos rows (block 741200) vs Ranked')
    lr = [r for r in live_rows() if r['ot'] and tuple(r['reg_cr']) == (0, 0)]
    print(f'  Ranked 0-0 OTs n {len(lr)}')
    out = {}
    for cls in ('behind', 'level', 'ahead'):
        y = [r for r in lr if state_class(r['reg_own_min'], r['reg_opp_min']) == cls]
        out[cls] = y
        print(f'    {cls:6s} share {pct(len(y), len(lr))}  CLX win {fmt(sum(r["win"] == 1 for r in y), len(y))}')
    for nm, root in (('I u40', POS_ROOT), *POS_OTHERS.items()):
        try:
            raw = sim_raw(root)
        except (ValueError, FileNotFoundError):
            continue
        rows = []
        for j in raw:
            s = sim_state300(j)
            if s and j['end_tick'] > REG + 10 and s['cr'] == (0, 0):
                rows.append((state_class(s['own_min'], s['opp_min']), j['outcome'] == 'win'))
        print(f'  SIM {nm} 0-0 OTs n {len(rows)} (of {len(raw)} games)')
        for cls in ('behind', 'level', 'ahead'):
            y = [w for c, w in rows if c == cls]
            lv = out[cls]
            print(f'    {cls:6s} share {pct(len(y), len(rows))} (Ranked {pct(len(lv), len(lr))})  CLX win {fmt(sum(y), len(y))}'
                  f'  vs Ranked {pct(sum(r["win"] == 1 for r in lv), len(lv))}')
        if nm == 'I u40':
            # counterfactual: SIM's per-state win rates at Ranked's state shares, and Ranked's win rates at the SIM's shares
            sh_s = {c: sum(1 for x, _ in rows if x == c) / len(rows) for c in ('behind', 'level', 'ahead')}
            wr_s = {c: (sum(w for x, w in rows if x == c) / max(1, sum(1 for x, _ in rows if x == c))) for c in sh_s}
            sh_l = {c: len(out[c]) / len(lr) for c in sh_s}
            wr_l = {c: sum(r['win'] == 1 for r in out[c]) / max(1, len(out[c])) for c in sh_s}
            f = lambda sh, wr: 100 * sum(sh[c] * wr[c] for c in sh)  # noqa: E731
            print(f'    0-0 OT win: SIM {f(sh_s, wr_s):.1f} | Ranked {f(sh_l, wr_l):.1f} | SIM win rates at Ranked state shares '
                  f'{f(sh_l, wr_s):.1f} | Ranked win rates at SIM state shares {f(sh_s, wr_l):.1f}')
    h('S2 regulation chip race: princess HP at 3:00 (sum of standing princesses, fractions), 0-0 at 3:00, all such matches')
    lr0 = [r for r in live_rows() if tuple(r['reg_cr']) == (0, 0)]
    print(f'  Ranked n {len(lr0)}: own sum mean {st.mean(r["reg_own_sum"] for r in lr0):.3f} opp sum mean '
          f'{st.mean(r["reg_opp_sum"] for r in lr0):.3f}; own min {st.mean(r["reg_own_min"] for r in lr0):.3f} '
          f'opp min {st.mean(r["reg_opp_min"] for r in lr0):.3f}')
    for nm, root in (('I u40', POS_ROOT), *POS_OTHERS.items()):
        try:
            raw = sim_raw(root)
        except (ValueError, FileNotFoundError):
            continue
        ss = [s for s in map(sim_state300, raw) if s and s['cr'] == (0, 0)]
        if ss:
            print(f'  SIM {nm:6s} n {len(ss)}: own min {st.mean(s["own_min"] for s in ss):.3f} opp min '
                  f'{st.mean(s["opp_min"] for s in ss):.3f}')


# ------------------------------------------------------------------------------------------------------- both took one
def first_and_after(r):
    """(who fell first, did the other side take one later) from the row's crowns."""
    if r['first'] is None:
        return None, False
    return r['first'], r['our_cr'] >= 1 and r['their_cr'] >= 1


def sec_both():
    h('B1 both took one = P(first fall) x P(the trailing side answers): SIM vs Ranked')
    for nm, rows in (('SIM', sim_rows()), ('Ranked', live_rows())):
        n = len(rows)
        own_first = [r for r in rows if r['first'] == 'own']     # CLX lost the first princess
        opp_first = [r for r in rows if r['first'] == 'opp']     # CLX took the first princess
        cb = sum(r['our_cr'] >= 1 for r in own_first)
        ob = sum(r['their_cr'] >= 1 for r in opp_first)
        print(f'  {nm:6s} n {n:4d} | CLX lost first {pct(len(own_first), n)} -> CLX takes one back {fmt(cb, len(own_first))} | '
              f'CLX took first {pct(len(opp_first), n)} -> opponent takes one back {fmt(ob, len(opp_first))}')
    for nm, rows in (('SIM', sim_rows()), ('Ranked', live_rows())):
        own_first = [r for r in rows if r['first'] == 'own']
        y = [r for r in own_first if r['our_cr'] >= 1]
        print(f'  {nm:6s} CLX answered a lost first princess: of those, {pct(sum(r["win"] == 1 for r in y), len(y))} won; '
              f'answer before 3:00 {pct(sum(not r["ot"] or (r.get("reg_cr") or (9, 9))[0] >= 1 for r in y), len(y))} (live only exact)')


# --------------------------------------------------------------------------------------------------- win conditions
def sec_wincon():
    h('W1 CLX win by the opponent win condition (revealed cards), SIM I u40 vs Ranked; BEAT first')
    s, l = defaultdict(list), defaultdict(list)
    for r in sim_rows():
        s[r['wincon_rev']].append(r['win'] == 1)
    for r in live_rows():
        l[r['wincon_rev']].append(r['win'] == 1)
    keys = sorted(set(s) | set(l), key=lambda k: (k not in T.BEAT, -len(l.get(k, []))))
    tot = defaultdict(lambda: [0, 0, 0, 0])
    for k in keys:
        a, b = s.get(k, []), l.get(k, [])
        if len(b) < 3 and len(a) < 30:
            continue
        g = 'BEAT' if k in T.BEAT else 'rest'
        print(f'  {g:4s} {k:16s} SIM {pct(sum(a), len(a))} (n {len(a):4d}) | Ranked {fmt(sum(b), len(b))}')
    # how much of the BEAT gap is the SIM's within-BEAT mix (re-weight SIM per-wincon win rates to Ranked's BEAT mix)
    lb = [r for r in live_rows() if r['wincon_rev'] in T.BEAT]
    w = Counter(r['wincon_rev'] for r in lb)
    num = sum(w[k] * (sum(s[k]) / len(s[k])) for k in w if s.get(k))
    den = sum(w[k] for k in w if s.get(k))
    print(f'  SIM BEAT win re-weighted to the Ranked BEAT win-condition mix: {100 * num / den:.1f} (raw {pct(sum(sum(s[k]) for k in T.BEAT if k in s), sum(len(s[k]) for k in T.BEAT if k in s))}; '
          f'Ranked {pct(sum(r["win"] == 1 for r in lb), len(lb))})')


def sec_comeback():
    h('B2 (iv) comebacks by the time of the first princess fall (more clock left = more chances to answer)')
    bins = ((0, 90), (90, 150), (150, 180), (180, 999))
    for nm, rows in (('SIM', sim_rows()), ('Ranked', live_rows())):
        fs = [r for r in rows if r['first'] is not None]
        print(f'  {nm:6s} first fall time: median {st.median(r["first_s"] for r in fs):.0f} s; share by bin ' +
              ' '.join(f'{a}-{b}s {pct(sum(a <= r["first_s"] < b for r in fs), len(fs))}' for a, b in bins))
        cells = []
        for a, b in bins:
            y = [r for r in fs if a <= r['first_s'] < b]
            cells.append(f'{a}-{b}s {fmt(sum(r["our_cr"] >= 1 and r["their_cr"] >= 1 for r in y), len(y))}')
        print(f'  {nm:6s} P(the trailing side answers) by bin: ' + ' | '.join(cells))
    # SIM comeback rate re-weighted to the Ranked first-fall-time distribution
    s = [r for r in sim_rows() if r['first'] is not None]
    l = [r for r in live_rows() if r['first'] is not None]
    rw = 0.0
    for a, b in bins:
        ys = [r for r in s if a <= r['first_s'] < b]
        wl = sum(a <= r['first_s'] < b for r in l) / len(l)
        rw += wl * (sum(r['our_cr'] >= 1 and r['their_cr'] >= 1 for r in ys) / max(1, len(ys)))
    print(f'  SIM P(answer | a first fall) at the Ranked fall-time mix: {100 * rw:.1f} (SIM raw '
          f'{pct(sum(r["our_cr"] >= 1 and r["their_cr"] >= 1 for r in s), len(s))}, Ranked '
          f'{pct(sum(r["our_cr"] >= 1 and r["their_cr"] >= 1 for r in l), len(l))})')


WINS = ('reg_0-120', 'reg_120-180', 'ot_0-60', 'ot_60-120')


def inten(rows, key):
    out = {}
    for w in WINS:
        mins = sum(r['intensity'][w]['min'] for r in rows if r.get('intensity') and w in r['intensity'])
        v = sum(r['intensity'][w][key] for r in rows if r.get('intensity') and w in r['intensity'])
        out[w] = v / mins if mins else float('nan')
    return out


def sec_intensity():
    h('I1 per-minute intensity by window: opponent TROOP elixir (visible on both sides) and CLX plays, SIM vs Ranked')
    for lab, f in (('all', lambda r: True), ('vs BEAT', lambda r: r['wincon_rev'] in T.BEAT),
                   ('vs rest', lambda r: r['wincon_rev'] not in T.BEAT)):
        for key, nmk in (('opp_troop_el', 'opp troop elixir/min'), ('opp_troops', 'opp troop plays/min'), ('own', 'CLX plays/min')):
            a, b = inten([r for r in sim_rows() if f(r)], key), inten([r for r in live_rows() if f(r)], key)
            print(f'  {lab:8s} {nmk:22s} ' + ' | '.join(f'{w} SIM {a[w]:5.2f} Ranked {b[w]:5.2f}' for w in WINS))


# ------------------------------------------------------------------------------------------------------- tank pushes
def tank_pushes(opp, own, end):
    """opp / own: [(tick, card)] landing ticks, one clock.  A push = the first tank play after >= 15 s without one.
    Per push: phase, support elixir the opponent adds in the next 10 s, whether CLX had placed an X-Bow in the 10 s before
    (a counter-push), CLX's first play landing after the tank (s) and CLX elixir spent in the next 10 s."""
    out, last = [], -10 ** 9
    for t, c in opp:
        if c not in TANKS or t - last < 300:
            if c in TANKS:
                last = t
            continue
        last = t
        sup = sum(H.cost(k) or 0 for tt, k in opp if t < tt <= t + 200 and H.kind(k) != 'spell')   # troops: visible live too
        xb = any(t - 200 <= tt < t and k == 'x_bow' for tt, k in own)
        nxt = next((tt for tt, k in own if tt > t), None)
        out.append(dict(t=t, ph=AN.phase_of(t), card=c, sup=sup, after_xbow=xb, resp_s=None if nxt is None else (nxt - t) / TPS,
                        own10=sum(H.cost(k) or 0 for tt, k in own if t < tt <= t + 200), end=end))
    return out


def sim_tank():
    out = []
    for j in sim_raw():
        pl = j.get('o3_plays') or {}
        opp = [(int(t), H.norm(c)) for t, c in pl.get('opp', [])]
        own = [(int(t), H.norm(c)) for t, c in pl.get('learner', [])]
        for p in tank_pushes(opp, own, j['end_tick']):
            p['win'] = j['outcome'] == 'win'
            out.append(p)
    return out


def live_tank():
    out = []
    for key, m in live_matches().items():
        opp = sorted((p['tick'], p['card']) for p in m['opp'])
        own = sorted((q['tick'], q['card']) for q in m['own'])
        for p in tank_pushes(opp, own, m['end']):
            p['win'] = m['win'] == 1
            out.append(p)
    return out


def sec_tank():
    h('K1 tank pushes (first tank play after >= 15 s without one): composition, timing, CLX response')
    for nm, ps, n in (('SIM', sim_tank(), len(sim_raw())), ('Ranked', live_tank(), len(live_matches()))):
        print(f'  {nm:6s} pushes {len(ps)} ({len(ps) / n:.2f} per match, all decks)')
        for ph in ('1x', '2x', 'OT2x', 'OT3x'):
            y = [p for p in ps if p['ph'] == ph]
            if not y:
                continue
            rs = [p['resp_s'] for p in y if p['resp_s'] is not None]
            print(f'    {ph:4s} n {len(y):4d}: support elixir in 10 s mean {st.mean(p["sup"] for p in y):4.2f} | after our X-Bow '
                  f'{pct(sum(p["after_xbow"] for p in y), len(y))}% | CLX first play after the tank: median {st.median(rs):4.1f} s, '
                  f'<= 3 s {pct(sum(r <= 3 for r in rs), len(rs))}% | CLX elixir in 10 s {st.mean(p["own10"] for p in y):4.2f} | '
                  f'match won {pct(sum(p["win"] for p in y), len(y))}%')
        c = Counter(p['card'] for p in ps)
        print('    tank cards: ' + ' '.join(f'{k} {v}' for k, v in c.most_common(8)))


# ------------------------------------------------------------------------------------------- X-Bows: SIM pos-row extract
def _tf(j):
    pos = j['o3_pos']
    me = int(j['learner_side'])
    mine = [p for p in pos if p[1] == me and PK.troop(p[2])]
    flip = sum(p[4] for p in mine) / max(1, len(mine)) < 16000
    return (lambda x, y: ((18000 - x) / 1000, (32000 - y) / 1000)) if flip else (lambda x, y: (x / 1000, y / 1000))


def slot_lane():
    """{(learner side, enemy princess slot): 'L' | 'R' in our frame}, by majority over every bridge X-Bow of the pos rows that
    targeted an enemy princess (the X-Bow's own lane = the targeted princess's lane).  Prints the vote once."""
    if 'lanes' in _C:
        return _C['lanes']
    import invlib as I
    vote = defaultdict(Counter)
    for root in (POS_ROOT, *POS_OTHERS.values()):
        try:
            raw = sim_raw(root)
        except (ValueError, FileNotFoundError):
            continue
        for j in raw:
            if not j.get('o3_pos') or not (j.get('o3_trace') or {}).get('snaps'):
                continue
            me, tf = int(j['learner_side']), _tf(j)
            towers = {int(u): v for u, v in j['o3_trace']['towers'].items()}
            first = {}
            for t, tw, xb in j['o3_trace']['snaps']:
                for uid, team, _, tgt in xb:
                    if team == me and tgt in towers and towers[tgt][0] != me and towers[tgt][1] in (1, 2):
                        first.setdefault(uid, (t, towers[tgt][1]))
            deps = [(p[0], *tf(p[3], p[4])) for p in j['o3_pos'] if p[1] == me and p[2] == 'Xbow']
            for uid, (t, slot) in first.items():
                d = max((d for d in deps if d[0] <= t), key=lambda d: d[0], default=None)
                if d and I.xtype(d[2]) == 'bridge':
                    vote[(me, slot)]['L' if d[1] < 9 else 'R'] += 1
    _C['lanes'] = {k: v.most_common(1)[0][0] for k, v in vote.items()}
    print('  slot -> lane vote (learner side, slot): ' + ' '.join(f'{k}:{dict(v)}' for k, v in sorted(vote.items())))
    return _C['lanes']


def sim_xbows(j):
    """Per own X-Bow of a pos row: our-frame (x, y), type, lane, crown state at birth, lock (targeted-tower HP lost >= 5% of a
    princess, pocket.py's SIM rule), REACH lock (live rule: HP lost by enemy towers within 13.5 tiles, any source), life (s), and
    the opponent plays landing within AT_XBOW tiles of it during its life (cards, elixir, first answer delay)."""
    import invlib as I
    pos, tr = j.get('o3_pos'), j.get('o3_trace')
    if not pos or not tr or not tr.get('snaps'):
        return []
    me, tf = int(j['learner_side']), _tf(j)
    towers = {int(u): v for u, v in tr['towers'].items()}
    pm = next(v[2] for v in towers.values() if v[1] in (1, 2))
    # enemy tower centres in OUR frame (own king y 29): king (9, 3); princess slot -> lane from slot_lane() (measured from
    # which slot our bridge X-Bows target, per learner side)
    lanes = slot_lane()
    tpos = {u: (9.0, 3.0) if slot == 0 else ((3.5 if lanes[(me, slot)] == 'L' else 14.5), 6.5)
            for u, (team, slot, mx) in towers.items() if team != me}
    snaps = []
    for t, tw, xb in tr['snaps']:
        hp = {u: 0 for u in towers}
        hp.update({int(u): x for u, x in tw})
        snaps.append((t, hp, xb))
    opp_p = [u for u, v in towers.items() if v[0] != me and v[1] in (1, 2)]
    own_p = [u for u, v in towers.items() if v[0] == me and v[1] in (1, 2)]
    cr = lambda hp: (sum(hp[u] <= 0 for u in opp_p), sum(hp[u] <= 0 for u in own_p))  # noqa: E731
    life = {}
    for i, (t, hp, xb) in enumerate(snaps):
        for uid, team, xhp, tgt in xb:
            if team == me:
                a = life.setdefault(uid, dict(t0=t, t1=t, tg=Counter(), dmg=0.0))
                a['t1'] = t
                if tgt in towers and towers[tgt][0] != me:
                    a['tg'][tgt] += 1
                    if i + 1 < len(snaps):              # pocket.py's SIM rule: HP the targeted tower loses while targeted
                        a['dmg'] += max(0, hp.get(tgt, 0) - snaps[i + 1][1].get(tgt, 0)) / pm
    deps = [p for p in pos if p[1] == me and p[2] == 'Xbow']
    opp_pl = [(p[0], H.norm(p[2]), *tf(p[3], p[4])) for p in pos if p[1] != me]
    out = []
    used = set()
    for t, _, _, x, y in deps:
        uid = min((u for u in life if u not in used and life[u]['t0'] >= t - 2), key=lambda u: life[u]['t0'] - t, default=None)
        if uid is None or life[uid]['t0'] - t > 60:
            continue
        used.add(uid)
        a = life[uid]
        X, Y = tf(x, y)
        hp0 = next(hp for tt, hp, _ in snaps if tt >= a['t0'])
        hp1 = next((hp for tt, hp, _ in snaps if tt >= a['t1'] + 1), snaps[-1][1])
        tgt = a['tg'].most_common(1)[0][0] if a['tg'] else None
        lock_t = a['dmg'] >= I.LOCK_MIN
        reach = [u for u, (tx, ty) in tpos.items() if math.hypot(X - tx, Y - ty) <= I.REACH]
        dmg_r = sum(max(0, hp0[u] - hp1[u]) for u in reach) / pm
        ans = [(tt, k) for tt, k, px, py in opp_pl if a['t0'] - 20 <= tt <= a['t1'] + 10 and math.hypot(px - X, py - Y) <= I.AT_XBOW]
        alive_lane = None
        st_ = PK.state(*cr(hp0))
        if st_ in ('1-0', '1-1'):
            lane_u = [u for u in opp_p if (tpos[u][0] < 9) == (X < 9)]
            alive_lane = bool(lane_u) and hp0[lane_u[0]] > 0
        out.append(dict(state=st_, type=I.xtype(Y), x=X, y=Y, lock=lock_t, lock_reach=dmg_r >= I.LOCK_MIN, dmg_reach=dmg_r,
                        tgt_king=tgt in towers and towers[tgt][1] == 0, life_s=(a['t1'] - a['t0']) / TPS,
                        ans=[k for _, k in ans], ans_el=sum(H.cost(k) or 0 for _, k in ans),
                        ans_s=min(((tt - a['t0']) / TPS for tt, _ in ans), default=None), alive_lane=alive_lane,
                        win=j['outcome'] == 'win', key=f"{j['seed']}:{j['tag']}", beat=T.sim_row(j, 'p')['wincon_rev'] in T.BEAT,
                        life_plays=[(k, (px < 9) == (X < 9), (tt - a['t0']) / TPS, py) for tt, k, px, py in opp_pl
                                    if a['t0'] - 20 <= tt <= a['t1'] + 10]))
    return out


def LIVE_BEAT():
    if 'lb' not in _C:
        _C['lb'] = {r['key']: r['wincon_rev'] in T.BEAT for r in live_rows()}
    return _C['lb']


def live_xbows():
    import invlib as I
    out = []
    for key, m in live_matches().items():
        for r in I.xbow_rows(m):
            if 'lock' not in r:
                continue
            st_ = PK.state(r['our_cr'], r['their_cr'])
            alive_lane = None
            if st_ in ('1-0', '1-1'):
                T_ = I._tower_at(m, r['tick'])
                alive_lane = T_.get(('opp', 'L' if r['x'] < 9 else 'R'), 0) > 0
            fs = [f for f in m['frames'] if f[0] >= r['tick']]
            ans_s = None
            ans_ts = [p['tick'] for p in m['opp'] if r['tick'] - 20 <= p['tick'] and p['x'] is not None
                      and math.hypot(p['x'] - r['x'], p['y'] - r['y']) <= I.AT_XBOW and p['tick'] <= r.get('end_tick', 10 ** 9) + 10]
            if ans_ts:
                ans_s = (min(ans_ts) - r['tick']) / TPS
            out.append(dict(state=st_, type=r['type'], x=r['x'], y=r['y'], lock=r['lock'], lock_reach=r['lock'], dmg_reach=r['dmg_reach'],
                            life_s=r['life_s'], ans=r['answer'], ans_el=r['answer_el'], ans_s=ans_s, alive_lane=alive_lane,
                            win=m['win'] == 1, key=key, beat=LIVE_BEAT()[key],
                            life_plays=[(p['card'], (p['x'] < 9) == (r['x'] < 9), (p['tick'] - (r['end_tick'] - r['life_s'] / I.TICK_S)) / TPS, p['y'])
                                        for p in m['opp'] if p['x'] is not None and
                                        r['end_tick'] - r['life_s'] / I.TICK_S - 20 <= p['tick'] <= r['end_tick'] + 10]))
    return out


def xb_table(nm, xs, states=PK.STATES):
    for s in states:
        y = [x for x in xs if x['state'] == s]
        if not y:
            continue
        ty = Counter(x['type'] for x in y)
        an = [x['ans_s'] for x in y if x['ans_s'] is not None]
        sp = sum(1 for x in y for k in x['ans'] if H.kind(k) == 'spell')
        print(f'  {nm:6s} {s}: n {len(y):4d} in {len({x["key"] for x in y}):3d} matches | type ' +
              ' '.join(f'{k} {pct(v, len(y))}' for k, v in sorted(ty.items(), key=str)) +
              f' | lock (scorer rule) {pct(sum(x["lock"] for x in y), len(y))} reach-rule {pct(sum(x["lock_reach"] for x in y), len(y))}'
              f' | life {st.mean(x["life_s"] for x in y):4.1f} s | answer elixir {st.mean(x["ans_el"] for x in y):4.2f}, answered '
              f'{pct(len(an), len(y))}, first answer median {st.median(an) if an else float("nan"):4.1f} s, spells {sp}')
        for ty_ in ('bridge', 'pocket'):
            z = [x for x in y if x['type'] == ty_]
            if z:
                print(f'           {ty_:7s} n {len(z):4d}: lock {pct(sum(x["lock"] for x in z), len(z))} reach-rule '
                      f'{pct(sum(x["lock_reach"] for x in z), len(z))} answer elixir {st.mean(x["ans_el"] for x in z):4.2f} '
                      f'life {st.mean(x["life_s"] for x in z):4.1f} s' +
                      (f' | lane princess alive {pct(sum(bool(x["alive_lane"]) for x in z), len(z))}'
                       f' (lock there {pct(sum(x["lock"] for x in z if x["alive_lane"]), sum(bool(x["alive_lane"]) for x in z))})'
                       if s in ('1-0', '1-1') else ''))


def sec_xbow():
    h('X1 our X-Bows by crown state at placement (ours-theirs): type, lock, opponent answer at the X-Bow (<= 7 tiles)')
    sx = [x for j in sim_raw(POS_ROOT) for x in sim_xbows(j)]
    lx = live_xbows()
    xb_table('Ranked', lx)
    xb_table('SIM', sx)
    k = [x for x in sx if x['state'] == '1-1']
    print(f'  SIM 1-1 X-Bows targeting the KING (counts as a lock in the SIM rule; the live reach rule counts the king only '
          f'from <= 13.5 tiles): {sum(x["tgt_king"] for x in k)} of {len(k)}; locks among them '
          f'{sum(x["lock"] and x["tgt_king"] for x in k)}')
    for nm, xs in (('Ranked', lx), ('SIM', sx)):
        y = [x for x in xs if x['state'] == '1-1']
        per = Counter(x['key'] for x in y)
        locks = Counter(x['key'] for x in y if x['lock'])
        print(f'  {nm:6s} 1-1 clustering: {len(y)} X-Bows in {len(per)} matches (max {max(per.values()) if per else 0} per '
              f'match); matches with >= 1 lock {len(locks)} of {len(per)}')
    h('X1b bridge X-Bows at 0-0 by deck class: reach-rule lock (the live rule) and troop answer elixir')
    for g, lab in ((True, 'vs BEAT'), (False, 'vs rest')):
        for nm, xs in (('Ranked', lx), ('SIM', sx)):
            y = [x for x in xs if x['state'] == '0-0' and x['type'] == 'bridge' and x['beat'] == g]
            el = st.mean(sum(H.cost(H.norm(k)) or 0 for k in x['ans'] if H.kind(H.norm(k)) != 'spell') for x in y)
            print(f'  {lab:8s} {nm:6s} n {len(y):4d} lock {fmt(sum(x["lock_reach"] for x in y), len(y))} | tower dmg per X-Bow '
                  f'{st.mean(x["dmg_reach"] for x in y):.3f} | troop answer elixir {el:4.2f} | life {st.mean(x["life_s"] for x in y):4.1f} s')
            if g:
                same = [x for x in y if any(H.norm(k) in TANKS and sl for k, sl, *_ in x['life_plays'])]
                other = [x for x in y if any(H.norm(k) in TANKS and not sl for k, sl, *_ in x['life_plays']) and x not in same]
                none = [x for x in y if x not in same and x not in other]
                print(f'           a tank played during the X-Bow life: SAME lane {pct(len(same), len(y))} (lock '
                      f'{pct(sum(x["lock_reach"] for x in same), len(same))}) | OTHER lane only {pct(len(other), len(y))} (lock '
                      f'{pct(sum(x["lock_reach"] for x in other), len(other))}) | none {pct(len(none), len(y))} (lock '
                      f'{pct(sum(x["lock_reach"] for x in none), len(none))})')
                tr = [sum(H.cost(H.norm(k)) or 0 for k, sl, *_ in x['life_plays'] if H.kind(H.norm(k)) != 'spell' and not sl) for x in y]
                print(f'           opponent troop elixir in the OTHER lane during the X-Bow life: mean {st.mean(tr):.2f}')
                tk = [(dt, yy) for x in same for k, sl, dt, yy in x['life_plays'] if H.norm(k) in TANKS and sl]
                if tk:
                    print(f'           same-lane tank vs the X-Bow landing: median {st.median(d for d, _ in tk):+.1f} s, within 3.5 s '
                          f'(before the X-Bow can lock) {pct(sum(d <= 3.5 for d, _ in tk), len(tk))}%; placed on OUR half (y > 16, '
                          f'at / past the bridge) {pct(sum(yy > 16 for _, yy in tk), len(tk))}%, at the river (15 <= y <= 17) '
                          f'{pct(sum(15 <= yy <= 17 for _, yy in tk), len(tk))}%, back (y < 10) {pct(sum(yy < 10 for _, yy in tk), len(tk))}%')
                    for lab2, f2 in (('<= 3.5 s', lambda d: d <= 3.5), ('> 3.5 s', lambda d: d > 3.5)):
                        z = [x for x in same if any(H.norm(k) in TANKS and sl and f2(dt) for k, sl, dt, _ in x['life_plays'])]
                        print(f'             X-Bows with a same-lane tank {lab2}: n {len(z)} lock {pct(sum(x["lock_reach"] for x in z), len(z))}')
    h('X2 bridge X-Bows: the opponent\'s answer at the X-Bow by card class (TROOPS only on both sides: live misses bodiless spells)')

    def cls(k):
        k = H.norm(k)
        if H.kind(k) == 'spell':
            return 'spell'
        if k in TANKS or k in ('mega_knight', 'knight', 'valkyrie', 'ice_golem', 'mini_pekka', 'prince', 'dark_prince', 'lumberjack',
                               'bandit', 'fisherman', 'giant_skeleton', 'guards', 'royal_ghost', 'golden_knight', 'monk', 'mighty_miner'):
            return 'melee/tank'
        if H.kind(k) == 'building':
            return 'building'
        return 'other troop'
    for nm, xs in (('Ranked', lx), ('SIM', sx)):
        for s in ('0-0', '0-1', '1-1'):
            y = [x for x in xs if x['state'] == s and x['type'] == 'bridge']
            fc = Counter()
            lk = Counter()
            for x in y:
                tr = [k for k in x['ans'] if H.kind(H.norm(k)) != 'spell']
                c0 = cls(tr[0]) if tr else 'no troop answer'
                fc[c0] += 1
                lk[c0] += x['lock_reach']
            el = st.mean(sum(H.cost(H.norm(k)) or 0 for k in x['ans'] if H.kind(H.norm(k)) != 'spell') for x in y) if y else float('nan')
            print(f'  {nm:6s} {s} bridge n {len(y):4d}: troop answer elixir {el:4.2f} | first troop answer class (share, reach-rule '
                  'lock): ' + ' | '.join(f'{k} {pct(v, len(y))} ({pct(lk[k], v)})' for k, v in fc.most_common()))
    _C['sx'], _C['lx'] = sx, lx


# ------------------------------------------------------------------------------------- (iii) CLX's own live execution
LOGS = L74.parent / 'L68/live_reader'
OFF = 78


def read_exec(key):
    """Own-side execution events of one live log (public / own data only): plays (taps), confirmations, unconfirmed taps, and
    our own elixir bar per frame.  Ticks -> clock (game tick - 78)."""
    import re
    rx = re.compile(rb'"tick": (\d+), "my_side": \d+, "elixir": ([\d.]+)')
    plays, conf, unc, el = [], [], [], []
    for raw in open(LOGS / key, 'rb'):
        if raw.startswith(b'{"event": "frame"'):
            m = rx.search(raw, 0, 200)
            if m:
                el.append((int(m[1]) - OFF, float(m[2])))
        elif raw.startswith((b'{"event": "play"', b'{"event": "confirmed"', b'{"event": "unconfirmed"')):
            j = json.loads(raw)
            j['tick'] -= OFF
            {'play': plays, 'confirmed': conf, 'unconfirmed': unc}[j['event']].append(j)
    return plays, conf, unc, el


def cost_of(name):
    return H.cost(H.norm(name)) or 1


def sec_exec():
    import bisect
    h('E1 (iii) CLX live execution on the 233 Ranked logs: taps, confirmations, lost taps, tap->confirm delay, X-Bow placement')
    n_m, mins = 0, Counter()
    c = Counter()
    lat, lost_ph, taps_ph = [], Counter(), Counter()
    lat_ph = defaultdict(list)
    aff_ph = Counter()
    drop = []                       # (tap -> the game's elixir drop in ticks, spell?) of confirmed plays
    xb_err, xb_rows = [], Counter()
    retry = []
    for key in sorted(r['key'] for r in live_rows()):
        try:
            plays, conf, unc, el = read_exec(key)
        except FileNotFoundError:
            continue
        n_m += 1
        end = el[-1][0] if el else 0
        for w, (a, b) in AN.INT_WIN.items():
            mins[w] += max(0, min(b, end) - a) / 1200
        ets = [t for t, _ in el]
        c['play'] += len(plays)
        c['confirmed'] += len(conf)
        c['unconfirmed'] += len(unc)
        for p in plays:
            ph = next(w for w, (a, b) in AN.INT_WIN.items() if p['tick'] < b) if p['tick'] < 5985 else 'ot_60-120'
            taps_ph[ph] += 1
            q = next((q for q in conf if q['name'] == p['name'] and 0 <= q['tick'] - p['tick'] <= 80), None)
            if q is not None:
                i, k = bisect.bisect_left(ets, p['tick']), bisect.bisect_right(ets, p['tick'] + 80)
                dt = next((el[x][0] for x in range(max(1, i), k) if el[x - 1][1] - el[x][1] >= .75 * cost_of(p['name'])), None)
                if dt is not None:
                    drop.append((dt - p['tick'], H.kind(H.norm(p['name'])) == 'spell'))
                lat.append(q['tick'] - p['tick'])
                lat_ph[ph].append(q['tick'] - p['tick'])
        for u in unc:
            # the tap behind this unconfirmed event = the latest play of that card at or before it
            p = max((p for p in plays if p['name'] == u['name'] and p['tick'] <= u['tick']), key=lambda p: p['tick'], default=None)
            t0 = p['tick'] if p else u['tick'] - 34
            i, k = bisect.bisect_left(ets, t0), bisect.bisect_right(ets, t0 + 50)
            drops = [el[x - 1][1] - el[x][1] for x in range(max(1, i), k)]
            taken = any(d >= .75 * cost_of(u['name']) for d in drops)
            c['unc_taken' if taken else 'unc_lost'] += 1
            if not taken:
                aff = (p or u).get('elixir', 0) >= cost_of(u['name']) - 1e-6
                c['lost_afford' if aff else 'lost_short'] += 1
                ph = next(w for w, (a, b) in AN.INT_WIN.items() if t0 < b) if t0 < 5985 else 'ot_60-120'
                lost_ph[ph] += 1
                if aff:
                    aff_ph[ph] += 1
                nxt = next((q['tick'] for q in conf if q['name'] == u['name'] and q['tick'] > u['tick']), None)
                retry.append(None if nxt is None else (nxt - t0) / TPS)
        for q in conf:
            if H.norm(q['name']) == 'x_bow':
                xb_err.append(q.get('err_tiles') or 0.0)
                iy = q['intended'][1] * 32
                xb_rows[round(iy * 2) / 2] += 1
    print(f'  matches {n_m}; taps {c["play"]} ({c["play"] / n_m:.1f}/match), confirmed {c["confirmed"]}, unconfirmed '
          f'{c["unconfirmed"]} ({c["unconfirmed"] / n_m:.2f}/match): elixir dropped within 2.5 s (the game took it) '
          f'{c["unc_taken"]}, no drop = LOST tap {c["unc_lost"]} ({c["unc_lost"] / n_m:.2f}/match, '
          f'{pct(c["unc_lost"], c["play"])}% of taps)')
    print('  lost taps per minute by window: ' + ' | '.join(f'{w} {lost_ph[w] / max(1e-9, mins[w]):.2f} '
                                                           f'(taps {taps_ph[w] / max(1e-9, mins[w]):.1f}/min)' for w in AN.INT_WIN))
    print(f'  lost taps with elixir >= cost at the tap (the game should have taken it: an EXECUTION loss) {c["lost_afford"]}; '
          f'short of elixir at the tap (the SIM refuses those too) {c["lost_short"]}')
    rph, smin = Counter(), Counter()
    for j in sim_raw():
        e = j['end_tick']
        for w, (a, b) in AN.INT_WIN.items():
            smin[w] += max(0, min(b, e) - a) / 1200
        for p in j['own_plays']:
            if not p[3]:
                rph[next((w for w, (a, b) in AN.INT_WIN.items() if p[1] < b), 'ot_60-120')] += 1
    rates = {w: aff_ph[w] / max(1, taps_ph[w]) for w in AN.INT_WIN}
    spec = ','.join(f'{n}:{rates[w]:.4f}' for n, w in zip(('1x', '2x', 'ot2x', 'ot3x'), AN.INT_WIN))
    print(f'  EXECUTION lost-tap rate per tap (elixir >= cost, no drop) by window -> the SIM --tap-loss spec: {spec}')
    print('  SIM refused own plays per minute by window: ' + ' | '.join(f'{w} {rph[w] / max(1e-9, smin[w]):.2f}' for w in AN.INT_WIN))
    rt = [x for x in retry if x is not None]
    print(f'  a lost tap\'s card was confirmed later in {len(rt)} of {len(retry)} cases, median {st.median(rt) if rt else float("nan"):.1f} s '
          f'after the first tap (p75 {sorted(rt)[3 * len(rt) // 4] if rt else float("nan"):.1f} s)')
    if lat:
        ls = sorted(lat)
        print(f'  tap -> confirmed (game ticks): median {st.median(ls)}, p10 {ls[len(ls) // 10]}, p90 {ls[9 * len(ls) // 10]} '
              f'(n {len(ls)}); the SIM lands every play 26 ticks after its decision (action_delay_ticks)')
        hist = Counter(min(x, 60) // 4 * 4 for x in ls)
        print('    histogram (4-tick bins, 60 = >= 60): ' + ' '.join(f'{k}:{pct(v, len(ls))}' for k, v in sorted(hist.items())))
        print('    by window: ' + ' | '.join(f'{w} median {st.median(v)} p90 {sorted(v)[9 * len(v) // 10]} share > 34 '
                                            f'{pct(sum(x > 34 for x in v), len(v))}%' for w, v in lat_ph.items() if v))
        _C['lat'] = ls
    if drop:
        dd = sorted(x for x, _ in drop)
        for lab, f in (('all', lambda sp: True), ('troops / buildings', lambda sp: not sp), ('spells', lambda sp: sp)):
            v = [x for x, sp in drop if f(sp)]
            print(f'  tap -> elixir drop ({lab}): n {len(v)} median {st.median(v)} share > 34 ticks {pct(sum(x > 34 for x in v), len(v))}% '
                  f'(the game took the play late; the SIM lands every play at 26)')
        slow = [x for x in dd if 34 < x < 60]
        print(f'    slow plays (35-59 ticks): mean {st.mean(slow):.1f} -> extra {st.mean(slow) - 26:.0f} ticks; --tap-slow '
              f'{sum(x > 34 for x in dd) / len(dd):.3f}:{round(st.mean(slow) - 26)}')
    if xb_err:
        print(f'  X-Bow placement error (confirmed spawn vs intended): mean {st.mean(xb_err):.2f} tiles, > 0.5 tile '
              f'{pct(sum(e > .5 for e in xb_err), len(xb_err))}%; intended rows (y, own frame): ' +
              ' '.join(f'{k:g}:{v}' for k, v in sorted(xb_rows.items())))
    sx = Counter()
    for j in sim_raw():
        for y in (j.get('habits') or {}).get('xbow_y') or []:
            sx[round(y * 32 * 2) / 2] += 1
    print('  SIM X-Bow rows (habits.xbow_y x 32): ' + ' '.join(f'{k:g}:{v}' for k, v in sorted(sx.items())))
    rej = sum(sum(1 for p in j['own_plays'] if not p[3]) for j in sim_raw())
    print(f'  SIM: rejected own plays (not accepted by the engine) {rej / len(sim_raw()):.2f}/match; every accepted play lands')


def sec_ot():
    h('O1 0-0 overtime targeting: does the opponent attack CLX\'s WEAK princess (lowest at 3:00)?  SIM pos rows vs Ranked')
    import invlib as I
    # live
    lv = Counter()
    for r in live_rows():
        if not (r['ot'] and tuple(r['reg_cr']) == (0, 0)) or r['reg_own_low'] is None:
            continue
        m = live_matches().get(r['key'])
        if m is None:
            continue
        weak = r['reg_own_low']
        tr = [p for p in m['opp'] if p['tick'] >= REG and p['x'] is not None and H.kind(p['card']) != 'spell'
              and p['card'] not in PK.ANYWHERE]
        lv['n'] += 1
        lv['el'] += sum(H.cost(p['card']) or 0 for p in tr)
        lv['el_weak'] += sum(H.cost(p['card']) or 0 for p in tr if (p['x'] < 9) == (weak == 'L'))
        f = [s for t, who, s in [(t / I.TICK_S, w, s) for t, w, s in r['seq']] if who == 'own' and t >= REG and s != 'K']
        if f and r['end_s'] < T.DRAIN_S:
            lv['fall'] += 1
            lv['fall_weak'] += f[0] == weak
    print(f'  Ranked 0-0 OTs {lv["n"]}: opponent troop elixir in OT placed in the weak lane {pct(lv["el_weak"], lv["el"])}% | '
          f'pre-drain OT falls of ours on the weak princess {lv["fall_weak"]} of {lv["fall"]}')
    sv = Counter()
    for j in sim_raw(POS_ROOT):
        s = sim_state300(j)
        if not s or j['end_tick'] <= REG + 10 or s['cr'] != (0, 0):
            continue
        me, tf = int(j['learner_side']), _tf(j)
        tr_ = j['o3_trace']
        towers = {int(u): v for u, v in tr_['towers'].items()}
        snap = None
        for t, tw, xb in tr_['snaps']:
            if t > REG - 10:
                break
            snap = dict((int(u), x) for u, x in tw)
        lanes = slot_lane()
        own = {u: v for u, v in towers.items() if v[0] == me and v[1] in (1, 2)}
        alive = {u: snap.get(u, 0) for u in own if snap.get(u, 0) > 0}
        if len(alive) < 2:
            continue
        weak_u = min(alive, key=alive.get)
        # our own princess lanes in OUR frame: our slot -> lane is the mirror of the enemy vote (the same engine x)
        weak = 'L' if lanes[(1 - me, own[weak_u][1])] == 'L' else 'R'
        weak = {'L': 'R', 'R': 'L'}[weak] if False else weak
        tr = [(p[0], H.norm(p[2]), *tf(p[3], p[4])) for p in j['o3_pos'] if p[1] != me and p[0] >= REG]
        tr = [p for p in tr if H.kind(p[1]) != 'spell' and p[1] not in PK.ANYWHERE]
        sv['n'] += 1
        sv['el'] += sum(H.cost(p[1]) or 0 for p in tr)
        sv['el_weak'] += sum(H.cost(p[1]) or 0 for p in tr if (p[2] < 9) == (weak == 'L'))
        fell = None
        for t, tw, xb in tr_['snaps']:
            if t < REG:
                continue
            hp = dict((int(u), x) for u, x in tw)
            d = [u for u in own if hp.get(u, 0) <= 0 and alive.get(u)]
            if d:
                fell = d[0]
                break
        if fell is not None and j['end_tick'] * .05 < T.DRAIN_S:
            sv['fall'] += 1
            sv['fall_weak'] += fell == weak_u
    print(f'  SIM I u40 0-0 OTs {sv["n"]}: opponent troop elixir in OT placed in the weak lane {pct(sv["el_weak"], sv["el"])}% | '
          f'pre-drain OT falls of ours on the weak princess {sv["fall_weak"]} of {sv["fall"]}')
    print('  (SIM weak-lane mapping: our princess slot -> lane taken as the enemy vote of the OTHER learner side, i.e. the same '
          'engine x; checked by the fall-on-weak share, which must be high if the mapping is right)')


J1_CLEAN = {'giant', 'electro_giant', 'golem', 'pekka', 'royal_giant', 'giant_skeleton', 'lava_hound', 'three_musketeers',
            'goblin_giant'}     # FIN13 stamped strict J1 >= 0.95 (n 10-58); fin15 changed only Tornado / elixir / drain laws
J1_SUSPECT = {'royal_hogs', 'elixir_golem', 'battle_ram'}   # J1 0.60 (fin14c; fin15 Tornado law 0.32 -> 0.72 on J2), 0.66, 0.89


def sec_engine():
    h('G1 (ii) the BEAT gap split by the engine fight parity of the win condition (FIN13 per-card J1, strict cohort)')
    for lab, ks in (('J1 >= 0.95 tanks', J1_CLEAN), ('J1-suspect (Royal Hogs, E-Golem, Battle Ram)', J1_SUSPECT),
                    ('other BEAT (Boss Bandit, Rune Giant ...)', T.BEAT - J1_CLEAN - J1_SUSPECT)):
        a = [r for r in sim_rows() if r['wincon_rev'] in ks]
        b = [r for r in live_rows() if r['wincon_rev'] in ks]
        print(f'  {lab:46s} SIM {fmt(sum(r["win"] == 1 for r in a), len(a))} | Ranked {fmt(sum(r["win"] == 1 for r in b), len(b))}'
              f' | SIM - Ranked {nc(sum(r["win"] == 1 for r in a), len(a), sum(r["win"] == 1 for r in b), len(b))}')
        if b:
            c = Counter(r['path'] for r in b)
            d = Counter(r['path'] for r in a)
            print(f'      drain-loss share SIM {pct(d["L_tiebreak_drain"], len(a))} Ranked {pct(c["L_tiebreak_drain"], len(b))}')


def _wr(rows):
    return sum(r['win'] == 1 for r in rows), len(rows)


def sec_ledger():
    """Hypothesis tests beyond the first pass (owner 10-22: several independent causes per cell). Each prints the measured
    share of the cell's gap it accounts for."""
    sr, lr = sim_rows(), live_rows()
    beat = lambda r: r['wincon_rev'] in T.BEAT  # noqa: E731

    h('L1 win | OT split by deck class: how much of the win | OT gap is tank decks?')
    tot_s = [r for r in sr if r['ot']]
    tot_l = [r for r in lr if r['ot']]
    for lab, f in (('vs BEAT', beat), ('vs rest', lambda r: not beat(r))):
        a, b = [r for r in tot_s if f(r)], [r for r in tot_l if f(r)]
        print(f'  {lab:8s} OT games: SIM {pct(len(a), len(tot_s))}% of OTs, win {fmt(*_wr(a))} | Ranked {pct(len(b), len(tot_l))}% '
              f'of OTs, win {fmt(*_wr(b))}')
    # counterfactual: the SIM's win | OT if its BEAT OTs won at the Ranked BEAT-OT rate (and the rest unchanged)
    a_b, a_r = [r for r in tot_s if beat(r)], [r for r in tot_s if not beat(r)]
    b_b = [r for r in tot_l if beat(r)]
    cf = (len(a_b) * _wr(b_b)[0] / _wr(b_b)[1] + _wr(a_r)[0]) / len(tot_s)
    print(f'  SIM win | OT {pct(*_wr(tot_s))} -> {100 * cf:.1f} if its BEAT overtimes went as on Ranked (Ranked {pct(*_wr(tot_l))}): '
          f'tank decks carry {100 * (_wr(tot_s)[0] / len(tot_s) - cf) / (_wr(tot_s)[0] / len(tot_s) - _wr(tot_l)[0] / len(tot_l)):.0f}% of '
          'the gap')

    h('L2 regulation losses by win condition (share of that win condition\'s matches), SIM vs Ranked; the excess by class')
    rl_ = lambda x: sum(r['win'] == 0 and not r['ot'] for r in x)  # noqa: E731
    s, l = defaultdict(list), defaultdict(list)
    for r in sr:
        s[r['wincon_rev']].append(r)
    for r in lr:
        l[r['wincon_rev']].append(r)
    exc = Counter()
    for k in sorted(set(s) | set(l), key=lambda k: -len(l.get(k, []))):
        a, b = s.get(k, []), l.get(k, [])
        if len(b) >= 8:
            print(f'  {k:16s} SIM {pct(rl_(a), len(a))} (n {len(a)}) Ranked {fmt(rl_(b), len(b))}')
        if a:
            # contribution to the overall SIM-Ranked reg-loss gap at the RANKED deck mix
            exc['BEAT' if k in T.BEAT else 'rest'] += len(b) / len(lr) * (rl_(a) / len(a) - (rl_(b) / len(b) if b else rl_(a) / len(a)))
    print('  gap contribution at the Ranked deck mix (pp): ' + ' '.join(f'{k} {100 * v:+.1f}' for k, v in exc.items()))
    kings = [r for r in sr if r['win'] == 0 and not r['ot'] and r['king_lost']]
    print(f'  SIM regulation losses with our KING down: {pct(len(kings), len(sr))}% of matches (Ranked: crowns count princesses '
          f'only; king falls {pct(sum(r["king_lost"] for r in lr if r["win"] == 0 and not r["ot"]), len(lr))}%)')

    h('L3 both took one by deck class and by who fell first')
    for lab, f in (('vs BEAT', beat), ('vs rest', lambda r: not beat(r))):
        a, b = [r for r in sr if f(r)], [r for r in lr if f(r)]
        both = lambda x: sum(r['our_cr'] >= 1 and r['their_cr'] >= 1 for r in x)  # noqa: E731
        print(f'  {lab:8s} SIM {fmt(both(a), len(a))} | Ranked {fmt(both(b), len(b))}')

    h('L4 (iv) opponent tower level on Ranked (87% max): CLX win and cells vs max-tower opponents only')
    mx = [r for r in lr if (r.get('opp_pmax') or 0) >= 4858]
    lo = [r for r in lr if 0 < (r.get('opp_pmax') or 0) < 4858]
    for lab, x in (('max towers', mx), ('lower towers', lo)):
        cells = []
        for cell in ('win', 'win_vs_BEAT', 'win_given_OT', 'win_OT_pre_drain', 'both_took_one', 'reg_loss'):
            sel, hit = next((s_, f_) for c, s_, f_ in T.CELLS if c == cell)
            y = sel(x)
            cells.append(f'{cell} {pct(sum(map(hit, y)), len(y))} (n {len(y)})')
        print(f'  {lab:12s} n {len(x):3d}: ' + ' | '.join(cells))

    h('L5 (iii) CLX lost / slow taps by deck class and in won vs lost overtimes (live)')
    import bisect
    acc = defaultdict(Counter)
    for r in lr:
        try:
            plays, conf, unc, el = read_exec(r['key'])
        except FileNotFoundError:
            continue
        ets = [t for t, _ in el]
        g = ('BEAT' if beat(r) else 'rest', 'OT ' + ('won' if r['win'] == 1 else 'lost') if r['ot'] else 'reg')
        for key in (g[0], g[1]):
            a = acc[key]
            a['m'] += 1
            a['taps'] += len(plays)
            for u in unc:
                p = max((p for p in plays if p['name'] == u['name'] and p['tick'] <= u['tick']), key=lambda p: p['tick'], default=None)
                t0 = p['tick'] if p else u['tick'] - 34
                i, k = bisect.bisect_left(ets, t0), bisect.bisect_right(ets, t0 + 50)
                if not any(el[x - 1][1] - el[x][1] >= .75 * cost_of(u['name']) for x in range(max(1, i), k)) \
                        and (p or u).get('elixir', 0) >= cost_of(u['name']) - 1e-6:
                    a['lost'] += 1
                    a['lost_ot'] += t0 >= REG
            for p in plays:
                q = next((q for q in conf if q['name'] == p['name'] and 0 <= q['tick'] - p['tick'] <= 80), None)
                if q is not None:
                    a['conf'] += 1
                    a['slow'] += q['tick'] - p['tick'] > 34
    for k, a in acc.items():
        print(f'  {k:8s} matches {a["m"]:3d}: lost taps {a["lost"] / a["m"]:.2f}/match ({pct(a["lost"], a["taps"])}% of taps; in OT '
              f'{a["lost_ot"] / a["m"]:.2f}/match) | slow (> 34 ticks) {pct(a["slow"], a["conf"])}% of confirmed plays')

    h('L6 (iv) style: the live inputs measured differently from the SIM\'s (the tap list, the clock offset)')
    import o3_score as O3
    import opp_behaviour as OB
    import live_table as LT
    base, conf_m, off_m = [], [], []
    for r in lr:
        d = LT.cached(LT.LOGS / r['key'])
        if not (d and d.get('start')):
            continue
        m = dict(src='live', id=r['key'], seen=d['seen'], res=0, end=d['end'], t0=d['t0'], side=d['side'], plays=d['plays'],
                 mine=d['mine'])
        base.append(OB.features(m))
        conf_m.append(OB.features({**m, 'mine': [t - 26 for t, _ in d.get('own_conf') or []]}))   # landed plays, SIM's rule
        off_m.append(OB.features({**m, 'plays': [[p[0] - OFF] + list(p[1:]) for p in d['plays']],
                                  'mine': [t - OFF for t in d['mine']], 'end': d['end'] - OFF, 't0': d['t0'] - OFF}))
    simf = [f for _, f in O3.behaviour(sim_raw())]
    for lab, L_ in (('as scored (taps, game ticks)', base), ('our plays = confirmed - 26 (lost / retried taps out)', conf_m),
                    ('ticks - 78 (clock, the SIM\'s frame)', off_m)):
        cmp = OB.compare(L_, simf)
        ds = [cmp[k][4] for k in O3.FEATS if not math.isnan(cmp[k][4])]
        print(f'  {lab:52s} distance {math.sqrt(sum(x * x for x in ds) / len(ds)):.2f} | react_s live {cmp["react_s"][1]:.2f} '
              f'(d {cmp["react_s"][4]:+.2f}) ppm_1x {cmp["ppm_1x"][1]:.2f} ppm_2x {cmp["ppm_2x"][1]:.2f} (d {cmp["ppm_2x"][4]:+.2f})')

    h('L7 (iv) Ranked opponent skill drift: cells by Ranked match order (thirds of the 233)')
    srt = sorted(lr, key=lambda r: r['key'])
    for i in range(3):
        x = srt[i * len(srt) // 3:(i + 1) * len(srt) // 3]
        cells = []
        for cell in ('win', 'win_vs_BEAT', 'win_given_OT', 'both_took_one', 'reg_loss'):
            sel, hit = next((s_, f_) for c, s_, f_ in T.CELLS if c == cell)
            y = sel(x)
            cells.append(f'{cell} {pct(sum(map(hit, y)), len(y))}')
        print(f'  third {i + 1} ({x[0]["key"][10:23]}..{x[-1]["key"][10:23]}): ' + ' | '.join(cells))


def sec_style():
    h('Y1 style distance: per-feature live Ranked mean / SIM mean (Cohen d) -- the O4 style cell is the RMS of these d')
    import o3_score as O3
    cfgs = (('I u40 (2,880)', SIM_ROOT), ('E u40 (2,880)', BK / 'o4/w14F_Eu40'), ('B u20 (1,920)', BK / 'o4/w14O4_Bu20'))
    for nm, root in cfgs:
        raw = sim_raw(root)
        d, cmp = T.style_dist(raw, 'ranked')
        print(f'  {nm:14s} distance {d:.2f}: ' + ' | '.join(f'{k} {cmp[k][1]:.2f}/{cmp[k][3]:.2f} ({cmp[k][4]:+.2f})' for k in O3.FEATS))
    # sensitivity: the two live-vs-SIM measurement asymmetries named in the scorer (iv)
    raw = sim_raw()
    import opp_behaviour as OB
    b = O3.behaviour(raw)
    live = T.live_style('ranked')
    # (1) the live 'mine' list holds every TAP (lost taps and retries included); the SIM's only landed plays
    # (2) the live PlayDetector merges a re-play of the same card within 100 ticks; the SIM rows do not
    merged = []
    for j in raw:
        pl = j.get('o3_plays')
        if not pl:
            continue
        opp, last = [], {}
        for t, c in pl['opp']:
            if not O3.visible(c):
                continue
            k = c.replace('-', '_')
            if k in last and int(t) - last[k] <= 100:
                last[k] = int(t)
                continue
            last[k] = int(t)
            opp.append([int(t), k, O3.card_cost(k) or 0.0, 0.0, 0.0, 1, 99, None])
        merged.append(OB.features(dict(plays=opp, mine=[int(t) - 26 for t, _ in pl['learner']], end=int(j['end_tick']), t0=0, seen=[])))
    cmp = OB.compare(live, merged)
    ds = [cmp[k][4] for k in O3.FEATS if not math.isnan(cmp[k][4])]
    print(f'  I u40 with the live detector\'s same-card 100-tick merge applied to the SIM plays: distance '
          f'{math.sqrt(sum(x * x for x in ds) / len(ds)):.2f}: ' + ' | '.join(f'{k} ({cmp[k][4]:+.2f})' for k in O3.FEATS))
    _ = b


SECTIONS = dict(defs=sec_defs, phase=sec_phase, state=sec_state, both=sec_both, comeback=sec_comeback, wincon=sec_wincon,
                intensity=sec_intensity, tank=sec_tank, xbow=sec_xbow, exec=sec_exec, ot=sec_ot, engine=sec_engine, ledger=sec_ledger, style=sec_style)


def main():
    want = [a for a in sys.argv[1:] if not a.startswith('-')] or list(SECTIONS)
    for k in want:
        SECTIONS[k]()


if __name__ == '__main__':
    main()
