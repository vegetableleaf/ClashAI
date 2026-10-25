"""Successor gate metrics (owner-approved 2026-10-25): X-Bow attempts vs a lock score, Rocket cycling vs the tower-HP margin,
"behind > 2,000 HP -> seek a lock", king activation / redirect vs the pros. ONE definition for every source, on the match
memory's events (pipeline/match_memory.py):
  live  L68/live_reader logs whose start event names the checkpoint (memory/live_dump.read -> match_memory.build)
  SIM   gate rows (gap.py --record-board 'hab'; DIR/*/D3/matches.jsonl, succ48/xbow_count.rows) -> match_memory.build
  pro   the dataset_gen memory tables (the table rows ARE the events, outcomes final, visibility by vis / res); sides that
        played an X-Bow, and the 'icebow8' subset (every own play in the icebow 8, X-Bow AND Tornado played)

    laptop: icebow/.venv/Scripts/python.exe -B -X utf8 scratchpad/gauntlet/L74/memory/gate_metrics.py --live CLX_PARITY CLXIII --pro
    pod:    python scratchpad/gauntlet/L74/memory/gate_metrics.py --sim NAME=DIR [NAME=DIR ...]     (DIR = a gate48 ev dir)

DEFINITIONS (20 ticks / s; clock = tick - off, off 78 live (live game_tick = clock + 78, doctrine/DOCTRINE_MEASURED.md), 0 SIM / pro)
  moment    a 1-s grid (every 20 ticks) over the match; a play "at" moment g has tick in [g, g + 20).
  tower HP  rebuilt from the memory's tower events for every source (start 1.0, minus each tower_damage 'lost', 0 at the fall);
            the events are debounced at 2 % per tower, so the rebuilt HP lags the true HP by < 2 % (< 100 HP).
  margin    the TIEBREAK RACE (equal crowns at the end -> the lowest tower loses): own weakest princess minus the enemy's weakest
            princess, a fallen princess = 0 HP (a crown down reads as behind by the enemy's weakest tower); when BOTH sides lost a
            princess, the standing princesses. Fractions x 4858 (level-16 princess, the live main account) for EVERY source:
            SIM / pro towers are level 11, so "2,000 HP" means 41 % of a princess everywhere.
  bins      ahead > +546 | level |m| <= 546 (one level-16 Rocket on a tower, decision_options.rocket_tower_damage(16)) |
            behind small -2,000 <= m < -546 | behind > 2000: m < -2,000.
  reach X-Bow / locked / tower Rocket = match_memory's (reach <= 13.5 tiles of an alive enemy princess; locked = it lost >= 5 %
            within 600 ticks; Rocket aim = blast <= 3 tiles of an enemy tower). Outcomes as of the match end (an X-Bow in the
            last 30 s is judged on the time it had, as in the pro tables).
  M1  per moment: score = score_fn(events visible at g, g) (DUMMY until memory v2's lock head lands, see scores()); bins of 0.2;
      per bin: reach X-Bow attempts per minute spent in the bin, realised lock rate of those attempts. Not conditioned on the
      X-Bow being in hand / affordable (no source here records the hand for every moment).
  M2  2x + OT (clock >= 120 s) and OT alone (>= 180 s): tower Rockets per minute spent in each margin bin.
  M3  moments with margin < -2,000 (all phases; 2x + OT): share followed by a reach X-Bow within 30 s; by a LOCKED reach X-Bow
      within 30 s; by a tower Rocket later in the match; and among the last, the share where a locked reach X-Bow was placed in
      [g, that Rocket) (= at least one real lock before cycling; a lock "before" = X-Bow placed before the Rocket).
  M4  per match, while both own princesses stand: king activated (an own-king tower_damage event, >= 2 % of king HP; an
      activation without damage is invisible, e.g. a pull the king only shoots); the activation preceded by an own Tornado
      within 5 s; own Tornados followed by a king hit within 5 s; king HP lost (x 7728, level-16 king); the king's share of
      own tower HP lost (king x 7728, princesses x 4858) = the redirect share.
  CIs: match-cluster bootstrap 95 % (resamples of whole matches; a ratio = sum / sum inside each resample).
"""
import argparse
import bisect
import importlib
import json
import pickle
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path[:0] = [str(REPO), str(HERE), str(HERE.parent / 'succ48')]
from pipeline import match_memory as M  # noqa: E402

PRINCESS_HP, KING_HP = 4858, 7728       # level-16 towers (ape/ape_score.py; live main account since 10-19)
BIG, LEVEL = 2000, 546                  # owner's "2,000 HP" deficit; one level-16 Rocket on a tower (rocket_tower_damage(16))
GRID, LOOK, TORN_PRE = 20, 600, 100     # ticks: 1-s moments, 30-s look-ahead, Tornado-before-activation window (5 s)
LIVE_OFF = 78                           # live game_tick = clock + 78
EDGES = (0.2, 0.4, 0.6, 0.8)            # M1 score bins
ICEBOW8 = {'x-bow', 'tesla', 'ice-wizard', 'tornado', 'rocket', 'knight', 'the-log', 'skeletons'}
C = M._COL


# ------------------------------------------------------------------------------------------------------------ definitions
def margin_hp(hp, al):
    """6 tower HP fractions + alive flags (TOWER order: my K, L, R, opp K, L, R) -> the tiebreak-race margin, level-16 HP."""
    a = sorted(h if x else 0.0 for h, x in zip(hp[1:3], al[1:3]))
    b = sorted(h if x else 0.0 for h, x in zip(hp[4:6], al[4:6]))
    i = int(not all(al[1:3]) and not all(al[4:6]))     # both sides down a princess: race the standing ones
    return (a[i] - b[i]) * PRINCESS_HP


MBINS = ('ahead', 'level', 'behind small', 'behind > 2000')


def mbin(m):
    return MBINS[0 if m > LEVEL else 1 if m >= -LEVEL else 2 if m >= -BIG else 3]


def towers_at(ev, grid):
    """(hp, alive) at each grid tick from the tower events with tick < g (ev chronological, grid increasing)."""
    tw = [e for e in ev if e['type'] in ('tower_damage', 'tower_fall')]
    hp, al, out, k = [1.0] * 6, [True] * 6, [], 0
    for g in grid:
        while k < len(tw) and tw[k]['tick'] < g:
            e, k = tw[k], k + 1
            if e['type'] == 'tower_fall':
                hp[e['tower']], al[e['tower']] = 0.0, False
            else:
                hp[e['tower']] = max(0.0, hp[e['tower']] - e['lost'])
        out.append((tuple(hp), tuple(al)))
    return out


def dummy_score(events, t):
    """DUMMY lock score: this match's own resolved reach X-Bow lock rate so far, shrunk to 0.55 with 2 pseudo X-Bows."""
    done = [e['xb']['locked'] for e in events if e['type'] == 'play' and e['mine'] and e.get('xb') is not None]
    return (sum(done) + 1.1) / (len(done) + 2)


def scores(m, grid, score_fn):
    # TODO(memory v2): the real score is the frozen lock head, match_memory's 'xb_lock_p' (the last v2 summary field, from
    # memory/s1c/lock_head.json once fit_s1c.py has written it). Vectorised per match, it replaces this loop:
    #     tab = mem.table(gid) (live / SIM: keep the MatchMemory in the match dict) or M.unpack(packed, j) (pro)
    #     M.features_at(tab, grid, deck_ids, 'v2', gid)['mem_summary'][:, -1]
    # (gid = dataset_gen.checkpoint_gid(the checkpoint's card_vocab), deck_ids = the own 8 cards in it). Until then
    # --score MODULE:FUNC plugs any f(events, t) -> float.
    return [score_fn(m['at'](g), g) for g in grid]


# ------------------------------------------------------------------------------------------------------------ sources
def live_matches(key, cache=None):
    import live_dump as LD
    for f in sorted((REPO / 'scratchpad/gauntlet/L68/live_reader').glob('live_play_*.jsonl')):
        ok = False
        with open(f, 'rb') as fh:                                 # the start event (with the ckpt) is not always line 1
            for _, raw in zip(range(400), fh):
                if b'"event": "start"' in raw[:60]:
                    ok = key.encode() in raw
                    break
        if not ok:
            continue
        c = cache / f'{f.stem}.pkl' if cache else None
        if c and c.exists():
            m = pickle.loads(c.read_bytes())
        else:
            try:
                m = LD.read(f)
            except Exception as exc:                              # a truncated / odd log: skip, say so
                print(f'skip {f.name}: {exc!r}'[:160], file=sys.stderr)
                continue
            if c:
                c.write_bytes(pickle.dumps(m))
        if not m['samples']:
            print(f'skip {f.name}: no decisions', file=sys.stderr)
            continue
        mem = M.build(m['side'], m['samples'], m['plays'])
        yield dict(T=m['last'] + 1, off=LIVE_OFF, ev=mem.events(M.NEVER), at=mem.events)


def _mt(x, y):
    """hab coordinates (engine millitiles, or tiles in older rows; ape_score.hab_match) -> engine millitiles."""
    return (x, y) if max(abs(x), abs(y)) > 100 else (x * 1000.0, y * 1000.0)


def sim_match(r, h):
    """One gap.py --record-board row -> a match dict. hab samples (1 s): [tick, ., ., ., own elixir, towers [side, type[0], x, y,
    hp], ...]; plays [decision tick, landing tick, card, accepted, why, elixir, cell x, cell y, engine X, Y]. Tower max HP = the
    most it ever shows (towers start full and never heal)."""
    L = int(h['L'])
    mx = defaultdict(float)
    for s in h['samples']:
        for tw in s[5]:
            mx[tw[0], tw[2], tw[3]] = max(mx[tw[0], tw[2], tw[3]], tw[4])
    samples = []
    for s in h['samples']:
        rows = [dict(side=tw[0], type='king' if tw[1] == 'k' else 'princess', x=_mt(tw[2], tw[3])[0], y=_mt(tw[2], tw[3])[1],
                     hp=tw[4], max_hp=mx[tw[0], tw[2], tw[3]]) for tw in s[5]]
        hp, al = M.tower_reads_engine(rows, L)
        samples.append(dict(tick=int(s[0]), towers=hp, alive=al, elixir=s[4]))
    plays = [dict(tick=int(q[1] if q[1] is not None else q[0]), side=sd, card=str(q[2]), accepted=bool(q[3]),
                  elixir_before=q[5], **dict(zip('xy', _mt(q[8], q[9]))))
             for sd, qs in ((L, h['own']), (1 - L, h['opp'])) for q in qs]
    mem = M.build(L, samples, plays)
    return dict(T=int(r.get('end_tick') or samples[-1]['tick'] + 1), off=0, ev=mem.events(M.NEVER), at=mem.events)


def sim_matches(d):
    import xbow_count as XC
    for r, h in XC.rows(d):
        yield sim_match(r, h)


def _table_events(vals, P, a, b, voc):
    """Table rows a..b -> match_memory.events-shaped dicts (final outcomes) + _vis / _mask / _done for the causal view. The
    table keeps reach as yes / no (not the princess indices) and a tower Rocket's aim as yes / no (aim = -1)."""
    out = []
    for i, v in zip(range(a, b), vals[a:b].tolist()):
        f = (lambda k: v[C[k]])
        mine, tick, vis, r = f('mine') > .5, int(P['tick'][i]), int(P['vis'][i]), P['res'][i].tolist()
        if f('is_tower_damage') > .5 or f('is_tower_fall') > .5:
            k = 0 if f('tower_k') > .5 else 1 if f('tower_l') > .5 else 2
            dmg = f('is_tower_damage') > .5
            out.append(dict(type='tower_damage' if dmg else 'tower_fall', tick=tick, mine=mine, tower=(0 if mine else 3) + k,
                            lost=f('tower_lost') if dmg else None, _vis=vis, _mask=(), _done=0))
            continue
        e = dict(type='ability' if f('is_ability') > .5 else 'play', tick=tick, seen=vis - 1, mine=mine,
                 card=voc[int(P['card'][i])], form=int(P['form'][i]), xy=(f('x'), f('y')) if f('xy_known') > .5 else None,
                 el=f('elixir_10') * 10 if f('elixir_known') > .5 else None, cost=f('cost_10') * 10,
                 crowns=(round(f('crowns_me_3') * 3), round(f('crowns_opp_3') * 3)),
                 margin=f('margin_2') * 2 if f('margin_known') > .5 else None,
                 out=dict(enemy_lost=f('out_enemy_lost') if f('out_tower_known') > .5 else None,
                          own_lost=f('out_own_lost') if f('out_tower_known') > .5 else None,
                          value=f('out_value_10') * 10 if f('out_value_known') > .5 else None))
        mask = [('out', r[1])]
        if e['type'] == 'play' and e['card'] == 'x-bow':
            e['reach'] = f('xb_reach') > .5
            e['xb'] = dict(locked=f('xb_locked') > .5, damage=float(P['xb_dmg'][i])) if e['reach'] else None
            e['answer'] = (voc[int(P['ans_card'][i])] if P['flag'][i] & 4 else '') if f('xb_answer_done') > .5 else None
            mask += [('xb', r[2])] * e['reach'] + [('answer', r[3])] * (e['answer'] is not None)
        if f('is_xb_answer') > .5:
            e['is_answer'] = True
            mask.append(('is_answer', r[4]))
        if e['type'] == 'play' and mine and e['card'] == 'rocket':
            e['aim'] = -1 if f('rk_tower') > .5 else None
            e['rk'] = dict(tower_lost=f('rk_tower_lost') if f('rk_tower_known') > .5 else None,
                           value=f('rk_value_10') * 10 if f('rk_value_known') > .5 else None, combo=f('rk_combo') > .5)
            mask.append(('rk', r[5]))
        e.update(_vis=vis, _mask=mask, _done=max(x for _, x in mask))
        out.append(e)
    return out


def _view(evs):
    """events(t) of a table match: visible rows, outcomes whose window is still open masked (None; is_answer dropped)."""
    ticks = [e['tick'] for e in evs]

    def at(t):
        out = []
        for e in evs[:bisect.bisect_left(ticks, t)]:
            if e['_vis'] > t:
                continue
            if t < e['_done']:
                e = dict(e)
                for k, rt in e['_mask']:
                    if t < rt:
                        e[k] = None
                if e.get('is_answer') is None:
                    e.pop('is_answer', None)
            out.append(e)
        return out
    return at


def pro_matches(tables, dataset):
    """Pro sides that played an X-Bow, from the memory tables; match end = the side's last dataset row tick (rows every <= 2 s)."""
    z = np.load(tables)
    voc = json.loads(str(z['meta']))['card_vocab']
    P = {k: z['tab_' + k] for k in ('tick', 'vis', 'res', 'card', 'form', 'ans_card', 'flag', 'xb_dmg', 'off')}
    vals = z['tab_vals']
    off = P['off']
    n = len(off) - 1
    T = np.zeros(n, np.int64)
    np.maximum.at(T, z['row_tab'], np.load(dataset)['tick'])
    own = (vals[:, C['is_play']] > .5) & (vals[:, C['mine']] > .5)
    tab = np.repeat(np.arange(n), np.diff(off))
    cards = defaultdict(set)
    for j, c in zip(tab[own].tolist(), P['card'][own].tolist()):
        cards[j].add(voc[c])
    for j in sorted(j for j, cs in cards.items() if 'x-bow' in cs):
        evs = _table_events(vals, P, int(off[j]), int(off[j + 1]), voc)
        yield dict(T=int(T[j]) + 1, off=0, ev=evs, at=_view(evs),
                   icebow8=cards[j] <= ICEBOW8 and 'tornado' in cards[j])


# ------------------------------------------------------------------------------------------------------------ metrics
def per_match(m, score_fn):
    """-> {(metric, row, stat): [num, den]} for one match (den 0 = the match has no such moment)."""
    ev, T, off = m['ev'], m['T'], m['off']
    out = defaultdict(lambda: [0.0, 0.0])
    grid = list(range(off, T, GRID))
    marg = [margin_hp(h, a) for h, a in towers_at(ev, grid)]
    own = [e for e in ev if e['type'] == 'play' and e['mine']]
    rxb = [e['tick'] for e in own if e['card'] == 'x-bow' and e.get('reach')]
    lk = [e['tick'] for e in own if e['card'] == 'x-bow' and e.get('reach') and e.get('xb') and e['xb']['locked']]
    trk = [e['tick'] for e in own if e['card'] == 'rocket' and e.get('aim') is not None]
    cnt = (lambda ts, lo, hi: bisect.bisect_left(ts, hi) - bisect.bisect_left(ts, lo))     # ticks in [lo, hi)

    def add(key, num, den):
        out[key][0] += num
        out[key][1] += den
    for g, s, mg in zip(grid, scores(m, grid, score_fn), marg):
        clock = g - off
        b = f'score {sum(s >= e for e in EDGES) * .2:.1f}-{sum(s >= e for e in EDGES) * .2 + .2:.1f}'
        add(('M1', b, 'reach X-Bows / min'), cnt(rxb, g, g + GRID), 1 / 60)
        add(('M1', b, 'lock rate of those'), cnt(lk, g, g + GRID), cnt(rxb, g, g + GRID))
        if clock >= M.DOUBLE_T:
            for ph in ('2x+OT',) + ('OT',) * (clock >= M.OT_T):
                add(('M2', f'{ph} {mbin(mg)}', 'tower Rockets / min'), cnt(trk, g, g + GRID), 1 / 60)
        if mg < -BIG:
            for ph in ('all',) + ('2x+OT',) * (clock >= M.DOUBLE_T):
                add(('M3', ph, 'reach X-Bow within 30 s'), cnt(rxb, g, g + LOOK) > 0, 1)
                add(('M3', ph, 'LOCKED reach X-Bow within 30 s'), cnt(lk, g, g + LOOK) > 0, 1)
                j = bisect.bisect_left(trk, g)
                add(('M3', ph, 'tower Rocket later'), j < len(trk), 1)
                if j < len(trk):
                    add(('M3', ph, 'lock placed before that Rocket'), cnt(lk, g, trk[j]) > 0, 1)
    fall = min([e['tick'] for e in ev if e['type'] == 'tower_fall' and e['mine'] and e['tower'] in (1, 2)] + [T])
    dmg = [e for e in ev if e['type'] == 'tower_damage' and e['mine'] and e['tick'] < fall]
    kd = [e['tick'] for e in dmg if e['tower'] == 0]
    torn = [e['tick'] for e in own if e['card'] == 'tornado' and e['tick'] < fall]
    act = kd[0] if kd else None
    pre = act is not None and any(act - TORN_PRE <= q <= act for q in torn)
    king = sum(e['lost'] for e in dmg if e['tower'] == 0) * KING_HP
    prin = sum(e['lost'] for e in dmg if e['tower'] != 0) * PRINCESS_HP
    add(('M4', 'both up', 'king activated (share of matches)'), act is not None, 1)
    add(('M4', 'both up', 'activation after own Tornado <= 5 s'), pre, act is not None)
    add(('M4', 'both up', 'Tornado-preceded activation (matches)'), pre, 1)
    add(('M4', 'both up', 'own Tornados -> king hit <= 5 s'), sum(cnt(kd, q, q + TORN_PRE + 1) > 0 for q in torn), len(torn))
    add(('M4', 'both up', 'king HP lost / match'), king, 1)
    add(('M4', 'both up', 'king share of own tower HP lost'), king, king + prin)
    return out


def _order(k):
    i = next((i for i, b in enumerate(MBINS) if k[1].endswith(b)), 0)
    return k[0], k[1][:len(k[1]) - len(MBINS[i])] if k[1].endswith(MBINS[i]) else k[1], i, k[2]


def report(name, R, boot, seed=0):
    keys = sorted({k for r in R for k in r}, key=_order)
    n = len(R)
    print(f'## {name}: {n} matches')
    if not n:
        return
    idx = np.random.default_rng(seed).integers(0, n, (boot, n))
    for k in keys:
        num = np.array([r[k][0] if k in r else 0.0 for r in R])
        den = np.array([r[k][1] if k in r else 0.0 for r in R])
        if den.sum() <= 0:
            continue
        bn, bd = num[idx].sum(1), den[idx].sum(1)
        lo, hi = np.percentile(bn[bd > 0] / bd[bd > 0], (2.5, 97.5))
        unit = 'min' if k[2].endswith('/ min') else 'n'
        print(f'  {k[0]} {k[1]:22s} {k[2]:38s} {num.sum() / den.sum():8.3f} [{lo:.3f}, {hi:.3f}]  ({num.sum():.0f} / '
              f'{den.sum():.1f} {unit}, {int((den > 0).sum())} matches)')


# ------------------------------------------------------------------------------------------------------------ self-check
def selfcheck():
    full, up = (1.0,) * 6, (True,) * 6
    assert margin_hp(full, up) == 0 and mbin(0) == 'level'
    assert abs(margin_hp((1, .5, 1, 1, 1, 1), up) + .5 * PRINCESS_HP) < 1e-6 and mbin(-.5 * PRINCESS_HP) == 'behind > 2000'
    assert margin_hp((1, 0, 1, 1, .9, 1), (True, False, True, True, True, True)) == -.9 * PRINCESS_HP   # a crown down
    assert abs(margin_hp((1, 0, .8, 1, .4, 0), (True, False, True, True, True, False)) - .4 * PRINCESS_HP) < 1e-6   # 1-1
    assert [mbin(x) for x in (547, 546, -546, -547, -2000, -2001)] == \
        ['ahead', 'level', 'level', 'behind small', 'behind small', 'behind > 2000']
    ev = [dict(type='tower_damage', tick=100, mine=True, tower=1, lost=.3), dict(type='tower_fall', tick=200, mine=False, tower=4)]
    t = towers_at(ev, [100, 101, 201])
    assert t[0][0][1] == 1.0 and abs(t[1][0][1] - .7) < 1e-9 and t[2][1][4] is False and t[1][1][4] is True
    # a synthetic gap.py --record-board row through the SIM adapter + every metric: side 0 (own king y 3000), one reach X-Bow at
    # tick 100 that locks the enemy left princess (-8 % by tick 400), one tower Rocket on it at tick 2500, own L princess -2,500 HP
    # (level 11 3052 max -> 82 % = 3,980 level-16 HP) from tick 1000 on -> behind > 2000 from then.
    def tw(t):
        return [[0, 'k', 9000, 3000, 4824], [0, 'p', 3500, 6500, 3052 if t < 1000 else 552], [0, 'p', 14500, 6500, 3052],
                [1, 'k', 9000, 29000, 4824], [1, 'p', 3500, 25500, 3052 if t < 400 else 2800], [1, 'p', 14500, 25500, 3052]]
    h = dict(L=0, samples=[[t, None, None, None, 5.0, tw(t), [], []] for t in range(0, 3000, 20)],
             own=[[100, 100, 'Xbow', True, '', 6.0, 0, 0, 3500, 15500], [2500, 2520, 'Rocket', True, '', 6.0, 0, 0, 3500, 25500]],
             opp=[])
    m = sim_match(dict(end_tick=3000), h)
    xb = [e for e in m['ev'] if e.get('card') == 'x-bow']
    assert len(xb) == 1 and xb[0]['reach'] and xb[0]['xb']['locked'], xb
    r = per_match(m, dummy_score)
    assert r['M1', 'score 0.4-0.6', 'reach X-Bows / min'][0] == 1 and r['M1', 'score 0.4-0.6', 'lock rate of those'] == [1, 1]
    assert r['M2', '2x+OT behind > 2000', 'tower Rockets / min'][0] == 1
    assert r['M3', 'all', 'tower Rocket later'][0] > 0 and r['M3', 'all', 'lock placed before that Rocket'][0] == 0  # lock < 1000
    assert r['M4', 'both up', 'king activated (share of matches)'] == [0, 1]
    # the pro table view: an outcome is masked until its window closes
    e = dict(type='play', tick=10, mine=True, card='x-bow', reach=True, xb=dict(locked=True), _vis=11, _mask=[('xb', 611)], _done=611)
    v = _view([e])
    assert v(11)[0]['xb'] is None and v(611)[0]['xb']['locked'] and v(10) == []


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n', 1)[0])
    ap.add_argument('--live', nargs='*', default=[], help='live checkpoint substrings (start event ckpt)')
    ap.add_argument('--sim', nargs='*', default=[], help='NAME=DIR, DIR holding */D3/matches.jsonl with hab rows')
    ap.add_argument('--pro', action='store_true', help='the pro memory tables (X-Bow sides; icebow8 subset)')
    ap.add_argument('--pro-tables', default=str(REPO / 'icebow/data/pipeline/gen_dataset_v32_fv5_memory_v1.npz'))
    ap.add_argument('--pro-dataset', default=str(REPO / 'icebow/data/pipeline/gen_dataset_v32_fv5.npz'))
    ap.add_argument('--score', default='', help='MODULE:FUNC, f(events, t) -> float (default: the dummy)')
    ap.add_argument('--cache', type=Path, help='live: pickle each read log here (re-runs skip live_dump.read)')
    ap.add_argument('--boot', type=int, default=1000)
    a = ap.parse_args()
    selfcheck()
    fn = dummy_score
    if a.score:
        mod, fun = a.score.split(':')
        fn = getattr(importlib.import_module(mod), fun)
    print(f'# gate_metrics (score: {a.score or "DUMMY running lock rate"}; margin = weakest-princess race, level-16 HP)')
    if a.cache:
        a.cache.mkdir(parents=True, exist_ok=True)
    for key in a.live:
        report(f'LIVE {key}', [per_match(m, fn) for m in live_matches(key, a.cache)], a.boot)
    for arg in a.sim:
        name, d = arg.split('=', 1)
        report(f'SIM {name}', [per_match(m, fn) for m in sim_matches(d)], a.boot)
    if a.pro:
        R = [(m['icebow8'], per_match(m, fn)) for m in pro_matches(a.pro_tables, a.pro_dataset)]
        report('PRO X-Bow sides (any deck)', [r for _, r in R], a.boot)
        report('PRO icebow8 sides (own plays all in the icebow 8, X-Bow + Tornado played)', [r for i, r in R if i], a.boot)


if __name__ == '__main__':
    main()
