# COPY of parity/metrics/replay_metrics.py (2026-10-25, parity_tornado): ONE change -- the J2 spell fights are narrowed to
# Tornado-anchored fights (to keep the laptop run short); J3 king windows unchanged.
"""Engine replay metrics J2 (Tornado pull), J3 (king activation), J7 (whole-match open loop) and J4 (own elixir) on live
frame logs (W1, 10-20; definitions in METRICS.md). J2 / J3 / J7 reuse fights.py's replay as is: its cut() is narrowed to
the fights a metric needs, and the rows each replay already samples (live + SIM + the K perturbed SIMs) are read off its
card_view calls. fights.py itself is not changed; its replay is byte-identical.

  python replay_metrics.py fights --out DIR [--files GLOB] [--limit N] [--ceiling K]     # J2 + J3
  python replay_metrics.py whole  --out DIR [--files GLOB] [--limit N] [--ceiling K]     # J7
  python replay_metrics.py elixir --out DIR [--files GLOB] [--limit N]                   # J4
  python replay_metrics.py score  --out DIR                                              # tables + CIs from DIR/*.json
Engine: PARITY_SIM_PATH (laptop wheel) or ROYALE_RUNTIME (pods), as fights.py. Single process (the laptop is shared).
"""
from __future__ import annotations

import argparse
from bisect import bisect_left
from collections import Counter, defaultdict
import json
import math
import os
from pathlib import Path
import random
import statistics
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[5]))
from scratchpad.gauntlet.L74.parity import fights as F  # noqa: E402

WAKE = 71                 # SIM: king_activate_time_ms 3550 = 71 ticks (probe: princess down 210 -> wake 0..3550 ms); live 70-71
KING_TOL = 10             # ticks (0.5 s), as fights.DEATH_TOL
PULL_TOL = 500            # millitiles: a pulled body's end point agrees within half a tile
NEAR_KING = 9000          # millitiles: a "risky" negative fight has an enemy this close to the king
MINUTE = 1200
TOWER_TOL = (300, .10)    # J7 tower hp agrees within max(300, 10% of max hp) (one Rocket crown hit at 16 ~ 500)
FALL_TOL = 200            # J7 a tower fall agrees within 10 s
ELIXIR_TOL = .1
FORMS = ('', ' evo', ' hero')

CAP = []                  # rows of every card_view call of the current fight (live+sim, then each perturbed run)
SELECT = {}               # match stem -> fight selector for the patched cut()


def _card_view(orig):
    def wrapped(rows, which, *a, **k):
        if not CAP or CAP[-1] is not rows:
            CAP.append(rows)
        return orig(rows, which, *a, **k)
    return wrapped


def _bodies(orig):
    def wrapped(self, catalog_by_name):
        st, out = orig(self, catalog_by_name)
        awake = {p['team']: p.get('king_active') for p in st['players']}
        for b in out:
            if b['tower'] and b['id'].endswith('K'):
                b['awake'] = bool(awake.get(b['side']))
        return st, out
    return wrapped


def _cut(orig):
    def wrapped(m, events, window):
        return SELECT[m['match']](m, events, orig(m, events, window))
    return wrapped


def _run_fight(orig):
    def wrapped(eng, m, events, fight, *a, **k):
        CAP.clear()
        r = orig(eng, m, events, fight, *a, **k)
        if CAP:
            r['jm'] = fight['metric'](m, events, fight, CAP[0], CAP[1:])
        return r
    return wrapped


def patch():
    F.card_view = _card_view(F.card_view)
    F.Engine.bodies = _bodies(F.Engine.bodies)
    F.cut = _cut(F.cut)
    F.run_fight = _run_fight(F.run_fight)


# ------------------------------------------------------------------ live helpers

def king_awake(rows, side, live=True):
    """First row tick the side's king is awake (live: tower kind 13; SIM: king_active)."""
    for t, lv, sm in rows:
        for b in (lv if live else sm):
            if b['tower'] and b['id'] == f'T{side}K' and ((b.get('kind') == 13) if live else b.get('awake')):
                return t
    return None


def asleep_at_start(rows, side):
    _, lv, sm = rows[0]
    k = [b for b in lv if b['tower'] and b['id'] == f'T{side}K']
    s = [b for b in sm if b['tower'] and b['id'] == f'T{side}K']
    return bool(k and s and k[0].get('kind') != 13 and not s[0].get('awake'))


def label(m, side, name, form):
    return ('own ' if side == m['side'] else 'opp ') + name + FORMS[form or 0]


# ------------------------------------------------------------------ J3: king activation in fights

def j3(m, events, fight, rows, pert):
    t1 = rows[-1][0]
    out = []
    for s_ in (0, 1):
        if not asleep_at_start(rows, s_):
            continue
        lt, st = king_awake(rows, s_), king_awake(rows, s_, live=False)
        lt, st = (lt - WAKE if lt else None), (st - WAKE if st else None)
        if (lt is not None and lt > t1 - WAKE - KING_TOL) and (st is None or st > t1 - WAKE - KING_TOL):
            continue                    # live trigger too close to the window end to judge
        agree = (lt is None and st is None) or (lt is not None and st is not None and abs(lt - st) <= KING_TOL)
        ceil = []
        for pr in pert:                 # SIM vs SIM: the unperturbed replay against each perturbed one
            pt = king_awake(pr, s_, live=False)
            pt = pt - WAKE if pt else None
            ceil.append((st is None and pt is None) or (st is not None and pt is not None and abs(st - pt) <= KING_TOL))
        down = [t for t, k in falls(rows, True) if k.startswith(f'T{s_}') and not k.endswith('K')]
        cause = None if lt is None else 'princess' if any(abs(t - lt) <= 4 for t in down) else 'damage'
        # the defender's own Tornado in the 4 s before the live trigger (the Tornado-to-king pull, reward-redirect-to-king)
        torn = lt is not None and any(e['name'] == 'Tornado' and e['side'] == s_ and lt - 80 <= e['tick'] <= lt
                                      for e in (events[j] for j in fight['events']))
        sdown = [t for t, k in falls(rows, False) if k.startswith(f'T{s_}') and not k.endswith('K')]
        k0 = [b['hp'] for b in rows[0][2] if b['tower'] and b['id'] == f'T{s_}K']
        shurt = next((t for t, _, sm in rows for b in sm if b['tower'] and b['id'] == f'T{s_}K' and k0 and b['hp'] < k0[0]), None)
        # the wake law given the SIM's own trigger: SIM trigger = its princess fall or first king damage
        strig = min([x for x in sdown + ([shurt] if shurt else [])], default=None)
        law = None if st is None or strig is None else abs(st - strig) <= 2
        out.append(dict(side='own' if s_ == m['side'] else 'opp', live=lt, sim=st, agree=agree, cause=cause, tornado=torn,
                        sim_down=sdown[:1], sim_hurt=shurt, wake_law_ok=law,
                        pert=[king_awake(pr, s_, live=False) for pr in pert], ceiling=ceil, kind=fight['why']))
    return dict(j3=out)


# ------------------------------------------------------------------ J6: river crossings (macro pathing)

def crossing(track, side):
    """(tick, lane) of a body's first river crossing toward the enemy: from below RIVER_LO to past RIVER_HI in its own
    forward frame; lane = 'L' / 'R' by x at the crossing (the board's left / right half)."""
    fwd = 1 if side == 0 else -1
    if not track or track[0][2] * fwd >= (14500 if fwd == 1 else -17500):
        return None
    for t, x, y in track:
        if y * fwd > (17500 if fwd == 1 else -14500):
            return t, 'L' if x < 9000 else 'R'
    return None


def j6(m, events, fight, rows, pert):
    catalog = fight['catalog']
    setup = [b for b in rows[0][1] if not b['tower']]
    pairs = F.initial_pairs(rows, setup, catalog)
    tr_l, tr_s = defaultdict(list), defaultdict(list)
    for t, lv, sm in rows:
        for b in lv:
            if not b['tower']:
                tr_l[b['id']].append((t, b['x'], b['y']))
        for b in sm:
            if not b['tower']:
                tr_s[b['id']].append((t, b['x'], b['y']))
    side = {b['id']: (b['side'], b['card_id']) for _, lv, _ in rows for b in lv if not b['tower']}
    pert_tracks = []
    for pr in pert:
        tk = defaultdict(list)
        for t, _, sm in pr:
            for b in sm:
                if not b['tower']:
                    tk[b['id']].append((t, b['x'], b['y']))
        pert_tracks.append(tk)
    out = []
    for lid, tl in tr_l.items():
        sd, cid = side[lid]
        c = catalog.get(cid)
        if c is None or c.get('type') == 'spell':
            continue
        cl, cs = crossing(tl, sd), crossing(tr_s.get(pairs.get(lid)), sd) if pairs.get(lid) else None
        if cl is None and cs is None:
            continue
        ok = cl is not None and cs is not None and cl[1] == cs[1] and abs(cl[0] - cs[0]) <= 10
        ceil = []
        for tk in pert_tracks:          # SIM vs SIM: the same SIM body (uid) in each perturbed replay
            if pairs.get(lid) in tk:
                ck = crossing(tk[pairs[lid]], sd)
                ceil.append((cs is None and ck is None) or (cs is not None and ck is not None and cs[1] == ck[1] and abs(cs[0] - ck[0]) <= 10))
        # pathing proper: both bodies still alive at the later crossing (a body that died first is a fight outcome, J1's)
        t_end = rows[-1][0]
        st_ = tr_s.get(pairs.get(lid)) or []
        last_l, last_s = tl[-1][0], (st_[-1][0] if st_ else None)
        when = max(x[0] for x in (cl, cs) if x)
        alive = last_l >= min(when, t_end - 2) and last_s is not None and last_s >= min(when, t_end - 2)
        out.append(dict(card=label(m, sd, c['display_name'], F.form_of(cid, c)), live=cl, sim=cs, paired=pairs.get(lid) is not None,
                        agree=ok, lane_agree=cl is not None and cs is not None and cl[1] == cs[1], ceiling=ceil,
                        both_alive=alive, edge=when > t_end - 20))
    return dict(j6=out)


def both(fn):
    return lambda m, events, fight, rows, pert: dict(fn(m, events, fight, rows, pert), **j6(m, events, fight, rows, pert))


# ------------------------------------------------------------------ J2: Tornado pull

def at_tick(rows, t):
    i = min(range(len(rows)), key=lambda j: abs(rows[j][0] - t))
    return rows[i]


def j2(m, events, fight, rows, pert):
    ev = events[fight['anchor']]
    eng = fight['eng']
    life, inside = spell_window(eng, ev)
    catalog = fight['catalog']
    t0r = at_tick(rows, ev['tick']); t1r = at_tick(rows, ev['tick'] + life)
    pairs = F.initial_pairs(rows, [b for b in rows[0][1] if not b['tower']], catalog)
    out = []
    S0 = {b['id']: b for b in t0r[2]}
    L1 = {b['id']: b for b in t1r[1]}
    S1 = {b['id']: b for b in t1r[2]}
    for b in t0r[1]:
        c = catalog.get(b['card_id'])
        if b['tower'] or b['side'] == ev['side'] or c is None or c.get('type') == 'spell':
            continue
        d0 = math.hypot(b['x'] - ev['x'], b['y'] - ev['y'])
        if not inside(b):
            continue
        sid = pairs.get(b['id'])
        lb, sb0, sb1 = L1.get(b['id']), S0.get(sid), S1.get(sid)
        st = eng.stats(c['display_name'])
        # H-J2-REACH (W8 round 2): a body the spell cannot touch is not a spell-effect item (an air body under a ground-only spell:
        # the Log's Minion Horde / Bats, 300 items on the clean fights, whose end point is their own flight). J2_AIR_ALL=1 keeps them.
        # (the projectile's aoe_to_air: the card-level attacks_air reads False for the Tornado and Poison too, which do touch air)
        if st.get('flying_height') and ((eng.stats(ev['name']) or {}).get('projectile') or {}).get('aoe_to_air') is False \
                and os.environ.get('J2_AIR_ALL') != '1':
            continue
        rec = dict(victim=label(m, b['side'], c['display_name'], F.form_of(b['card_id'], c)), mass=st.get('mass'),
                   flying=bool(st.get('flying_height')), d0=round(d0), paired=sb0 is not None,
                   live_end=None if lb is None else (lb['x'], lb['y']), sim_end=None if sb1 is None else (sb1['x'], sb1['y']))
        if lb and sb1:
            rec['err'] = round(math.hypot(lb['x'] - sb1['x'], lb['y'] - sb1['y']))
            rec['pull_live'] = round(d0 - math.hypot(lb['x'] - ev['x'], lb['y'] - ev['y']))
            rec['pull_sim'] = round(math.hypot(sb0['x'] - ev['x'], sb0['y'] - ev['y']) - math.hypot(sb1['x'] - ev['x'], sb1['y'] - ev['y']))
            rec['agree'] = rec['err'] <= PULL_TOL
            cl = []
            for pr in pert:              # the same body in each perturbed SIM: nearest same-side same-name body
                p1 = at_tick(pr, ev['tick'] + life)[2]
                cand = [q for q in p1 if not q['tower'] and q['side'] == sb1['side'] and q.get('name') == sb1.get('name')]
                if cand:
                    q = min(cand, key=lambda q: math.hypot(q['x'] - sb1['x'], q['y'] - sb1['y']))
                    cl.append(math.hypot(q['x'] - sb1['x'], q['y'] - sb1['y']) <= PULL_TOL)
            rec['ceiling'] = cl
        elif lb is None and sb1 is None:
            rec['agree'] = True          # both gone (killed) by the window's end: not a pull sample
            rec['both_gone'] = True
        else:
            rec['agree'] = False
        rec['spell'] = ev['name']
        out.append(rec)
    return dict(j2=out, caster='own' if ev['side'] == m['side'] else 'opp', tick=ev['tick'], spell=ev['name'])


ROLLING_W = 30            # ticks: a rolling spell's (Log, Barbarian Barrel) box crosses its 10 tiles in ~1.5 s


def spell_window(eng, ev):
    """(window ticks, inside(body)) of a cast: the spell's own reach (area radius, or a rolling spell's box), the window its
    area effect lives (Tornado 21 ticks, Freeze 70, Poison 80 capped), else 20 ticks (an impact: knockback settles)."""
    c = eng.stats(ev['name']) or {}
    sp = (c.get('projectile') or {}).get('spawn_projectile') or {}
    if sp.get('projectile_range_milli') and sp.get('projectile_radius_milli'):
        fwd = 1 if ev['side'] == 0 else -1
        L, hw = sp['projectile_range_milli'], sp['projectile_radius_milli'] + 500
        return ROLLING_W, lambda b: abs(b['x'] - ev['x']) <= hw and -500 <= (b['y'] - ev['y']) * fwd <= L + 500
    R = max(c.get('area_damage_radius_milli') or 0, (c.get('spell') or {}).get('radius_milli') or 0,
            ((c.get('projectile') or {}).get('area_damage_radius_milli') or 0)) or 2500
    life = eng.effect_life(ev['name'])
    w = min(max((life or 0) // 50, 20), 80)
    return w, lambda b: math.hypot(b['x'] - ev['x'], b['y'] - ev['y']) <= R + 500


# ------------------------------------------------------------------ J7: whole match

def tower_state(rows_t, live=True):
    return {b['id']: max(0, b['hp']) for b in rows_t if b['tower']}


def falls(rows, live=True):
    seen, out = {}, []
    for t, lv, sm in rows:
        cur = {b['id']: b['hp'] for b in (lv if live else sm) if b['tower']}
        for k in ('T0L', 'T0R', 'T0K', 'T1L', 'T1R', 'T1K'):
            if k in cur and cur[k] > 0:
                seen[k] = True
            elif seen.get(k) and k not in [o[1] for o in out]:
                out.append((t, k))
    return out


def j7(m, events, fight, rows, pert):
    maxhp = {b['id']: b['max_hp'] for b in rows[0][1] if b['tower']}
    ticks = [t for t, _, _ in rows]

    def traj(rr, live):
        out = {}
        for mk in range(MINUTE, ticks[-1] + 1, MINUTE):
            t, lv, sm = rr[min(bisect_left([x[0] for x in rr], mk), len(rr) - 1)]
            out[mk] = tower_state(lv if live else sm)
        return out

    def agree_traj(a, b):
        ok = n = 0
        for mk in a:
            for k, hp in a[mk].items():
                if k not in maxhp:
                    continue
                n += 1
                ok += abs(hp - b.get(mk, {}).get(k, 0)) <= max(TOWER_TOL[0], TOWER_TOL[1] * maxhp[k])
        return ok, n

    def seq_agree(fa, fb):
        same = [k for _, k in fa] == [k for _, k in fb]
        timing = same and all(abs(x[0] - y[0]) <= FALL_TOL for x, y in zip(fa, fb))
        return same, timing

    def result(fs):
        c = Counter(k[1] for _, k in fs)     # crowns taken FROM side k[1]: falls of side 0 towers are side 1's crowns
        crowns = [c.get('1', 0), c.get('0', 0)]
        if any(k.endswith('K') for _, k in fs):
            crowns = [3 if any(k == 'T1K' for _, k in fs) else crowns[0], 3 if any(k == 'T0K' for _, k in fs) else crowns[1]]
        return crowns

    lt, st = traj(rows, True), traj(rows, False)
    lf, sf = falls(rows, True), falls(rows, False)
    ok, n = agree_traj(lt, st)
    same, timing = seq_agree(lf, sf)
    kl = [king_awake(rows, s_) for s_ in (0, 1)]
    ks = [king_awake(rows, s_, live=False) for s_ in (0, 1)]
    res = dict(traj_ok=ok, traj_n=n, falls_live=lf, falls_sim=sf, seq_same=same, seq_timing=timing,
               king_live=kl, king_sim=ks, result_live=result(lf), result_sim=result(sf),
               traj_live={mk: v for mk, v in lt.items()}, traj_sim={mk: v for mk, v in st.items()}, end_tick=ticks[-1])
    cl = []
    for pr in pert:                       # SIM vs SIM (perturbed replays): the ceiling of every J7 quantity
        pt, pf = traj(pr, False), falls(pr, False)
        o2, n2 = agree_traj(st, pt)
        s2, t2 = seq_agree(sf, pf)
        cl.append(dict(traj_ok=o2, traj_n=n2, seq_same=s2, seq_timing=t2, result=result(pf),
                       king=[king_awake(pr, s_, live=False) for s_ in (0, 1)]))
    res['ceiling'] = cl
    # diagnosis: the first frame where a tower differs beyond tolerance, and the plays of the 12 s before it (the fight
    # that started the divergence is among them; its J1 card view names the card)
    for t, lv, sm in rows:
        a_, b_ = tower_state(lv), tower_state(sm)
        bad = [k for k in a_ if k in maxhp and abs(a_[k] - b_.get(k, 0)) > max(TOWER_TOL[0], TOWER_TOL[1] * maxhp[k])]
        if bad:
            res['first_div'] = dict(tick=t, towers=bad, live={k: a_[k] for k in bad}, sim={k: b_.get(k, 0) for k in bad},
                                    plays=[(e['tick'], 'own' if e['side'] == m['side'] else 'opp', e['name'], e.get('form'))
                                           for e in events if e['kind'] == 'play' and t - 240 <= e['tick'] <= t])
            break
    return dict(j7=res)


# ------------------------------------------------------------------ fight selection

def select_fights(mode, eng, catalog):
    def fn(m, events, fights):
        ticks = [t for t, _ in m['frames']]
        out = []
        if mode == 'whole':
            first = next((k for k, e in enumerate(events) if e['kind'] == 'play'), None)
            if first is None:
                return []
            frames = [t for t in ticks if t < F.TIME_OUT_TICK]
            return [dict(anchor=first, t0=ticks[0], t1=frames[-1], frame0=0, events=list(range(len(events))),
                         metric=j7, why='whole')]
        rng = random.Random(m['match'])
        spells = [f for f in fights if events[f['anchor']]['source'] in F.SPELL_SOURCES and events[f['anchor']]['name'] == 'Tornado' and events[f['anchor']]['name'] in eng.ids]  # parity_tornado copy: Tornado fights only (+ the J3 windows below)
        for f in spells:
            out.append(dict(f, metric=both(j2), why='spell', eng=eng, catalog=catalog))
        # J3: live king wake ticks per side -> fights whose window holds the trigger; negatives: king asleep all window
        # with an enemy within NEAR_KING of the king (where a false activation could happen), as many as positives
        wake = {}
        for s_ in (0, 1):
            for t, bodies in m['frames']:
                if any(b['tower'] and b['id'] == f'T{s_}K' and b['kind'] == 13 for b in bodies):
                    wake[s_] = t; break
        pos, neg = [], []
        for f in fights:
            for s_ in (0, 1):
                w = wake.get(s_)
                trig = w - WAKE if w else None
                if trig is not None and f['t0'] < trig <= f['t1'] - WAKE - KING_TOL:
                    pos.append(f); break
                if w is None or w > f['t1']:
                    i0, i1 = f['frame0'], bisect_left(ticks, f['t1'])
                    ky = 3000 if s_ == 0 else 29000
                    if any(not b['tower'] and b['side'] != s_ and math.hypot(b['x'] - 9000, b['y'] - ky) < NEAR_KING
                           for _, bodies in m['frames'][i0:i1:5] for b in bodies):
                        neg.append(f); break
        pos = pos[:6]                                    # several plays share one trigger: keep up to 6 windows on it
        neg = rng.sample(neg, min(len(neg), max(2, len(pos))))
        for f in pos + neg:
            out.append(dict(f, metric=both(j3), why='king_pos' if any(f is p for p in pos) else 'king_neg', catalog=catalog))
        return out
    return fn


# ------------------------------------------------------------------ J4: own elixir

def j4(path, eng, catalog, resync=False, cap_date=True, drop_cost=True, gain=True):
    """Own elixir, open loop: the SIM's battle from the first live frame (its tick, the live elixir there), with every
    live own deduction applied by its card's cost at the live drop tick (deduction amount + timing are J5's / static's;
    this isolates regeneration, the 2x / 3x / overtime switches and the cap). Compared on every live frame."""
    fr, plays, presses = [], [], []
    side = None
    with open(path, 'rb') as f:
        for raw in f:
            h = raw[:40]
            if b'"frame"' in h:
                j = json.loads(raw)
                if j.get('elixir') is not None:
                    fr.append((j['tick'], j['elixir'])); side = j['my_side']
            elif b'"confirmed"' in h:
                j = json.loads(raw); plays.append((j.get('tick'), j['name']))
            elif b'"ability_confirmed"' in h:
                j = json.loads(raw); presses.append(j.get('tick'))
    if len(fr) < 100:
        return dict(skipped='no_elixir_frames')
    from scratchpad.gauntlet.L74.parity.mechanics import load_edited
    by = eng.stats
    cost = lambda n: (by(n) or {}).get('elixir')
    # live deductions: frames where elixir falls by >= 0.5; matched to the nearest confirmed play / press within 6 ticks
    drops = []
    for (ta, ea), (tb, eb) in zip(fr, fr[1:]):
        if ea - eb >= .5:
            names = [n for t, n in plays if t is not None and abs(t - tb) <= 6]
            press = any(t is not None and abs(t - tb) <= 6 for t in presses)
            c = cost(names[0]) if names else (F.HERO_IW_ABILITY_COST if press else None)
            # H-J4-DROPCOST (W8 round 2): every drop is deducted by its OWN size rounded to whole elixir (costs are whole; the regen
            # inside the gap is at most 2 x 0.0537, so the rounding is exact, and two spends in one gap sum exactly). Before, a drop
            # that matched no confirmed play / press was never deducted (an 'unconfirmed' tap the game took, a Hero IW press without
            # its event: analysis/j4_unmatched.py), and two drops beside one play were both charged its cost (20261017_021702 t4812:
            # 1.893 + 2.893 both read as the Knight's 3)
            if drop_cost:
                c = round(ea - eb)
            # H-J4-CAPDATE (W8): a spend from a FULL bar (ea at the cap) lands between the frames; the live bar regenerates
            # from the spend tick td, so date it td = tb - (eb - (10 - cost)) / step (step = the live 1/10000 step a tick),
            # inside (ta, tb]. Deducting at tb instead lost (tb - td) steps: 0.018-0.036 at 1x, 0.071 at 2x, 0.107 at 3x
            # (20261017_114921 t2843: live 4.0714, SIM 4.0). Below the cap the spend tick does not move the bar.
            td = tb
            if c and ea >= 9.995 and cap_date:
                step = .0178 if tb <= 2400 else .0357 if tb <= 4800 else .0537
                td = min(tb, max(ta + 1, tb - round((eb - (10 - c)) / step)))
            drops.append(dict(tick=tb, td=td, live_drop=round(ea - eb, 3), card=names[0] if names else ('IceWizard ability' if press else None), cost=c,
                              after=eb))
        # H-J4-GAIN (W8 round 2): a live rise beyond the regen (the opponent's Elixir Golem pays us 1 / 0.5 / 0.5 as its golem,
        # golemites and blobs die: 20261016_213647 t328-t514 rose +1, then +0.5 six times) is credited in 0.5 steps; the open
        # loop has no units, so before it the SIM fell up to 4 elixir behind until the cap
        elif gain and eb - ea - (.0178 if tb <= 2400 else .0357 if tb <= 4800 else .0537) * (tb - ta) >= .4:
            g = round(2 * (eb - ea - (.0178 if tb <= 2400 else .0357 if tb <= 4800 else .0537) * (tb - ta))) / 2
            drops.append(dict(tick=tb, td=tb, live_drop=round(ea - eb, 3), card='gain', cost=-g, after=eb))
    b = eng.b
    t0, e0 = fr[0]
    mana = [10000, 10000]; mana[side] = round(e0 * 1000)
    b.reset(1, [[eng.ids['Knight']], [eng.ids['Knight']]], 0, t0, mana, None, [],
            levels=[[16], [16]], tower_levels=[16, 16])
    unit = json.loads(b.save())['mana_unit']
    sv = json.loads(b.save())
    out, di = [], 0
    for t, e in fr:
        now = json.loads(b.state_json())['tick']
        while di < len(drops) and drops[di]['tick'] <= t:
            d = drops[di]; di += 1
            at = d['tick'] if resync else d['td']
            if at > now:
                b.step([], at - now); now = at
            if d['cost'] or resync:
                # open loop: minus the card's cost; resync: set to the live value after the drop (the error then is one
                # segment's regeneration only, i.e. the regen law, not its accumulation)
                sv = json.loads(b.save()); after = json.loads(json.dumps(sv))
                after['players'][side]['mana'] = round(d['after'] * unit) if resync else min(10 * unit, max(0, after['players'][side]['mana'] - round(d['cost'] * unit)))
                load_edited(b, sv, after)
        if t > now:
            b.step([], t - now)
        st = json.loads(b.state_json())
        if st.get('game_over'):
            break
        sim_e = st['players'][side]['elixir_milli'] / 1000
        out.append((t, e, sim_e))
    phase = lambda t: '1x' if t < 2400 else '2x' if t < 3600 else 'ot2x' if t < 4800 else 'ot3x'
    per = defaultdict(lambda: [0, 0, []])
    for t, e, s in out:
        p = per[phase(t)]
        p[0] += abs(e - s) <= ELIXIR_TOL; p[1] += 1; p[2].append(abs(e - s))
    # regen slopes: consecutive frames, no deduction, both below the cap
    dt = {d['tick'] for d in drops}
    slope = defaultdict(lambda: [[], []])
    for (ta, ea, sa), (tb, eb, sb) in zip(out, out[1:]):
        if tb in dt or tb == ta or max(ea, eb, sa, sb) >= 9.99:
            continue
        slope[phase(tb)][0].append((eb - ea) / (tb - ta)); slope[phase(tb)][1].append((sb - sa) / (tb - ta))
    return dict(match=Path(path).stem, side=side, frames=len(out), drops=len(drops), unmatched_drops=sum(d['card'] is None for d in drops),
                start=(t0, e0), per_phase={k: dict(ok=v[0], n=v[1], med_abs=round(statistics.median(v[2]), 4), max_abs=round(max(v[2]), 3))
                                           for k, v in per.items()},
                slope={k: dict(live=round(statistics.median(v[0]) * 20, 4), sim=round(statistics.median(v[1]) * 20, 4), n=len(v[0]))
                       for k, v in slope.items() if v[0]},
                drop_vs_cost=Counter(round(d['live_drop'] - d['cost'], 1) for d in drops if d['cost']).most_common(6))



# ------------------------------------------------------------------ J5b card cycle + J8 match end (law checks on live logs)

def j5_cycle(path):
    """Own card cycle, live only: the SIM's law is a FIFO queue (the played card goes to the back of a 4-card queue, the
    queue's head fills the slot). From the 5th play on, the card that ENTERS the hand must be the one played 4 plays
    before."""
    hands, plays = [], []
    with open(path, 'rb') as f:
        for raw in f:
            h = raw[:40]
            if b'"decision"' in h:
                j = json.loads(raw)
                hands.append((j['tick'], [(c['name'], int(c.get('form', 0))) for c in (j.get('public') or {}).get('own_hand', [])]))
            elif b'"confirmed"' in h:
                j = json.loads(raw)
                plays.append((j.get('tick'), j['name']))
    plays = [p_ for p_ in plays if p_[0] is not None]
    if len(plays) < 6 or len(hands) < 20:
        return dict(skipped='too_short')
    ht = [t for t, _ in hands]
    entered = []
    for t, name in plays:
        i = bisect_left(ht, t)
        before = hands[i - 1][1] if i else None
        after = next((hh for tt, hh in hands[i:] if Counter(n for n, _ in hh) != Counter(n for n, _ in before or [])), None)
        if before is None or after is None:
            entered.append(None); continue
        new = Counter(n for n, _ in after) - Counter(n for n, _ in before)
        entered.append(next(iter(new)) if len(new) == 1 else None)
    ok = n = 0
    bad = []
    for k in range(4, len(plays)):
        if entered[k] is None:
            continue
        n += 1
        if entered[k] == plays[k - 4][1]:
            ok += 1
        else:
            bad.append((plays[k][0], entered[k], plays[k - 4][1]))
    return dict(match=Path(path).stem, fifo_ok=ok, fifo_n=n, bad=bad[:5])


def j8_end(path, eng):
    """Match end, law check: from the live tower hp just before regulation end (3590) or the overtime end (5990), does the
    SIM end the match with the same winner? Overtime sudden death is J7's (it needs the plays)."""
    end = None
    frames = []
    with open(path, 'rb') as f:
        for raw in f:
            h = raw[:40]
            if b'"frame"' in h:
                j = json.loads(raw)
                frames.append((j['tick'], j['my_side'], [(e[0], e[1], max(0, e[4])) for e in j['ents'] if e[3] == -1]))
            elif b'"end"' in raw[:30]:
                end = json.loads(raw).get('towers') or {}
    if not frames or not end or end.get('won') is None:
        return dict(skipped='no_end')
    last, side, et = frames[-1][0], frames[0][1], end.get('tick') or 0
    # the end event / last frame trail the real end by ~80 ticks (result screen), so the class comes from the tower falls
    up, fell, king = {}, [], False
    for t, _, tw in frames:
        cur = {(s_, x): h_ for s_, x, h_ in tw}
        for k_, h_ in cur.items():
            if h_ > 0:
                up[k_] = True
        for k_ in [k_ for k_ in up if cur.get(k_, 0) <= 0]:
            fell.append(t); up.pop(k_); king |= abs(k_[1] - 9000) < 1000
    tf = max(fell, default=0)
    # H-J8-CLASS (W8): a tiebreak's real end (last - 81) is past overtime's end; a sudden-death fall just before 6000 whose result
    # screen runs past it (20261018_072302 last 6050, 100712 last 6009) is an overtime crown, not a drain
    cls = 'early_3crown' if king else 'tiebreak' if last - 81 >= 6000 else 'overtime_crown' if tf > 3600 and last - tf < 150 else \
        'regulation' if 3600 <= last < 3800 else 'other'
    if cls not in ('tiebreak', 'regulation'):
        return dict(match=Path(path).stem, cls=cls, end_tick=et, won=end['won'])
    at = 5990 if cls == 'tiebreak' else 3590
    fr = max((x for x in frames if x[0] <= at), key=lambda x: x[0])
    hp = [[0, 0, 0], [0, 0, 0]]
    for s_, x, h_ in fr[2]:
        k = 0 if abs(x - 9000) < 1000 else (1 if (x < 9000) == (eng.k_order[s_][1] < 162000) else 2)
        hp[s_][k] = h_
    b = eng.b
    b.reset(1, [[eng.ids['Knight']], [eng.ids['Knight']]], 0, fr[0], [10000, 10000], hp, [], levels=[[16], [16]], tower_levels=[16, 16])
    b.step([], at + 10 - fr[0])
    st = json.loads(b.state_json())
    while not st.get('game_over') and st['tick'] < at + 1000:      # the SIM's end tick (its tiebreak drains towers)
        b.step([], 5)
        st = json.loads(b.state_json())
    won_sim = None if st.get('winner') is None else st['winner'] == side
    return dict(match=Path(path).stem, cls=cls, end_tick=et, last_frame=last, won=end['won'], sim_over=st.get('game_over'),
                sim_tick=st['tick'], won_sim=won_sim, agree=won_sim == end['won'], tower_hp=hp)

# ------------------------------------------------------------------ scoring

def boot(items, f, B=2000, seed=0):
    """(value, (lo, hi)): bootstrap over matches; items = [(match, x)]."""
    by = defaultdict(list)
    for mt, x in items:
        by[mt].append(x)
    keys = sorted(by)
    if not keys:
        return None, (None, None)
    v = f([x for k in keys for x in by[k]])
    rng = random.Random(seed); vals = []
    for _ in range(B):
        s = [x for k in (rng.choice(keys) for _ in keys) for x in by[k]]
        vals.append(f(s))
    vals.sort()
    return v, (vals[int(.025 * B)], vals[int(.975 * B) - 1])


def score(out, to=None):
    mean = lambda xs: sum(xs) / len(xs) if xs else float('nan')
    rep = {}
    files = sorted(Path(out, 'matches').glob('*.json'))
    j2r, j3r, j7r = [], [], []
    for p in files:
        d = json.loads(p.read_text())
        for f in d.get('fights', []):
            jm = f.get('jm') or {}
            for r in jm.get('j2', []):
                j2r.append((p.stem, r))
            for r in jm.get('j3', []):
                j3r.append((p.stem, r))
            if 'j7' in jm:
                j7r.append((p.stem, jm['j7']))
    lines = []
    j6r = [(p.stem, r) for p in files for f in json.loads(p.read_text()).get('fights', []) for r in (f.get('jm') or {}).get('j6', [])]
    if j6r:
        v, ci = boot([(m, r['agree']) for m, r in j6r], mean)
        lv, lci = boot([(m, r['lane_agree']) for m, r in j6r], mean)
        c6 = mean([mean(r['ceiling']) for _, r in j6r if r.get('ceiling')])
        dts = [abs(r['live'][0] - r['sim'][0]) for _, r in j6r if r['live'] and r['sim']]
        lines.append(f"J6 river crossing (same lane and within 10 ticks; a crossing on one side only fails): {v:.3f} [{ci[0]:.3f}, {ci[1]:.3f}]; "
                     f"ceiling {c6:.3f}; median |dt| {statistics.median(dts) if dts else None} ticks; "
                     f"same lane {lv:.3f} [{lci[0]:.3f}, {lci[1]:.3f}]; n={len(j6r)} bodies, {len({m for m, _ in j6r})} matches")
        pa = [(m, r) for m, r in j6r if r.get('both_alive') and not r.get('edge')]
        if pa:
            pv, pci = boot([(m, r['agree']) for m, r in pa], mean)
            pc = mean([mean(r['ceiling']) for _, r in pa if r.get('ceiling')])
            lines.append(f"   pathing proper (both bodies alive at the crossing, not in the window's last 20 ticks): {pv:.3f} [{pci[0]:.3f}, {pci[1]:.3f}] "
                         f"n={len(pa)}; ceiling {pc:.3f}; excluded as a survival difference (J1) or edge: {len(j6r) - len(pa)}")
            rep['j6_pathing'] = dict(agree=pv, ci=pci, n=len(pa), ceiling=pc)
        byc = defaultdict(list)
        for m, r in (pa or j6r):
            byc[r['card']].append(r['agree'])
        worst = sorted(((mean(v_), len(v_), k) for k, v_ in byc.items() if len(v_) >= 10))[:8]
        lines.append('   worst cards (n >= 10): ' + '; '.join(f'{k} {a:.2f} (n {n})' for a, n, k in worst))
        rep['j6'] = dict(agree=v, ci=ci, lane=lv, n=len(j6r))
    dep = [(p.stem, b) for p in files for f in json.loads(p.read_text()).get('fights', []) for b in f.get('bodies', [])
           if b.get('deploy_live') is not None and b.get('deploy_sim') is not None and not b.get('setup')]
    if dep:
        v, ci = boot([(m, abs(b['deploy_live'] - b['deploy_sim']) <= 3) for m, b in dep], mean)
        lines.append(f"J5a deploy duration (first seen -> active, live vs SIM within 3 ticks): {v:.3f} [{ci[0]:.3f}, {ci[1]:.3f}] n={len(dep)} bodies")
        rep['j5a'] = dict(agree=v, ci=ci, n=len(dep))
    if j2r:
        s = [(m, r) for m, r in j2r if 'err' in r]
        v, ci = boot([(m, r['agree']) for m, r in s], mean)
        cv, cci = boot([(m, mean(r['ceiling'])) for m, r in s if r.get('ceiling')], mean)
        ctxt = f"ceiling {cv:.3f} [{cci[0]:.3f}, {cci[1]:.3f}]; normalised {v / cv:.3f}" if cv else "ceiling n/a (K = 0)"
        lines.append(f"J2 spell effect (body end point within {PULL_TOL} mt at the window end, both alive): agree {v:.3f} [{ci[0]:.3f}, {ci[1]:.3f}] n={len(s)} bodies "
                     f"in {len({m for m, _ in s})} matches; {ctxt}")
        lines.append(f"   unpaired / one-side-gone bodies (counted as fails in 'all'): {sum(1 for _, r in j2r if 'err' not in r and not r.get('both_gone'))}; "
                     f"all-bodies agree {mean([r['agree'] for _, r in j2r]):.3f} n={len(j2r)}")
        bys = defaultdict(list)
        for m, r in s:
            bys[r.get('spell', 'Tornado')].append((m, r))
        for k in sorted(bys, key=lambda k: -len(bys[k])):
            g = bys[k]
            gv, gci = boot([(m, r['agree']) for m, r in g], mean)
            gc = mean([mean(r['ceiling']) for _, r in g if r.get('ceiling')])
            lines.append(f"   spell {k}: agree {gv:.3f} [{gci[0]:.3f}, {gci[1]:.3f}] n={len(g)} bodies; ceiling {gc:.3f}; median |err| "
                         f"{statistics.median(r['err'] for _, r in g)} mt")
        bym = defaultdict(list)
        for m, r in s:
            if r.get('spell', 'Tornado') == 'Tornado':
                bym[r['mass'] if r['mass'] is not None else 'building'].append((m, r))
        lines.append('   Tornado by victim mass:')
        for k in sorted(bym, key=lambda x: (isinstance(x, str), x)):
            g = bym[k]
            lines.append(f"   mass {k}: agree {mean([r['agree'] for _, r in g]):.3f} n={len(g)} median |err| {statistics.median(r['err'] for _, r in g)} mt; "
                         f"median pull live {statistics.median(r['pull_live'] for _, r in g)} / sim {statistics.median(r['pull_sim'] for _, r in g)} mt; "
                         f"cards {sorted(Counter(r['victim'] for _, r in g).items(), key=lambda kv: -kv[1])[:5]}")
        rep['j2'] = dict(agree=v, ci=ci, ceiling=cv, n=len(s))
    if j3r:
        for kind in ('king_pos', 'king_neg', None):
            g = [(m, r) for m, r in j3r if kind is None or r['kind'] == kind]
            if not g:
                continue
            v, ci = boot([(m, r['agree']) for m, r in g], mean)
            cv, _ = boot([(m, mean(r['ceiling'])) for m, r in g if r['ceiling']], mean)
            lines.append(f"J3 king activation [{kind or 'all'}] (trigger within {KING_TOL} ticks or both none): agree {v:.3f} [{ci[0]:.3f}, {ci[1]:.3f}] "
                         f"n={len(g)} side-windows, {len({m for m, _ in g})} matches; ceiling {'n/a' if cv is None else format(cv, '.3f')}")
        for nm, sel in (('princess-fall triggers', lambda r: r.get('cause') == 'princess'), ('damage triggers', lambda r: r.get('cause') == 'damage'),
                        ('damage triggers after the defender Tornado', lambda r: r.get('cause') == 'damage' and r.get('tornado'))):
            g = [(m, r) for m, r in j3r if sel(r)]
            if g:
                v_, ci_ = boot([(m, r['agree']) for m, r in g], mean)
                lines.append(f"   {nm}: agree {v_:.3f} [{ci_[0]:.3f}, {ci_[1]:.3f}] n={len(g)}")
        wl = [r['wake_law_ok'] for _, r in j3r if r.get('wake_law_ok') is not None]
        if wl:
            lines.append(f"   wake law given the SIM's own trigger (SIM wake - 71 = its princess fall / first king damage, +-2): {sum(wl)}/{len(wl)}")
        lo = [r for _, r in j3r if not r['agree'] and r['live'] is not None and r['sim'] is None]
        if lo:
            lines.append(f"   live-only wakes: the SIM princess fell {sum(bool(r.get('sim_down')) for r in lo)}, SIM king hurt "
                         f"{sum(r.get('sim_hurt') is not None for r in lo)}, neither {sum(not r.get('sim_down') and r.get('sim_hurt') is None for r in lo)} of {len(lo)}")
        bad = [r for _, r in j3r if not r['agree']]
        lines.append(f"   misses: live-only {sum(r['live'] is not None and r['sim'] is None for r in bad)}, sim-only "
                     f"{sum(r['live'] is None and r['sim'] is not None for r in bad)}, both but off "
                     f"{sum(r['live'] is not None and r['sim'] is not None for r in bad)} "
                     f"(dt {[r['sim'] - r['live'] for r in bad if r['live'] is not None and r['sim'] is not None][:12]})")
        rep['j3'] = dict(agree=v, ci=ci, n=len(j3r))
    if j7r:
        tv, tci = boot([(m, r['traj_ok'] / max(1, r['traj_n'])) for m, r in j7r], mean)
        tc = mean([mean([c['traj_ok'] / max(1, c['traj_n']) for c in r['ceiling']]) for _, r in j7r if r['ceiling']])
        sv = mean([r['seq_same'] for _, r in j7r]); sc = mean([mean([c['seq_same'] for c in r['ceiling']]) for _, r in j7r if r['ceiling']])
        st_ = mean([r['seq_timing'] for _, r in j7r]); stc = mean([mean([c['seq_timing'] for c in r['ceiling']]) for _, r in j7r if r['ceiling']])
        rv = mean([r['result_live'] == r['result_sim'] for _, r in j7r])
        rc = mean([mean([c['result'] == r['result_sim'] for c in r['ceiling']]) for _, r in j7r if r['ceiling']])
        kl = [(r['king_live'][s], r['king_sim'][s]) for _, r in j7r for s in (0, 1)]
        kv = mean([(a is None and b is None) or (a is not None and b is not None and abs(a - b) <= 100) for a, b in kl])
        kc = mean([mean([((r['king_sim'][s] is None) == (c['king'][s] is None)) and (r['king_sim'][s] is None or abs(r['king_sim'][s] - c['king'][s]) <= 100)
                         for c in r['ceiling'] for s in (0, 1)]) for _, r in j7r if r['ceiling']])
        lines.append(f"J7 whole-match open loop, {len(j7r)} matches:")
        lines.append(f"   tower-hp trajectory per minute (within max(300, 10%)): live-vs-sim {tv:.3f} [{tci[0]:.3f}, {tci[1]:.3f}]; ceiling (sim-vs-perturbed) {tc:.3f}; normalised {tv / tc if tc else float('nan'):.3f}")
        lines.append(f"   crown sequence identical: {sv:.3f} (ceiling {sc:.3f}); and every fall within {FALL_TOL} ticks: {st_:.3f} (ceiling {stc:.3f})")
        lines.append(f"   result (crowns each side) identical: {rv:.3f} (ceiling {rc:.3f}); king wake within 5 s or both none: {kv:.3f} (ceiling {kc:.3f})")
        for m, r in j7r:
            lines.append(f"   {m}: traj {r['traj_ok']}/{r['traj_n']} falls live {r['falls_live']} sim {r['falls_sim']} result {r['result_live']} vs {r['result_sim']} "
                         f"king live {r['king_live']} sim {r['king_sim']}")
        rep['j7'] = dict(traj=tv, traj_ci=tci, traj_ceiling=tc, seq=sv, seq_ceiling=sc, result=rv, result_ceiling=rc, n=len(j7r))
    lw = [json.loads(p.read_text()) for p in sorted(Path(out, 'laws').glob('*.json'))] if Path(out, 'laws').exists() else []
    cy = [(r['match'], r['cycle']) for r in lw if r.get('cycle', {}).get('fifo_n')]
    if cy:
        v, ci = boot([(m, c['fifo_ok'] / c['fifo_n']) for m, c in cy], mean)
        lines.append(f"J5b own card cycle FIFO (entering card = the one played 4 plays before): {v:.3f} [{ci[0]:.3f}, {ci[1]:.3f}] over "
                     f"{sum(c['fifo_n'] for _, c in cy)} plays, {len(cy)} matches; examples {[b_ for _, c in cy for b_ in c['bad']][:5]}")
        rep['j5b'] = dict(agree=v, ci=ci, n=sum(c['fifo_n'] for _, c in cy))
    en = [r['end'] for r in lw if 'cls' in r.get('end', {})]
    if en:
        cls = Counter(e['cls'] for e in en)
        pr = [e for e in en if 'agree' in e]
        byc = {c: f"{sum(e['agree'] for e in pr if e['cls'] == c)}/{sum(e['cls'] == c for e in pr)}" for c in ('regulation', 'tiebreak')}
        dis = [(e['match'][11:], e['cls'], e['won'], e['won_sim'], e['sim_tick']) for e in pr if not e['agree']][:6]
        lines.append(f"J8 match end: live classes {dict(cls)}; SIM end-law probe (live tower hp at 3590 / 5990 -> SIM winner) agrees "
                     f"{sum(e['agree'] for e in pr)}/{len(pr)}; by class {byc}; disagreements {dis}")
        # live end = the end event tick - 81 (the result screen trails it: regulation ends read 3681 on 15 of 15 10-19 logs)
        tk = [e for e in pr if e['cls'] == 'tiebreak' and e.get('sim_over')]
        dts = [e['sim_tick'] - (e['end_tick'] - 81) for e in tk]
        lines.append(f"   tiebreak end tick SIM - live: {sorted(dts)} (within 5 ticks: {sum(abs(d) <= 5 for d in dts)}/{len(dts)})")
        rep['j8'] = dict(agree=sum(e['agree'] for e in pr) / len(pr) if pr else None, n=len(pr), classes=dict(cls),
                         tiebreak_tick_ok=sum(abs(d) <= 5 for d in dts), tiebreak_n=len(dts))
    el = [json.loads(p.read_text()) for p in sorted(Path(out, 'elixir').glob('*.json'))] if Path(out, 'elixir').exists() else []
    el = [e for e in el if 'per_phase' in e]
    if el:
        lines.append(f"J4 own elixir open loop, {len(el)} matches (|sim - live| <= {ELIXIR_TOL} elixir per live frame):")
        for ph in ('1x', '2x', 'ot2x', 'ot3x'):
            g = [(e['match'], e['per_phase'][ph]) for e in el if ph in e['per_phase']]
            if not g:
                continue
            v, ci = boot([(m, x['ok'] / x['n']) for m, x in g], mean)
            sl = [(e['slope'][ph]['live'], e['slope'][ph]['sim']) for e in el if ph in e.get('slope', {})]
            lines.append(f"   {ph}: {v:.3f} [{ci[0]:.3f}, {ci[1]:.3f}] of frames; median |d| {statistics.median(x['med_abs'] for _, x in g):.4f}; "
                         f"regen elixir/s live {statistics.median(a for a, _ in sl):.4f} sim {statistics.median(b for _, b in sl):.4f} ({len(g)} matches)")
        allf = [(e['match'], sum(x['ok'] for x in e['per_phase'].values()) / sum(x['n'] for x in e['per_phase'].values())) for e in el]
        v, ci = boot(allf, mean)
        lines.append(f"   all frames: {v:.3f} [{ci[0]:.3f}, {ci[1]:.3f}]; unmatched drops {sum(e['unmatched_drops'] for e in el)} of {sum(e['drops'] for e in el)}; "
                     f"drop - cost {Counter(k for e in el for k, _ in e['drop_vs_cost']).most_common(5)}")
        rep['j4'] = dict(agree=v, ci=ci, n=len(el))
    Path(to or out, 'SCORE.txt').write_text('\n'.join(lines) + '\n')
    Path(to or out, 'score.json').write_text(json.dumps(rep, indent=1, default=str))
    print('\n'.join(lines))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('mode', choices=['fights', 'whole', 'elixir', 'laws', 'score'])
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--files', default='live_play_2026101[6-9]_*.jsonl')
    ap.add_argument('--limit', type=int, default=0)
    ap.add_argument('--stride', type=int, default=1)
    ap.add_argument('--ceiling', type=int, default=4)
    ap.add_argument('--live', type=Path, default=F.ps.LIVE)
    ap.add_argument('--workers', type=int, default=1)
    ap.add_argument('--resync', action='store_true', help='elixir: re-sync the SIM to the live value at every deduction')
    ap.add_argument('--no-cap-date', action='store_true', help='elixir: deduct a spend from a full bar at its frame tick (the pre-W8 harness)')
    ap.add_argument('--no-drop-cost', action='store_true', help='elixir: never deduct a drop that matches no confirmed play / press (pre-W8 round 2)')
    ap.add_argument('--no-gain', action='store_true', help='elixir: never credit a live rise beyond the regen (pre-W8 round 2)')
    ap.add_argument('--to', type=Path, help='score: write SCORE.txt / score.json here (default --out)')
    a = ap.parse_args()
    if a.mode == 'score':
        return score(a.out, a.to)
    paths = sorted(a.live.glob(a.files))[::a.stride]
    if a.limit:
        paths = paths[:a.limit]
    catalog, _ = F.load_catalog()
    t = time.monotonic()
    if a.mode == 'laws':
        (a.out / 'laws').mkdir(parents=True, exist_ok=True)
        eng = F.Engine()
        for n, p in enumerate(paths, 1):
            o = a.out / 'laws' / (p.stem + '.json')
            if o.exists():
                continue
            r = dict(match=p.stem)
            for k, fn in (('cycle', lambda: j5_cycle(str(p))), ('end', lambda: j8_end(str(p), eng))):
                try:
                    r[k] = fn()
                except Exception as e:
                    r[k] = dict(crash=type(e).__name__ + ':' + str(e)[:200])
            o.write_text(json.dumps(r))
            if n % 100 == 0:
                print(n, f'{time.monotonic() - t:.0f}s', flush=True)
        return score(a.out, a.to)
    if a.mode == 'elixir':
        (a.out / 'elixir').mkdir(parents=True, exist_ok=True)
        eng = F.Engine()
        for n, p in enumerate(paths, 1):
            o = a.out / 'elixir' / (p.stem + '.json')
            if o.exists():
                continue
            try:
                r = j4(str(p), eng, catalog, resync=a.resync, cap_date=not a.no_cap_date, drop_cost=not a.no_drop_cost, gain=not a.no_gain)
            except Exception as e:
                r = dict(match=p.stem, crash=type(e).__name__ + ':' + str(e)[:200])
            o.write_text(json.dumps(r))
            print(n, p.stem, r.get('per_phase') or r.get('skipped') or r.get('crash'), f'{time.monotonic() - t:.0f}s', flush=True)
        return score(a.out, a.to)
    (a.out / 'matches').mkdir(parents=True, exist_ok=True)
    jobs = [(str(p), a.mode, str(a.out), a.ceiling) for p in paths]
    if a.workers > 1:            # pods (Linux fork); the laptop runs one process
        from concurrent.futures import ProcessPoolExecutor
        with ProcessPoolExecutor(a.workers) as ex:
            for n, s in enumerate(ex.map(one, jobs), 1):
                print(f"{n}/{len(jobs)} {s.get('match')} fights={s.get('fights')} crash={s.get('crash')} {time.monotonic() - t:.0f}s", flush=True)
    else:
        for n, j in enumerate(jobs, 1):
            s = one(j)
            print(f"{n}/{len(jobs)} {s.get('match')} fights={s.get('fights')} err={s.get('errors')} skip={s.get('skipped')} "
                  f"crash={s.get('crash')} {time.monotonic() - t:.0f}s", flush=True)
    score(a.out)


_ENG = {}


def one(job):
    path, mode, out, ceiling = job
    if not _ENG:
        patch()
        _ENG['eng'] = F.Engine()          # card stats for the selector (run_match makes its own engine)
        _ENG['catalog'] = F.load_catalog()[0]
    SELECT[Path(path).stem] = select_fights(mode, _ENG['eng'], _ENG['catalog'])
    os.environ.pop('PARITY_MAX_FIGHTS', None)
    try:
        return F.run_match(path, 240, out, ceiling)
    except Exception as e:
        return dict(match=Path(path).stem, crash=type(e).__name__ + ':' + str(e)[:200])


if __name__ == '__main__':
    main()
