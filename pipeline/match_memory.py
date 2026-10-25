"""Plan A (owner-approved 2026-10-25, scratchpad/gauntlet/L74/memory/PLAN_A.md): the MATCH MEMORY. A causal stream of what has
publicly happened so far in this match -- EVERY play of both sides (own ability presses too), tower damage, tower falls -- and
what each play led to, encoded to fixed width for the model (model_gen.MemoryEncoder, a ``memory: v1`` model). Pure python +
numpy, deterministic, no I/O at import.

INPUTS (only what the SIM env, the live reader and the pro dataset all have; the adapters below build them):
  MatchMemory(side).observe(tick, towers, alive, elixir=None, units=None, plays=())   once per decision, ticks increasing
    towers  6 HP fractions in obs_contract TOWER order (my K, L, R, opp K, L, R; L / R in MY frame), None = not read
            (``tower_reads(bs)``, ``tower_reads_sc(sc)``, ``tower_reads_engine(crown towers, side)``)
    alive   6 bools, same order; a dead tower counts as HP 0
    elixir  own elixir at this decision, None = unknown
    units   None = this path has no board bodies (value removed stays UNKNOWN), else the public bodies of BOTH sides as
            ``public_observation.public_frame(frame, source=...)['entities']``: dicts side (engine), x, y (engine
            millitiles), hp, max_hp, card_id (native catalog id), address (stable body identity)
    plays   the FULL lists of plays known so far, every call (repeats are ignored; a play with tick > ``tick`` waits for a
            later call): dicts tick, side (engine), card (engine name / key / slug), form (absent = unknown), x, y (engine
            millitiles; absent / None = position unknown), accepted (default True), ability (an own press), optional
            elixir_before (the pro log carries it), optional seen (tick it became known: offline replays of late reports).
            = PublicObserver.plays (the opponent, public detector) + PublicObserver.own_events (SIM env.public_plays +
            own_ability_events, pro rec['log'], live record_play / record_ability)
  build(side, samples, plays): the same from a whole recorded match (samples = dicts of observe's arguments).
  features(t, gid, deck): the model arrays (MEM_KEYS) at decision tick t. Incremental and offline give identical arrays.
  table(gid) at the END of a match -> the per-match EVENT TABLE (every event with its tick, the tick it becomes visible and
  the tick each outcome group resolves); features_at(table, ticks, deck) rebuilds features(t) for any rows, vectorised and
  bit-identical (tested) -- storage keeps tables per match and only the decision tick per row.

CAUSALITY: a decision at tick t sees plays with tick < t (and seen <= t), tower events with tick < t, and an outcome only once
its window has closed (window end < t); before that it is PENDING (flag 0), never zeros pretending to be data. A play reported
after a decision later than its tick (``late``) becomes visible at the decision that first receives it; a late play is never an
X-Bow answer or a combo Tornado (both are decided from ON-TIME plays, so they never change once shown).

EVENTS (``MatchMemory.events(t)``, chronological; dicts):
  play / ability  tick, mine, card (slug), form, xy (own frame, me at the bottom; None = unknown), el (own elixir before the
                  play; opponent / unknown None), crowns (me, opp) and margin (my princesses - theirs, HP fractions; None =
                  unknown) at the last sample BEFORE the play, cost;
                  out (pending None) = the generic outcome after W_OUT: enemy_lost / own_lost (tower HP fractions summed over
                  3 towers, None = unknown), value (enemy elixir value removed within VALUE_R tiles: habit_terms.body_value,
                  buildings at card cost x hp fraction; None = unknown);
                  X-Bows (both sides): reach (enemy princess indices within XB_REACH at the play, None = unknown), xb
                  (pending None) = locked / damage after XB_WINDOW (succ48 xbow_count.py's rule), answer (pending None,
                  '' = none, else the slug of the other side's first on-time play within XB_ANSWER_T, in the X-Bow's lane
                  and within XB_ANSWER_R tiles), ans_dist (its distance, tiles); the answering play carries is_answer;
                  own Rockets: aim (the enemy tower within RK_TOWER_R, or None), rk (pending None) = tower_lost, value (in
                  the blast), combo (an on-time own Tornado within COMBO).
  tower_damage    tick, mine (= my tower), tower (TOWER index), lost: debounced, >= DMG_MIN per tower and <= 1 per DMG_GAP
  tower_fall      tick, mine, tower
"""
from __future__ import annotations

import math
from bisect import bisect_left, bisect_right

import numpy as np

from . import vocab
from .dataset_gen import FORM_PAD, card_key
from .habit_terms import XB_LOCK, XB_REACH, XB_WINDOW, _card, body_value, play_cost
from .obs_contract import (KING_X, MY_KING_Y, MY_PRINCESS_Y, OPP_KING_Y, OPP_PRINCESS_Y, PRINCESS_X_L, PRINCESS_X_R,
                           TICK_S, TILES_X, TILES_Y, _engine_xy, catalog_card_form)
from .own_ability import SUPPLEMENT

VERSION = "v1"                   # the model flag (checkpoint meta / rl config ``memory``) these features belong to
W_OUT = 200                      # ticks (10 s): the generic play-outcome window
VALUE_R = 5.0                    # tiles: other-side bodies this close to a play (any sample in its window) count for it
DMG_MIN, DMG_GAP = 0.02, 20      # tower_damage: >= 2 % of max HP accumulated, at most one event per tower per 20 ticks (1 s)
XB_ANSWER_T, XB_ANSWER_R = 80, 12.0  # X-Bow answer (lead 10-25): the other side's first play in the X-Bow's first 4 s, in its
#                                      LANE (own-frame x on the same side of the centre line) and within 12 tiles
RK_WIN, RK_R, RK_TOWER_R = 100, 2.0, 3.0   # Rocket: outcome window (flight from our king <= ~4 s), blast radius (cards.json
#                                            area_damage_radius 2000), tower aim (rocket_slices.rocket_aim: blast <= 3 tiles)
COMBO = (-24, 40)                # Rocket tick - own Tornado tick (rocket_slices.COMBO, the S5 window)
E_MAX = 128                      # events kept (the newest)
DOUBLE_T, OT_T = 2400, 3600      # ticks: 1x < 120 s, 2x < 180 s, then overtime (tick clock; live game_tick runs 78 ahead)
ABILITY_COST = {k: float(v['mana_cost']) for (k, _), v in SUPPLEMENT.items()}   # own presses; another hero's = 0
TOWER_XY = ((KING_X, MY_KING_Y), (PRINCESS_X_L, MY_PRINCESS_Y), (PRINCESS_X_R, MY_PRINCESS_Y),
            (KING_X, OPP_KING_Y), (PRINCESS_X_L, OPP_PRINCESS_Y), (PRINCESS_X_R, OPP_PRINCESS_Y))   # own frame, TOWER order
TYPES = ('play', 'ability', 'tower_damage', 'tower_fall')
NEVER = 2 ** 31 - 1              # table: a resolution tick that never comes

# encode(): one row per event, newest first; numeric fields ~[0, 1]; every outcome field has a done / known flag
FIELDS = ('is_play', 'is_ability', 'is_tower_damage', 'is_tower_fall',     # type one-hot
          'mine',                                  # play: played by me; tower event: my tower
          'x', 'y', 'xy_known',                    # own frame [0, 1] (my edge y = 1); tower events: the tower's centre
          'ago_60', 't_300',                       # (t - tick) s / 60; game time at the event / 300 s
          'ph_1x', 'ph_2x', 'ph_ot',               # phase at the event
          'elixir_10', 'elixir_known',             # own elixir before an own play / 10
          'crowns_me_3', 'crowns_opp_3', 'margin_2', 'margin_known',   # before the play / at the tower event
          'cost_10',                               # the play's elixir
          'tower_k', 'tower_l', 'tower_r', 'tower_lost',               # tower events: which tower, HP fraction lost
          'out_done', 'out_enemy_lost', 'out_own_lost', 'out_tower_known', 'out_value_10', 'out_value_known',
          'xb_reach', 'xb_done', 'xb_locked', 'xb_failed', 'xb_damage', 'xb_answer_done', 'xb_answered',
          'xb_answer_dist_12',                     # tiles from the X-Bow to its answer / 12
          'is_xb_answer',                          # this play was the first answer to the other side's X-Bow
          'rk_tower', 'rk_done', 'rk_tower_lost', 'rk_tower_known', 'rk_value_10', 'rk_value_known', 'rk_combo')
F = len(FIELDS)                  # 46
_COL = {k: i for i, k in enumerate(FIELDS)}
GROUPS = ('static', 'out', 'xb', 'answer', 'is_answer', 'rk')     # table: when each field appears (its group's res tick)
FIELD_GROUP = np.array([1 if k.startswith('out_') else 2 if k in ('xb_done', 'xb_locked', 'xb_failed', 'xb_damage')
                        else 3 if k in ('xb_answer_done', 'xb_answered', 'xb_answer_dist_12') else 4 if k == 'is_xb_answer'
                        else 5 if k.startswith('rk_') and k != 'rk_tower' else 0 for k in FIELDS])

# summary(): the compact plan-B vector (own side), then CARD_FIELDS per own deck card in the caller's deck order
SUMMARY_FIELDS = ('xb_placed_10', 'xb_resolved_10', 'xb_locked_10', 'xb_failed_10', 'xb_pending_10',   # reach X-Bows
                  'xb_fails_since_lock_10', 'xb_mean_damage', 'xb_has_lock', 'xb_since_lock_60', 'xb_answered_share',
                  'rk_tower_5', 'rk_tower_damage', 'rk_all_5', 'rk_combo_5')
CARD_FIELDS = ('plays_10', 'swing_known', 'swing_mean', 'vpe_known', 'vpe_mean_2')   # swing = enemy - own tower HP lost;
#                                                                                       vpe = value removed per elixir
DECK_N = 8
S = len(SUMMARY_FIELDS) + DECK_N * len(CARD_FIELDS)   # 54
MEM_KEYS = ('mem_ev', 'mem_mask', 'mem_card', 'mem_form', 'mem_summary', 'mem_answer')   # the model's batch keys
TABLE_KEYS = ('tick', 'vis', 'vals', 'res', 'card', 'form', 'ans_card', 'flag', 'xb_dmg', 'rk_tl', 'swing', 'vpe')


def _tiles(a, b):
    return math.hypot((a[0] - b[0]) * TILES_X, (a[1] - b[1]) * TILES_Y)


def _crowns(al):
    """(mine, theirs) from the alive flags: a fallen king is 3."""
    return (3 if not al[3] else (not al[4]) + (not al[5]), 3 if not al[0] else (not al[1]) + (not al[2]))


def _margin(hp):
    v = (hp[1], hp[2], hp[4], hp[5])
    return None if None in v else (v[0] + v[1]) - (v[2] + v[3])


def _order(e):
    return (e['tick'], TYPES.index(e['type']), not e['mine'], e.get('card', ''), e.get('tower', -1), e.get('xy') or (-1.0, -1.0))


def _value(key, hp, mx, top):
    """habit_terms.body_value, and a BUILDING (lead 10-25) at its card cost x hp fraction; None = not counted."""
    v = body_value(key, hp, mx, top)
    if v is None and mx >= 20:
        k, kind, cost = _card(key)
        if kind == 'building' and 'tower' not in k:
            v = cost * max(0, hp) / max(1, mx)
    return v


def warm():
    """Load the card tables the outcomes read (habit_terms' RoyaleSim card table, the reader catalog) ahead of the first
    decision (the live pilot calls it when a memory checkpoint loads)."""
    from .public_observation import public_frame
    public_frame(dict(game_tick=0, entities=[]), source='reader')
    _value('knight', 1.0, 1.0, {})
    catalog_card_form(0)


def _ids(deck, gid):
    return [int(c) if isinstance(c, (int, np.integer)) else (gid or {}).get(card_key(str(c)), 0) for c in list(deck)[:DECK_N]]


# ------------------------------------------------------------------------------------------------------------ adapters
def engine_xy(xn, yn, side):
    """Inverse of obs_contract._engine_xy: own-frame (x, y) in [0, 1] -> engine millitiles (live own plays carry own-frame xy)."""
    x, y = xn * 18000.0, (1.0 - yn) * 32000.0
    return (18000.0 - x, 32000.0 - y) if int(side) == 1 else (x, y)


def tower_reads(bs):
    """BoardState -> (6 HP fractions or None, 6 alive flags) in TOWER order."""
    return tuple(t.hp_frac for t in bs.towers), tuple(t.alive for t in bs.towers)


def tower_reads_sc(sc):
    """Row scalars (obs_contract.to_tokens sc) -> the same: hp sc[52:58] where known sc[58:64], alive sc[64:70]."""
    return (tuple(float(sc[52 + i]) if sc[58 + i] > .5 else None for i in range(6)),
            tuple(bool(sc[64 + i] > .5) for i in range(6)))


def tower_reads_engine(towers, side):
    """Engine crown towers -> the same, by obs_contract.from_engine's rule (frac hp / max_hp; alive = hp > 0 and not destroyed;
    a missing tower is destroyed; lane by own-frame x). Rows: dicts side, type, x, y, hp, max_hp[, destroyed] (SIM
    episode.crown_towers, live_mem.to_observe) or native lists [side, kind, lane, x, y, hp, max_hp]."""
    hp, al = [0.0] * 6, [False] * 6
    for tw in towers:
        if isinstance(tw, dict):
            s, kind, X, Y, h, mh, dead = (tw['side'], tw.get('type'), tw['x'], tw['y'], tw['hp'], tw['max_hp'],
                                          bool(tw.get('destroyed', False)))
        else:
            (s, kind, _, X, Y, h, mh), dead = tw[:7], False
        x = _engine_xy(float(X), float(Y), int(side) == 1)[0]
        i = 3 * int(int(s) != int(side)) + (0 if kind == 'king' else 1 if x < .5 else 2)
        al[i] = h > 0 and not dead
        hp[i] = (float(h) / float(mh) if mh else 0.0) if al[i] else 0.0
    return tuple(hp), tuple(al)


def sample_sim(state, side):
    """A RoyaleSim raw state (Match.state, UN-extrapolated) -> observe()'s sample (towers, alive, own elixir, bodies)."""
    from .public_observation import public_frame
    tw, al = tower_reads_engine(state['episode']['crown_towers'], side)
    el = next(float(p['elixir_exact']) for p in state['players'] if int(p['side']) == int(side))
    return dict(tick=int(state['tick']), towers=tw, alive=al, elixir=el,
                units=public_frame(state, source='sim')['entities'])


# ------------------------------------------------------------------------------------------------------------ memory
class MatchMemory:
    """One match, one observer side. ``observe`` once per decision (ticks increasing), ``features(t)`` after it."""

    def __init__(self, side):
        self.side = int(side)
        self.t, self.hp, self.alive, self.el, self.units, self.top = [], [], [], [], [], []
        self.plays, self.tower_ev = [], []
        self._keys, self._cache, self._sorted, self._ticks = set(), {}, None, []
        self._ref, self._last, self._up = [None] * 6, [None] * 6, [None] * 6
        self.late = 0                              # plays received after a decision later than their tick (S2 measures)

    # ------------------------------------------------------------------------------------------------------- input
    def observe(self, tick, towers, alive, elixir=None, units=None, plays=()):
        tick = int(tick)
        prev = self.t[-1] if self.t else None
        if prev is not None and tick < prev:
            raise ValueError('MatchMemory.observe: tick went backwards (a new match needs a new MatchMemory)')
        if prev is None or tick > prev:
            self._sample(tick, towers, alive, elixir, units)
        for p in plays:
            tp = int(p['tick'])
            if tp > tick:
                continue
            late = prev is not None and tp < prev
            if self._add(p, tick if late else p.get('seen', tp)) and late:
                self.late += 1

    def _sample(self, tick, towers, alive, elixir, units):
        al = tuple(bool(a) for a in alive)
        hp = tuple((None if h is None else float(h)) if a else 0.0 for h, a in zip(towers, al))
        if len(hp) != 6 or len(al) != 6:
            raise ValueError('towers / alive need 6 entries in TOWER order')
        self.t.append(tick)
        self.hp.append(hp)
        self.alive.append(al)
        self.el.append(None if elixir is None else float(elixir))
        for i in range(6):                         # tower events, debounced (one pass, causal)
            if self._up[i] is None:
                self._up[i] = al[i]
            h, ref = hp[i], self._ref[i]
            if h is not None:
                if ref is None or h > ref:         # first read, or a re-read upwards: new baseline (towers never heal)
                    self._ref[i] = h
                elif ref - h >= DMG_MIN and (self._last[i] is None or tick - self._last[i] >= DMG_GAP):
                    self._tower(tick, 'tower_damage', i, ref - h, hp, al)
                    self._ref[i], self._last[i] = h, tick
            if self._up[i] and not al[i]:          # a fall is recorded once
                self._up[i] = False
                self._tower(tick, 'tower_fall', i, None, hp, al)
        mine, opp = self.top[-1] if self.top else ({}, {})
        if units is None:
            self.units.append(None)
        else:
            U = {}
            for e in units:
                name = catalog_card_form(int(e['card_id']))[0]
                key = vocab.engine_key(name) if name else None
                if not key:
                    continue
                rel, mx = int(int(e['side']) != self.side), float(e['max_hp'])
                U[e['address']] = (rel, key, float(e['hp']), mx, *_engine_xy(float(e['x']), float(e['y']), self.side == 1))
                d = opp if rel else mine           # the biggest body of a card so far (body_value's child rule)
                if mx > d.get(key, 0.0):
                    if d is (self.top[-1][rel] if self.top else None):
                        d = dict(d)                # copy on write: earlier samples keep their snapshot
                        if rel:
                            opp = d
                        else:
                            mine = d
                    d[key] = mx
            self.units.append(U)
        self.top.append((mine, opp))

    def _tower(self, tick, kind, i, lost, hp, al):
        self.tower_ev.append(dict(type=kind, tick=tick, mine=i < 3, tower=i, lost=lost, xy=TOWER_XY[i], el=None,
                                  crowns=_crowns(al), margin=_margin(hp)))
        self._sorted = None

    def _add(self, p, seen):
        if not p.get('accepted', True):
            return False
        slug = card_key(str(p.get('card') or ''))
        if not slug:
            return False
        tp, side, ab = int(p['tick']), int(p['side']), bool(p.get('ability'))
        x, y = p.get('x'), p.get('y')
        xy = None if x is None or y is None else _engine_xy(float(x), float(y), self.side == 1)
        k = (tp, side, slug, ab, xy)
        if k in self._keys:
            return False
        self._keys.add(k)
        mine = side == self.side
        i = bisect_left(self.t, tp) - 1            # the state BEFORE the play: the last sample < its tick
        hp, al = (self.hp[i], self.alive[i]) if i >= 0 else ((None,) * 6, (True,) * 6)
        el = p.get('elixir_before') if mine else None
        if mine and el is None and i >= 0:
            el = self.el[i]
        e = dict(type='ability' if ab else 'play', tick=tp, seen=max(tp, int(seen)), mine=mine, card=slug,
                 form=FORM_PAD if p.get('form') is None else int(p['form']), xy=xy, el=None if el is None else float(el),
                 crowns=_crowns(al), margin=_margin(hp), cost=ABILITY_COST.get(slug, 0.0) if ab else play_cost(slug))
        if slug == 'x-bow' and not ab:             # reach: an alive enemy princess within XB_REACH at the play (xbow_count)
            j = bisect_right(self.t, tp) - 1
            e['reach'] = None if xy is None or j < 0 else tuple(
                q for q in ((4, 5) if mine else (1, 2)) if (self.hp[j][q] or 0.0) > 0 and _tiles(xy, TOWER_XY[q]) <= XB_REACH)
        if slug == 'rocket' and mine and not ab:
            d = min((_tiles(xy, TOWER_XY[q]), q) for q in (3, 4, 5)) if xy is not None else (99.0, None)
            e['aim'] = d[1] if d[0] <= RK_TOWER_R else None
        self.plays.append(e)
        self._sorted = None
        return True

    # ------------------------------------------------------------------------------------------------------ outcomes
    def _lost(self, idx, i0, i1):
        if i0 < 0 or i1 < 0:
            return None
        a, b = [self.hp[i0][j] for j in idx], [self.hp[i1][j] for j in idx]
        return None if None in a or None in b else sum(max(0.0, u - v) for u, v in zip(a, b))

    def _removed(self, xy, target, i0, i1, radius):
        """Value (``_value``) the ``target`` side's bodies lost between their first sample within ``radius`` tiles of ``xy``
        (samples i0..i1) and sample i1 (absent there = dead). None = unknown."""
        i0 = max(i0, 0)
        if xy is None or i1 < i0:
            return None
        span = self.units[i0:i1 + 1]
        if any(u is None for u in span):
            return None
        first = {}
        for U in span:
            for uid, (rel, key, hp, mx, x, y) in U.items():
                if rel == target and uid not in first and _tiles((x, y), xy) <= radius:
                    first[uid] = (key, hp, mx)
        top, end, out = self.top[i1][target], span[-1], 0.0
        for uid, (key, hp, mx) in first.items():   # ponytail: whoever killed it, the nearby play gets the credit
            v0 = _value(key, hp, mx, top)
            if v0:
                u = end.get(uid)
                v1 = (_value(u[1], u[2], u[3], top) or 0.0) if u is not None else 0.0
                out += max(0.0, v0 - v1)
        return out

    def _generic(self, e):
        tp = e['tick']
        i0, i1 = bisect_left(self.t, tp) - 1, bisect_right(self.t, tp + W_OUT) - 1
        en, own = ((3, 4, 5), (0, 1, 2)) if e['mine'] else ((0, 1, 2), (3, 4, 5))
        return dict(enemy_lost=self._lost(en, i0, i1), own_lost=self._lost(own, i0, i1),
                    value=self._removed(e['xy'], int(e['mine']), i0, i1, VALUE_R))

    def _xbow(self, e):
        """succ48/xbow_count.py: locked = a reach princess lost >= XB_LOCK of its max HP in (tick, tick + XB_WINDOW]."""
        tp = e['tick']
        i0, lo, hi = bisect_right(self.t, tp) - 1, bisect_right(self.t, tp), bisect_right(self.t, tp + XB_WINDOW)
        locked, dmg = False, 0.0
        for j in e['reach']:
            later = [self.hp[k][j] for k in range(lo, hi) if self.hp[k][j] is not None]
            if later:
                d = self.hp[i0][j] - min(later)
                locked |= d >= XB_LOCK
                dmg += max(0.0, d)
        return dict(locked=locked, damage=dmg)

    def _rocket(self, e):
        tp = e['tick']
        i0, i1 = bisect_left(self.t, tp) - 1, bisect_right(self.t, tp + RK_WIN) - 1
        return dict(tower_lost=None if e['aim'] is None else self._lost((e['aim'],), i0, i1),
                    value=self._removed(e['xy'], 1, i0, i1, RK_R))

    def _get(self, e, k, fn):
        key = (id(e), k)
        if key not in self._cache:                 # computed once, after its window closed: samples up to it are final
            self._cache[key] = fn(e)
        return self._cache[key]

    # ------------------------------------------------------------------------------------------------------ output
    def events(self, t):
        """Every event visible at decision tick ``t`` (chronological), outcomes merged in where resolved."""
        t = int(t)
        if self._sorted is None:
            self._sorted = sorted(self.plays + self.tower_ev, key=_order)
            self._ticks = [e['tick'] for e in self._sorted]
        out = []
        for e in self._sorted[:bisect_left(self._ticks, t)]:
            if e.get('seen', e['tick']) > t:
                continue
            d = dict(e)
            if e['type'] in ('play', 'ability'):
                tp = e['tick']
                d['out'] = self._get(e, 'g', self._generic) if tp + W_OUT < t else None
                if 'reach' in e:
                    d['xb'] = self._get(e, 'xb', self._xbow) if e['reach'] and tp + XB_WINDOW < t else None
                if 'aim' in e:
                    d['rk'] = dict(self._get(e, 'rk', self._rocket)) if tp + RK_WIN < t else None
            out.append(d)
        plays = [d for d in out if d['type'] == 'play']
        ontime = [q for q in plays if q['seen'] == q['tick']]
        for d in plays:
            tp = d['tick']
            if 'reach' in d:                       # the answer: the other side's first on-time play in lane in 4 s
                a = None
                if d['xy'] is not None:
                    a = next((q for q in ontime if q['mine'] != d['mine'] and tp < q['tick'] <= tp + XB_ANSWER_T
                              and q['xy'] is not None and (q['xy'][0] < .5) == (d['xy'][0] < .5)
                              and _tiles(q['xy'], d['xy']) <= XB_ANSWER_R), None)
                if a is not None:
                    a['is_answer'] = True
                    d['answer'], d['ans_dist'], d['_ans'] = a['card'], _tiles(a['xy'], d['xy']), a
                else:
                    d['answer'] = '' if d['xy'] is not None and t > tp + XB_ANSWER_T else None
            if d.get('rk') is not None:
                d['rk']['combo'] = any(COMBO[0] <= tp - q['tick'] <= COMBO[1] for q in ontime
                                       if q['mine'] and q['card'] == 'tornado')
        return out

    def features(self, t, gid, deck=()):
        """The model inputs at decision tick ``t`` (MEM_KEYS); ``deck`` = the own deck's 8 card ids (gid) or names, the order
        the per-card summary rows follow (the model's ``deck_card``)."""
        ev = self.events(t)
        e, m, c, f = encode(ev, t, gid)
        s, ans = summary(ev, t, deck, gid)
        return dict(mem_ev=e, mem_mask=m, mem_card=c, mem_form=f, mem_summary=s, mem_answer=np.int64(ans))

    def table(self, gid):
        """The per-match event table (TABLE_KEYS) for ``features_at``. Call at the END of the match (an outcome whose window
        is still open is computed from the samples so far; features_at only shows it at ticks after its window)."""
        saved, self._cache = self._cache, dict(self._cache)    # nothing computed here may leak into a later features(t)
        try:
            ev = self.events(NEVER)
        finally:
            self._cache = saved
        n = len(ev)
        pos = {id(d): i for i, d in enumerate(ev)}
        tab = dict(tick=np.array([d['tick'] for d in ev], np.int32),
                   vis=np.array([max(d['tick'] + 1, d.get('seen', d['tick'])) for d in ev], np.int32),
                   vals=np.zeros((n, F), np.float32), res=np.zeros((n, len(GROUPS)), np.int32),
                   card=np.array([gid.get(d['card'], 0) if 'card' in d else 0 for d in ev], np.int32),
                   form=np.array([d['form'] if 'card' in d else FORM_PAD for d in ev], np.int8),
                   ans_card=np.zeros(n, np.int32), flag=np.zeros(n, np.int8), xb_dmg=np.zeros(n), rk_tl=np.zeros(n),
                   swing=np.zeros(n), vpe=np.zeros(n))
        tab['res'][[i for i, d in enumerate(ev) if 'card' in d], 1:] = NEVER   # before any is_answer tick is lowered
        for i, d in enumerate(ev):
            for k, x in _row(d, d['tick']).items():
                tab['vals'][i, _COL[k]] = x
            tab['vals'][i, _COL['ago_60']] = 0.0
            if 'card' not in d:
                continue
            tp = d['tick']
            tab['res'][i, 1] = tp + W_OUT + 1
            o = d['out']
            if o['enemy_lost'] is not None and o['own_lost'] is not None:
                tab['swing'][i] = o['enemy_lost'] - o['own_lost']
            if o['value'] is not None and d['cost'] > 0:
                tab['vpe'][i] = o['value'] / d['cost']
            own = d['type'] == 'play' and d['mine']
            if 'reach' in d:
                tab['flag'][i] |= int(own)
                if d['reach']:
                    tab['res'][i, 2], tab['xb_dmg'][i] = tp + XB_WINDOW + 1, d['xb']['damage']
                if d['answer'] is not None:
                    a = d.get('_ans')
                    tab['res'][i, 3] = a['tick'] + 1 if a is not None else tp + XB_ANSWER_T + 1
                    if a is not None:
                        tab['ans_card'][i], tab['flag'][i] = gid.get(a['card'], 0), tab['flag'][i] | 4
                        j = pos[id(a)]
                        tab['res'][j, 4] = min(tab['res'][j, 4], max(a['tick'] + 1, tab['vis'][i]))
            if 'aim' in d:
                tab['flag'][i] |= 2 * int(own)
                tab['res'][i, 5], tab['rk_tl'][i] = tp + RK_WIN + 1, d['rk']['tower_lost'] or 0.0
        return tab


def build(side, samples, plays=()):
    """Offline: a whole recorded match -> MatchMemory (its features(t) = the incremental ones at every decision tick)."""
    m = MatchMemory(side)
    for s in sorted(samples, key=lambda s: int(s['tick'])):
        m.observe(**s)
    for p in plays:
        m._add(p, p.get('seen', p['tick']))
    return m


def _row(e, t):
    tp = e['tick']
    v = {'is_' + e['type']: 1.0, 'mine': float(e['mine']), 'ago_60': (t - tp) * TICK_S / 60, 't_300': tp * TICK_S / 300,
         ('ph_1x', 'ph_2x', 'ph_ot')[0 if tp < DOUBLE_T else 1 if tp < OT_T else 2]: 1.0,
         'crowns_me_3': e['crowns'][0] / 3, 'crowns_opp_3': e['crowns'][1] / 3}
    if e['xy'] is not None:
        v.update(x=e['xy'][0], y=e['xy'][1], xy_known=1.0)
    if e['el'] is not None:
        v.update(elixir_10=e['el'] / 10, elixir_known=1.0)
    if e['margin'] is not None:
        v.update(margin_2=e['margin'] / 2, margin_known=1.0)
    if 'tower' in e:
        v[('tower_k', 'tower_l', 'tower_r')[e['tower'] % 3]] = 1.0
        v['tower_lost'] = e['lost'] or 0.0
        return v
    v['cost_10'] = e['cost'] / 10
    o = e.get('out')
    if o is not None:
        v['out_done'] = 1.0
        if o['enemy_lost'] is not None and o['own_lost'] is not None:
            v.update(out_enemy_lost=o['enemy_lost'], out_own_lost=o['own_lost'], out_tower_known=1.0)
        if o['value'] is not None:
            v.update(out_value_10=o['value'] / 10, out_value_known=1.0)
    if e.get('reach'):
        v['xb_reach'] = 1.0
    if e.get('xb') is not None:
        v.update(xb_done=1.0, xb_locked=float(e['xb']['locked']), xb_failed=float(not e['xb']['locked']),
                 xb_damage=e['xb']['damage'])
    if e.get('answer') is not None:
        v.update(xb_answer_done=1.0, xb_answered=float(bool(e['answer'])))
        if e['answer']:
            v['xb_answer_dist_12'] = e['ans_dist'] / XB_ANSWER_R
    if e.get('is_answer'):
        v['is_xb_answer'] = 1.0
    if e.get('aim') is not None:
        v['rk_tower'] = 1.0
    rk = e.get('rk')
    if rk is not None:
        v.update(rk_done=1.0, rk_combo=float(rk['combo']))
        if rk['tower_lost'] is not None:
            v.update(rk_tower_lost=rk['tower_lost'], rk_tower_known=1.0)
        if rk['value'] is not None:
            v.update(rk_value_10=rk['value'] / 10, rk_value_known=1.0)
    return v


def encode(events, t, gid):
    """events(t) -> (ev [E_MAX, F] float32, mask [E_MAX] bool, card [E_MAX] int64 (gid ids, 0 = pad / tower event),
    form [E_MAX] int64 (FORM_PAD = pad / unknown)); the newest E_MAX events, newest first."""
    ev = np.zeros((E_MAX, F), np.float32)
    mask = np.zeros(E_MAX, bool)
    card = np.zeros(E_MAX, np.int64)
    form = np.full(E_MAX, FORM_PAD, np.int64)
    for r, e in enumerate(reversed(events[-E_MAX:])):
        for k, x in _row(e, t).items():
            ev[r, _COL[k]] = x
        mask[r] = True
        if 'card' in e:
            card[r], form[r] = gid.get(e['card'], 0), e['form']
    return ev, mask, card, form


def _mean(xs):
    return sum(xs) / len(xs) if xs else 0.0


def summary(events, t, deck=(), gid=None):
    """events(t) -> ([S] float32 = SUMMARY_FIELDS + CARD_FIELDS per card of ``deck`` (up to 8 gid ids or names, the caller's
    order; missing / id 0 = zeros), the opponent's most frequent answer card to our X-Bows as a gid id (0 = none; tie =
    latest))."""
    gid = gid or {}
    own = [e for e in events if e['type'] == 'play' and e['mine']]
    xb = [e for e in own if e['card'] == 'x-bow']
    reach = [e for e in xb if e.get('reach')]
    done = [e for e in reach if e.get('xb') is not None]
    locked = [e for e in done if e['xb']['locked']]
    since = 0
    for e in done:
        since = 0 if e['xb']['locked'] else since + 1
    answers = [e['answer'] for e in xb if e.get('answer') is not None]
    found = [gid.get(a, 0) for a in answers if a]
    rk = [e for e in own if e['card'] == 'rocket']
    rkt = [e for e in rk if e.get('aim') is not None]
    s = [len(xb) / 10, len(done) / 10, len(locked) / 10, (len(done) - len(locked)) / 10, (len(reach) - len(done)) / 10,
         since / 10, _mean([e['xb']['damage'] for e in done]), float(bool(locked)),
         (t - locked[-1]['tick']) * TICK_S / 60 if locked else 0.0, len(found) / len(answers) if answers else 0.0,
         len(rkt) / 5, sum(e['rk']['tower_lost'] or 0.0 for e in rkt if e.get('rk')), len(rk) / 5,
         sum(bool(e.get('rk') and e['rk']['combo']) for e in rk) / 5]
    for c in _ids(deck, gid):
        ps = [e for e in own if c and gid.get(e['card'], 0) == c]
        res = [e['out'] for e in ps if e.get('out') is not None]
        sw = [o['enemy_lost'] - o['own_lost'] for o in res if o['enemy_lost'] is not None and o['own_lost'] is not None]
        vp = [e['out']['value'] / e['cost'] for e in ps if e.get('out') is not None and e['out']['value'] is not None
              and e['cost'] > 0]
        s += [len(ps) / 10, float(bool(sw)), _mean(sw), float(bool(vp)), _mean(vp) / 2]
    s += [0.0] * (S - len(s))
    cnt, last = {}, {}
    for i, a in enumerate(found):
        cnt[a], last[a] = cnt.get(a, 0) + 1, i
    best = max(cnt, key=lambda a: (cnt[a], last[a])) if cnt else 0
    return np.asarray(s, np.float32), best


# ------------------------------------------------------------------------------------------------------------ tables
def features_at(tab, ticks, deck=()):
    """MatchMemory.features(t, gid, deck) for every t in ``ticks``, from the match's ``table(gid)``, vectorised (numpy, CPU;
    sums run in event order through np.cumsum, as the python sums do, so the arrays are bit-identical). ``deck`` = 8 gid ids."""
    ticks = np.asarray(ticks, np.int64)
    T, N = len(ticks), len(tab['tick'])
    out = dict(mem_ev=np.zeros((T, E_MAX, F), np.float32), mem_mask=np.zeros((T, E_MAX), bool),
               mem_card=np.zeros((T, E_MAX), np.int64), mem_form=np.full((T, E_MAX), FORM_PAD, np.int64),
               mem_summary=np.zeros((T, S), np.float32), mem_answer=np.zeros(T, np.int64))
    if not T or not N:
        return out
    tick, vals, res = tab['tick'].astype(np.int64), tab['vals'], tab['res'].astype(np.int64)
    t = ticks[:, None]
    V = t >= tab['vis'].astype(np.int64)[None]
    rank = np.cumsum(V[:, ::-1], 1)[:, ::-1]                  # visible events at or after each one
    r, n = np.nonzero(V & (rank <= E_MAX))
    p = rank[r, n] - 1                                        # 0 = the newest
    rows = np.where(ticks[r][:, None] >= res[n][:, FIELD_GROUP], vals[n], np.float32(0))
    rows[:, _COL['ago_60']] = ((ticks[r] - tick[n]) * TICK_S / 60).astype(np.float32)
    out['mem_ev'][r, p] = rows
    out['mem_mask'][r, p] = True
    out['mem_card'][r, p] = tab['card'][n]
    out['mem_form'][r, p] = tab['form'][n]
    col = (lambda k: vals[:, _COL[k]] == 1)
    fl = tab['flag'].astype(np.int64)
    idx = np.arange(N)
    csum = (lambda m, x: np.cumsum(np.where(m, x[None], 0.0), 1)[:, -1])
    mean = (lambda m, x: np.where(m.sum(1) > 0, csum(m, x) / np.maximum(m.sum(1), 1), 0.0))
    xb = V & ((fl & 1) > 0)[None]
    reach = xb & col('xb_reach')[None]
    done = reach & (t >= res[None, :, 2])
    locked = done & col('xb_locked')[None]
    last = np.where(locked, idx, -1).max(1)
    since = (done & ~locked & (idx[None] > last[:, None])).sum(1)
    ans = xb & (t >= res[None, :, 3])
    found = ans & ((fl & 4) > 0)[None]
    rk = V & ((fl & 2) > 0)[None]
    rkt = rk & col('rk_tower')[None]
    rkd = rk & (t >= res[None, :, 5])
    nl, na = locked.sum(1), ans.sum(1)
    s = [xb.sum(1) / 10, done.sum(1) / 10, nl / 10, (done.sum(1) - nl) / 10, (reach.sum(1) - done.sum(1)) / 10, since / 10,
         mean(done, tab['xb_dmg']), (nl > 0).astype(np.float64),
         np.where(nl > 0, (ticks - tick[np.maximum(last, 0)]) * TICK_S / 60, 0.0),
         np.where(na > 0, found.sum(1) / np.maximum(na, 1), 0.0), rkt.sum(1) / 5, csum(rkt & rkd, tab['rk_tl']),
         rk.sum(1) / 5, (rkd & col('rk_combo')[None]).sum(1) / 5]
    own = V & (col('is_play') & col('mine'))[None]
    od = own & (t >= res[None, :, 1])
    tk, vk = od & col('out_tower_known')[None], od & (col('out_value_known') & (vals[:, _COL['cost_10']] > 0))[None]
    card = tab['card'].astype(np.int64)
    for c in list(deck)[:DECK_N]:
        c = int(c)
        m = (card == c)[None] & (c != 0)
        s += [(own & m).sum(1) / 10, ((tk & m).sum(1) > 0).astype(np.float64), mean(tk & m, tab['swing']),
              ((vk & m).sum(1) > 0).astype(np.float64), mean(vk & m, tab['vpe']) / 2]
    out['mem_summary'][:, :len(s)] = np.stack([np.broadcast_to(np.asarray(x, np.float64), (T,)) for x in s], 1)
    ac = tab['ans_card'].astype(np.int64)
    best, key = np.zeros(T, np.int64), np.full(T, -1, np.int64)
    for u in np.unique(ac[(fl & 4) > 0]):                     # most frequent answer card, tie = the latest
        mu = found & (ac == u)[None]
        k = np.where(mu.any(1), mu.sum(1) * (N + 1) + np.where(mu, idx, -1).max(1), -1)
        best, key = np.where(k > key, u, best), np.maximum(k, key)
    out['mem_answer'][:] = best
    return out


def pack(tables):
    """A list of tables -> one dict of concatenated arrays + ``off`` (event offsets, len(tables) + 1)."""
    off = np.concatenate([[0], np.cumsum([len(tb['tick']) for tb in tables])]).astype(np.int64)
    out = {k: np.concatenate([tb[k] for tb in tables]) if tables else np.zeros(0) for k in TABLE_KEYS}
    out['off'] = off
    return out


def unpack(packed, j):
    a, b = int(packed['off'][j]), int(packed['off'][j + 1])
    return {k: packed[k][a:b] for k in TABLE_KEYS}


def rows_features(packed, row_tab, row_t, row_deck, ids):
    """MEM_KEYS arrays for rows ``ids`` of a batch / dataset: row i is table ``row_tab[i]`` (index into ``packed``; -1 = no
    table: an empty memory) at tick ``row_t[i]`` with deck ``row_deck[i]`` (8 gid ids; one table = one match side = one
    deck). Grouped per table."""
    ids = np.asarray(ids, np.int64)
    tabs = np.asarray(row_tab)[ids]
    out = empty_rows(len(ids))
    for j in np.unique(tabs[tabs >= 0]):
        sel = np.flatnonzero(tabs == j)
        f = features_at(unpack(packed, int(j)), np.asarray(row_t)[ids[sel]], np.asarray(row_deck)[ids[sel[0]]])
        for k in MEM_KEYS:
            out[k][sel] = f[k]
    return out


def mirror_ev(ev):
    """Left-right mirror of encoded events [..., F] (torch or numpy; train_gen's mirror augmentation): x -> 1 - x where
    known, tower L <-> R. The only lateral fields: the X-Bow lane rule and the summary are mirror-invariant."""
    out = ev.clone() if hasattr(ev, 'clone') else ev.copy()
    x, k, lc, rc = _COL['x'], _COL['xy_known'], _COL['tower_l'], _COL['tower_r']
    out[..., x] = (1 - ev[..., x]) * ev[..., k] + ev[..., x] * (1 - ev[..., k])
    out[..., lc], out[..., rc] = ev[..., rc], ev[..., lc]
    return out


def empty_rows(n):
    """MEM_KEYS for ``n`` rows with an EMPTY memory (no event, zero summary): a path with no tables (declared, never silent)."""
    return dict(mem_ev=np.zeros((n, E_MAX, F), np.float32), mem_mask=np.zeros((n, E_MAX), bool),
                mem_card=np.zeros((n, E_MAX), np.int64), mem_form=np.full((n, E_MAX), FORM_PAD, np.int64),
                mem_summary=np.zeros((n, S), np.float32), mem_answer=np.zeros(n, np.int64))
