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

MEMORY v2 (Plan A S1c, owner 2026-10-25): v1 + S1C_FIELDS appended to the summary (S_V2 floats), computed at feature time
from the SAME event tables (no rebuild; ``version='v2'`` + the vocabulary ``gid`` on features / features_at / rows_features):
counter priors of the opponent cards revealed so far (counter_priors.json), their cycle (plays since, plays until back in
hand, elixir to cycle there, the public opponent elixir estimate, counter ready), king activation, the tower-HP margin and its
30 / 60 s trend, and the frozen lock head's P(lock) for a reach X-Bow placed now (lock_head.json; both artifacts by
scratchpad/gauntlet/L74/memory/s1c/fit_s1c.py). v1 (its features, tables, config hash, checkpoints) is untouched: every v2
path is opt-in by ``version``.
"""
from __future__ import annotations

import hashlib
import json
import math
from bisect import bisect_left, bisect_right
from functools import lru_cache

import numpy as np

from . import vocab
from .dataset_gen import CARD_STANDINS, FORM_PAD, card_key
from .habit_terms import XB_LOCK, XB_REACH, XB_WINDOW, _card, body_value, play_cost
from .obs_contract import (KING_X, MY_KING_Y, MY_PRINCESS_Y, OPP_KING_Y, OPP_PRINCESS_Y, PRINCESS_X_L, PRINCESS_X_R, REPO,
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

# memory v2 (S1c): appended to the summary, all from the visible events at t (``_s1c``)
S1C_DIR = REPO / 'scratchpad/gauntlet/L74/memory/s1c'
PRIORS = S1C_DIR / 'counter_priors.json'      # fit_s1c.py: per opponent card, the shrunk X-Bow lock lifts (deck / answer view)
LOCK_HEAD = S1C_DIR / 'lock_head.json'        # fit_s1c.py: logistic P(lock) of a reach X-Bow placed now
COUNTER_LIFT = -0.10     # a revealed card whose ANSWER-view lift is below this counts as a counter (fit_s1c.out: the spread)
CYCLE = 4                # 8-card deck, 4 in hand: a played card is back in hand after 4 further plays
SLOT_N = 8               # per revealed opponent card, strongest answer-lift first
SLOT_FIELDS = ('on', 'need_4', 'cost_10', 'ans_lift', 'deck_lift')    # need = plays before it is back in hand (0 = in hand)
S1C_FIELDS = (('opp_revealed_8', 'deck_lift_min', 'deck_lift_neg_sum', 'ans_lift_min',          # priors of revealed cards
               'ctr_known', 'ctr_plays_4', 'ctr_cycle_el_10', 'opp_el_10', 'ctr_ready')        # cycle + counter ready
              + tuple(f'slot{i}_{k}' for i in range(SLOT_N) for k in SLOT_FIELDS)
              + ('own_king_on', 'own_king_since_60', 'opp_king_on', 'opp_king_since_60',       # king activated
                 'margin_p_2', 'margin_k', 'margin_p_d30_2', 'margin_p_d60_2', 'margin_k_d30', 'margin_k_d60',
                 'xb_lock_p'))                                                                  # the frozen lock head
S_V2 = S + len(S1C_FIELDS)                    # 114
N_SUM = {'v1': S, 'v2': S_V2}                 # summary width per memory version (model_gen reads the version from it)
LOCK_INPUTS = SUMMARY_FIELDS + S1C_FIELDS[:-1] + ('t_300', 'ph_1x', 'ph_2x', 'ph_ot')


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

    def features(self, t, gid, deck=(), version='v1'):
        """The model inputs at decision tick ``t`` (MEM_KEYS); ``deck`` = the own deck's 8 card ids (gid) or names, the order
        the per-card summary rows follow (the model's ``deck_card``). ``version`` 'v2': + the S1C_FIELDS, from this match's
        table so far (the one vectorised implementation, so incremental == offline by construction of the table)."""
        ev = self.events(t)
        e, m, c, f = encode(ev, t, gid)
        s, ans = summary(ev, t, deck, gid)
        if version != 'v1':                       # = features_at(table, [t], deck, 'v2', gid) minus its v1 part (= s)
            if version != 'v2':
                raise ValueError(f'memory version {version!r}: v1 or v2')
            tab = self.table(gid)
            E = {k: tab[k][None] for k in TABLE_KEYS}
            s = np.concatenate([s, _s1c(E, [t], s[None, :len(SUMMARY_FIELDS)], v2_lut(gid), lock_head())[0].astype(np.float32)])
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
def _features(E, ticks, decks, version='v1', gid=None):
    """``_features_v1``; version 'v2' appends ``_s1c`` (needs ``gid``, the vocabulary the tables' card ids are in)."""
    out = _features_v1(E, ticks, decks)
    if version == 'v1':
        return out
    if version != 'v2':
        raise ValueError(f'memory version {version!r}: v1 or v2')
    T = len(out['mem_answer'])
    s = np.zeros((T, S_V2), np.float32)
    s[:, :S] = out['mem_summary']
    if T:
        s[:, S:] = _s1c(E, ticks, s[:, :len(SUMMARY_FIELDS)], v2_lut(gid), lock_head())
    out['mem_summary'] = s
    return out


def _features_v1(E, ticks, decks):
    """The vectorised MatchMemory.features: ``E`` = per-ROW event arrays {TABLE_KEYS: [T, N, ...]} (each row its own match's
    events, padding never visible), ``ticks`` [T], ``decks`` [T, <= 8] gid ids. Sums run in event order through np.cumsum,
    as the python sums do, so every array is bit-identical to MatchMemory.features (tested)."""
    ticks = np.asarray(ticks, np.int64)
    T, N = E['tick'].shape
    out = empty_rows(T)
    if not T or not N:
        return out
    tick, vals, res = E['tick'].astype(np.int64), E['vals'], E['res'].astype(np.int64)
    t = ticks[:, None]
    V = t >= E['vis'].astype(np.int64)
    rank = np.cumsum(V[:, ::-1], 1)[:, ::-1]                  # visible events at or after each one
    r, n = np.nonzero(V & (rank <= E_MAX))
    p = rank[r, n] - 1                                        # 0 = the newest
    rows = np.where(ticks[r][:, None] >= res[r, n][:, FIELD_GROUP], vals[r, n], np.float32(0))
    rows[:, _COL['ago_60']] = ((ticks[r] - tick[r, n]) * TICK_S / 60).astype(np.float32)
    out['mem_ev'][r, p] = rows
    out['mem_mask'][r, p] = True
    out['mem_card'][r, p] = E['card'][r, n]
    out['mem_form'][r, p] = E['form'][r, n]
    col = (lambda k: vals[..., _COL[k]] == 1)
    fl = E['flag'].astype(np.int64)
    idx = np.arange(N)[None]
    csum = (lambda m, x: np.cumsum(np.where(m, x, 0.0), 1)[:, -1])
    mean = (lambda m, x: np.where(m.sum(1) > 0, csum(m, x) / np.maximum(m.sum(1), 1), 0.0))
    xb = V & ((fl & 1) > 0)
    reach = xb & col('xb_reach')
    done = reach & (t >= res[..., 2])
    locked = done & col('xb_locked')
    last = np.where(locked, idx, -1).max(1)
    since = (done & ~locked & (idx > last[:, None])).sum(1)
    ans = xb & (t >= res[..., 3])
    found = ans & ((fl & 4) > 0)
    rk = V & ((fl & 2) > 0)
    rkt = rk & col('rk_tower')
    rkd = rk & (t >= res[..., 5])
    nl, na = locked.sum(1), ans.sum(1)
    t_last = np.take_along_axis(tick, np.maximum(last, 0)[:, None], 1)[:, 0]
    s = [xb.sum(1) / 10, done.sum(1) / 10, nl / 10, (done.sum(1) - nl) / 10, (reach.sum(1) - done.sum(1)) / 10, since / 10,
         mean(done, E['xb_dmg']), (nl > 0).astype(np.float64), np.where(nl > 0, (ticks - t_last) * TICK_S / 60, 0.0),
         np.where(na > 0, found.sum(1) / np.maximum(na, 1), 0.0), rkt.sum(1) / 5, csum(rkt & rkd, E['rk_tl']),
         rk.sum(1) / 5, (rkd & col('rk_combo')).sum(1) / 5]
    own = V & col('is_play') & col('mine')
    od = own & (t >= res[..., 1])
    tk, vk = od & col('out_tower_known'), od & col('out_value_known') & (vals[..., _COL['cost_10']] > 0)
    card = E['card'].astype(np.int64)
    decks = np.asarray(decks, np.int64).reshape(T, -1)
    for k in range(min(decks.shape[1], DECK_N)):
        c = decks[:, k:k + 1]
        m = (card == c) & (c != 0)
        s += [(own & m).sum(1) / 10, ((tk & m).sum(1) > 0).astype(np.float64), mean(tk & m, E['swing']),
              ((vk & m).sum(1) > 0).astype(np.float64), mean(vk & m, E['vpe']) / 2]
    out['mem_summary'][:, :len(s)] = np.stack([np.broadcast_to(np.asarray(x, np.float64), (T,)) for x in s], 1)
    ac = E['ans_card'].astype(np.int64)
    best, key = np.zeros(T, np.int64), np.full(T, -1, np.int64)
    for u in np.unique(ac[(fl & 4) > 0]):                     # most frequent answer card, tie = the latest
        mu = found & (ac == u)
        kk = np.where(mu.any(1), mu.sum(1) * (N + 1) + np.where(mu, idx, -1).max(1), -1)
        best, key = np.where(kk > key, u, best), np.maximum(kk, key)
    out['mem_answer'][:] = best
    return out


def features_at(tab, ticks, deck=(), version='v1', gid=None):
    """MatchMemory.features(t, gid, deck, version) for every t in ``ticks``, from the match's ``table(gid)``, vectorised
    (numpy, CPU). ``deck`` = up to 8 gid ids (the model's deck_card order); v2 needs the ``gid`` the table was built with."""
    T = len(ticks)
    E = {k: np.broadcast_to(tab[k], (T,) + tab[k].shape) for k in TABLE_KEYS}
    return _features(E, ticks, np.broadcast_to(np.asarray(deck, np.int64).reshape(1, -1), (T, len(deck))), version, gid)


def pack(tables):
    """A list of tables -> one dict of concatenated arrays + ``off`` (event offsets, len(tables) + 1)."""
    off = np.concatenate([[0], np.cumsum([len(tb['tick']) for tb in tables])]).astype(np.int64)
    out = {k: np.concatenate([tb[k] for tb in tables]) if tables else np.zeros(0) for k in TABLE_KEYS}
    out['off'] = off
    return out


def unpack(packed, j):
    a, b = int(packed['off'][j]), int(packed['off'][j + 1])
    return {k: packed[k][a:b] for k in TABLE_KEYS}


def gather_rows(packed, tabs):
    """Per-row padded event arrays {TABLE_KEYS: [T, N, ...]} of tables ``tabs`` [T] (-1 = none); padding is never visible."""
    tabs = np.asarray(tabs, np.int64)
    off = np.asarray(packed['off'], np.int64)
    a = np.where(tabs >= 0, off[np.maximum(tabs, 0)], 0)
    n = np.where(tabs >= 0, off[np.maximum(tabs, 0) + 1] - a, 0)
    N = int(n.max()) if len(n) else 0
    j = np.arange(N)[None]
    ok = j < n[:, None]
    src = np.where(ok, a[:, None] + j, 0)
    E = {k: np.asarray(packed[k])[src] for k in TABLE_KEYS}
    E['vis'] = np.where(ok, E['vis'], NEVER)
    return E


def rows_features(packed, row_tab, row_t, row_deck, ids, version='v1', gid=None):
    """MEM_KEYS arrays for rows ``ids`` of a batch / dataset: row i is table ``row_tab[i]`` (index into ``packed``; -1 = no
    table: an empty memory) at tick ``row_t[i]`` with deck ``row_deck[i]`` (8 gid ids). One vectorised pass for the batch.
    v2: + ``gid`` (the vocabulary of the tables' card ids)."""
    ids = np.asarray(ids, np.int64)
    return _features(gather_rows(packed, np.asarray(row_tab)[ids]), np.asarray(row_t)[ids], np.asarray(row_deck)[ids],
                     version, gid)


def mirror_ev(ev):
    """Left-right mirror of encoded events [..., F] (torch or numpy; train_gen's mirror augmentation): x -> 1 - x where
    known, tower L <-> R. The only lateral fields: the X-Bow lane rule and the summary are mirror-invariant."""
    out = ev.clone() if hasattr(ev, 'clone') else ev.copy()
    x, k, lc, rc = _COL['x'], _COL['xy_known'], _COL['tower_l'], _COL['tower_r']
    out[..., x] = (1 - ev[..., x]) * ev[..., k] + ev[..., x] * (1 - ev[..., k])
    out[..., lc], out[..., rc] = ev[..., rc], ev[..., lc]
    return out


def empty_rows(n, version='v1'):
    """MEM_KEYS for ``n`` rows with an EMPTY memory (no event, zero summary): a path with no tables (declared, never silent)."""
    return dict(mem_ev=np.zeros((n, E_MAX, F), np.float32), mem_mask=np.zeros((n, E_MAX), bool),
                mem_card=np.zeros((n, E_MAX), np.int64), mem_form=np.full((n, E_MAX), FORM_PAD, np.int64),
                mem_summary=np.zeros((n, N_SUM[version]), np.float32), mem_answer=np.zeros(n, np.int64))


# ------------------------------------------------------------------------------------------------------------ memory v2
def _json(path):
    return json.loads(path.read_text(encoding='utf-8'))


def v2_meta():
    """The S1c artifacts a v2 model's features depend on (checkpoint ``memory_v2`` / rl config hash): their sha256."""
    return {'priors_sha256': hashlib.sha256(PRIORS.read_bytes()).hexdigest(),
            'lock_head_sha256': hashlib.sha256(LOCK_HEAD.read_bytes()).hexdigest()}


def v2_lut(gid, priors=None):
    """Per card id of ``gid``: the counter priors' lifts {'deck', 'answer'} (0 = no prior / pad); ``priors`` = a priors dict
    (default: the PRIORS artifact). A stand-in alias (dataset_gen.CARD_STANDINS) shares its stand-in's id and never overrides
    the vocabulary's own card."""
    if gid is None:
        raise ValueError('memory v2 needs the card vocabulary (gid) its tables were built with (the counter priors)')
    return _lut(tuple(sorted(gid.items())), None if priors is None else json.dumps(priors, sort_keys=True))


@lru_cache(maxsize=16)
def _lut(items, priors):
    pri = (json.loads(priors) if priors is not None else _json(PRIORS))['cards']
    g = dict(items)
    n = max([i for _, i in items] + [0]) + 1
    lut = dict(deck=np.zeros(n), answer=np.zeros(n))
    for k, i in items:
        if i and k in pri and not (k in CARD_STANDINS and g.get(CARD_STANDINS[k]) == i):
            lut['deck'][i], lut['answer'][i] = pri[k]['deck']['lift'], pri[k]['answer']['lift']
    return lut


@lru_cache(maxsize=1)
def lock_head():
    """The frozen lock head (fit_s1c.py's lock_head.json): standardise, logistic. Its inputs must be LOCK_INPUTS."""
    return parse_lock_head(_json(LOCK_HEAD))


def parse_lock_head(h):
    if tuple(h['inputs']) != LOCK_INPUTS:
        raise ValueError(f'lock head inputs {h["inputs"][:3]}... are not this match_memory LOCK_INPUTS')
    return {k: np.asarray(h[k], np.float64) for k in ('mean', 'std', 'w', 'b')}


def lock_x(s14, f, ticks):
    """The lock head's inputs (LOCK_INPUTS): the v1 SUMMARY_FIELDS, the S1C_FIELDS before xb_lock_p, game time + phase."""
    ticks = np.asarray(ticks, np.int64)
    ph = np.stack([ticks < DOUBLE_T, (ticks >= DOUBLE_T) & (ticks < OT_T), ticks >= OT_T], 1)
    return np.concatenate([np.asarray(s14, np.float64), np.asarray(f, np.float64)[:, :len(S1C_FIELDS) - 1],
                           (ticks * TICK_S / 300)[:, None], ph], 1)


def lock_p(head, x):
    """P(lock) for rows of LOCK_INPUTS (sequential sums: a row's score never depends on the batch it is in)."""
    z = np.cumsum((x - head['mean']) / head['std'] * head['w'], 1)[:, -1] + head['b']
    return 1.0 / (1.0 + np.exp(-z))


@lru_cache(maxsize=1)
def _regen_table():
    from .opp_elixir_count import REGEN_SCHEDULE
    bp = np.array([lo for lo, _ in REGEN_SCHEDULE], np.float64)
    rate = np.array([r for _, r in REGEN_SCHEDULE], np.float64)
    return bp, rate, np.concatenate([[0.0], np.cumsum(np.diff(bp) * rate[:-1])])


def _regen_cum(x):
    """Elixir regenerated over [0, x) ticks by opp_elixir_count.REGEN_SCHEDULE (the real engine's: 1x < 2400, 2x < 4800 --
    regulation double AND overtime's first minute --, 3x < 6002, then none), the cap ignored."""
    bp, rate, cum = _regen_table()
    x = np.asarray(x, np.float64)
    i = np.maximum(np.searchsorted(bp, x, 'right') - 1, 0)
    return cum[i] + rate[i] * (x - bp[i])


def _s1c(E, ticks, s14, lut, head):
    """The S1C_FIELDS [T, len(S1C_FIELDS)] float64 at ``ticks`` from per-row event arrays ``E`` (``_features``' input), only
    from events visible at t. Sums run sequentially in event order (np.cumsum), so a row's values never depend on the other
    rows or the padding of its batch (incremental == offline). ``lut`` = v2_lut; ``head`` None = xb_lock_p 0 (fit_s1c).
      priors   over the opponent's REVEALED cards (a visible accepted play; card id 0 = outside the vocabulary: cycles, no prior)
      cycle    since = the opponent's plays with a LATER tick than the card's last (public_observation.opponent_cycle's rule);
               need = max(0, CYCLE - since) plays before it is back in hand (assumes every opponent play was seen); elixir
               to cycle there = the need cheapest of the other 7 deck slots (revealed costs, unrevealed slots at the revealed
               mean cost; ponytail: ignores which of them are in hand -- a lower bound); opp elixir = OppElixirCounter's rule
               (start 6, the real regen, cap 10, a play it cannot afford re-bases to its cost) on the visible plays
      counter  a revealed card with answer lift < COUNTER_LIFT; ready = back in hand and affordable now
      king     activated = my (their) king took a recorded tower_damage or a tower of that side fell (DMG_MIN debounce: a hit
               under 2 % of max HP is not seen); since = seconds since that event / 60
      margin   per tower lost = min(1, recorded damage), 1 once fallen: princesses (enemy - mine) / 2, kings (enemy - mine);
               trends = minus the same from the events with tick < t - 600 (30 s) / t - 1200 (60 s)"""
    if E['tick'].shape[1] == 0:                       # no event at all: one never-visible pad event
        E = {k: np.zeros(v.shape[:1] + (1,) + v.shape[2:], v.dtype) for k, v in E.items()}
        E['vis'] = np.full(E['vis'].shape, NEVER, E['vis'].dtype)
    ticks = np.asarray(ticks, np.int64)
    T, N = E['tick'].shape
    tick, vals, inf = E['tick'].astype(np.int64), E['vals'], np.inf
    V = ticks[:, None] >= E['vis'].astype(np.int64)
    col = (lambda k: vals[..., _COL[k]] == 1)
    mine = col('mine')
    opp = V & col('is_play') & ~mine
    cost = np.round(vals[..., _COL['cost_10']].astype(np.float64) * 10, 1)
    dl, al = lut['deck'], lut['answer']
    card = E['card'].astype(np.int64)
    card = np.where((card > 0) & (card < len(dl)), card, 0)
    last = np.full((T, len(dl)), -1, np.int64)        # each revealed card's last visible play (event index)
    r, n = np.nonzero(opp & (card > 0))
    np.maximum.at(last, (r, card[r, n]), n)
    rev = last >= 0
    nrev = rev.sum(1)
    K = max(int(nrev.max()), 1)
    cid = np.argsort(~rev, 1, kind='stable')[:, :K]    # revealed card ids first, ascending: [T, K]
    ok = np.take_along_axis(rev, cid, 1)
    li = np.take_along_axis(np.maximum(last, 0), cid, 1)
    cnt = np.cumsum(opp, 1)
    brk = np.ones((T, N), bool)
    brk[:, :-1] = tick[:, 1:] != tick[:, :-1]
    run_end = np.minimum.accumulate(np.where(brk, np.arange(N), N)[:, ::-1], 1)[:, ::-1]   # last event of the same tick
    since = cnt[:, -1:] - np.take_along_axis(cnt, np.take_along_axis(run_end, li, 1), 1)
    need = np.where(ok, np.maximum(0, CYCLE - since), CYCLE)
    x = np.where(ok, np.take_along_axis(cost, li, 1), 0.0)
    a, d = np.where(ok, al[cid], 0.0), np.where(ok, dl[cid], 0.0)
    est, at, R = np.full(T, 6.0), np.zeros(T), _regen_cum(tick)   # START_ELIXIR at tick 0; at = regen to the last play
    for j in np.flatnonzero(opp.any(0)):
        m = opp[:, j]
        e = np.minimum(10.0, est + R[:, j] - at)
        est = np.where(m, np.maximum(e, cost[:, j]) - cost[:, j], est)
        at = np.where(m, R[:, j], at)
    est = np.minimum(10.0, est + _regen_cum(ticks) - at)
    mean = np.cumsum(np.where(ok, x, 0.0), 1)[:, -1] / np.maximum(nrev, 1)
    fill = np.arange(DECK_N)[None] < (DECK_N - nrev)[:, None]
    pool = np.sort(np.concatenate([np.where(ok, x, inf), np.where(fill, mean[:, None], inf)], 1), 1)[:, :CYCLE + 1]
    P = np.concatenate([np.zeros((T, 1)), np.cumsum(pool, 1)], 1)          # P[:, k] = the k cheapest slots' elixir
    s_k = np.take_along_axis(pool, np.maximum(need - 1, 0), 1)
    cyc = np.where(need == 0, 0.0, np.where(x <= s_k, np.take_along_axis(P, np.minimum(need + 1, CYCLE + 1), 1) - x,
                                            np.take_along_axis(P, need, 1)))    # (x <= s_k: the card itself is not "other")
    ctr = ok & (a < COUNTER_LIFT)
    ck = ctr.any(1)
    has = nrev > 0
    sl = np.zeros((T, SLOT_N, len(SLOT_FIELDS)))
    order = np.lexsort((cid, np.where(ok, a, inf)), axis=1)[:, :SLOT_N]
    g = (lambda v: np.take_along_axis(v, order, 1))
    sl[:, :order.shape[1]] = np.stack([g(ok), g(need) / CYCLE, g(x) / 10, g(a), g(d)], -1) * g(ok)[..., None]
    tdm, tfl = V & col('is_tower_damage'), V & col('is_tower_fall')
    tk, tl, tr = col('tower_k'), col('tower_l'), col('tower_r')
    big = np.iinfo(np.int64).max

    def king(side):
        first = np.where(side & ((tdm & tk) | tfl), tick, big).min(1)
        return first < big, np.where(first < big, (ticks - first) * TICK_S / 60, 0.0)
    lost = vals[..., _COL['tower_lost']].astype(np.float64)

    def margin(cut):
        m = V & (tick < cut[:, None])
        hp = [[np.where((m & side & tw & tfl).any(1), 1.0,
                        np.minimum(1.0, np.cumsum(np.where(m & side & tw & tdm, lost, 0.0), 1)[:, -1])) for tw in (tk, tl, tr)]
              for side in (~mine, mine)]
        return (hp[0][1] + hp[0][2]) - (hp[1][1] + hp[1][2]), hp[0][0] - hp[1][0]
    p0, k0 = margin(ticks)
    p30, k30 = margin(ticks - 600)
    p60, k60 = margin(ticks - 1200)
    f = np.column_stack([np.minimum(nrev, DECK_N) / DECK_N, np.where(has, np.where(ok, d, inf).min(1), 0.0),
                         np.cumsum(np.minimum(d, 0.0), 1)[:, -1], np.where(has, np.where(ok, a, inf).min(1), 0.0),
                         ck, np.where(ctr, need, CYCLE).min(1) / CYCLE, np.where(ck, np.where(ctr, cyc, inf).min(1), 0.0) / 10,
                         est / 10, (ctr & (need == 0) & (est[:, None] >= x)).any(1), sl.reshape(T, -1),
                         *king(mine), *king(~mine), p0 / 2, k0, (p0 - p30) / 2, (p0 - p60) / 2, k0 - k30, k0 - k60,
                         np.zeros(T)]).astype(np.float64)
    if head is not None:
        f[:, -1] = lock_p(head, lock_x(s14, f, ticks))
    return f
