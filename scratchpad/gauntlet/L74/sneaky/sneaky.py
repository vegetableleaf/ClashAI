"""W20 SNEAKY LOCK (owner 10-22): with our X-Bow placed and ONE enemy ground troop holding (or about to take) its
attention while an enemy princess is in X-Bow range, does the model Tornado that blocker away, does the X-Bow then lock
the tower, and what is it worth?  Read-only, single thread, idle priority (shared laptop).

    icebow/.venv/Scripts/python.exe -B sneaky.py live   [--since live_play_20261019_140200] -> live_opps.jsonl, live_matches.jsonl
    icebow/.venv/Scripts/python.exe -B sneaky.py sim    [ROOT ...]                           -> sim_opps.jsonl, sim_matches.jsonl
    icebow/.venv/Scripts/python.exe -B sneaky.py pro    [--limit N]                          -> pro_opps.jsonl, pro_matches.jsonl
    icebow/.venv/Scripts/python.exe -B sneaky.py report                                      -> stdout (SNEAKY.md tables)
    icebow/.venv/Scripts/python.exe -B sneaky.py rulecheck [--n 40]   pro adapter's inferred target vs the reader -> rule_check.json
    icebow/.venv/Scripts/python.exe -B sneaky.py dropcheck [--n 80]   live X-Bow acquire / drop distances, lock hp/s
    icebow/.venv/Scripts/python.exe -B sneaky.py selftest

Public information only: our own hand / elixir / plays, the bodies and towers on screen (positions, hp, the reader's
per-body attack target = the model's own cue input, pipeline/live_unit_state.LiveCues), projectiles on screen. The
opponent's hand, deck, elixir and the frame's opp_elixir_est are never read.

Geometry (engine units, millitiles; the SIM card table cards-160402017): X-Bow range 11.5 t, collision radius 0.6 t,
GROUND ONLY (attacks_air false), deploy 3.5 s, life 30 s; princess radius 1.0 t, king 1.4 t; Tornado radius 5.5 t,
1.05 s.  In range = centre distance - 0.6 - target radius <= 11.5 (the engine's edge rule, live_unit_state's too).
"""
from __future__ import annotations

import argparse
import bisect
import glob
import json
import math
import random
import sys
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
L74 = HERE.parent
REPO = L74.parents[2]
try:                                    # shared laptop: idle priority
    import ctypes
    ctypes.windll.kernel32.SetPriorityClass(ctypes.windll.kernel32.GetCurrentProcess(), 0x40)
except Exception:                       # noqa: BLE001
    pass
sys.path[:0] = [str(REPO), str(L74 / 'monitor'), str(L74 / 'habits'), str(L74 / 'investment')]

TPS = 20
XBOW_ID, TORNADO_ID = 27000008, 28000012
RANGE, XR, PR, KR = 11500, 600, 1000, 1400
TORNADO_R = 5500
REACH_P = RANGE + XR + PR             # X-Bow centre -> princess centre in range (13.1 t)
WIN_ATTEMPT = (-10, 40)               # a Tornado decided 0.5 s before .. 2 s after the opportunity
LOCK_AFTER_T = 60                     # success: tower targeted <= 3 s after the Tornado lands
LOCK_NAT = 100                        # natural lock: <= 5 s after the opportunity (the 2 s window + 3 s)
GAP = 20                              # frames further apart than this split an episode
PM = 4858                             # princess max hp, level 16 (live main account and SIM all16)
SIMCARDS = REPO / 'research/ext/Royale/RoyaleSim/data/derived/cards-160402017-20261006.json'
LOGS = REPO / 'scratchpad/gauntlet/L68/live_reader'
REG = L74 / 'models/registry.json'
SIM_ROOTS = [*sorted(glob.glob('C:/Users/benpe/pod_backup_weekend/w14/o3/*_pos')),
             *sorted(glob.glob('C:/Users/benpe/pod_backup_weekend/w18/*_pos'))]


# ------------------------------------------------------------------------------------------------------------ traits
def _traits():
    d = json.loads(SIMCARDS.read_text(encoding='utf-8'))
    from pipeline import vocab
    out = {}
    for c in [*d['units'].values(), *d['cards'], *d.get('evolutions', []), *d.get('hero_forms', [])]:
        k = vocab.engine_key(c['name'])
        air = (c.get('flying_height') or 0) > 0
        if k in out and c.get('kind') is None:
            continue                    # a card row wins over a same-named character row (kind known)
        out[k] = dict(air=air, kind=c.get('kind'), r=c.get('collision_radius_milli') or 500)
    return out


TRAITS = None


def traits(key):
    global TRAITS
    if TRAITS is None:
        TRAITS = _traits()
    return TRAITS.get(key)


def body_class(key):
    """'air' | 'building' | 'troop' (unknown -> troop: an unknown ground body can block); radius in mt."""
    t = traits(key) if key else None
    if t is None:
        return 'troop', 500
    return ('air' if t['air'] else 'building' if t['kind'] == 'building' else 'troop'), t['r']


def edge(ax, ay, bx, by, r):
    return math.hypot(ax - bx, ay - by) - XR - r


# ------------------------------------------------------------------------------------------------------------ stats
def wilson(k, n, z=1.96):
    if not n:
        return float('nan'), float('nan'), float('nan')
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return p, max(0.0, c - h), min(1.0, c + h)


def cluster_boot(rows, f, B=2000, seed=0):
    """mean of f over rows, 95% bootstrap CI resampling MATCHES (rows sharing 'key' are not independent)."""
    by = defaultdict(list)
    for r in rows:
        v = f(r)
        if v is not None:
            by[r['key']].append(float(v))
    ks = list(by)
    if not ks:
        return float('nan'), float('nan'), float('nan'), 0
    tot = lambda sel: sum(sum(by[k]) for k in sel) / max(1, sum(len(by[k]) for k in sel))  # noqa: E731
    rng = random.Random(seed)
    bs = sorted(tot([rng.choice(ks) for _ in ks]) for _ in range(B))
    return tot(ks), bs[int(.025 * B)], bs[int(.975 * B) - 1], sum(len(v) for v in by.values())


def cluster_diff(a, b, f, B=2000, seed=0):
    """mean f(a) - mean f(b), match-cluster bootstrap (each group resampled by its own matches)."""
    def prep(rows):
        by = defaultdict(list)
        for r in rows:
            v = f(r)
            if v is not None:
                by[r['key']].append(float(v))
        return by
    A, Bb = prep(a), prep(b)
    if not A or not Bb:
        return float('nan'), float('nan'), float('nan')
    m = lambda by, ks: sum(sum(by[k]) for k in ks) / max(1, sum(len(by[k]) for k in ks))  # noqa: E731
    rng = random.Random(seed)
    ka, kb = list(A), list(Bb)
    bs = sorted(m(A, [rng.choice(ka) for _ in ka]) - m(Bb, [rng.choice(kb) for _ in kb]) for _ in range(B))
    return m(A, ka) - m(Bb, kb), bs[int(.025 * B)], bs[int(.975 * B) - 1]


# ------------------------------------------------------------------------------------------------------------- core
def find_episodes(frames, tornado_ok, lone=True):
    """frames: [dict(t, el, xb {gen: dict(x, y, hp, dep, tgt, tcls)}, tw {gen: (x, y, r, hp, slot)}, en {gen: (key, cls,
    r, x, y, hp)})], own X-Bow frames only, one frame of reference (engine mt).  tgt/tcls = the X-Bow's current target
    (None when the source has no target).  -> episodes: one per (X-Bow, blocker) pair: dict(xg, bg, kind 'held'|'about',
    t_first, t_last, t0 = first frame where tornado_ok(t, el), became_held, n_troops).
    lone=True: the OPPORTUNITY (exactly one enemy ground troop in range, no enemy building in range; held = the X-Bow
    targets it, about = the X-Bow is deploying and it is closer than the nearest in-range princess).
    lone=False: the SIM-comparable SUPERSET (the active X-Bow targets an enemy troop, any number of bodies in range)."""
    cur, eps = {}, []
    for f in frames:
        for xg, x in f['xb'].items():
            tin = [(edge(x['x'], x['y'], tx, ty, tr), g) for g, (tx, ty, tr, hp, slot) in f['tw'].items()
                   if slot != 'K' and hp > 0 and edge(x['x'], x['y'], tx, ty, tr) <= RANGE]
            if not tin:
                continue
            gr = [(edge(x['x'], x['y'], e[3], e[4], e[2]), g, e[1]) for g, e in f['en'].items()
                  if e[1] != 'air' and e[5] > 0 and edge(x['x'], x['y'], e[3], e[4], e[2]) <= RANGE]
            troops = [g for d, g, c in gr if c == 'troop']
            if not lone:
                if x['dep'] or x['tcls'] != 'troop':
                    continue
                b, kind = x['tgt'], 'held'
            else:
                if len(troops) != 1 or any(c == 'building' for _, _, c in gr):
                    continue
                b = troops[0]
                db = next(d for d, g, c in gr if g == b)
                if not x['dep'] and x['tgt'] == b:
                    kind = 'held'
                elif x['dep'] and db < min(tin)[0]:
                    kind = 'about'
                else:
                    continue
            e = cur.get((xg, b))
            if e is not None and f['t'] - e['t_last'] > GAP:      # same pair again after a gap -> a new episode
                e = None
            if e is None:
                e = cur[xg, b] = dict(xg=xg, bg=b, kind=kind, t_first=f['t'], t_last=f['t'], t0=None, became_held=False,
                                 n_tin=len(tin), n_troops=None)
                eps.append(e)
            e['t_last'] = f['t']
            e['became_held'] |= kind == 'held'
            if e['t0'] is None and tornado_ok(f['t'], f['el']):
                e['t0'] = f['t']
                e['n_troops'] = len(troops)
    return eps


def lock_tick(frames, ts, xg, t_from, t_to):
    """first frame tick in [t_from, t_to] where X-Bow xg targets an enemy crown tower, else None."""
    for f in frames[bisect.bisect_left(ts, t_from):bisect.bisect_right(ts, t_to)]:
        x = f['xb'].get(xg)
        if x is not None and x['tcls'] in ('tower', 'king'):
            return f['t']
    return None


def xbow_dmg(frames, ts, xg, t_from, t_to, pm=PM):
    """enemy tower HP lost while X-Bow xg targets that tower (pocket.py's SIM rule), princess units."""
    lo, hi = bisect.bisect_left(ts, t_from), bisect.bisect_right(ts, t_to)
    out = 0.0
    for a, b in zip(frames[lo:hi], frames[lo + 1:hi]):
        x = a['xb'].get(xg)
        if x is None or x['tcls'] not in ('tower', 'king') or x['tgt'] not in a['tw'] or b['t'] - a['t'] > GAP:
            continue
        h0, h1 = a['tw'][x['tgt']][3], (b['tw'].get(x['tgt']) or (0, 0, 0, 0, 0))[3]
        out += max(0, h0 - h1) / pm
    return out


def score_episode(e, frames, ts, tornados, key, extra, pm=PM):
    """tornados: [(decision tick, land tick, x, y, meta)] own confirmed Tornados (engine mt, same frame as frames)."""
    t0 = e['t0']
    r = dict(key=key, kind=e['kind'], became_held=e['became_held'], t_first=e['t_first'], t0=t0, n_troops=e['n_troops'],
             dur_s=round((e['t_last'] - e['t_first']) / TPS, 2), **extra)
    i0 = max(0, bisect.bisect_right(ts, t0) - 1)
    f0 = frames[i0]
    x0, b0 = f0['xb'].get(e['xg']), f0['en'].get(e['bg'])
    r['el0'] = round(f0['el'], 2) if f0['el'] is not None else None
    r['blocker'] = b0[0] if b0 else None
    r['xbow_hp'] = x0['hp'] if x0 else None
    win = [q for q in tornados if t0 + WIN_ATTEMPT[0] <= q[0] <= t0 + WIN_ATTEMPT[1]]
    r['tornado_any'] = bool(win)
    if win:
        r['success_any'] = lock_tick(frames, ts, e['xg'], win[0][1], win[0][1] + LOCK_AFTER_T) is not None
    att = None
    for q in win:
        bp = blocker_pos(frames, ts, e['bg'], q[1])
        d = None if bp is None else math.hypot(q[2] - bp[0], q[3] - bp[1]) / 1000
        if d is not None and d <= (TORNADO_R + (b0[2] if b0 else 500)) / 1000:
            att = (q, d)
            break
    r['attempt'] = att is not None
    r['tornado_meta'] = (att[0][4] if att else win[0][4]) if win else None
    r['t_tick'] = (att[0][0] if att else win[0][0]) if win else None      # dedupe: one Tornado can sit in two episodes
    late = [q for q in tornados if t0 + WIN_ATTEMPT[1] < q[0] <= e['t_last']]
    r['late_tornado'] = bool(late)
    r['lock_nat'] = lock_tick(frames, ts, e['xg'], t0, t0 + LOCK_NAT) is not None
    lt = lock_tick(frames, ts, e['xg'], t0, t0 + 400)
    r['lock_s'] = None if lt is None else round((lt - t0) / TPS, 2)
    if att:
        q, d = att
        r['t_dist'] = round(d, 2)
        r['t_land_s'] = round((q[1] - t0) / TPS, 2)
        r['success'] = lock_tick(frames, ts, e['xg'], q[1], q[1] + LOCK_AFTER_T) is not None
        bp1 = blocker_pos(frames, ts, e['bg'], q[1] + 25)
        r['blocker_out'] = bp1 is None or (x0 is not None and edge(x0['x'], x0['y'], bp1[0], bp1[1], b0[2] if b0 else 500) > RANGE)
    for s in (10, 15):
        r[f'dmg{s}'] = round(xbow_dmg(frames, ts, e['xg'], t0, t0 + s * TPS, pm), 4)
    r['blocker_gone3'] = blocker_pos(frames, ts, e['bg'], t0 + 60) is None
    return r


def blocker_pos(frames, ts, bg, t):
    """(x, y) of body bg at the last X-Bow frame <= t, None if it is not on that frame (dead / no frame)."""
    i = bisect.bisect_right(ts, t) - 1
    if i < 0:
        return None
    e = frames[i]['en'].get(bg)
    return None if e is None else (e[3], e[4])


# ------------------------------------------------------------------------------------------------------------- live
def live_index(since):
    """{log name: dict(mark, result)} for every non-dry main-account log since `since` whose checkpoint is CLX / CLXI."""
    reg = json.load(open(REG, encoding='utf-8'))
    sha2mark = {f['sha256']: m['name'] for m in reg['marks'] for f in m.get('files', []) if f.get('sha256')}
    ranked = {}
    p = L74 / 'clx_ranked/index.json'
    if p.exists():
        ranked = {n: v.get('result') for n, v in json.load(open(p)).items()}
    out = {}
    for p in sorted(LOGS.glob('live_play_2026*.jsonl')):
        if p.name < since + '.jsonl':
            continue
        with open(p, 'rb') as f:
            try:
                j = json.loads(f.readline())
            except ValueError:
                continue
        mark = sha2mark.get(j.get('ckpt_sha256'))
        if j.get('event') != 'start' or j.get('dry_run') or mark is None or 'CLX' not in mark:
            continue
        out[p.name] = dict(mark=mark, result=ranked.get(p.name))
    return out


def live_parse(path):
    """-> (match dict, validation Counter) or (None, reason).  Frames kept only while our X-Bow (or its bolt) is on screen."""
    from pipeline.live_unit_state import LiveCues
    from pipeline.obs_contract import catalog_card_form
    from pipeline import vocab
    cues = LiveCues()
    keyc = {}

    def key_of(cid):
        if cid not in keyc:
            n, _ = catalog_card_form(cid)
            keyc[cid] = vocab.engine_key(n) if n else None
        return keyc[cid]

    side = None; frames = []; decs = []; plays = []; outs = []; end = None; pmax = set(); deck = set()
    val = Counter()
    first = True
    for raw in open(path, 'rb'):
        head = raw[:40]
        if b'"frame"' in head:
            if first or b'27000008' in raw:
                j = json.loads(raw)
                if j.get('ents') is None:
                    continue
                side = j['my_side']
                if first:
                    pmax = {e[5] for e in j['ents'] if e[0] == side and e[3] == -1 and abs(e[2] - (6500 if side == 0 else 25500)) < 600}
                    first = False
                f = live_frame(j, side, cues, key_of, val)
                if f is not None:
                    frames.append(f)
        elif b'"decision"' in head:
            j = json.loads(raw)
            h = [x.get('name') for x in (j.get('public') or {}).get('own_hand', [])]
            decs.append((j['tick'], set(h)))
            deck |= set(h)
        elif b'"play"' in head:
            j = json.loads(raw)
            meta = {k: v for k, v in j.items() if k not in ('event', 'tick', 't_dev', 'name', 'p_play', 'elixir', 'hand_pos',
                                                              'xy', 'tap_hand', 'tap_board')}
            plays.append(dict(tick=j['tick'], name=j['name'], xy=j['xy'], p=j.get('p_play'), meta=meta))
        elif b'"confirmed"' in head or b'"unconfirmed"' in head:
            j = json.loads(raw)
            outs.append((j['event'], j['name'], j.get('intended'), j['tick']))
        elif b'"end"' in head:
            end = json.loads(raw)
    if side is None:
        return None, 'noframes'
    if not pmax or not pmax <= {4858} or not {'Xbow', 'Tornado'} <= deck:
        return None, f'not main-account icebow (princess {sorted(pmax)})'
    own = []
    for p, o in zip(plays, outs):
        if o[0] == 'confirmed' and o[1] == p['name']:
            own.append(dict(p, xy=o[2] or p['xy'], land=o[3]))
    return dict(side=side, frames=frames, decs=decs, own=own, end=end), val


def raw_xy(side, xy):
    """own-frame screen xy (0..1, own edge y=1) -> engine mt (log_use.raw_xy)."""
    x, y = 18 - xy[0] * 18, xy[1] * 32
    return (x * 1000, y * 1000) if side == 1 else ((18 - x) * 1000, (32 - y) * 1000)


def live_frame(j, side, cues, key_of, val):
    ents, st = j['ents'], j.get('ents_state') or [[None] * 4] * len(j['ents'])
    xbs = [(e, s) for e, s in zip(ents, st) if e[3] == XBOW_ID and e[0] == side and e[4] > 0]
    if not xbs:
        return None
    rf = dict(game_tick=int(j['tick']), my_side=side, phase2=j.get('phase2'), phase3=j.get('phase3'),
              cues_degraded=j.get('cues_degraded'),
              entities=[dict(side=e[0], x=e[1], y=e[2], card_id=e[3], hp=e[4], max_hp=e[5], kind=e[6], address=e[7],
                             behavior_state_raw=s[0], evo=s[1], level=s[2], category=s[3]) for e, s in zip(ents, st)])
    us = cues.units(rf)                                   # None = degraded frame: target unknown
    ucue = {u['generation']: u for u in us} if us else {}
    tw, en, a2g = {}, {}, {}
    for e, s in zip(ents, st):
        a2g[e[7]] = s[3]
        if e[0] == side or e[4] <= 0:
            continue
        if e[3] == -1:
            k = 'K' if abs(e[1] - 9000) < 600 else 'P'
            tw[s[3]] = (e[1], e[2], KR if k == 'K' else PR, e[4], k)
        else:
            key = key_of(e[3])
            c, r = body_class(key)
            en[s[3]] = (key, c, r, e[1], e[2], e[4])
    bolt = {}
    for p in j.get('proj') or ():
        if p[3] == XBOW_ID and p[0] == side and len(p) >= 10:
            bolt[p[8]] = a2g.get(p[9], 'unseen')

    def cls(g):
        if g is None:
            return None
        if g in tw:
            return 'king' if tw[g][4] == 'K' else 'tower'
        if g in en:
            return en[g][1]
        return 'unseen'
    xb = {}
    for e, s in xbs:
        u = ucue.get(s[3])
        dep = (u['state'] == 'deploying') if u else s[0] in (4, 11)
        tgt = u['attack']['target'] if u else None
        bt = bolt.get(e[7])
        xb[s[3]] = dict(x=e[1], y=e[2], hp=e[4], dep=dep, tgt=tgt if u else None, tcls=cls(tgt) if u else None,
                        bolt=cls(bt) if bt is not None else None)
        if u is None:
            val['frames_degraded'] += 1
        if bt is not None and u is not None:            # validation: the reader target vs the bolt in flight
            val['bolt_frames'] += 1
            val['bolt_agree'] += bt == tgt
            val['bolt_agree_cls'] += cls(bt) == cls(tgt)
        if u is not None and tgt is not None:
            val['tcls_' + str(cls(tgt))] += 1
        val['xbow_frames'] += 1
    return dict(t=int(j['tick']), el=j.get('elixir'), xb=xb, tw=tw, en=en)


def live_cmd(args):
    idx = live_index(args.since)
    print(len(idx), 'CLX / CLXI logs since', args.since, dict(Counter(v['mark'] for v in idx.values())), flush=True)
    done = set()
    mpath, opath, spath = HERE / 'live_matches.jsonl', HERE / 'live_opps.jsonl', HERE / 'livesup_opps.jsonl'
    if mpath.exists() and not args.fresh:
        done = {json.loads(l)['key'] for l in open(mpath, encoding='utf-8')}
    mode = 'a' if done else 'w'
    with open(mpath, mode, encoding='utf-8') as fm, open(opath, mode, encoding='utf-8') as fo, \
            open(spath, mode, encoding='utf-8') as fs:
        for n, (name, v) in enumerate(sorted(idx.items())):
            if name in done:
                continue
            try:
                m, val = live_parse(LOGS / name)
            except Exception as ex:  # noqa: BLE001 -- a broken log is named and skipped
                print('FAIL', name, repr(ex)[:200], flush=True)
                continue
            if m is None:
                fm.write(json.dumps(dict(key=name, mark=v['mark'], skipped=val)) + '\n')
                continue
            res = v['result']
            tw = (m['end'] or {}).get('towers') or {}
            if res is None and tw:
                res = 'WIN' if tw.get('won') else 'DRAW' if tw.get('crowns_me') == tw.get('crowns_opp') else 'LOSS'
            win = {'WIN': 1.0, 'LOSS': 0.0}.get(res, .5)
            side = m['side']
            decs = m['decs']
            dts = [d[0] for d in decs]

            def tornado_ok(t, el):
                i = bisect.bisect_right(dts, t) - 1
                return i >= 0 and 'Tornado' in decs[i][1] and (el or 0) >= 3

            frames = m['frames']
            ts = [f['t'] for f in frames]
            torn = [(q['tick'], q['land'], *raw_xy(side, q['xy']), q['meta']) for q in m['own'] if q['name'] == 'Tornado']
            eps = find_episodes(frames, tornado_ok)
            opps = []
            for e in eps:
                if e['t0'] is None:
                    continue
                r = score_episode(e, frames, ts, torn, name, dict(src='live', mark=v['mark'], win=win))
                opps.append(r)
                fo.write(json.dumps(r) + '\n')
            sup = [e for e in find_episodes(frames, tornado_ok, lone=False) if e['t0'] is not None]
            for e in sup:
                fs.write(json.dumps(score_episode(e, frames, ts, torn, name, dict(src='livesup', mark=v['mark'], win=win))) + '\n')
            # every own Tornado while our X-Bow lived: what the X-Bow targeted then, lock within 3 s of the landing
            tx = []
            for q in torn:
                i = bisect.bisect_right(ts, q[0]) - 1
                if i < 0 or q[0] - ts[i] > GAP:
                    continue
                for xg, x in frames[i]['xb'].items():
                    tx.append(dict(tcls=x['tcls'], dep=x['dep'],
                                   lock3=lock_tick(frames, ts, xg, q[1], q[1] + LOCK_AFTER_T) is not None,
                                   was_tower=x['tcls'] in ('tower', 'king')))
            held_any = sum(1 for f in frames for x in f['xb'].values() if x['tcls'] == 'troop')
            row = dict(key=name, mark=v['mark'], win=win, n_xbow_frames=len(frames), xbow_s=round(len(frames) * 2 / TPS, 1),
                       held_troop_s=round(held_any * 2 / TPS, 1),
                       n_xbows=sum(q['name'] == 'Xbow' for q in m['own']), n_tornados=len(torn),
                       episodes=len(eps), eps_no_tornado=sum(e['t0'] is None for e in eps), opps=len(opps), sup_opps=len(sup),
                       attempts=sum(o['attempt'] for o in opps), tornado_xbow=tx, val=dict(val))
            fm.write(json.dumps(row) + '\n')
            fm.flush(); fo.flush()
            if n % 10 == 0:
                print(n, name, 'frames', len(frames), 'eps', len(eps), 'opps', len(opps), 'att', row['attempts'], flush=True)
    print('done', flush=True)


# -------------------------------------------------------------------------------------------------------------- SIM
def sim_cmd(args):
    """SIM rows with W14's opt-in pos telemetry (o3_pos deploys + o3_trace tower hp / X-Bow [uid, team, hp, target uid]).
    No body positions -> 'lone blocker' cannot be checked: the SIM opportunity is the SUPERSET 'X-Bow held by any non-tower
    target while an enemy princess is in reach' (enemy building deploys in range drop the episode, see below)."""
    sys.path.insert(0, str(L74 / 'opp_model/w14'))
    import o4r_table as T
    import hablib as H
    roots = args.roots or SIM_ROOTS
    mpath, opath = HERE / 'sim_matches.jsonl', HERE / 'sim_opps.jsonl'
    cost = lambda k: H.cost(k) or 0  # noqa: E731
    with open(mpath, 'w', encoding='utf-8') as fm, open(opath, 'w', encoding='utf-8') as fo:
        for root in roots:
            for name, rows in T.load_sim(root).items():
                print(root, name, len(rows), flush=True)
                for j in rows:
                    sim_match(j, name, fm, fo, H, cost)
    print('done', flush=True)


def sim_rate(t):
    return 1 / 56 if t < 2400 else 2 / 56 if t < 4800 else 3 / 56


def sim_match(j, name, fm, fo, H, cost):
    pos, tr = j.get('o3_pos'), j.get('o3_trace')
    if not pos or not tr or not tr.get('snaps'):
        return
    me = int(j['learner_side'])
    towers = {int(u): v for u, v in tr['towers'].items()}
    # engine frame throughout; enemy tower centres: a princess slot's x is not logged -> the side whose OWN deploys sit at
    # low y owns the low-y towers; slot x from the vote below (the X-Bow it was targeted by)
    own_y = [p[4] for p in pos if p[1] == me]
    low = sum(own_y) / max(1, len(own_y)) < 16000
    ty_p = 25500 if low else 6500
    xb_dep = [(p[0], p[3], p[4]) for p in pos if p[1] == me and p[2] == 'Xbow']
    snaps = []
    for t, tw, xb in tr['snaps']:
        hp = {u: 0 for u in towers}
        hp.update({int(u): x for u, x in tw})
        snaps.append((int(t), hp, [(int(a), int(b), int(c), int(d)) for a, b, c, d in xb]))
    opp_p = [u for u, v in towers.items() if v[0] != me and v[1] in (1, 2)]
    # X-Bow uid -> deploy position (the first unmatched own X-Bow deploy at most 3 s before the uid first appears)
    first = {}
    for t, hp, xb in snaps:
        for uid, team, xhp, tgt in xb:
            if team == me:
                first.setdefault(uid, t)
    xpos, used = {}, set()
    for uid, t1 in sorted(first.items(), key=lambda a: a[1]):
        c = [d for d in xb_dep if d not in used and t1 - 60 <= d[0] <= t1 + 2]
        if c:
            d = max(c, key=lambda d: d[0])
            used.add(d)
            xpos[uid] = (d[1], d[2], d[0])
    # slot -> engine x, measured by which lane's X-Bows target each slot (w14c_Iu40_pos, 1,257 votes, no exceptions):
    # team 1's slot 1 sits at x 14500, team 0's slot 1 at x 3500 (slot 2 the other side)
    tpos = {u: (14500 if (towers[u][0] == 1) == (towers[u][1] == 1) else 3500, ty_p) for u in opp_p}
    plays = sorted([p for p in j.get('own_plays') or [] if p[3]], key=lambda p: p[1])
    tornados = [(p[0], p[3], p[4]) for p in pos if p[1] == me and p[2] == 'Tornado']
    enemy_bld = [(p[0], p[3], p[4]) for p in pos if p[1] != me and H.kind(H.norm(p[2])) == 'building']

    def hand_tornado(t):
        seq = [H.norm(p[2]).replace('_evo', '') for p in plays if p[1] <= t]
        if 'tornado' in seq:
            last = len(seq) - 1 - seq[::-1].index('tornado')
            return len(seq) - 1 - last >= 4
        return True if len(seq) >= 4 else None

    def elixir(t):
        prev = [p for p in plays if p[0] <= t]
        if not prev:
            return min(10.0, 5 + t / 56)
        p = prev[-1]
        e = p[4] - cost(H.norm(p[2]).replace('_evo', ''))
        for a in range(p[0], t, 20):
            e = min(10.0, e + sim_rate(a) * min(20, t - a))
        return e
    ts = [s[0] for s in snaps]
    cur = {}
    eps = []
    for i, (t, hp, xb) in enumerate(snaps):
        alive = {uid for uid, team, xhp, tgt in xb if team == me}
        for uid in list(cur):
            if uid not in alive:
                eps.append(cur.pop(uid))
        for uid, team, xhp, tgt in xb:
            if team != me or uid not in xpos:
                continue
            X, Y, tdep = xpos[uid]
            tin = [u for u in opp_p if hp[u] > 0 and tpos[u][0] is not None and math.hypot(X - tpos[u][0], Y - tpos[u][1]) <= REACH_P]
            held = tgt >= 0 and tgt not in towers and bool(tin)
            e = cur.get(uid)
            if e is not None and (not held or e['tgt'] != tgt):
                eps.append(cur.pop(uid))
                e = None
            if held and e is None:
                cur[uid] = dict(uid=uid, tgt=tgt, t_first=t, t_last=t, X=X, Y=Y)
            elif held:
                cur[uid]['t_last'] = t
    eps.extend(cur.values())
    win = {'win': 1.0, 'loss': 0.0}.get(j['outcome'], .5)
    key = f"{name}:{j['seed']}:{j.get('tag')}:{j.get('opp_deck_name')}"
    opps = []
    for e in eps:
        # the episode ends at the next snapshot that changes the X-Bow (target change / death); snaps hold state until then
        k = bisect.bisect_right(ts, e['t_last'])
        e['t_end'] = ts[k] if k < len(ts) else int(j['end_tick'])
        if any(e['t_first'] - 800 <= t <= e['t_end'] and math.hypot(x - e['X'], y - e['Y']) <= REACH_P for t, x, y in enemy_bld):
            e['bld'] = True             # an enemy building may be the target: not a Tornado-able blocker
        t0 = next((t for t in range(e['t_first'], e['t_end'] + 1, 2)
                   if hand_tornado(t) and elixir(t) >= 3), None)
        r = dict(key=key, src='sim', cfg=name, kind='held', win=win, bld=bool(e.get('bld')),
                 dur_s=round((e['t_end'] - e['t_first']) / TPS, 2), hand_known=hand_tornado(e['t_first']) is not None,
                 t0=t0, t_first=e['t_first'])
        if t0 is None:
            r['opp'] = False
            opps.append(r)
            continue
        r['opp'] = True
        win_t = [q for q in tornados if t0 + WIN_ATTEMPT[0] <= q[0] <= t0 + WIN_ATTEMPT[1]]
        r['tornado_any'] = bool(win_t)
        if win_t:
            q = win_t[0]
            r['t_dist_xbow'] = round(math.hypot(q[1] - e['X'], q[2] - e['Y']) / 1000, 2)
            lt = sim_lock(snaps, ts, e['uid'], q[0], q[0] + LOCK_AFTER_T, towers, me)
            r['success_any'] = lt is not None
        r['lock_nat'] = sim_lock(snaps, ts, e['uid'], t0, t0 + LOCK_NAT, towers, me) is not None
        lt = sim_lock(snaps, ts, e['uid'], t0, t0 + 400, towers, me)
        r['lock_s'] = None if lt is None else round((lt - t0) / TPS, 2)
        for s in (10, 15):
            r[f'dmg{s}'] = round(sim_dmg(snaps, ts, e['uid'], t0, t0 + s * TPS, towers, me), 4)
        r['late_tornado'] = any(t0 + WIN_ATTEMPT[1] < q[0] <= e['t_end'] for q in tornados)
        opps.append(r)
    for r in opps:
        fo.write(json.dumps(r) + '\n')
    fm.write(json.dumps(dict(key=key, cfg=name, win=win, n_xbows=len(xb_dep), n_tornados=len(tornados),
                             episodes=len(eps), opps=sum(r['opp'] for r in opps),
                             tornado_xbow=sim_tornado_ctx(snaps, ts, tornados, towers, me))) + '\n')


def _xb_at(snaps, ts, t):
    i = bisect.bisect_right(ts, t) - 1
    return snaps[i] if i >= 0 else None


def sim_lock(snaps, ts, uid, t_from, t_to, towers, me):
    s = _xb_at(snaps, ts, t_from)
    cands = ([s] if s else []) + snaps[bisect.bisect_right(ts, t_from):bisect.bisect_right(ts, t_to)]
    for t, hp, xb in cands:
        for u, team, xhp, tgt in xb:
            if u == uid and tgt in towers and towers[tgt][0] != me:
                return max(t, t_from)
    return None


def sim_dmg(snaps, ts, uid, t_from, t_to, towers, me):
    lo = max(0, bisect.bisect_right(ts, t_from) - 1)
    hi = bisect.bisect_right(ts, t_to)
    out = 0.0
    for (t, hp, xb), nxt in zip(snaps[lo:hi], snaps[lo + 1:hi + 1]):
        for u, team, xhp, tgt in xb:
            if u == uid and tgt in towers and towers[tgt][0] != me:
                out += max(0, hp[tgt] - nxt[1][tgt]) / PM
    return out


def sim_tornado_ctx(snaps, ts, tornados, towers, me):
    out = []
    for t, x, y in tornados:
        s = _xb_at(snaps, ts, t)
        if not s:
            continue
        for u, team, xhp, tgt in s[2]:
            if team == me:
                tc = 'tower' if tgt in towers else 'none' if tgt < 0 else 'unit'
                out.append(dict(tcls=tc, lock3=sim_lock(snaps, ts, u, t, t + LOCK_AFTER_T + 30, towers, me) is not None))
    return out


# -------------------------------------------------------------------------------------------------------------- pro
def pro_cmd(args):
    """Pro icebow8 Path of Legend sides (invlib.pro_matches): decisions + hands real, BOARD = native re-drive (level 11,
    open loop, 1-s frames, no target field).  The X-Bow's target is inferred by the targeting rule (infer_targets),
    whose accuracy is measured on the live frames (report: 'rule vs reader')."""
    import invlib as I
    mpath, opath = HERE / 'pro_matches.jsonl', HERE / 'pro_opps.jsonl'
    with open(mpath, 'w', encoding='utf-8') as fm, open(opath, 'w', encoding='utf-8') as fo:
        for n, m in enumerate(I.pro_matches(limit=args.limit)):
            frames = pro_frames(m)
            infer_targets(frames)
            ts = [f['t'] for f in frames]
            hand = m['hand']

            def tornado_ok(t, el, hand=hand):
                h = hand(t)
                return h is not None and 'tornado' in h[0] and (h[1] or 0) >= 3
            for f in frames:
                h = hand(f['t'])
                f['el'] = None if h is None else h[1]
            torn = [(q['tick'], q['tick'] + 20, q['x'] * 1000, q['y'] * 1000, None) for q in m['own'] if q['card'] == 'tornado']
            eps = find_episodes(frames, tornado_ok)
            opps = [score_episode(e, frames, ts, torn, m['key'], dict(src='pro', win=m['win']),
                                  pm=m['tmax'].get(('opp', 'L')) or 3052) for e in eps if e['t0'] is not None]
            for r in opps:
                fo.write(json.dumps(r) + '\n')
            fm.write(json.dumps(dict(key=m['key'], win=m['win'], n_xbows=sum(q['card'] == 'x_bow' for q in m['own']),
                                     n_tornados=len(torn), episodes=len(eps), opps=len(opps),
                                     attempts=sum(o['attempt'] for o in opps))) + '\n')
            if n % 200 == 0:
                print(n, m['key'], 'eps', len(eps), 'opps', len(opps), flush=True)
    print('done', flush=True)


def pro_frames(m):
    """invlib frames (own-frame tiles) -> find_episodes frames in mt; body identity by same-key nearest neighbour
    (<= 2.5 t / s); X-Bow deploying = its first 3.5 s after the play (invlib X-Bow bodies carry no state)."""
    xplays = [q for q in m['own'] if q['card'] == 'x_bow']
    out, prev, nid = [], {}, [0]
    tslot = {('opp', 'L'): (3500, 6500, PR, 'P'), ('opp', 'R'): (14500, 6500, PR, 'P'), ('opp', 'K'): (9000, 3000, KR, 'K')}
    for t, T, en, xb in m['frames']:
        tw = {k[1]: (*tslot[k][:3], hp, tslot[k][3]) for k, hp in T.items() if k in tslot and hp > 0}
        cur, taken = {}, set()
        for key, hp, x, y in en:
            if not key or hp <= 0:
                continue
            X, Y = x * 1000, y * 1000
            g = min((g for g, e in prev.items() if e[0] == key and g not in taken and math.hypot(e[3] - X, e[4] - Y) <= 2500),
                    key=lambda g: math.hypot(prev[g][3] - X, prev[g][4] - Y), default=None)
            if g is None:
                nid[0] += 1
                g = ('b', nid[0])
            taken.add(g)
            c, r = body_class(key)
            cur[g] = (key, c, r, X, Y, hp)
        xd = {}
        for bid, hp, mx, x, y in xb:
            q = min((q for q in xplays if q['tick'] <= t + 20 and math.hypot(q['x'] - x, q['y'] - y) <= 1.5),
                    key=lambda q: t - q['tick'], default=None)
            g = ('x', q['tick']) if q else ('x', round(x, 1), round(y, 1))
            xd[g] = dict(x=x * 1000, y=y * 1000, hp=hp, dep=q is not None and t - q['tick'] < 70, tgt=None, tcls=None)
        prev = cur
        out.append(dict(t=t, el=None, xb=xd, tw=tw, en=cur))
    return out


def infer_targets(frames):
    """The X-Bow targeting rule on frames that carry no target: deploying -> none; keep the current target while it is
    on the frame and in range; else take the CLOSEST in-range ground target (troop, building, crown tower; edge rule)."""
    cur = {}
    for f in frames:
        for xg, x in f['xb'].items():
            if x['dep']:
                cur.pop(xg, None)
                continue
            g = cur.get(xg)
            ok = False
            if g is not None:
                if g in f['tw']:
                    tx, ty, tr, hp, _ = f['tw'][g]
                    ok = hp > 0 and edge(x['x'], x['y'], tx, ty, tr) <= RANGE
                elif g in f['en']:
                    e = f['en'][g]
                    ok = e[1] != 'air' and e[5] > 0 and edge(x['x'], x['y'], e[3], e[4], e[2]) <= RANGE
            if not ok:
                c = [(edge(x['x'], x['y'], tx, ty, tr), g2) for g2, (tx, ty, tr, hp, _) in f['tw'].items() if hp > 0]
                c += [(edge(x['x'], x['y'], e[3], e[4], e[2]), g2) for g2, e in f['en'].items() if e[1] != 'air' and e[5] > 0]
                c = [a for a in c if a[0] <= RANGE]
                g = min(c, key=lambda a: a[0])[1] if c else None
                cur[xg] = g
            x['tgt'] = g
            x['tcls'] = None if g is None else ('king' if f['tw'][g][4] == 'K' else 'tower') if g in f['tw'] else f['en'][g][1]


# ----------------------------------------------------------------------------------------------------------- report
def load(name):
    p = HERE / name
    return [json.loads(l) for l in open(p, encoding='utf-8')] if p.exists() else []


def pct(k, n):
    p, lo, hi = wilson(k, n)
    return f'{k}/{n} = {100 * p:.1f}% [{100 * lo:.1f}, {100 * hi:.1f}]' if n else f'{k}/0'


def cm(rows, f, scale=1.0, fmt='{:.3f}'):
    m, lo, hi, n = cluster_boot(rows, f)
    return (fmt + ' [' + fmt + ', ' + fmt + '] (n {})').format(m * scale, lo * scale, hi * scale, n) if n else 'n/a'


SOURCES = (('live', 'live_matches.jsonl', 'live_opps.jsonl', 'attempt'),
           ('livesup', 'live_matches.jsonl', 'livesup_opps.jsonl', 'tornado_any'),
           ('sim', 'sim_matches.jsonl', 'sim_opps.jsonl', 'tornado_any'),
           ('pro', 'pro_matches.jsonl', 'pro_opps.jsonl', 'attempt'))


def stratum(o):
    """matching key for 'attempt vs a matched no-Tornado opportunity': kind, phase, X-Bow hp band, our elixir band."""
    t = (o['t0'] or 0) - (78 if o['src'] in ('live', 'livesup') else 0)        # live game tick = clock + 78
    ph = '1x' if t < 2400 else '2x' if t < 3600 else 'OT'
    hp = o.get('xbow_hp')
    el = o.get('el0')
    return (o['kind'], ph, None if hp is None else min(2, int(hp // 900)), None if el is None else min(2, int(el // 2.5)))


def matched_diff(att, non, f, B=2000, seed=0):
    """mean over attempts of f(attempt) - mean f(non-attempts in the same stratum); bootstrap over attempts."""
    pool = defaultdict(list)
    for o in non:
        pool[stratum(o)].append(f(o))
    d = [f(o) - sum(pool[stratum(o)]) / len(pool[stratum(o)]) for o in att if pool[stratum(o)]]
    if not d:
        return float('nan'), float('nan'), float('nan'), 0
    rng = random.Random(seed)
    bs = sorted(sum(rng.choice(d) for _ in d) / len(d) for _ in range(B))
    return sum(d) / len(d), bs[int(.025 * B)], bs[int(.975 * B) - 1], len(d)


def report_cmd(args):
    for src, mf, of, ak in SOURCES:
        M, O = load(mf), load(of)
        M = [m for m in M if not m.get('skipped')]
        if not M:
            continue
        print(f'\n## {src.upper()}  matches {len(M)}  (attempt = {ak})')
        groups = [('all', lambda r: True)]
        if src in ('live', 'livesup'):
            groups += [(mk, lambda r, mk=mk: r['mark'] == mk) for mk in sorted({m['mark'] for m in M})]
        if src == 'sim':
            groups += [(c, lambda r, c=c: r['cfg'] == c) for c in sorted({m['cfg'] for m in M})]
        for lab, g in groups:
            m_ = [m for m in M if g(m)]
            o_ = [o for o in O if g(o) and o.get('opp', True)]
            if src == 'sim':
                o_ = [o for o in o_ if not o['bld']]
            xb = sum(m.get('n_xbows', 0) for m in m_)
            print(f'\n### {lab}: matches {len(m_)}, own X-Bows {xb} ({xb / max(1, len(m_)):.2f}/match), '
                  f'opportunities {len(o_)} ({len(o_) / max(1, len(m_)):.3f}/match, {len(o_) / max(1, xb):.3f}/X-Bow); '
                  f'matches with >= 1 opportunity {len({o["key"] for o in o_})}')
            per = Counter(o['key'] for o in o_)
            pera = Counter(o['key'] for o in o_ if o.get(ak))
            rows = [dict(key=m['key'], n=per[m['key']], a=pera[m['key']]) for m in m_]
            print(f'  per match (bootstrap over matches): opportunities {cm(rows, lambda r: r["n"], 1, "{:.2f}")}; '
                  f'attempts {cm(rows, lambda r: r["a"], 1, "{:.3f}")}')
            if src == 'live':
                print(f'  X-Bow alive {sum(m["xbow_s"] for m in m_) / 60:.0f} min; X-Bow targeting an enemy troop '
                      f'{sum(m["held_troop_s"] for m in m_) / 60:.1f} min; lone-blocker episodes {sum(m["episodes"] for m in m_)}, '
                      f'of them without Tornado-in-hand + 3 elixir {sum(m["eps_no_tornado"] for m in m_)}')
            if not o_:
                continue
            kinds = [('held', lambda o: o['kind'] == 'held'), ('about', lambda o: o['kind'] == 'about'), ('both', lambda o: True)]
            if src == 'livesup':
                kinds = [('1 troop in range', lambda o: o['n_troops'] == 1), ('2+ troops', lambda o: (o['n_troops'] or 0) >= 2),
                         ('all', lambda o: True)]
            for kind, kf in kinds:
                oo = [o for o in o_ if kf(o)]
                if not oo:
                    continue
                att = [o for o in oo if o.get(ak)]
                non = [o for o in oo if not o.get(ak)]
                print(f'  [{kind}] n {len(oo)} | ATTEMPT {pct(len(att), len(oo))} '
                      f'| any Tornado in the window {pct(sum(o["tornado_any"] for o in oo), len(oo))} '
                      f'| attempt rate, match-cluster CI {cm(oo, lambda o: o.get(ak), 100, "{:.1f}")}')
                if att:
                    sk = 'success' if ak == 'attempt' else 'success_any'
                    print(f'      SUCCESS (tower locked <= 3 s after the Tornado lands) {pct(sum(bool(o.get(sk)) for o in att), len(att))}; '
                          f'blocker out of range after {sum(bool(o.get("blocker_out")) for o in att)}/{len(att)}')
                print(f'      natural lock <= 5 s, no attempt: {pct(sum(o["lock_nat"] for o in non), len(non))}; '
                      f'with attempt {pct(sum(o["lock_nat"] for o in att), len(att))}')
                for s in (10, 15):
                    d = cluster_diff(att, non, lambda o, s=s: o[f'dmg{s}'])
                    md = matched_diff(att, non, lambda o, s=s: o[f'dmg{s}'])
                    print(f'      X-Bow tower dmg next {s} s (princess units): attempt {cm(att, lambda o, s=s: o[f"dmg{s}"])} | '
                          f'no attempt {cm(non, lambda o, s=s: o[f"dmg{s}"])} | diff {d[0]:+.3f} [{d[1]:+.3f}, {d[2]:+.3f}] | '
                          f'matched (kind, phase, X-Bow hp, elixir) {md[0]:+.3f} [{md[1]:+.3f}, {md[2]:+.3f}] (n {md[3]})')
                print(f'      match win: with attempt {cm(att, lambda o: o["win"])} | without {cm(non, lambda o: o["win"])}')
                if src != 'sim':
                    print(f'      blocker gone <= 3 s: {pct(sum(o["blocker_gone3"] for o in oo), len(oo))}; '
                          f'late Tornado (after 2 s, same episode) {pct(sum(o["late_tornado"] for o in oo), len(oo))}; '
                          f'elixir at t0 {cm(oo, lambda o: o["el0"], 1, "{:.2f}")}')
                    print('      blockers: ' + ', '.join(f'{k} {v}' for k, v in Counter(o['blocker'] for o in oo).most_common(10)))
        tx = [r for m in M for r in m.get('tornado_xbow', [])]
        if tx:
            c = Counter(r['tcls'] for r in tx)
            print(f'\n  every own Tornado while our X-Bow lived: {len(tx)}; X-Bow target then: {dict(c)}')
            for k in c:
                z = [r for r in tx if r['tcls'] == k]
                print(f'    target {k}: tower locked <= 3 s after landing {pct(sum(r["lock3"] for r in z), len(z))}')
        if src == 'live':
            v = Counter()
            for m in M:
                v.update(m.get('val', {}))
            print(f'\n  reader target vs the X-Bow bolt in flight: same body {pct(v["bolt_agree"], v["bolt_frames"])}, '
                  f'same class {pct(v["bolt_agree_cls"], v["bolt_frames"])}; degraded X-Bow frames {v["frames_degraded"]} of '
                  f'{v["xbow_frames"]}; reader target classes ' + ', '.join(f'{k[5:]} {n}' for k, n in v.items() if k.startswith('tcls_')))
    rule_check()


def rule_check():
    """Accuracy of the pro adapter's inferred target (infer_targets on live geometry) vs the reader target, live frames."""
    p = HERE / 'rule_check.json'
    if p.exists():
        c = json.load(open(p))
        n = c['n']
        print(f'\n## rule vs reader (live frames, X-Bow active, reader target known): n {n}; same class {pct(c["same"], n)}; '
              f'reader troop -> rule troop {pct(c["tt"], c["t"])}; reader tower -> rule tower {pct(c["ww"], c["w"])}')


def rulecheck_cmd(args):
    """Run infer_targets on live frames (subsampled to the pro adapter's 1-s cadence) and compare with the reader."""
    idx = live_index(args.since)
    names = sorted(idx)[::max(1, len(idx) // args.n)][:args.n]
    c = Counter()
    for name in names:
        m, val = live_parse(LOGS / name)
        if m is None:
            continue
        fr = [f for f in m['frames'] if f['t'] % 20 < 2]
        truth = [{g: (x['tcls'], x['dep']) for g, x in f['xb'].items()} for f in fr]
        for f in fr:
            for x in f['xb'].values():
                x['tgt'] = x['tcls'] = None
        infer_targets(fr)
        for f, tr in zip(fr, truth):
            for g, x in f['xb'].items():
                tc, dep = tr[g]
                if dep or tc is None:
                    continue
                c['n'] += 1
                rc = 'tower' if x['tcls'] in ('tower', 'king') else x['tcls']
                tc = 'tower' if tc in ('tower', 'king') else tc
                c['same'] += rc == tc
                c['t'] += tc == 'troop'
                c['tt'] += tc == 'troop' and rc == 'troop'
                c['w'] += tc == 'tower'
                c['ww'] += tc == 'tower' and rc == 'tower'
        print(name, dict(c), flush=True)
    json.dump(dict(c), open(HERE / 'rule_check.json', 'w'))


def dropcheck_cmd(args):
    """Live X-Bow keep / drop distances (the mechanism a sneaky lock needs): edge distance (tiles) of an enemy troop when
    the X-Bow ACQUIRES it, and when the X-Bow DROPS it while it is still alive on the next frame. SIM reference
    (drills/sneaky_rule.py, RoyaleSim): acquired at edge 11.5, dropped at ~11.85 (Knight 12.6 / ~12.95 centre)."""
    idx = live_index(args.since)
    names = sorted(idx)[::max(1, len(idx) // args.n)][:args.n]
    acq, drop, hpdrop, ticks = [], [], 0, 0
    for name in names:
        m, _ = live_parse(LOGS / name)
        if m is None:
            continue
        fr = m['frames']
        for a, b in zip(fr, fr[1:]):
            if b['t'] - a['t'] > 4:
                continue
            for xg, x in b['xb'].items():
                xa = a['xb'].get(xg)
                if xa is not None and xa['tcls'] == 'tower' and xa['tgt'] in a['tw'] and xa['tgt'] in b['tw']:
                    hpdrop += max(0, a['tw'][xa['tgt']][3] - b['tw'][xa['tgt']][3])     # X-Bow on a princess: hp/s
                    ticks += b['t'] - a['t']
                if xa is None or xa['dep'] or xa['tgt'] == x['tgt'] or xa['tcls'] is None or x['tcls'] is None:
                    continue
                if x['tcls'] == 'troop' and x['tgt'] in b['en']:
                    e = b['en'][x['tgt']]
                    acq.append(edge(x['x'], x['y'], e[3], e[4], e[2]) / 1000)
                if xa['tcls'] == 'troop' and xa['tgt'] in b['en']:
                    e = b['en'][xa['tgt']]
                    drop.append(edge(x['x'], x['y'], e[3], e[4], e[2]) / 1000)
    q = lambda v, p: sorted(v)[int(p * (len(v) - 1))] if v else float('nan')  # noqa: E731
    for lab, v in (('acquire', acq), ('drop (target alive)', drop)):
        print(f'{lab:20s} n {len(v):4d} edge tiles: p10 {q(v, .1):.2f} median {q(v, .5):.2f} p90 {q(v, .9):.2f}; '
              f'<= 11.5 {sum(d <= 11.5 for d in v)}; > 11.5 {sum(d > 11.5 for d in v)}')
    print(f'princess hp lost while an X-Bow targets it: {hpdrop * TPS / max(1, ticks):.1f} hp/s = '
          f'{hpdrop * TPS / max(1, ticks) / PM:.4f} princess/s over {ticks / TPS:.0f} s (all sources on that tower)')


# --------------------------------------------------------------------------------------------------------- selftest
def selftest():
    """Synthetic board: X-Bow at the bridge, one Knight in range targeted, tower in range; a Tornado on the Knight 1 s in,
    the X-Bow on the tower 2 s later -> one held opportunity, attempt, success, damage counted only while on the tower."""
    xb = lambda t, dep, tg, tc: {1: dict(x=3500, y=12500, hp=1000, dep=dep, tgt=tg, tcls=tc)}  # noqa: E731
    fr = []
    for t in range(100, 400, 2):
        on_tower = t >= 160
        fr.append(dict(t=t, el=5.0, xb=xb(t, t < 110, 9 if on_tower else (7 if t >= 110 else None),
                                          'tower' if on_tower else ('troop' if t >= 110 else None)),
                       tw={9: (3500, 25500, PR, 4858 - (t - 160) * 10 if on_tower else 4858, 'P')},
                       en={7: ('knight', 'troop', 500, 3600, 14000 + (t - 100) * 40 if t >= 130 else 14000, 1000)} if t < 150 else {}))
    eps = find_episodes(fr, lambda t, el: True)
    assert len(eps) == 1 and eps[0]['kind'] == 'about' and eps[0]['became_held'], eps
    gap = [f for f in fr if f['t'] < 120 or 140 <= f['t'] < 150]          # the same pair after a 1-s+ gap: 2 episodes, not 1/frame
    assert len(find_episodes(gap, lambda t, el: True)) == 2
    ts = [f['t'] for f in fr]
    r = score_episode(eps[0], fr, ts, [(110, 130, 3600, 15000, {})], 'k', {})
    assert r['attempt'] and r['success'] and r['lock_nat'], r
    assert abs(r['dmg10'] - (298 - 160) * 10 / PM) < 0.02, r['dmg10']
    infer_targets(fr)
    assert fr[-1]['xb'][1]['tcls'] == 'tower', fr[-1]['xb']
    assert wilson(0, 10)[2] > 0.25 and abs(wilson(5, 10)[0] - .5) < 1e-9
    assert body_class('minions')[0] == 'air' and body_class('tesla')[0] == 'building' and body_class('knight')[0] == 'troop'
    print('selftest ok')


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest='cmd', required=True)
    a = sub.add_parser('live'); a.add_argument('--since', default='live_play_20261019_140200'); a.add_argument('--fresh', action='store_true')
    a = sub.add_parser('sim'); a.add_argument('roots', nargs='*')
    a = sub.add_parser('pro'); a.add_argument('--limit', type=int)
    sub.add_parser('report')
    a = sub.add_parser('rulecheck'); a.add_argument('--since', default='live_play_20261019_140200'); a.add_argument('--n', type=int, default=25)
    sub.add_parser('selftest')
    a = sub.add_parser('dropcheck'); a.add_argument('--since', default='live_play_20261019_140200'); a.add_argument('--n', type=int, default=60)
    args = ap.parse_args()
    dict(live=live_cmd, sim=sim_cmd, pro=pro_cmd, report=report_cmd, rulecheck=rulecheck_cmd, dropcheck=dropcheck_cmd,
         selftest=lambda a: selftest())[args.cmd](args)


if __name__ == '__main__':
    main()
