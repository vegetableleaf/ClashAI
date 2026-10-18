"""L74/habits shared definitions (live, pros, SIM use the SAME code). Positions: the X-Bow player's OWN frame, tiles (own king
y 29, own princess line 25.5, river 16, enemy princess line 6.5, enemy king 3); x mirrored with y, so lanes are consistent
within a match. A match is a dict:
  src, group (Mark / pro source / SIM arm), win (1 / 0 / .5), key (id),
  own: [dict(tick, card, x, y, why)]   opp: [dict(tick, card, x, y)]      (card = snake_case base key)
  frames (optional): [(tick, towers {(own|opp, K|L|R): hp}, enemy bodies [(bid, key, form, hp, max_hp, x, y)],
                       own buildings [(bid, key, hp, x, y)])]
  est (optional): callable tick -> the opponent-elixir counter the model sees (live / SIM); else rebuilt from opp plays.
  truth (optional): callable tick -> the opponent's true elixir (SIM only).
  hand (optional): callable tick -> (own hand card keys, own elixir) at the last decision <= tick (live / SIM)."""
from __future__ import annotations

import bisect
import math
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO))
from pipeline.opp_elixir_count import OppElixirCounter, card_db  # noqa: E402

BRIDGE_Y = (16.0, 20.5)      # offensive (bridge) X-Bow: live intended y <= 0.64 (card_use OFFENSIVE_Y) = 20.48 tiles; < 16 = pocket
BACK_Y = 7.0                 # "in the back" = behind the enemy princess line (centre 6.5) in our frame
OUR_HALF_Y = 16.0
HEAVY_COST = 5               # heavy card = a troop of cost >= 5 (MK, PEKKA, Golem, Giant, E-Giant, RG, Sparky, Bowler, ...)
BIG_SPELLS = {'rocket', 'lightning', 'fireball', 'poison', 'earthquake'}
CHEAP_COST = 3
PUNISH_TICKS = 160           # "what the opponent did next": 8 s
BACK_TICKS = 100             # "just spent big in the back": the last 5 s
AT_XBOW_TILES = 7.0          # a play "on / at the X-Bow": within 7 tiles of it (X-Bow range 11.5; a bridge drop is ~3-4 away)
PUSH_VALUE = 10.0
PUSH_WINDOW = 300            # play-based push: opponent troop elixir within the trailing 15 s
PUSH_COOLDOWN = 400          # no new push event within 20 s of the last
RESP = (-100, 200)           # our response window around a push event: 5 s before .. 10 s after
TICK_S = 0.05


def norm(card) -> str:
    """Any spelling (live 'Xbow' / 'IceWizard' / 'Log', SIM 'knight_evo', pro 'x-bow', engine 'mega_knight') -> base key."""
    s = str(card).split('@')[0]
    s = re.sub(r'(?<=[a-z])(?=[A-Z])', '_', s).lower().replace('-', '_')
    s = re.sub(r'_(evo|ev1|ev2|hero)$', '', s)
    return {'xbow': 'x_bow', 'log': 'the_log', 'icewizard': 'ice_wizard', 'x_bow': 'x_bow'}.get(s, s)


_C = {}


def cost(k):
    if k not in _C:
        try:
            c = card_db().elixir(k)
        except Exception:                      # noqa: BLE001
            c = None
        _C[k] = float(c) if c is not None else (3.0 if k != 'mirror' else 0.0)
    return _C[k]


_K = {}


def kind(k):
    if k not in _K:
        try:
            _K[k] = card_db().kind(k)
        except Exception:                      # noqa: BLE001
            _K[k] = None
    return _K[k]


def band(e):
    return None if e is None else '<=3' if e < 3.5 else '4-6' if e < 6.5 else '>=7'


def counter_fn(opp):
    """Opponent elixir from its plays (OppElixirCounter, the live schedule): tick -> estimate (plays at that tick excluded)."""
    c = OppElixirCounter()
    marks = []
    for p in sorted(opp, key=lambda p: p['tick']):
        marks.append((p['tick'], c.at(p['tick'])))     # before the play
        c.play(p['tick'], p['card'], cost(p['card']))
        marks.append((p['tick'] + 1e-3, c.est))
    ts = [t for t, _ in marks]

    def at(t):
        i = bisect.bisect_right(ts, t) - 1
        if i < 0:
            return OppElixirCounter().at(int(t))
        t0, e = marks[i]
        from pipeline.opp_elixir_count import regen_between, MAX_ELIXIR
        return min(MAX_ELIXIR, e + regen_between(t0, t))
    at.rebases = c.rebases
    return at


def is_bridge_xbow(q):
    return q['card'] == 'x_bow' and q['y'] is not None and BRIDGE_Y[0] <= q['y'] <= BRIDGE_Y[1]


def xbow_body(m, q):
    """The own X-Bow body of play q in m['frames']: first seen within 60 ticks after q within 2.5 tiles -> (first, last, bid)."""
    fr = m.get('frames')
    if not fr:
        return None
    ts = [f[0] for f in fr]
    i = bisect.bisect_left(ts, q['tick'] - 30)
    cand = None
    for f in fr[i:]:
        if f[0] > q['tick'] + 60:
            break
        for bid, k, hp, x, y in f[3]:
            if k == 'x_bow' and math.hypot(x - q['x'], y - q['y']) <= 2.5:
                prior = [g for g in fr[max(0, i - 40):i] if any(b[0] == bid for b in g[3])]
                if not prior:
                    cand = bid
                    break
        if cand:
            break
    if cand is None:
        return None
    seen = [f[0] for f in fr[i:] if any(b[0] == cand for b in f[3])]
    return seen[0], seen[-1], cand


def tower_sum(towers, who):
    return sum(towers.get((who, s), 0) for s in 'KLR')


def tower_at(m, t):
    """Towers at the last frame <= t; a tower missing after the first frame counts 0 (destroyed)."""
    fr = m['frames']
    ts = [f[0] for f in fr]
    i = max(0, bisect.bisect_right(ts, t) - 1)
    return fr[i][1]


def xbow_events(m):
    """One row per own bridge X-Bow (A): the counter the model saw, back spend, the opponent's next 8 s, life, damage, result."""
    est = m.get('est') or counter_fn(m['opp'])
    own = sorted(m['own'], key=lambda q: q['tick'])
    rows, first_done = [], False
    for i, q in enumerate(own):
        if not is_bridge_xbow(q):
            continue
        t = q['tick']
        e = q.get('est_model')
        e = est(t) if e is None else e
        back = [p for p in m['opp'] if t - BACK_TICKS <= p['tick'] <= t and p['y'] is not None and p['y'] <= BACK_Y
                and cost(p['card']) >= 4 and kind(p['card']) != 'spell']
        spent5 = sum(cost(p['card']) for p in m['opp'] if t - BACK_TICKS <= p['tick'] <= t)
        nxt = [p for p in m['opp'] if t < p['tick'] <= t + PUNISH_TICKS]
        at = [p for p in nxt if p['x'] is not None and math.hypot(p['x'] - q['x'], p['y'] - q['y']) <= AT_XBOW_TILES]
        heavy = [p for p in at if (kind(p['card']) == 'troop' and cost(p['card']) >= HEAVY_COST) or p['card'] in BIG_SPELLS]
        r = dict(group=m['group'], key=m['key'], win=m['win'], tick=t, idx=i, first=not first_done, early=i < 2,
                 est=round(e, 2), band=band(e), truth=None if m.get('truth') is None else round(m['truth'](t), 2),
                 punish=bool(back), back_cost=sum(cost(p['card']) for p in back), spent5=spent5,
                 next_at=sum(cost(p['card']) for p in at), heavy=bool(heavy), heavy_cards=[p['card'] for p in heavy])
        first_done = True
        b = xbow_body(m, q)
        if b:
            f0, f1, bid = b
            T0, T1 = tower_at(m, f0), tower_at(m, f1)
            r.update(life_s=round((f1 - f0) * TICK_S, 1), dmg=tower_sum(T0, 'opp') - tower_sum(T1, 'opp'),
                     taken=tower_sum(T0, 'own') - tower_sum(T1, 'own'), end_tick=f1)
        rows.append(r)
    return rows


def push_events(m):
    """Play-based heavy pushes (B; same rule for live, pros, SIM): the opponent's TROOP elixir played in the trailing 15 s
    first reaches PUSH_VALUE (cooldown 20 s). Our response in RESP; outcome = tower HP we lost in 20 s (frames), result."""
    opp = sorted([p for p in m['opp'] if kind(p['card']) == 'troop'], key=lambda p: p['tick'])
    ev, last = [], -10 ** 9
    for j, p in enumerate(opp):
        win_ = [o for o in opp[:j + 1] if p['tick'] - o['tick'] <= PUSH_WINDOW]
        v = sum(cost(o['card']) for o in win_)
        if v >= PUSH_VALUE and p['tick'] - last > PUSH_COOLDOWN:
            ev.append((p['tick'], v, win_))
            last = p['tick']
    rows = []
    hand = m.get('hand')
    for t, v, plays in ev:
        ours = [q for q in m['own'] if t + RESP[0] <= q['tick'] <= t + RESP[1]]
        cards = [q['card'] for q in ours]
        rk = [q for q in ours if q['card'] == 'rocket']
        tn = [q for q in ours if q['card'] == 'tornado']
        combo = any(abs(a['tick'] - b['tick']) <= 60 for a in rk for b in tn)
        cheap = [q for q in ours if cost(q['card']) <= CHEAP_COST]
        resp = 'rocket+tornado' if combo else 'rocket' if rk else 'cheap_only' if ours and len(cheap) == len(ours) else \
            'none' if not ours else 'other'
        r = dict(group=m['group'], key=m['key'], win=m['win'], tick=t, value=v, cards=sorted({o['card'] for o in plays}),
                 resp=resp, n_cheap=len(cheap), spent=sum(cost(c) for c in cards), ours=cards)
        if hand:
            h, el = hand(t)
            r.update(rocket_in_hand=h is not None and 'rocket' in h, own_el=el)
        if m.get('frames'):
            T0, T1 = tower_at(m, t), tower_at(m, t + 400)
            r.update(taken=tower_sum(T0, 'own') - tower_sum(T1, 'own'),
                     lost_tower=sum(T0.get(('own', s), 0) > 0 and T1.get(('own', s), 0) <= 0 for s in 'KLR'))
        rows.append(r)
    return rows


def rocket_uses(m):
    """C: each own Rocket by aim (tower = blast on an enemy princess / king slot; defence = our half; else enemy-half troops) and
    the decision rule that played it (why: lethal_rocket / rocket_tornado / None = the model)."""
    out = []
    for q in m['own']:
        if q['card'] != 'rocket' or q['y'] is None:
            continue
        x, y = q['x'], q['y']
        tower = any(math.hypot(x - tx, y - ty) <= 3.0 for tx, ty in ((3.5, 6.5), (14.5, 6.5), (9.0, 3.0)))
        aim = 'tower' if tower else 'defence' if y >= OUR_HALF_Y - 1 else 'enemy_half'
        out.append(dict(group=m['group'], key=m['key'], win=m['win'], tick=q['tick'], aim=aim, why=q.get('why'),
                        late=q['tick'] >= 2400))
    return out


def boot_ci(xs, f, B=2000, seed=0, groups=None):
    """Match-cluster bootstrap 95% CI of f over rows xs (rows of one match resampled together via r['key'])."""
    import random
    rng = random.Random(seed)
    by = {}
    for r in xs:
        by.setdefault(r['key'], []).append(r)
    keys = list(by)
    B = B if len(keys) < 1500 else 300
    if not keys:
        return (float('nan'), float('nan'))
    vals = []
    for _ in range(B):
        s = [r for k in (rng.choice(keys) for _ in keys) for r in by[k]]
        try:
            vals.append(f(s))
        except ZeroDivisionError:
            pass
    vals.sort()
    if not vals:
        return (float('nan'), float('nan'))
    return round(vals[int(.025 * len(vals))], 3), round(vals[int(.975 * len(vals)) - 1], 3)


def mean(xs):
    xs = [x for x in xs if x is not None]
    return sum(xs) / len(xs) if xs else float('nan')


def wr(rows):
    return mean([r['win'] for r in rows])
