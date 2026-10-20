"""W5 investment-card study: ONE extractor for live matches and pro replays (same code for both).

Match dict (built by live_matches / pro_matches; hablib conventions):
  src 'live'|'pro', group (Mark short name | 'pro'), key, win 1/0/.5, end (clock tick),
  own / opp: [dict(tick, card, x, y)]  (clock ticks: live game_tick - 78, pro replay tick; own-frame tiles: own king y 29,
             own princesses y 25.5, river 16, enemy princesses y 6.5, enemy king y 3; x mirrored with y)
  frames: [(tick, towers {(own|opp, K|L|R): hp}, enemy bodies [(key, hp, x, y)], own x_bows [(bid|None, hp, max|None, x, y)])]
  tmax {(own|opp, slot): max hp}, hand(t) -> (set of own hand card keys, own elixir) or None.
Live frames are the reader's real frames. PRO FRAMES ARE A NATIVE-ENGINE RE-DRIVE of the recorded plays (corpus_v6/icebow,
level 11 both sides, open loop; 76% of re-drives end with the recorded crowns): pro X-Bow / Rocket OUTCOMES are a
counterfactual estimate, pro DECISIONS and match results are real."""
from __future__ import annotations

import bisect
import glob
import json
import math
import pickle
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
L74 = HERE.parent
REPO = L74.parents[2]
sys.path.insert(0, str(L74 / 'habits'))
import hablib as H  # noqa: E402

LIVE_CLOCK_OFF = 78               # live game_tick = clock + 78 (doctrine/DOCTRINE_MEASURED.md "Live clock")
NATIVE = REPO / 'scratchpad/gauntlet/ext/corpus_v6/icebow'
PRO_MODES = ('pathOfLegend', 'pathOfLegend/Ranked')
I8 = {'tornado', 'tesla', 'ice_wizard', 'x_bow', 'rocket', 'knight', 'the_log', 'skeletons'}
TICK_S = 0.05
AT_XBOW = 7.0                     # a play "at" the X-Bow (hablib AT_XBOW_TILES)
LOCK_MIN = 0.05                   # "locked": enemy towers lost >= 5% of a princess while it lived (~3-4 bolts)
NEXT = 400                        # "the next 20 s"
REACH = 13.5                      # X-Bow centre -> tower centre it can hit (row 19.5 in lane: 13.04; centre 8.5,19.5 -> 13.9 no)
BRIDGE_MAX_Y = 20.5               # hablib BRIDGE_Y upper edge: rows 18.5 / 19.5 reach a princess, 21.5+ do not
TOWER_XY = {'L': (3.5, 6.5), 'R': (14.5, 6.5), 'K': (9.0, 3.0)}
SHORT = {'ICEBOW Mark CXXXVIII: CUES': 'CXXXVIII', 'ICEBOW Mark CLIII: LEVELS': 'CLIII', 'ICEBOW Mark CLIX: PRESS': 'CLIX',
         'ICEBOW Mark CLX: PARITY': 'CLX'}


def xtype(y):
    return None if y is None else 'pocket' if y < 16 else 'bridge' if y <= BRIDGE_MAX_Y else 'defensive'


# ------------------------------------------------------------------------------------------------------------ loaders
def live_matches(marks=None, index=None):
    idx = json.load(open(index or HERE / 'index.json'))     # index: another build_live-format index (W10 rocket/)
    for name, v in sorted(idx.items()):
        g = SHORT.get(v['mark'])
        if g is None or (marks and g not in marks):
            continue
        p = L74 / 'habits/cache' / (Path(name).stem + '.pkl')
        if not p.exists():
            continue
        c = pickle.load(open(p, 'rb'))
        o = LIVE_CLOCK_OFF
        frames = [(t - o, T, [(k, hp, x, y) for _, k, _, hp, _, x, y in en],
                   [(bid, hp, None, x, y) for bid, k, hp, x, y in ob if k == 'x_bow']) for t, T, en, ob in c['frames']]
        if not frames:
            continue
        tmax = dict(frames[0][1])
        dec = [(t - o, h, el) for t, h, el, *_ in c['dec']]
        dts = [d[0] for d in dec]

        def hand(t, dec=dec, dts=dts):
            i = bisect.bisect_right(dts, t) - 1
            return None if i < 0 else ({H.norm(x) for x in dec[i][1] if x}, dec[i][2])
        yield dict(src='live', group=g, key=name, win={'WIN': 1.0, 'LOSS': 0.0}.get(v['result'], .5),
                   end=frames[-1][0],
                   own=[dict(tick=q['tick'] - o, card=H.norm(q['name']), x=q['x'], y=q['y'], why=q.get('why')) for q in c['own']
                        if q['name']],
                   opp=[dict(tick=p['tick'] - o, card=H.norm(p['card']), x=p['x'], y=p['y']) for p in c['opp']],
                   frames=frames, tmax=tmax, hand=hand, xbow_track='bid')


def _pro_meta():
    out = {}
    for line in open(L74 / 'habits/pro_sides.jsonl', encoding='utf-8'):
        r = json.loads(line)
        if r['icebow8'] and r['mode'] in PRO_MODES:
            out.setdefault(r['tag'], []).append(r)
    return {t: v[0] for t, v in out.items() if len(v) == 1}       # mirrors (two icebow8 sides) dropped


def pro_matches(limit=None):
    meta = _pro_meta()
    files = sorted(glob.glob(str(NATIVE / 'replay_*.json')))
    n = 0
    for f in files:
        tag = Path(f).stem[7:]
        mt = meta.get(tag)
        if mt is None:
            continue
        d = json.load(open(f))
        fd = {int(k): {H.norm(c) for c in v} for k, v in d['final_decks'].items()}
        sides = [s for s, v in fd.items() if v == I8]
        if len(sides) != 1:
            continue
        s = sides[0]
        rot = s == 0                                             # own king at low engine y -> rotate to the own frame

        def tr(x, y, rot=rot):
            return ((18000 - x) / 1000, (32000 - y) / 1000) if rot else (x / 1000, y / 1000)

        own, opp, hands = [], [], []
        for p in d['log']:
            if not p.get('accepted') or p.get('x') is None:
                continue
            x, y = tr(p['x'], p['y'])
            row = dict(tick=p['tick'], card=H.norm(p['card']), x=x, y=y)
            if p['side'] == s:
                own.append(row)
                hands.append((p['tick'], {H.norm(c) for c in p.get('hand_before') or []}))
            else:
                opp.append(row)
        frs = sorted(d['frames'] + d.get('play_frames', []), key=lambda f: f['tick'])
        frames, tmax = [], {}
        for fr in frs:
            T = {}
            for ts, typ, lane, x, y, hp, mx in fr['towers']:
                X = tr(x, y)[0]
                k = ('own' if ts == s else 'opp', 'K' if typ == 'king' else 'L' if X < 9 else 'R')
                T[k] = hp
                tmax[k] = mx
            en, xb = [], []
            for e in fr['entities']:
                es, x, y, name, hp, mx = e[:6]
                if name == '-1':
                    continue
                X, Y = tr(x, y)
                if es != s:
                    en.append((H.norm(name), hp, X, Y))
                elif name == 'Xbow':
                    xb.append((None, hp, mx, X, Y))
            if frames and frames[-1][0] == fr['tick']:
                continue
            frames.append((fr['tick'], T, en, xb))
        if not frames:
            continue
        el_t = [f['tick'] for f in frs]
        el_v = [f['elixir'][s] for f in frs]
        h_t = [h[0] for h in hands]

        def hand(t, el_t=el_t, el_v=el_v, hands=hands, h_t=h_t):
            i = bisect.bisect_right(h_t, t)              # hand at t = hand_before of the next own play
            j = bisect.bisect_right(el_t, t) - 1
            if i >= len(hands) or j < 0:
                return None
            return hands[i][1], el_v[j]
        yield dict(src='pro', group='pro', key=tag, win=mt['win'], end=frames[-1][0], own=own, opp=opp, frames=frames,
                   tmax=tmax, hand=hand, xbow_track='pos', rating=mt.get('rating'), psrc=mt['src'],
                   crowns_match=bool(d['grade'].get('crowns_match')), opp_deck_true=mt['opp_deck'])
        n += 1
        if limit and n >= limit:
            return


# ---------------------------------------------------------------------------------------------------------- helpers
def _tower_at(m, t):
    fr = m['frames']
    ts = m.setdefault('_ts', [f[0] for f in fr])
    i = max(0, bisect.bisect_right(ts, t) - 1)
    return fr[i][1]


def tower_loss(m, who, t0, t1):
    """Tower HP `who` lost over [t0, t1], in princess-tower units (1.0 = one full princess)."""
    a, b = _tower_at(m, t0), _tower_at(m, t1)
    pm = m['tmax'].get((who, 'L')) or 1
    return sum(max(0, a.get((who, s), 0) - b.get((who, s), 0)) for s in 'KLR') / pm


def crowns(m, t):
    T = _tower_at(m, t)
    down = lambda who: sum(T.get((who, s), 0) <= 0 for s in 'LR')  # noqa: E731
    return down('opp'), down('own')       # (our crowns, their crowns)


def opp_cycle(m, t):
    """Revealed opponent cards before t -> {card: plays since its last play}; a card is in hand iff that is >= 4
    (8-card deck, 4 in hand: a played card re-enters the hand after 4 more plays)."""
    seq = [p['card'] for p in sorted(m['opp'], key=lambda p: p['tick']) if p['tick'] < t]
    out = {}
    for i, c in enumerate(seq):
        out[c] = len(seq) - 1 - i
    return out


def _est(m):
    if '_est' not in m:
        m['_est'] = H.counter_fn(m['opp'])
    return m['_est']


def context(m, t):
    T = _tower_at(m, t)
    oc, tc = crowns(m, t)
    h = m['hand'](t)
    return dict(clock=round(t * TICK_S, 1), phase='1x' if t < 2400 else '2x' if t < 3600 else 'OT', our_cr=oc, their_cr=tc,
                own_el=None if h is None else round(h[1], 2), opp_est=round(_est(m)(t), 2), cycle=opp_cycle(m, t),
                own_hp=sum(T.get(('own', s), 0) for s in 'LR') / (m['tmax'].get(('own', 'L')) or 1))


def _xbow_life(m, q):
    """(first, last) frame ticks of the X-Bow body of own play q, or None."""
    fr = m['frames']
    ts = m.setdefault('_ts', [f[0] for f in fr])
    i = bisect.bisect_left(ts, q['tick'] - 30)
    if m['xbow_track'] == 'bid':
        cand = None
        for f in fr[i:]:
            if f[0] > q['tick'] + 60:
                break
            for bid, hp, mx, x, y in f[3]:
                if math.hypot(x - q['x'], y - q['y']) <= 2.5 and not any(b[0] == bid for g in fr[max(0, i - 40):i] for b in g[3]):
                    cand = bid
                    break
            if cand:
                break
        if cand is None:
            return None
        seen = [f[0] for f in fr[i:] if any(b[0] == cand for b in f[3])]
        return seen[0], seen[-1]
    first = last = None
    for f in fr[bisect.bisect_left(ts, q['tick']):]:
        hit = [b for b in f[3] if math.hypot(b[3] - q['x'], b[4] - q['y']) <= 1.5]
        if first is None:
            if f[0] > q['tick'] + 60:
                return None
            if hit and hit[0][1] >= 0.9 * hit[0][2]:
                first = last = f[0]
            continue
        if hit:
            last = f[0]
        elif f[0] - last > 40:
            break
    return None if first is None else (first, last)


# -------------------------------------------------------------------------------------------------------- extractors
def xbow_rows(m):
    rows = []
    own = sorted(m['own'], key=lambda q: q['tick'])
    prev = []
    for q in own:
        if q['card'] != 'x_bow' or q['y'] is None:
            continue
        t = q['tick']
        r = dict(src=m['src'], group=m['group'], key=m['key'], win=m['win'], tick=t, x=round(q['x'], 1), y=round(q['y'], 1),
                 type=xtype(q['y']), lane='C' if abs(q['x'] - 9) <= 1.5 else 'L' if q['x'] < 9 else 'R', n_before=len(prev),
                 prev_types=[p['type'] for p in prev], prev_locks=[p.get('lock') for p in prev], why=q.get('why'),
                 crowns_match=m.get('crowns_match'))
        r.update(context(m, t))
        life = _xbow_life(m, q)
        if life:
            f0, f1 = life
            r.update(life_s=round((f1 - f0) * TICK_S, 1), dmg=round(tower_loss(m, 'opp', f0, f1), 3),
                     taken_life=round(tower_loss(m, 'own', f0, f1), 3), end_tick=f1,
                     censored=f1 >= m['end'] - 40)
            a, b = _tower_at(m, f0), _tower_at(m, f1)
            reach = [s_ for s_, (tx, ty) in TOWER_XY.items() if math.hypot(q['x'] - tx, q['y'] - ty) <= REACH]
            r['dmg_reach'] = round(sum(max(0, a.get(('opp', s_), 0) - b.get(('opp', s_), 0)) for s_ in reach)
                                   / (m['tmax'].get(('opp', 'L')) or 1), 3)
            r['lock'] = r['dmg_reach'] >= LOCK_MIN
            ans = [p for p in m['opp'] if f0 - 20 <= p['tick'] <= f1 + 10 and p['x'] is not None
                   and math.hypot(p['x'] - q['x'], p['y'] - q['y']) <= AT_XBOW]
            r['answer'] = [p['card'] for p in ans]
            r['answer_el'] = sum(H.cost(c) for c in r['answer'])
            sup = [p for p in own if f0 < p['tick'] <= f1 and p is not q and p['x'] is not None and p['card'] != 'x_bow'
                   and math.hypot(p['x'] - q['x'], p['y'] - q['y']) <= AT_XBOW]
            r['support_el'] = sum(H.cost(p['card']) for p in sup)
            near = set()
            ts = m['_ts']
            for f in m['frames'][bisect.bisect_left(ts, f0):bisect.bisect_right(ts, f1)]:
                near |= {k for k, hp, x, y in f[2] if k and math.hypot(x - q['x'], y - q['y']) <= AT_XBOW}
            r['near'] = sorted(near)
            r['after_own20'] = round(tower_loss(m, 'own', f1, f1 + NEXT), 3)
            r['after_opp20'] = round(tower_loss(m, 'opp', f1, f1 + NEXT), 3)
        r['next_own20'] = round(tower_loss(m, 'own', t, t + NEXT), 3)
        r['next_own40'] = round(tower_loss(m, 'own', t, t + 2 * NEXT), 3)
        r['next_opp40'] = round(tower_loss(m, 'opp', t, t + 2 * NEXT), 3)
        r['princess_fell40'] = crowns(m, min(t + 2 * NEXT, m['end']))[1] > r['their_cr']
        r['next_opp20'] = round(tower_loss(m, 'opp', t, t + NEXT), 3)
        rows.append(r)
        prev.append(r)
    return rows


def rocket_rows(m):
    rows = []
    xb_alive = lambda t: bool(_frame(m, t)[3])  # noqa: E731
    for q in m['own']:
        if q['card'] != 'rocket' or q['y'] is None:
            continue
        t = q['tick']
        slot = next((s for s, (tx, ty) in TOWER_XY.items() if math.hypot(q['x'] - tx, q['y'] - ty) <= 3.0), None)
        aim = 'tower' if slot else 'defence' if q['y'] >= 15 else 'enemy_half'
        r = dict(src=m['src'], group=m['group'], key=m['key'], win=m['win'], tick=t, aim=aim, slot=slot, why=q.get('why'),
                 xbow_alive=xb_alive(t))
        r.update(context(m, t))
        if slot:
            a, b = _tower_at(m, t - 10), _tower_at(m, t + 80)
            r['tower_dmg'] = round(max(0, a.get(('opp', slot), 0) - b.get(('opp', slot), 0)) / (m['tmax'].get(('opp', 'L')) or 1), 3)
        rows.append(r)
    return rows


def _frame(m, t):
    fr = m['frames']
    ts = m.setdefault('_ts', [f[0] for f in fr])
    return fr[max(0, bisect.bisect_right(ts, t) - 1)]


def opportunities(m, step=20):
    """Every `step` ticks: X-Bow in hand and own elixir >= 6 -> context sample (no outcome; used as the denominator)."""
    out = []
    for t in range(0, int(m['end']), step):
        h = m['hand'](t)
        if h is None or 'x_bow' not in h[0] or (h[1] or 0) < 6:
            continue
        c = context(m, t)
        c.update(src=m['src'], group=m['group'], key=m['key'], win=m['win'], tick=t)
        out.append(c)
    return out


def match_row(m):
    rev = sorted({p['card'] for p in m['opp']})
    xs = [q for q in m['own'] if q['card'] == 'x_bow']
    oc, tc = crowns(m, m['end'])
    return dict(src=m['src'], group=m['group'], key=m['key'], win=m['win'], end=m['end'], revealed=rev,
                n_bridge=sum(xtype(q['y']) == 'bridge' for q in xs), n_def=sum(xtype(q['y']) == 'defensive' for q in xs),
                n_pocket=sum(xtype(q['y']) == 'pocket' for q in xs), our_cr=oc, their_cr=tc,
                crowns_match=m.get('crowns_match'), rating=m.get('rating'),
                opp_lost=round(tower_loss(m, 'opp', 0, m['end']), 3), own_lost=round(tower_loss(m, 'own', 0, m['end']), 3))


KING = (9.0, 29.0)
TORNADO_R = 5.5
BRIDGE_ATTACK_Y = (11.0, 18.5)     # an opponent troop dropped at / just behind the bridge, or already across it


def near_king(m, keys, t0, t1):
    """{unit key: closest approach (tiles) of any enemy body of that key to OUR king centre over frames in [t0, t1]}."""
    ts = m.setdefault('_ts', [f[0] for f in m['frames']])
    out = {}
    for f in m['frames'][bisect.bisect_left(ts, t0):bisect.bisect_right(ts, t1)]:
        for k, hp, x, y in f[2]:
            if k in keys:
                d = math.hypot(x - KING[0], y - KING[1])
                out[k] = min(out.get(k, 99.0), round(d, 2))
    return out


def bridge_rows(m):
    """(a) each opponent TROOP play in a lane at the bridge (x < 7 or > 11, y 11..18.5 own frame) while BOTH own princesses
    stand: our hand / elixir, our first answer within 5 s, own princess + king HP lost in the next 15 s, king hit."""
    rows = []
    own = sorted(m['own'], key=lambda q: q['tick'])
    for p in m['opp']:
        if p['x'] is None or H.kind(p['card']) != 'troop' or not (BRIDGE_ATTACK_Y[0] <= p['y'] <= BRIDGE_ATTACK_Y[1]):
            continue
        if 7 <= p['x'] <= 11:
            continue
        t = p['tick']
        T = _tower_at(m, t)
        if not all(T.get(('own', s_), 0) > 0 for s_ in 'LR'):
            continue
        h = m['hand'](t)
        resp = [q for q in own if t <= q['tick'] <= t + 100]
        tn = next((q for q in resp if q['card'] == 'tornado'), None)
        a, b = T, _tower_at(m, t + 300)
        pm = m['tmax'].get(('own', 'L')) or 1
        km = m['tmax'].get(('own', 'K')) or 1
        rows.append(dict(src=m['src'], group=m['group'], key=m['key'], win=m['win'], tick=t, card=p['card'],
                         lane='L' if p['x'] < 9 else 'R', hand=None if h is None else sorted(h[0]),
                         own_el=None if h is None else h[1], first=resp[0]['card'] if resp else None,
                         resp=[q['card'] for q in resp], tornado=None if tn is None else dict(
                             x=round(tn['x'], 1), y=round(tn['y'], 1), dt=tn['tick'] - t,
                             d_king=round(math.hypot(tn['x'] - KING[0], tn['y'] - KING[1]), 1)),
                         princess_lost=round(sum(max(0, a.get(('own', s_), 0) - b.get(('own', s_), 0)) for s_ in 'LR') / pm, 3),
                         king_lost=round(max(0, a.get(('own', 'K'), 0) - b.get(('own', 'K'), 0)) / km, 3),
                         king_hit=b.get(('own', 'K'), 0) < a.get(('own', 'K'), 0),
                         king_full_before=a.get(('own', 'K'), 0) >= km,
                         att_king_dist=near_king(m, {p['card']}, t, t + 300).get(p['card'])))
    return rows


def tornado_rows(m):
    """(b) each own Tornado: own princesses standing, enemy bodies within the radius just before the cast and the pull
    direction (toward_king = mean over them of dist(body, king) - dist(cast, king); > 0 = pulled toward OUR king),
    king / tower HP lost after, match result."""
    rows = []
    for q in m['own']:
        if q['card'] != 'tornado' or q['y'] is None:
            continue
        t = q['tick']
        f = _frame(m, t - 1)
        T = f[1]
        inr = [(k, x, y) for k, hp, x, y in f[2] if k and math.hypot(x - q['x'], y - q['y']) <= TORNADO_R]
        dk = math.hypot(q['x'] - KING[0], q['y'] - KING[1])
        tw = [math.hypot(x - KING[0], y - KING[1]) - dk for _, x, y in inr]
        a, b = T, _tower_at(m, t + 200)
        km = m['tmax'].get(('own', 'K')) or 1
        rows.append(dict(src=m['src'], group=m['group'], key=m['key'], win=m['win'], tick=t, x=round(q['x'], 1),
                         y=round(q['y'], 1), d_king=round(dk, 1), why=q.get('why'),
                         princesses_up=sum(T.get(('own', s_), 0) > 0 for s_ in 'LR'), n_in=len(inr),
                         units=sorted({k for k, _, _ in inr}), toward_king=round(sum(tw) / len(tw), 2) if tw else None,
                         king_lost10=round(max(0, a.get(('own', 'K'), 0) - b.get(('own', 'K'), 0)) / km, 3),
                         own_lost20=round(tower_loss(m, 'own', t, t + 400), 3), clock=round(t * TICK_S, 1),
                         king_full_before=a.get(('own', 'K'), 0) >= km,
                         reach_king=near_king(m, {k for k, _, _ in inr}, t, t + 200)))
    return rows


def extract(m):
    return dict(match=match_row(m), xbow=xbow_rows(m), rocket=rocket_rows(m), opp_samples=opportunities(m),
                bridge=bridge_rows(m), tornado=tornado_rows(m))


if __name__ == '__main__':          # self-check on a few matches of each source
    for src, it in (('live', live_matches({'CLX'})), ('pro', pro_matches(limit=3))):
        for k, m in zip(range(2), it):
            e = extract(m)
            print(src, m['key'], e['match'])
            for r in e['xbow']:
                print('   X', {k: r.get(k) for k in ('tick', 'type', 'lane', 'life_s', 'dmg', 'lock', 'answer', 'answer_el',
                                                    'near', 'next_own20', 'our_cr', 'their_cr', 'own_el', 'opp_est')})
            for r in e['rocket']:
                print('   R', {k: r.get(k) for k in ('tick', 'aim', 'slot', 'tower_dmg', 'xbow_alive')})
            print('   opp samples', len(e['opp_samples']))
