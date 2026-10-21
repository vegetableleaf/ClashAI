"""W13: where does ICEBOW Mark CLX lose live?  One row per CLX live match (Ranked since 10-20 + the 13.5-14k ladder since 10-19
14:02 at our tower 4858), with the crown path and the anatomy of the DECISIVE own tower fall of each loss.

    icebow/.venv/Scripts/python.exe -B scratchpad/gauntlet/L74/clx_ranked/anatomy.py   -> clx_ranked/rows.json (+ prints)

Inputs: clx_ranked/index.json (index.py: overnight.out results incl. Ranked 'trophies n/a', decision timing) and the
habits/cache pickles, loaded through investment/invlib.live_matches (clock = game tick - 78; own frame: own king y 29,
river 16, enemy princesses y 6.5; L = x < 9).  Single process, idle priority, local files only.

Definitions (all from the reader's tower HP frames, exact to one cached frame ~6 ticks):
  fall          a tower's last frame with hp > 0, followed by frames where it is missing / <= 0 to the end of the match
  decisive fall (loss) the own princess / king fall after which the opponent led in crowns for the rest of the match;
                None when the loss was decided on tower HP at equal crowns (tiebreak)
  window        the 20 s (400 ticks) before the decisive fall; 'pre' = the 20 s before that (offence committed earlier)
  attackers     enemy bodies within 8 tiles of the fallen tower's centre in the last 10 s, by frames present
  zone of an own play: x_bow -> bridge / pocket / defensive (invlib.xtype); rocket at an enemy tower -> rocket_tower;
                y < 16 -> offence; else same lane as the falling tower -> defend_lane, other lane -> other_lane
"""
from __future__ import annotations

import bisect
import ctypes
import json
import math
import sys
from collections import Counter
from pathlib import Path

try:
    ctypes.windll.kernel32.SetPriorityClass(ctypes.windll.kernel32.GetCurrentProcess(), 0x40)   # IDLE: live play shares the laptop
except Exception:
    pass

HERE = Path(__file__).resolve().parent
L74 = HERE.parent
sys.path[:0] = [str(L74 / 'investment'), str(L74 / 'weekend')]
import invlib as I  # noqa: E402
import archetypes as A  # noqa: E402
H = I.H

OWN_PMAX = 4858                  # main account, level-16 towers (OPP_MODEL.md 0.1); anything else = another account
MAX_DELTA = 100                  # |trophy change| > 100 = account-switch grading artefact (card_use known bug)
WIN_T, PRE_T, LAST_T = 400, 400, 200
OWN_TOWER = {'L': (3.5, 25.5), 'R': (14.5, 25.5), 'K': (9.0, 29.0)}
ATT_R = 8.0
REG = 3600
DRAIN = 5985                     # live: the equal-amount tiebreak drain of every tower starts at clock ~5993 (OT end)


def phase_of(t):
    return '1x' if t < 2400 else '2x' if t < REG else 'OT2x' if t < 4800 else 'OT3x' if t < DRAIN else 'drain'
SPELLS = {'rocket', 'fireball', 'poison', 'lightning', 'earthquake', 'arrows', 'zap', 'the_log', 'giant_snowball', 'tornado',
          'barbarian_barrel', 'royal_delivery', 'freeze', 'rage', 'clone', 'void', 'goblin_curse', 'graveyard', 'mirror',
          'vines', 'electro_spirit'}
# primary win condition of the opponent deck, first match wins (siege before beatdown: an X-Bow / Mortar deck is siege)
WINCON = ('x_bow', 'mortar', 'royal_giant', 'lava_hound', 'golem', 'electro_giant', 'goblin_giant', 'giant', 'elixir_golem',
          'mega_knight', 'pekka', 'hog_rider', 'royal_hogs', 'ram_rider', 'battle_ram', 'balloon', 'graveyard', 'goblin_drill',
          'miner', 'goblin_barrel', 'wall_breakers', 'three_musketeers', 'sparky', 'skeleton_barrel', 'goblin_machine',
          'rune_giant', 'boss_bandit', 'giant_skeleton', 'skeleton_king', 'goblinstein', 'bowler', 'executioner')


def wilson(k, n, z=1.959964):
    if n == 0:
        return float('nan'), float('nan'), float('nan')
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return p, c - h, c + h


def fmt(k, n):
    p, lo, hi = wilson(k, n)
    return f'{100 * p:5.1f}% [{100 * lo:4.1f}, {100 * hi:4.1f}] n={n}' if n else 'n=0'


def falls(m):
    """{(who, slot): clock tick of the fall}; a tower missing in the first frame counts as never present (skipped)."""
    fr = m['frames']
    out = {}
    for k in m['tmax']:
        alive = [f[0] for f in fr if f[1].get(k, 0) > 0]
        if alive and alive[-1] < fr[-1][0]:
            j = bisect.bisect_right([f[0] for f in fr], alive[-1])
            out[k] = fr[j][0]
    return out


def crown_seq(fl):
    return sorted(((t, who, s) for (who, s), t in fl.items()), key=lambda r: r[0])


def zone(q, lane):
    c, x, y = q['card'], q['x'], q['y']
    if x is None or y is None:
        return 'unknown'
    if c == 'x_bow':
        return 'xbow_' + I.xtype(y)
    if c == 'rocket' and any(math.hypot(x - tx, y - ty) <= 3.0 for tx, ty in I.TOWER_XY.values()):
        return 'rocket_tower'
    if y < 16:
        return 'offence'
    return 'defend_lane' if (x < 9) == (lane == 'L') or lane == 'K' else 'other_lane'


def deck(m):
    s = {p['card'] for p in m['opp']}
    for f in m['frames'][::5]:
        s |= {k for k, hp, x, y in f[2] if k}
    return s


def wincon(cards):
    return next((w for w in WINCON if w in cards), 'other')


def el_at(m, t):
    h = m['hand'](t)
    return None if h is None else round(h[1], 2)


def anatomy(m, t, who_slot):
    """The decisive-fall window of an own tower falling at clock t."""
    slot = who_slot[1]
    tx, ty = OWN_TOWER[slot]
    ts = m.setdefault('_ts', [f[0] for f in m['frames']])
    pm = m['tmax'].get(('own', slot)) or 1
    hp = lambda tt: round(I._tower_at(m, tt).get(('own', slot), 0) / pm, 3)  # noqa: E731
    att = Counter()
    for f in m['frames'][bisect.bisect_left(ts, t - LAST_T):bisect.bisect_right(ts, t)]:
        for k, h_, x, y in f[2]:
            if k and math.hypot(x - tx, y - ty) <= ATT_R:
                att[k] += 1
    opp_w = [p for p in m['opp'] if t - WIN_T <= p['tick'] <= t]
    lane_side = lambda p: p['x'] is not None and (slot == 'K' or (p['x'] < 9) == (slot == 'L'))  # noqa: E731
    opp_lane = [p for p in opp_w if lane_side(p)]
    spells_at = [p['card'] for p in m['opp'] if t - 100 <= p['tick'] <= t + 10 and p['x'] is not None
                 and math.hypot(p['x'] - tx, p['y'] - ty) <= 4.0 and p['card'] in SPELLS]
    own_w = [q for q in m['own'] if t - WIN_T <= q['tick'] <= t]
    own_pre = [q for q in m['own'] if t - WIN_T - PRE_T <= q['tick'] < t - WIN_T]
    zw = Counter()
    for q in own_w:
        zw[zone(q, slot)] += H.cost(q['card'])
    zp = Counter()
    for q in own_pre:
        zp[zone(q, slot)] += H.cost(q['card'])
    offz = ('offence', 'xbow_bridge', 'xbow_pocket', 'rocket_tower')
    xb = [b for b in I._frame(m, t - WIN_T)[3]]
    h15 = m['hand'](t - 300)
    els = [e for e in (el_at(m, tt) for tt in range(t - WIN_T, t + 1, 20)) if e is not None]
    return dict(
        t=t, clock_s=round(t * I.TICK_S, 1), phase=phase_of(t), slot=slot,
        hp40=hp(t - 800), hp20=hp(t - WIN_T), hp10=hp(t - LAST_T),
        attackers=dict(att.most_common(5)),
        opp_cards=[(p['tick'] - t, p['card']) for p in opp_w], opp_lane_el=sum(H.cost(p['card']) for p in opp_lane),
        opp_lane_troops=sorted({p['card'] for p in opp_lane if H.kind(p['card']) != 'spell'}),
        spell_finish=spells_at,
        own_cards=[(q['tick'] - t, q['card'], zone(q, slot)) for q in own_w],
        own_zone_w=dict(zw), own_zone_pre=dict(zp),
        own_off_w=sum(v for k, v in zw.items() if k in offz), own_off_pre=sum(v for k, v in zp.items() if k in offz),
        own_def_w=zw.get('defend_lane', 0) + zw.get('xbow_defensive', 0), own_spend_w=sum(zw.values()),
        el20=el_at(m, t - WIN_T), el10=el_at(m, t - LAST_T), el0=el_at(m, t), el_min=min(els) if els else None,
        el_max=max(els) if els else None,
        opp_est20=round(I._est(m)(t - WIN_T), 2),
        xbow_alive20=len(xb), xbow_y20=[round(b[4], 1) for b in xb],
        opp_dmg_w=round(I.tower_loss(m, 'opp', t - WIN_T, t), 3),
        hand15=sorted(h15[0]) if h15 else None)


def match_row(m, meta):
    fl = falls(m)
    seq = crown_seq(fl)
    our = their = 0
    led = trailed = False
    path = []
    for t, who, s in seq:
        if s == 'K':
            path.append((t, who, 'K'))
            continue
        if who == 'opp':
            our += 1
        else:
            their += 1
        led |= our > their
        trailed |= their > our
        path.append((t, who, s))
    oc, tc = I.crowns(m, m['end'])
    first = next(((t, who) for t, who, s in seq if s != 'K'), None)
    ot = m['end'] > REG + 10
    cards = deck(m)
    row = dict(key=m['key'], sample=meta['sample'], win=m['win'], end_s=round(m['end'] * I.TICK_S, 1), ot=ot,
               our_cr=oc, their_cr=tc, king_lost=('own', 'K') in fl, king_took=('opp', 'K') in fl,
               first=None if first is None else first[1], first_s=None if first is None else round(first[0] * I.TICK_S, 1),
               led=led, trailed=trailed, reached_11=_reached_11(seq),
               seq=[(round(t * I.TICK_S, 1), who, s) for t, who, s in seq],
               arch=A.classify([c.replace('_', '') for c in cards]), wincon=wincon(cards), deck=sorted(cards),
               opp_pmax=m['tmax'].get(('opp', 'L')), **{k: meta.get(k) for k in (
                   'dec_ms_median', 'dec_ms_p90', 'frac_dec_gt80', 'n_cpu_starved', 'tap_end_ms_median',
                   'confirm_latency_median', 'n_play', 'n_confirmed', 'ts')})
    row.update(reg_state(m))
    row['intensity'] = intensity(m['own'], m['opp'], m['end'])
    xr = I.xbow_rows(m)
    br = [r for r in xr if r['type'] == 'bridge' and 'lock' in r]
    row['xbow'] = dict(n=len(xr), bridge=sum(r['type'] == 'bridge' for r in xr), bridge_tracked=len(br),
                       bridge_lock=sum(r['lock'] for r in br), bridge_dmg=round(sum(r['dmg_reach'] for r in br), 3),
                       bridge_answer_el=sum(r['answer_el'] for r in br), bridge_life_s=round(sum(r['life_s'] for r in br), 1))
    for nm, (a, b) in (('reg', (0, REG)), ('ot', (REG, m['end'] + 1))):
        row['taken_' + nm], row['dealt_' + nm] = chip_sources(m, a, b)
    dec = None
    if m['win'] == 0.0:
        dec = _decisive(seq)
        row['decisive'] = None if dec is None else anatomy(m, dec[0], ('own', dec[2]))
        f1 = next(((t, s) for t, who, s in seq if who == 'own' and s != 'K'), None)
        row['first_own'] = None if f1 is None else anatomy(m, f1[0], ('own', f1[1]))
    ph = None if dec is None else phase_of(dec[0])
    row['path'] = path_label(m['win'], led, trailed, ph, m['win'] == 0.0 and dec is None)
    return row


SIEGE = {'x_bow', 'mortar'}
SPELL_HIT = (-10, 60)            # a spell's tower damage lands within [first sighting - 0.5 s, + 3 s]
BIG_DROP = 250                   # one frame step losing > 250 hp while a spell is in its window = the spell's hit
OPP_TOWER = {'L': (3.5, 6.5), 'R': (14.5, 6.5), 'K': (9.0, 3.0)}


def chip_sources(m, t0, t1):
    """Approximate attribution of princess-tower HP lost in [t0, t1] (fractions of one princess), both directions.
    Own towers: a step's drop goes to an opponent spell landing within 4 tiles in its window when the drop > BIG_DROP, else is
    split over the enemy bodies within 8 tiles (13 for X-Bow / Mortar); none -> 'unseen' (bodiless / out-of-view).
    Opponent towers: own X-Bow alive within REACH -> x_bow; own Rocket in its window -> rocket; else 'other' (troops, Log...)."""
    fr = m['frames']
    ts = m.setdefault('_ts', [f[0] for f in fr])
    pm_o, pm_t = m['tmax'].get(('own', 'L')) or 1, m['tmax'].get(('opp', 'L')) or 1
    ospell = [p for p in m['opp'] if p['card'] in SPELLS and p['x'] is not None]
    rockets = [q for q in m['own'] if q['card'] == 'rocket' and q['x'] is not None]
    taken, dealt = Counter(), Counter()
    fl = falls(m)   # a step to a missing tower counts only as its real fall (reader drop-outs come back)
    i0, i1 = max(1, bisect.bisect_left(ts, t0)), bisect.bisect_right(ts, t1)
    for a, b in zip(fr[i0 - 1:i1 - 1], fr[i0:i1]):
        t = b[0]
        for s in 'LR':
            d = a[1].get(('own', s), 0) - b[1].get(('own', s), 0)
            if d > 0 and a[1].get(('own', s), 0) > 0 and (b[1].get(('own', s), 0) > 0 or fl.get(('own', s)) == t):
                tx, ty = OWN_TOWER[s]
                sp = [p['card'] for p in ospell if SPELL_HIT[0] <= t - p['tick'] <= SPELL_HIT[1]
                      and math.hypot(p['x'] - tx, p['y'] - ty) <= 4.0]
                at = [k for k, hp, x, y in a[2] if k and math.hypot(x - tx, y - ty) <= (13 if k in SIEGE else ATT_R)]
                if t >= DRAIN:
                    taken['tiebreak_drain'] += d / pm_o
                    continue
                if sp and (d > BIG_DROP or not at):
                    taken[sp[-1]] += d / pm_o
                    continue
                if not at:
                    taken['unseen'] += d / pm_o
                for k in at:
                    taken[k] += d / pm_o / len(at)
            d = a[1].get(('opp', s), 0) - b[1].get(('opp', s), 0)
            if d > 0 and a[1].get(('opp', s), 0) > 0 and (b[1].get(('opp', s), 0) > 0 or fl.get(('opp', s)) == t):
                tx, ty = OPP_TOWER[s]
                if t >= DRAIN:
                    dealt['tiebreak_drain'] += d / pm_t
                elif any(math.hypot(x - tx, y - ty) <= I.REACH for _, hp, _, x, y in a[3]):
                    dealt['x_bow'] += d / pm_t
                elif any(SPELL_HIT[0] <= t - q['tick'] <= SPELL_HIT[1] and math.hypot(q['x'] - tx, q['y'] - ty) <= 4.0
                         for q in rockets):
                    dealt['rocket'] += d / pm_t
                else:
                    dealt['other'] += d / pm_t
    return {k: round(v, 3) for k, v in taken.most_common()}, {k: round(v, 3) for k, v in dealt.most_common()}


INT_WIN = {'reg_0-120': (0, 2400), 'reg_120-180': (2400, REG), 'ot_0-60': (REG, 4800), 'ot_60-120': (4800, DRAIN)}


def intensity(own, opp, end):
    """Per window fully played (match still running at its end or ended inside it): minutes, own plays, opponent TROOP plays
    and troop elixir (bodies are visible live; bodiless spells may be missed), so live and SIM rows compare like-for-like."""
    out = {}
    for k, (a, b) in INT_WIN.items():
        if end <= a:
            continue
        b2 = min(b, end)
        tr = [p for p in opp if a <= p['tick'] < b2 and H.kind(p['card']) != 'spell']
        out[k] = dict(min=round((b2 - a) / 1200, 3), own=sum(a <= q['tick'] < b2 for q in own), opp_troops=len(tr),
                      opp_troop_el=sum(H.cost(p['card']) for p in tr))
    return out


def reg_state(m, t=REG - 10):
    """State at the end of regulation (clock 3590): crowns, lowest standing princess HP (fraction of max) per side, and what each
    side did to the other's towers in overtime."""
    T = I._tower_at(m, t)
    pm_o, pm_t = m['tmax'].get(('own', 'L')) or 1, m['tmax'].get(('opp', 'L')) or 1
    up = lambda who, pm: [T.get((who, s), 0) / pm for s in 'LR' if T.get((who, s), 0) > 0]  # noqa: E731
    oc, tc = I.crowns(m, t)
    own_up, opp_up = up('own', pm_o), up('opp', pm_t)
    ot = m['end'] > REG + 10
    xs = [q for q in m['own'] if q['tick'] >= REG and q['card'] == 'x_bow']
    low = lambda who, pm: min((s for s in 'LR' if T.get((who, s), 0) > 0), key=lambda s: T[(who, s)], default=None)  # noqa: E731
    return dict(reg_cr=(oc, tc), reg_own_low=low('own', pm_o), reg_opp_low=low('opp', pm_t),
                reg_own_min=round(min(own_up), 3) if own_up else 0.0,
                reg_opp_min=round(min(opp_up), 3) if opp_up else 0.0,
                reg_own_sum=round(sum(own_up), 3), reg_opp_sum=round(sum(opp_up), 3),
                ot_own_lost=round(I.tower_loss(m, 'own', REG, m['end']), 3) if ot else None,
                ot_opp_lost=round(I.tower_loss(m, 'opp', REG, m['end']), 3) if ot else None,
                ot_xbows=len(xs), ot_xbow_types=[I.xtype(q['y']) for q in xs],
                ot_own_spend=sum(H.cost(q['card']) for q in m['own'] if q['tick'] >= REG) if ot else None,
                ot_len_s=round((m['end'] - REG) * I.TICK_S, 1) if ot else None)


def path_label(win, led, trailed, decisive_phase, tie_loss):
    """Crown path, mutually exclusive.  Losses: tiebreak (equal crowns at the end), gave_back (led, then the opponent took the
    lead for good), never_led_<phase of the decisive fall>.  Wins: clean (never trailed) / comeback.  Draws: draw."""
    if win == 0.5:
        return 'draw'
    if win == 1.0:
        return 'win_comeback' if trailed else 'win_clean'
    if tie_loss or decisive_phase == 'drain':
        return 'L_tiebreak_drain'
    return 'L_gave_back' if led else 'L_never_led_' + decisive_phase


def _reached_11(seq):
    o = t_ = 0
    for _, who, s in seq:
        if s == 'K':
            continue
        o += who == 'opp'
        t_ += who == 'own'
        if o >= 1 and t_ >= 1:
            return True
    return False


def _decisive(seq):
    """Own fall after which the opponent led in crowns to the end (king fall = 3 crowns)."""
    o = t_ = 0
    states = []
    for t, who, s in seq:
        if s == 'K':
            if who == 'own':
                t_ = 3
            else:
                o = 3
        elif who == 'opp':
            o += 1
        else:
            t_ += 1
        states.append((t, who, s, o, t_))
    dec = None
    for t, who, s, o_, t2 in states:
        if t2 > o_:
            if dec is None and who == 'own':
                dec = (t, who, s)
        else:
            dec = None
    return dec


def load(index_path=HERE / 'index.json'):
    """Ranked = from the first main-account 'trophies n/a' match of 10-20 on (20261020_132855; every later CLX match is n/a,
    same LIVE_OPTIONS / decision options hash a81f578b); ladder = 10-19 14:02..23:59 with a graded trophy delta.  The five
    10-19 17:37-17:56 'n/a' matches (mode unknown: a Ranked test or unread trophies) are dropped as ambiguous."""
    idx = json.load(open(index_path))
    main_acct = {n: v for n, v in idx.items() if v.get('own_pmax') == OWN_PMAX}
    ranked_start = min(n for n, v in main_acct.items() if v.get('tro_na') and v['ts'] >= '20261020_000000')
    keep, why = {}, Counter()
    for n, v in idx.items():
        if v.get('own_pmax') != OWN_PMAX:
            why['other_account_or_no_frames(own_pmax=%s)' % v.get('own_pmax')] += 1
            continue
        if v['result'] not in ('WIN', 'LOSS', 'DRAW'):
            why['no_result:' + str(v['result'])] += 1
            continue
        if n >= ranked_start:
            assert v.get('tro_na'), n
            keep[n] = dict(v, sample='ranked')
        elif v.get('tro_na'):
            why['ambiguous_mode_tro_na_10-19'] += 1
        elif v.get('tro') is not None and abs(v['tro']) <= MAX_DELTA:
            keep[n] = dict(v, sample='ladder')
        else:
            why['baddelta'] += 1
    return keep, why, ranked_start


def main():
    keep, why, rs = load()
    print('ranked start', rs, '| kept', Counter(v['sample'] for v in keep.values()), '| dropped', dict(why))
    sub = HERE / '_index_kept.json'
    json.dump({n: dict(mark=v['mark'], result=v['result'], tro=v['tro']) for n, v in keep.items()}, open(sub, 'w'))
    rows, miss = [], 0
    for m in I.live_matches({'CLX'}, index=sub):
        rows.append(match_row(m, keep[m['key']]))
    miss = len(keep) - len(rows)
    sub.unlink()
    print('rows', len(rows), 'no cache / no frames', miss)
    json.dump(rows, open(HERE / 'rows.json', 'w'), indent=0, default=str)


if __name__ == '__main__':
    main()
