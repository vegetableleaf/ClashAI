"""P6-MACRO miner (plan1026 PLAN P6.1): one set of macro detectors over three sources -> episode rows (jsonl.gz).

    python -B mine.py pro  --out EP/pro.jsonl.gz                      # icebow8 pro corpus (invlib.pro_matches)
    python -B mine.py live --out EP/live.jsonl.gz                     # CLXIII live, index_clxiii.json (sealed block excluded)
    python -B mine.py hf   --rows RD/rows --hf HF/data --out EP/hf --workers 12 [--limit N]   # HF IL_Replay, crforge re-drive

Match record = invlib's dict (hablib conventions, OWN frame tiles: own king y 29, own princesses y 25.5, river 16, enemy
princesses y 6.5, enemy king y 3; lane L = x < 9), plus own_deck / opp_deck (sets of base keys) and cid (cluster id).
  pro / live: invlib adapters unchanged (pro frames = native re-drive, decisions + results real; live = reader frames).
  hf: plays from the HF actions table (exact ticks / cells), towers + own elixir + own hand from the crforge re-drive rows of
      that side (rows sc: 3 my_elixir/10, 52..57 tower hp frac my K L R / opp K L R, 64..69 alive; hand_card = vocab ids).
      Tier A only (every play accepted, crowns == HF). No unit bodies (frames carry towers only), so macros that need
      bodies use their play-based start condition on HF and say so.
An EPISODE = one occurrence of a macro's START condition for one player-side: the matching cell at that moment (phase,
crown diff, princess-HP margin, own elixir band, own / opponent deck archetype), treated = the macro's prefix was played
within its window, well = the executed prefix's immediate success (where defined), and outcomes: match win and the net
PRINCESS margin change (enemy princess HP lost - own princess HP lost, princess units; king HP left out: it decides
nothing short of 3 crowns, and king activation trades king HP for princess HP) over 10 / 20 / 30 / 60 s and to the end.
stats.py turns episodes into cell-matched lifts with match-cluster bootstrap CIs. Association only, never causal."""
from __future__ import annotations

import argparse
import bisect
import gzip
import json
import math
import os
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
L74 = HERE.parents[1]
REPO = L74.parents[2]
sys.path[:0] = [str(L74 / 'rocket'), str(L74 / 'habits'), str(L74 / 'investment'), str(REPO)]
import hablib as H  # noqa: E402
import invlib as I  # noqa: E402
import rocket_slices as RS  # noqa: E402  (K = X-Bow answer cards, archetype, answer_ctx: reused, not re-derived)

I8 = set(I.I8)


def _catalog():
    """{base key: (elixir, type)} from the native live card catalogue (pro2.build_rows.card_catalog's slug rule). hablib's
    CardDB (icebow/config/cards.yaml) lacks 91 of the 118 HF cards AND x_bow (H.cost('x_bow') = the 3.0 fallback, kind None),
    which would make every elixir-commit / zone rule wrong on HF and the opponent elixir counter wrong everywhere."""
    from pipeline import vocab
    p = REPO / 'research/ext/cr-native-sandbox/native_core/data/live_card_catalog.json'
    out = {}
    for c in sorted(json.load(open(p, encoding='utf-8'))['cards'], key=lambda c: not c.get('standard_1v1')):
        k = vocab.engine_key(c['display_name'])
        if k and c.get('elixir') is not None:
            out.setdefault(H.norm(vocab.base_key(k)), (float(c['elixir']), c.get('type')))
    return out


_CAT = _catalog()
_h_cost, _h_kind = H.cost, H.kind


def _cost(k):
    v = _CAT.get(k)
    return v[0] if v else _h_cost(k)


def _kind(k):
    v = _CAT.get(k)
    return v[1] if v else _h_kind(k)


H.cost, H.kind = _cost, _kind        # in-process only: invlib / counter_fn / rocket_slices call H.cost / H.kind at run time
K_RATIO = 4824.0 / 3052.0           # king / princess max HP (obs_contract level factor): HF fractions -> princess units
HOR = (200, 400, 600, 1200)         # outcome horizons, ticks (10 / 20 / 30 / 60 s) + 'end'
EN_T = {'L': (3.5, 6.5), 'R': (14.5, 6.5), 'K': (9.0, 3.0)}
OWN_KING = (9.0, 29.0)
LOCK_HP = 0.05                      # invlib LOCK_MIN: >= 5% of a princess lost in the X-Bow lane = locked (HF proxy)
FAIL_WIN = 400                      # X-Bow judged over 20 s after placement (HF proxy; pro / live use invlib's X-Bow life)


# ------------------------------------------------------------------------------------------------------------ helpers
def lane(x):
    return 'L' if x < 9 else 'R'


def other(ln):
    return 'R' if ln == 'L' else 'L'


def _ts(m):
    if '_ts' not in m:
        m['_ts'] = [f[0] for f in m['frames']]
    return m['_ts']


def towers(m, t):
    i = max(0, bisect.bisect_right(_ts(m), t) - 1)
    return m['frames'][i][1]


def pmax(m):
    return m['tmax'].get(('own', 'L')) or 1.0


def lost(m, who, t0, t1, slots='KLR'):
    t1 = min(t1, m['end'])
    a, b = towers(m, t0), towers(m, t1)
    return sum(max(0, a.get((who, s), 0) - b.get((who, s), 0)) for s in slots) / pmax(m)


def up(m, who, s, t):
    return towers(m, t).get((who, s), 0) > 0


def crowns(m, t):
    T = towers(m, t)
    return sum(T.get(('opp', s), 0) <= 0 for s in 'LR'), sum(T.get(('own', s), 0) <= 0 for s in 'LR')


def hand(m, t):
    return m['hand'](t)


def elixir(m, t):
    h = hand(m, t)
    return None if h is None or h[1] is None else float(h[1])


def inhand(m, t, card):
    h = hand(m, t)
    return None if h is None else card in h[0]


def est(m, t):
    if '_est' not in m:
        m['_est'] = H.counter_fn(m['opp'])
    return m['_est'](t)


def tower_spell(q):
    return q['y'] is not None and any(math.hypot(q['x'] - x, q['y'] - y) <= 3.0 for x, y in EN_T.values())


def zone(q):
    """'off' / 'def' for an own (or, in the opponent's frame, an opponent) play."""
    if q['y'] is None:
        return None
    if H.kind(q['card']) == 'spell':
        return 'off' if q['y'] < 16 else 'def'
    return 'off' if q['y'] <= 19.0 else 'def'


def opp_zone(p):
    """Opponent play seen from OUR frame: 'att' = at their bridge or in our half (y >= 11), 'back' = behind it."""
    return None if p['y'] is None else 'att' if p['y'] >= 11 else 'back'


def is_troopish(c):
    return H.kind(c) in ('troop', 'building')


def phase(t):
    return '1x' if t < 2400 else '2x' if t < 3600 else 'OT'


def band(e):
    return 'na' if e is None else 'lo' if e < 4 else 'mid' if e < 7 else 'hi'


def cell(m, t):
    oc, tc = crowns(m, t)
    T = towers(m, t)
    pm = pmax(m)
    mar = (sum(T.get(('own', s), 0) for s in 'LR') - sum(T.get(('opp', s), 0) for s in 'LR')) / pm
    return dict(ph=phase(t), cr=max(-1, min(1, oc - tc)), hm='-' if mar < -0.3 else '+' if mar > 0.3 else '0',
                el=band(elixir(m, t)), oa=m['opp_arch'], wa=m['own_arch'])


def outcome(m, t):
    o = dict(win=m['win'])
    for h in HOR:
        o['n%d' % h] = round(lost(m, 'opp', t, t + h, 'LR') - lost(m, 'own', t, t + h, 'LR'), 4)
    o['nend'] = round(lost(m, 'opp', t, m['end'], 'LR') - lost(m, 'own', t, m['end'], 'LR'), 4)
    return o


def ep(m, macro, t, treated, well=None, xc=None, **x):
    """xc = an extra matching key for this macro (stats.py appends it to the cell), e.g. the attacking unit."""
    r = dict(macro=macro, src=m['src'], cid=m['cid'], side=m.get('side', 0), t=int(t), tr=int(bool(treated)),
             well=None if well is None else int(bool(well)), xc=xc)
    r.update(cell(m, t))
    r.update(outcome(m, t))
    if x:
        r['x'] = x
    return r


def xbow_lock_map(m):
    """{own X-Bow play tick: (locked, end tick)}: invlib's X-Bow life where frames carry own X-Bows (pro / live); HF: the
    HP proxy (>= LOCK_HP of a princess lost in that lane within 20 s; end = placement + 20 s)."""
    out = {}
    if m['src'] in ('pro', 'live'):
        for r in I.xbow_rows(m):
            if 'lock' in r and not r.get('censored'):
                out[r['tick']] = (bool(r['lock']), r['end_tick'])
        return out
    for q in m['own']:
        if q['card'] == 'x_bow' and q['y'] is not None and q['tick'] + FAIL_WIN <= m['end']:
            out[q['tick']] = (lost(m, 'opp', q['tick'], q['tick'] + FAIL_WIN, lane(q['x'])) >= LOCK_HP,
                              q['tick'] + FAIL_WIN)
    return out


def opp_cycle(m, t):
    return I.opp_cycle(m, t)


# ---------------------------------------------------------------------------------------------------------- detectors
def det_sneaky_lock(m, X):
    """1. Tornado pulls a defender, then the X-Bow locks. START: an own bridge X-Bow (y 16..20.5) with Tornado in the deck
    (pro / live refine: an enemy body within 7 tiles of the X-Bow site at placement). PREFIX: own Tornado on the bridge /
    enemy half (y < 20) within X-Bow range (11.5 tiles) of the X-Bow, from 6 s before to 15 s after it (the defender often
    arrives after the X-Bow). well = the X-Bow locked."""
    if not {'x_bow', 'tornado'} <= m['own_deck']:
        return []
    out = []
    tor = [q for q in m['own'] if q['card'] == 'tornado' and q['y'] is not None]
    for q in m['own']:
        if not H.is_bridge_xbow(q) or q['tick'] not in X:
            continue
        t = q['tick']
        tn = [p for p in tor if t - 120 <= p['tick'] <= t + 300 and p['y'] < 20
              and math.hypot(p['x'] - q['x'], p['y'] - q['y']) <= 11.5]
        defender = None
        if m['src'] != 'hf':
            f = m['frames'][max(0, bisect.bisect_right(_ts(m), t) - 1)]
            defender = any(math.hypot(x - q['x'], y - q['y']) <= I.AT_XBOW for k, hp, x, y in f[2] if k)
        out.append(ep(m, 'sneaky_lock', t, bool(tn), well=X[t][0], defender=defender))
    return out


def det_rocket_cycle(m, X):
    """2. Rocket cycling after failed X-Bows in 2x / OT. START: a failed bridge X-Bow whose life ends at >= 2:00 (tick 2400),
    Rocket in the deck. PREFIX: an own tower Rocket on a princess within 30 s of the failure's end. well = that Rocket
    chipped (>= 3% of a princess lost in 2 s at its slot)."""
    if not {'x_bow', 'rocket'} <= m['own_deck']:
        return []
    out, nfail = [], 0
    rk = [q for q in m['own'] if q['card'] == 'rocket' and tower_spell(q)]
    for q in sorted(m['own'], key=lambda q: q['tick']):
        if not H.is_bridge_xbow(q) or q['tick'] not in X or X[q['tick']][0]:
            continue
        nfail += 1
        te = X[q['tick']][1]
        if te < 2400 or te >= m['end'] - 20:
            continue
        r = [p for p in rk if te <= p['tick'] <= te + 600]
        well = None
        if r:
            s = min(EN_T, key=lambda s: math.hypot(r[0]['x'] - EN_T[s][0], r[0]['y'] - EN_T[s][1]))
            well = lost(m, 'opp', r[0]['tick'], r[0]['tick'] + 60, s) >= 0.03
        out.append(ep(m, 'rocket_cycle', te, bool(r), well=well, xc=min(nfail, 3)))
    return out


def det_rocket_tornado(m, X):
    """3. Rocket + Tornado. 3a clump: START = an opponent commitment of >= 7 troop elixir in 6 s attacking (y >= 11) with
    Rocket AND Tornado in our hand and >= 8 own elixir; PREFIX = own Rocket and Tornado landing within 3 s of each other in
    the next 10 s (well = enemy elixir committed >= 9). 3b into princess: START = an own tower Rocket (Tornado in deck);
    PREFIX = an own Tornado played within 3 s of the Rocket play (rocket_slices COMBO -24..+40 is LANDING ticks; the Rocket
    flies ~1-2 s, so play ticks get a wider symmetric window); well = the Rocket chipped >= 3%."""
    if not {'rocket', 'tornado'} <= m['own_deck']:
        return []
    out = []
    own = sorted(m['own'], key=lambda q: q['tick'])
    rk = [q for q in own if q['card'] == 'rocket' and q['y'] is not None]
    tn = [q for q in own if q['card'] == 'tornado' and q['y'] is not None]
    last = -10 ** 9
    for p in m['opp']:
        t = p['tick']
        if t - last < 200 or opp_zone(p) != 'att':
            continue
        com = sum(H.cost(o['card']) for o in m['opp'] if t - 120 <= o['tick'] <= t and is_troopish(o['card']))
        if com < 7:
            continue
        h = hand(m, t)
        if h is None or not {'rocket', 'tornado'} <= h[0] or (h[1] or 0) < 8:
            continue
        last = t
        hit = any(abs(r['tick'] - q['tick']) <= 60 for r in rk if t <= r['tick'] <= t + 200
                  for q in tn if t <= q['tick'] <= t + 200)
        out.append(ep(m, 'rocket_tornado_clump', t, hit, well=com >= 9, committed=com))
    for r in rk:
        if not tower_spell(r):
            continue
        hit = any(abs(r['tick'] - q['tick']) <= 60 for q in tn)
        s = min(EN_T, key=lambda s: math.hypot(r['x'] - EN_T[s][0], r['y'] - EN_T[s][1]))
        out.append(ep(m, 'rocket_tornado_tower', r['tick'], hit, well=lost(m, 'opp', r['tick'], r['tick'] + 60, s) >= 0.03))
    return out


def det_king_redirect(m, X):
    """4. Tornado into our king while both princesses stand. START (invlib.bridge_rows): an opponent troop dropped at a lane
    bridge (x < 7 or > 11, y 11..18.5) with both own princesses up, Tornado in hand, >= 3 own elixir. PREFIX: own Tornado
    within 5 s cast within 8 tiles of our king. well = no own princess HP lost in the 15 s after."""
    if 'tornado' not in m['own_deck']:
        return []
    out = []
    tn = [q for q in m['own'] if q['card'] == 'tornado' and q['y'] is not None]
    for p in m['opp']:
        if p['y'] is None or H.kind(p['card']) != 'troop' or not (11.0 <= p['y'] <= 18.5) or 7 <= p['x'] <= 11:
            continue
        t = p['tick']
        if not (up(m, 'own', 'L', t) and up(m, 'own', 'R', t)):
            continue
        h = hand(m, t)
        if h is None or 'tornado' not in h[0] or (h[1] or 0) < 3:
            continue
        hit = [q for q in tn if t <= q['tick'] <= t + 100 and math.hypot(q['x'] - OWN_KING[0], q['y'] - OWN_KING[1]) <= 8]
        out.append(ep(m, 'king_redirect', t, bool(hit), well=lost(m, 'own', t, t + 300, 'LR') < 0.02, xc=p['card']))
    return out


def det_def_xbow(m, X):
    """5. Defensive X-Bow in a hard matchup, then the counter-lock. START: an own X-Bow placement in a hostile cluster
    (rocket_slices.HOSTILE: EQ / HOG / BEATDOWN matchup with their X-Bow answer ready or short). PREFIX: the X-Bow is
    defensive (y > 20.5). well = an own bridge X-Bow locks within the next 30 s (the counter-lock)."""
    if 'x_bow' not in m['own_deck']:
        return []
    out = []
    for q in m['own']:
        if q['card'] != 'x_bow' or q['y'] is None:
            continue
        t = q['tick']
        ctx = RS.answer_ctx(opp_cycle(m, t), est(m, t))
        if (m['opp_arch'], ctx) not in RS.HOSTILE:
            continue
        cl = [b for b in m['own'] if H.is_bridge_xbow(b) and t < b['tick'] <= t + 600 and X.get(b['tick'], (False,))[0]]
        out.append(ep(m, 'def_xbow_hard', t, I.xtype(q['y']) == 'defensive', well=bool(cl), xc=ctx))
    return out


def det_opp_lane(m, X):
    """6. Opposite-lane punish. START: the opponent commits >= 6 elixir of troops / buildings in one lane within 5 s and its
    estimated elixir is <= 4 after; own elixir >= 4. PREFIX: an own offensive play (zone 'off') in the OTHER lane within
    8 s. well = enemy princess HP lost in that other lane within 20 s >= 5%."""
    out, last = [], -10 ** 9
    for p in m['opp']:
        t = p['tick']
        if t - last < 300 or p['y'] is None or not is_troopish(p['card']):
            continue
        ln = lane(p['x'])
        com = sum(H.cost(o['card']) for o in m['opp'] if t - 100 <= o['tick'] <= t and o['y'] is not None
                  and is_troopish(o['card']) and lane(o['x']) == ln)
        if com < 6 or est(m, t + 1) > 4:
            continue
        e = elixir(m, t)
        if e is None or e < 4:
            continue
        last = t
        hit = [q for q in m['own'] if t < q['tick'] <= t + 160 and q['y'] is not None and zone(q) == 'off'
               and lane(q['x']) == other(ln)]
        out.append(ep(m, 'opp_lane_punish', t, bool(hit), well=lost(m, 'opp', t, t + 400, other(ln)) >= 0.05, committed=com))
    return out


def det_counterpush(m, X):
    """7. Counter-push behind surviving defenders. START: an opponent attack (>= 8 troop elixir in 5 s, y >= 11, one lane)
    that we defended with >= 3 elixir of own plays in our half within 10 s. PREFIX: an own troop placed in the same lane in
    our half behind the defence (y 16..24) 5..20 s after the attack started. Survival of our defenders is NOT observed (no
    own bodies in the frames): (b). well = enemy princess HP lost in that lane within 30 s >= 5%."""
    out, last = [], -10 ** 9
    for p in m['opp']:
        t = p['tick']
        if t - last < 400 or opp_zone(p) != 'att' or not is_troopish(p['card']):
            continue
        ln = lane(p['x'])
        com = sum(H.cost(o['card']) for o in m['opp'] if t - 100 <= o['tick'] <= t and opp_zone(o) == 'att'
                  and is_troopish(o['card']) and lane(o['x']) == ln)
        if com < 8:
            continue
        de = sum(H.cost(q['card']) for q in m['own'] if t - 40 <= q['tick'] <= t + 200 and zone(q) == 'def')
        if de < 3:
            continue
        last = t
        hit = [q for q in m['own'] if t + 100 <= q['tick'] <= t + 400 and q['y'] is not None and H.kind(q['card']) == 'troop'
               and 16 <= q['y'] <= 24 and lane(q['x']) == ln]
        out.append(ep(m, 'counterpush', t + 100, bool(hit), well=lost(m, 'opp', t, t + 600, ln) >= 0.05, committed=com))
    return out


def det_out_of_cycle(m, X):
    """8. X-Bow when their known answer is out of cycle (memory). START: an own bridge X-Bow with an X-Bow answer card
    (rocket_slices.K) revealed. PREFIX ('treated'): the answer is cycled (seen, not back in hand) vs ready / short.
    well = locked."""
    if 'x_bow' not in m['own_deck']:
        return []
    out = []
    for q in m['own']:
        if not H.is_bridge_xbow(q) or q['tick'] not in X:
            continue
        t = q['tick']
        ctx = RS.answer_ctx(opp_cycle(m, t), est(m, t))
        if ctx == 'unrevealed':
            continue
        out.append(ep(m, 'xbow_out_of_cycle', t, ctx == 'cycled', well=X[t][0], ctx=ctx))
    return out


def det_weakest(m, X):
    """9. Focus the weakest princess. START: an own offensive play (zone 'off', incl. tower spells) while both enemy
    princesses stand and differ by >= 15% HP. PREFIX: that play is in the weaker princess's lane. well = that princess lost
    >= 5% within 20 s."""
    out = []
    for q in m['own']:
        if q['y'] is None or zone(q) != 'off':
            continue
        t = q['tick']
        T = towers(m, t)
        a, b = T.get(('opp', 'L'), 0), T.get(('opp', 'R'), 0)
        if a <= 0 or b <= 0 or abs(a - b) / pmax(m) < 0.15:
            continue
        weak = 'L' if a < b else 'R'
        out.append(ep(m, 'weakest_princess', t, lane(q['x']) == weak, well=lost(m, 'opp', t, t + 400, weak) >= 0.05))
    return out


def det_lead(m, X):
    """10a lead protection: START = we are a crown ahead and have >= 5 elixir (sampled every 30 s while it holds);
    PREFIX = defend out: no own offensive play costing >= 4 in the next 30 s. well = no crown lost in that 30 s.
    10b at 1-1: START = an own offensive play; PREFIX = in the lane of the enemy princess still standing (not the open lane
    / their king). well = that princess lost >= 5% within 20 s."""
    out, nxt = [], 0
    for t in range(200, int(m['end']) - 200, 100):
        if t < nxt:
            continue
        oc, tc = crowns(m, t)
        e = elixir(m, t)
        if oc <= tc or e is None or e < 5:
            continue
        nxt = t + 600
        inv = [q for q in m['own'] if t < q['tick'] <= t + 600 and zone(q) == 'off' and H.cost(q['card']) >= 4]
        out.append(ep(m, 'lead_defend', t, not inv, well=crowns(m, t + 600)[1] == tc))
    for q in m['own']:
        if q['y'] is None or zone(q) != 'off':
            continue
        t = q['tick']
        if crowns(m, t) != (1, 1):
            continue
        st = [s for s in 'LR' if up(m, 'opp', s, t)]
        if len(st) != 1:
            continue
        out.append(ep(m, 'one_one_other', t, lane(q['x']) == st[0], well=lost(m, 'opp', t, t + 400, st[0]) >= 0.05))
    return out


def det_bank(m, X):
    """11a bank before 2x: START = tick 2200 (1:50), every side; PREFIX = own elixir >= 7 at 2:00 (tick 2390) with no own
    offensive play in 1:50..2:00. 11b their bank: START = their estimated elixir >= 9 and ours >= 7, no play by either side
    in the last 3 s (once per 15 s); PREFIX = we hold (no own offensive play in the next 5 s). well = no own princess HP
    lost >= 5% in the 20 s after."""
    out = []
    if m['end'] > 2500:
        e = elixir(m, 2390)
        if e is not None:
            off = [q for q in m['own'] if 2200 <= q['tick'] <= 2400 and zone(q) == 'off']
            out.append(ep(m, 'bank_pre2x', 2200, e >= 7 and not off, well=None, el=e))
    allp = sorted([q['tick'] for q in m['own']] + [p['tick'] for p in m['opp']])
    nxt = 0
    for t in range(100, int(m['end']) - 400, 40):
        if t < nxt:
            continue
        e = elixir(m, t)
        if e is None or e < 7 or est(m, t) < 9:
            continue
        i = bisect.bisect_right(allp, t)
        if i and allp[i - 1] > t - 60:
            continue
        nxt = t + 300
        hold = not [q for q in m['own'] if t < q['tick'] <= t + 100 and zone(q) == 'off']
        out.append(ep(m, 'hold_vs_bank', t, hold, well=lost(m, 'own', t, t + 400, 'LR') < 0.05))
    return out


def det_pull(m, X):
    """12. Pulls / kiting to split a push. START: an opponent attack of >= 2 troops and >= 8 elixir in one lane within 5 s
    (y >= 11). PREFIX: our first play in the 6 s after is a troop / building placed in the centre of our half
    (|x - 9| <= 2.5, y 18..25) or a Tornado. well = own princess HP lost in 15 s < 10%."""
    out, last = [], -10 ** 9
    for p in m['opp']:
        t = p['tick']
        if t - last < 300 or opp_zone(p) != 'att' or not is_troopish(p['card']):
            continue
        ln = lane(p['x'])
        grp = [o for o in m['opp'] if t - 100 <= o['tick'] <= t and opp_zone(o) == 'att' and H.kind(o['card']) == 'troop'
               and lane(o['x']) == ln]
        if len(grp) < 2 or sum(H.cost(o['card']) for o in grp) < 8:
            continue
        last = t
        first = next((q for q in sorted(m['own'], key=lambda q: q['tick']) if t <= q['tick'] <= t + 120
                      and q['y'] is not None), None)
        hit = first is not None and (first['card'] == 'tornado' or (
            is_troopish(first['card']) and abs(first['x'] - 9) <= 2.5 and 18 <= first['y'] <= 25))
        out.append(ep(m, 'pull_split', t, hit, well=lost(m, 'own', t, t + 300, 'LR') < 0.10))
    return out


def det_log_barrel(m, X):
    """13. Hold the Log for the Barrel. START: an opponent Goblin Barrel (the_log in our deck). PREFIX: the Log was held
    (in our hand at the Barrel). well = we Logged within 3 s."""
    if 'the_log' not in m['own_deck']:
        return []
    out = []
    lg = [q['tick'] for q in m['own'] if q['card'] == 'the_log']
    for p in m['opp']:
        if p['card'] != 'goblin_barrel':
            continue
        t = p['tick']
        h = inhand(m, t, 'the_log')
        if h is None:
            continue
        out.append(ep(m, 'log_for_barrel', t, h, well=any(t <= x <= t + 60 for x in lg)))
    return out


def det_siege(m, X):
    """14. Siege answer. START: an opponent X-Bow / Mortar placed at their bridge / pocket (our frame y 8..16). PREFIX: an
    own troop placed within 6 tiles of it within 2 s. well = an own Rocket within 4 tiles of it within 10 s (Rocket when
    locked) or no own princess HP lost >= 5% in 20 s."""
    out = []
    for p in m['opp']:
        if p['card'] not in ('x_bow', 'mortar') or p['y'] is None or not (8 <= p['y'] <= 16):
            continue
        t = p['tick']
        tr = [q for q in m['own'] if t <= q['tick'] <= t + 40 and q['y'] is not None and H.kind(q['card']) == 'troop'
              and math.hypot(q['x'] - p['x'], q['y'] - p['y']) <= 6]
        rk = [q for q in m['own'] if t <= q['tick'] <= t + 200 and q['card'] == 'rocket' and q['y'] is not None
              and math.hypot(q['x'] - p['x'], q['y'] - p['y']) <= 4]
        out.append(ep(m, 'siege_answer', t, bool(tr), well=bool(rk) or lost(m, 'own', t, t + 400, 'LR') < 0.05,
                      rocket=bool(rk), xc=p['card']))
    return out


def det_iw_press(m, X):
    """15. Hero Ice Wizard press timing. START: an own ability press while our deck has the hero Ice Wizard (HF: presses are
    'ability' plays; pro / live corpora have no press records -> none). PREFIX: the press comes during a defence (>= 5
    opponent troop elixir attacking, y >= 11, in the 5 s before). well = own princess HP lost in 10 s < 5%."""
    if not m.get('iw_hero'):
        return []
    out = []
    for q in m['own']:
        if q['card'] != 'ability:ice_wizard':
            continue
        t = q['tick']
        att = sum(H.cost(o['card']) for o in m['opp'] if t - 100 <= o['tick'] <= t and opp_zone(o) == 'att'
                  and H.kind(o['card']) == 'troop')
        out.append(ep(m, 'iw_press', t, att >= 5, well=lost(m, 'own', t, t + 200, 'LR') < 0.05))
    return out


TANKS = RS.TANKS


def det_opening(m, X):
    """16 (new, live 10-28). Opening restraint vs heavy-push decks. START: match start vs a BEATDOWN deck (a tank in their
    deck). PREFIX (generic) = defend first: <= 3 elixir of own offensive plays (zone 'off') before 0:30. For X-Bow decks
    the sub-macro opening_restraint_xb: no own X-Bow before the opponent's first tank play (or 0:40); 'xb_tesla' extra =
    the 10-elixir X-Bow + Tesla opening (both before the first tank / 0:40)."""
    if m['opp_arch'] != 'BEATDOWN' or m['end'] < 1200:
        return []
    off = sum(H.cost(q['card']) for q in m['own'] if q['tick'] < 600 and zone(q) == 'off')
    out = [ep(m, 'opening_restraint', 0, off <= 3, well=None, off_el=off)]
    if 'x_bow' in m['own_deck']:
        ft = next((p['tick'] for p in sorted(m['opp'], key=lambda p: p['tick']) if p['card'] in TANKS), 800)
        lim = min(ft, 800)
        xb = [q for q in m['own'] if q['card'] == 'x_bow' and q['tick'] < lim]
        ts = [q for q in m['own'] if q['card'] == 'tesla' and q['tick'] < lim]
        out.append(ep(m, 'opening_restraint_xb', 0, not xb, well=None, xb_tesla=bool(xb and ts), first_tank=ft))
    return out


DETECTORS = (det_sneaky_lock, det_rocket_cycle, det_rocket_tornado, det_king_redirect, det_def_xbow, det_opp_lane,
             det_counterpush, det_out_of_cycle, det_weakest, det_lead, det_bank, det_pull, det_log_barrel, det_siege,
             det_iw_press, det_opening)


def side_summary(m):
    """Per player-side record for the mined extras: ordered pairs (A then B within 5 s) of icebow8 cards, B's lane relation
    to A (S same / O other) and B's zone (o off / d def)."""
    pairs = Counter()
    own = [q for q in sorted(m['own'], key=lambda q: q['tick']) if q['y'] is not None and q['card'] in I8]
    for i, a in enumerate(own):
        for b in own[i + 1:]:
            if b['tick'] - a['tick'] > 100:
                break
            if b['card'] == a['card']:
                continue
            pairs['%s>%s:%s%s' % (a['card'], b['card'], 'S' if lane(a['x']) == lane(b['x']) else 'O',
                                  'o' if zone(b) == 'off' else 'd')] += 1
    return dict(macro='_side', src=m['src'], cid=m['cid'], side=m.get('side', 0), win=m['win'], oa=m['opp_arch'],
                wa=m['own_arch'], deck8=sorted(m['own_deck'] & I8), pairs=dict(pairs), end=int(m['end']))


def mine_match(m):
    m['own_arch'] = RS.archetype(m['own_deck'])
    m['opp_arch'] = RS.archetype(m['opp_deck'])
    X = xbow_lock_map(m) if 'x_bow' in m['own_deck'] else {}
    out = []
    for d in DETECTORS:
        out.extend(d(m, X))
    out.append(side_summary(m))
    return out


# ------------------------------------------------------------------------------------------------------------ sources
def pro_source():
    for m in I.pro_matches():
        m['cid'] = 'pro:' + m['key']
        m['own_deck'] = set(I8)
        od = m.get('opp_deck_true')
        od = od.split(',') if isinstance(od, str) else (od or [])
        m['opp_deck'] = {H.norm(c) for c in od if c} or {p['card'] for p in m['opp']}
        yield m


def live_source():
    """invlib.live_matches with index_clxiii.json, pickles from habits/cache or macros/live_cache (live_index.py)."""
    import pickle
    idx = json.load(open(HERE / 'index_clxiii.json'))
    o = I.LIVE_CLOCK_OFF
    for name in sorted(idx):
        stem = Path(name).stem
        p = next((c / (stem + '.pkl') for c in (L74 / 'habits/cache', HERE / 'live_cache') if (c / (stem + '.pkl')).exists()), None)
        if p is None:
            continue
        c = pickle.load(open(p, 'rb'))
        frames = [(t - o, T, [(k, hp, x, y) for _, k, _, hp, _, x, y in en],
                   [(bid, hp, None, x, y) for bid, k, hp, x, y in ob if k == 'x_bow']) for t, T, en, ob in c['frames']]
        if not frames:
            continue
        dec = [(t - o, h, el) for t, h, el, *_ in c['dec']]
        dts = [d[0] for d in dec]

        def hnd(t, dec=dec, dts=dts):
            i = bisect.bisect_right(dts, t) - 1
            return None if i < 0 else ({H.norm(x) for x in dec[i][1] if x}, dec[i][2])
        r = idx[name]['result']
        m = dict(src='live', group='CLXIII', key=name, cid='live:' + name,
                 win={'WIN': 1.0, 'LOSS': 0.0}.get(r, .5), end=frames[-1][0],
                 own=[dict(tick=q['tick'] - o, card=H.norm(q['name']), x=q['x'], y=q['y'], why=q.get('why')) for q in c['own']
                      if q['name']],
                 opp=[dict(tick=p['tick'] - o, card=H.norm(p['card']), x=p['x'], y=p['y']) for p in c['opp']],
                 frames=frames, tmax=dict(frames[0][1]), hand=hnd, xbow_track='bid')
        m['own_deck'] = set(I8)
        m['opp_deck'] = {p['card'] for p in m['opp']}
        yield m


def _base(k):
    for s in ('-ev1', '-hero'):
        if k.endswith(s):
            return k[:-len(s)]
    return k


def hf_matches(rows_file, hf_root):
    """Tier-A HF matches of one re-drive rows shard -> two match records each (one per side)."""
    import numpy as np
    import pyarrow.parquet as pq
    pf = pq.ParquetFile(rows_file)
    vocab = [H.norm(_base(c)) for c in json.loads(pf.schema_arrow.metadata[b'meta'])['card_vocab']]
    t = pq.read_table(rows_file, columns=['tag', 'side', 'tick', 'tier', 'sc', 'hand_card'])
    tier = np.asarray(t.column('tier').to_numpy(zero_copy_only=False))
    keep = tier == 'A'
    if not keep.any():
        return
    tags = np.asarray(t.column('tag').to_numpy(zero_copy_only=False))[keep]
    side = t.column('side').to_numpy()[keep]
    tick = t.column('tick').to_numpy()[keep]
    sc = np.asarray(t.column('sc').combine_chunks().flatten().to_numpy()).reshape(-1, 70)[keep]
    hc = np.asarray(t.column('hand_card').combine_chunks().flatten().to_numpy()).reshape(-1, 4)[keep]
    part = Path(rows_file).name.split('_')[0]                       # part-000000
    want = sorted(set(tags.tolist()))
    reps = {r['replay_tag']: r for r in pq.read_table(Path(hf_root) / 'replays' / (part + '.parquet'),
                                                      columns=['replay_tag', 'result', 'battle_type', 'payload_json'],
                                                      filters=[('replay_tag', 'in', want)]).to_pylist()}
    acts = defaultdict(list)
    for a in pq.read_table(Path(hf_root) / 'actions' / (part + '.parquet'), filters=[('replay_tag', 'in', want)],
                           columns=['replay_tag', 'event_index', 'kind', 'side', 'card_key', 'replay_tick_20hz', 'native_x',
                                    'native_y', 'ability_source_candidates']).to_pylist():
        acts[a['replay_tag']].append(a)
    order = np.lexsort((tick, side, tags))
    tags, side, tick, sc, hc = tags[order], side[order], tick[order], sc[order], hc[order]
    bounds = np.flatnonzero(np.r_[True, (tags[1:] != tags[:-1]) | (side[1:] != side[:-1]), True])
    per = defaultdict(dict)
    for a, b in zip(bounds[:-1], bounds[1:]):
        per[tags[a]][int(side[a])] = (tick[a:b], sc[a:b], hc[a:b])
    for tag, sides in per.items():
        rp = reps.get(tag)
        if rp is None or set(sides) != {0, 1}:
            continue
        b = json.loads(rp['payload_json'])['battle']
        decks = {s: [c['card_key'] for c in b[k]['players'][0]['deck']] for s, k in ((0, 'team'), (1, 'opponent'))}
        res0 = {'victory': 1.0, 'defeat': 0.0}.get(rp['result'], .5)
        evs = sorted(acts[tag], key=lambda a: (a['replay_tick_20hz'], a['event_index']))
        for s in (0, 1):
            tk, S, HC = sides[s]

            def tr(x, y, s=s):
                return (x / 1000, 32 - y / 1000) if s == 0 else (18 - x / 1000, y / 1000)
            own, opp = [], []
            for a in evs:
                mine = (a['side'] == 'team') == (s == 0)
                if a['kind'] == 'activate_ability':
                    c = [H.norm(_base(x)) for x in (a['ability_source_candidates'] or [])]
                    if mine:
                        own.append(dict(tick=a['replay_tick_20hz'], card='ability:' + (c[0] if len(c) == 1 else '?'),
                                        x=None, y=None))
                    continue
                if a['kind'] != 'play_card' or a['card_key'] is None or a['native_x'] is None:
                    continue
                x, y = tr(a['native_x'], a['native_y'])
                (own if mine else opp).append(dict(tick=a['replay_tick_20hz'], card=H.norm(_base(a['card_key'])), x=x, y=y))
            frames = []
            for i in range(len(tk)):
                v = S[i]
                T = {}
                for j, (w, sl) in enumerate((('own', 'K'), ('own', 'L'), ('own', 'R'), ('opp', 'K'), ('opp', 'L'), ('opp', 'R'))):
                    T[(w, sl)] = (float(v[52 + j]) if v[64 + j] > 0 else 0.0) * (K_RATIO if sl == 'K' else 1.0)
                frames.append((int(tk[i]), T, [], []))
            hts = tk.tolist()
            hands = [{vocab[c] for c in row if 0 < c < len(vocab)} for row in HC.tolist()]
            els = (S[:, 3] * 10).tolist()

            def hnd(t, hts=hts, hands=hands, els=els):
                i = bisect.bisect_right(hts, t) - 1
                return None if i < 0 else (hands[i], els[i])
            od = decks[1 - s]
            m = dict(src='hf', key=tag, cid='hf:' + tag, side=s, win=res0 if s == 0 else (1 - res0 if res0 != .5 else .5),
                     end=int(tk[-1]), own=own, opp=opp, frames=frames,
                     tmax={(w, sl): (K_RATIO if sl == 'K' else 1.0) for w in ('own', 'opp') for sl in 'KLR'},
                     hand=hnd, xbow_track=None, own_deck={H.norm(_base(c)) for c in decks[s]},
                     opp_deck={H.norm(_base(c)) for c in od}, iw_hero='ice-wizard-hero' in decks[s],
                     battle_type=rp['battle_type'])
            yield m


def hf_shard(job):
    rows_file, hf_root, out_dir = job
    out = Path(out_dir) / (Path(rows_file).stem + '.jsonl.gz')
    if out.exists():
        return out.name, 'skip'
    t0, n, ne = time.time(), 0, 0
    tmp = out.with_suffix('.tmp')
    with gzip.open(tmp, 'wt', encoding='utf-8') as f:
        for m in hf_matches(rows_file, hf_root):
            n += 1
            for e in mine_match(m):
                f.write(json.dumps(e, separators=(',', ':')) + '\n')
                ne += 1
    os.replace(tmp, out)
    return out.name, dict(sides=n, eps=ne, s=round(time.time() - t0, 1))


def write_eps(it, out):
    n = ne = 0
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(out, 'wt', encoding='utf-8') as f:
        for m in it:
            n += 1
            for e in mine_match(m):
                f.write(json.dumps(e, separators=(',', ':')) + '\n')
                ne += 1
    print(json.dumps(dict(out=str(out), sides=n, eps=ne)), flush=True)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('src', choices=('pro', 'live', 'hf'))
    ap.add_argument('--out', required=True)
    ap.add_argument('--rows')
    ap.add_argument('--hf')
    ap.add_argument('--workers', type=int, default=1)
    ap.add_argument('--limit', type=int, default=0)
    a = ap.parse_args(argv)
    if a.src == 'pro':
        return write_eps(pro_source(), a.out)
    if a.src == 'live':
        return write_eps(live_source(), a.out)
    files = sorted(str(p) for p in Path(a.rows).glob('*.parquet'))
    if a.limit:
        files = files[:a.limit]
    Path(a.out).mkdir(parents=True, exist_ok=True)
    jobs = [(f, a.hf, a.out) for f in files]
    if a.workers <= 1:
        for j in jobs:
            print(json.dumps(hf_shard(j)), flush=True)
        return
    from multiprocessing import Pool
    with Pool(a.workers, maxtasksperchild=50) as pool:
        for r in pool.imap_unordered(hf_shard, jobs):
            print(json.dumps(r), flush=True)


if __name__ == '__main__':
    main()
