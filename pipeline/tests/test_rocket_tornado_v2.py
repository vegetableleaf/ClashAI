"""Rocket + Tornado rule changes (owner 2026-10-17 ~21:30: "for now, make the listed rule changes"), each behind an option whose default
keeps the old rule (test_rocket_value2.py / test_tornado_river.py cover the defaults; L74/combo/identity_check.py replays HEAD's module):
  --rocket-tornado-window measured   the pull-landing window + Rocket flight re-fit on the fork36 timing sweep (L74/combo/fit_window.py)
  --rocket-tornado-order either      Tornado first, the Rocket as its follow-up, when that window is wider (short flights at my towers)
  --rocket-tornado-lone best         a clump one Rocket covers gets that lone Rocket unless the combo beats it by more than 3 elixir
  --rocket-value-min-y < 16          the enemy half (+ --rocket-value-towers on: an alive princess in the blast; never the king)
  --tornado-river full               pull paths: either bank, and the bridge edge (the live 182814 t3008 miss)
    icebow/.venv/Scripts/python.exe -m pytest -q pipeline/tests/test_rocket_tornado_v2.py"""
import argparse
import math
from types import SimpleNamespace

import numpy as np
import pytest
import torch

from pipeline import vocab
from pipeline.decision_options import (COMBO_GAIN_MIN, DecisionOptions, ENEMY_TOWERS_TILES, PULL_LANDS_V2, PULL_LANDS_V2_MINE, ROCKET_TOWER_VALUE,
                                      add_arguments, best_rocket_clump, best_tornado_centre, cell_centres_tiles, combo_flight_ticks,
                                      combo_plan, config_from_args, decide_batch, options_from_config, rocket_bodies,
                                      rocket_flight_ticks, rocket_tornado_choice, rocket_tornado_plan, rocket_tornado_timing,
                                      tornado_radius_tiles, water_stop_tiles)
from pipeline.extrapolate import water_stop
from pipeline.obs_contract import Tower
from pipeline.tests.test_rocket_value2 import HAND, Model, board, combo_pilot, pups, sim_args, split_pups, unit
from pipeline.tests.test_lethal_rocket import live_frame

ONLY = dict(rocket_value=7.0, rocket_tornado='only')
V2 = dict(rocket_tornado_window='measured', rocket_tornado_order='either')
DECK = ['knight', 'rocket', 'the-log', 'tornado', 'x-bow', 'ice-wizard', 'skeletons', 'tesla']
HAND_IDS = (vocab.unit_id('rocket'), vocab.unit_id('tornado'), vocab.unit_id('knight'), vocab.unit_id('the_log'))


def towers6(left=True, right=True):
    mine = (Tower(0, 'king', None, 1.0, True), Tower(0, 'princess', 'L', 1.0, True), Tower(0, 'princess', 'R', 1.0, True))
    return mine + (Tower(1, 'king', None, 1.0, True), Tower(1, 'princess', 'L', 1.0, left), Tower(1, 'princess', 'R', 1.0, right))


def sim_run(options, bs, allowed_slots=(0, 1, 2, 3)):
    bs.my_hand = HAND_IDS
    allowed = np.zeros((1, 8), bool)
    allowed[0, list(allowed_slots)] = True
    a = sim_args(1)
    a['allowed'] = allowed
    a['heads'] = {'card': torch.tensor([[9., 0, 0, 0, 0, 0, 0, 0]])}
    return decide_batch(Model(), **a, options=options, rocket_value=[(bs, False, SimpleNamespace())], tau=.35, device='cpu',
                        rngs=[None], card_names=[DECK], grid='lattice')[0]


def test_flags_parse_validate_and_default_to_the_old_rule():
    o = DecisionOptions()
    assert (o.rocket_tornado_window, o.rocket_tornado_order, o.rocket_tornado_lone, o.rocket_value_towers) == ('v1', 'rocket', 'skip', 'off')
    ap = argparse.ArgumentParser()
    add_arguments(ap)
    cfg = config_from_args(ap.parse_args(['--rocket-value', '9', '--rocket-tornado', 'only', '--rocket-tornado-window', 'measured',
                                          '--rocket-tornado-order', 'either', '--rocket-tornado-lone', 'best', '--rocket-value-towers', 'on',
                                          '--rocket-value-min-y', '4', '--tornado-river', 'full']))
    o = options_from_config(cfg)
    assert (o.rocket_tornado_window, o.rocket_tornado_order, o.rocket_tornado_lone, o.rocket_value_towers, o.tornado_river,
            o.rocket_value_min_y) == ('measured', 'either', 'best', 'on', 'full', 4.0)
    for bad in (dict(rocket_tornado_window='x'), dict(rocket_tornado_order='tornado'), dict(rocket_tornado_lone='x'),
                dict(rocket_value_towers='x'), dict(tornado_river='x'), dict(rocket_value_min_y=8.0, tornado_river='on'),
                dict(rocket_tornado='rocket_only', rocket_tornado_order='either')):
        with pytest.raises(ValueError):
            DecisionOptions(rocket_value=7.0, **bad)


# ---- 1. window + flight --------------------------------------------------------------------------------------------------------
def test_v1_plan_is_unchanged_and_measured_flight_is_half_a_tick_above_d_over_035():
    x, y = cell_centres_tiles('lattice')
    for cx, cy in zip(x[y >= 16], y[y >= 16]):
        assert combo_plan(cx, cy) == rocket_tornado_plan(cx, cy)
    assert combo_flight_ticks(9.0, 28.65 - 7.0, 'measured') == pytest.approx(7.0 / .35 + .5)
    assert combo_flight_ticks(9.0, 28.65 - 7.0) == rocket_flight_ticks(9.0, 28.65 - 7.0) == 22       # v1: round(d / .35) + 2
    # live 182814 t3008: aim (8.5, 16.5), measured flight 33-35 ticks: v1 says 37, measured 35.2
    assert rocket_flight_ticks(8.5, 16.5) == 37 and combo_flight_ticks(8.5, 16.5, 'measured') == pytest.approx(35.24, abs=.01)


@pytest.mark.parametrize('cx,cy,rocket,tornado', [
    (9.0, 22.0, (4, 12), (4, 20)),     # my king (the owner's complaint): F 19.5; both orders, Tornado first wider (window 7..40, y >= 19)
    (6.5, 23.0, (4, 11), (4, 21)),     # my princess: F 18.2
    (9.0, 26.0, None, (4, 31)),        # 2.65 tiles from my king: F 8.1, only Tornado first lands in the pull
    (3.5, 17.5, (13, 29), None),       # the left bridge exit: F 36.0, window 7..24
    (6.5, 12.0, (25, 41), None),       # the enemy half: F 48.6
])
def test_measured_plans_per_order(cx, cy, rocket, tornado):
    assert combo_plan(cx, cy, 'rocket', 'measured') == rocket
    assert combo_plan(cx, cy, 'tornado', 'measured') == tornado
    for order, plan in (('rocket', rocket), ('tornado', tornado)):     # every gap of the plan lands the Rocket inside the window
        if plan is None:
            continue
        f, (lf, lt) = combo_flight_ticks(cx, cy, 'measured'), (PULL_LANDS_V2_MINE if cy >= 19 else PULL_LANDS_V2)
        for g in range(plan[0], plan[1] + 1):
            assert lf - 1e-9 <= (f - g if order == 'rocket' else f + g) <= lt + 1e-9


# ---- 2. Tornado first ----------------------------------------------------------------------------------------------------------
def near_king_split(elixir=9.5):
    """A clump split around (9, 25): too close to my king for Rocket first (v1 / measured: no window), Tornado first lands."""
    return board(*split_pups(gap=2.6, y=25.5), elixir=elixir)


def test_tornado_first_fires_where_rocket_first_cannot_and_is_a_sim_follow_up_of_the_rocket():
    from pipeline.e1_eval import follow_up_spec
    bs = near_king_split()
    bs.my_hand = HAND_IDS
    assert rocket_tornado_choice(DecisionOptions(**ONLY), DECK, [True] * 8, bs, 'lattice') is None             # v1: no plan
    hit = rocket_tornado_choice(DecisionOptions(**ONLY, **V2), DECK, [True] * 8, bs, 'lattice')
    assert hit is not None and hit[5] == 'tornado' and hit[0] == 1 and hit[1] == 3
    out = sim_run(DecisionOptions(**ONLY, **V2), near_king_split())
    after, within = rocket_tornado_timing(hit[3])
    assert out['why'] == 'rocket_tornado' and out['slot'] == 3 and out['cell'] == hit[2]                   # the Tornado now ...
    assert out['follow_ups'] == [follow_up_spec(1, hit[2], after, within)]                                 # ... the Rocket follows
    out = sim_run(DecisionOptions(**ONLY, **V2), near_king_split(), allowed_slots=(0, 1, 2))                # the Tornado not affordable now
    assert out.get('why') != 'rocket_tornado'


def test_rocket_first_is_kept_where_its_window_is_at_least_as_wide():
    bs = board(*split_pups(), elixir=9.5)                       # the default split at y 22: Rocket first 4..12 vs Tornado first 4..20
    bs.my_hand = HAND_IDS
    hit = rocket_tornado_choice(DecisionOptions(**ONLY, rocket_tornado_window='measured'), DECK, [True] * 8, bs, 'lattice')
    assert hit[5] == 'rocket'                                   # order 'rocket': never Tornado first
    hit = rocket_tornado_choice(DecisionOptions(**ONLY, **V2), DECK, [True] * 8, bs, 'lattice')
    x, y = cell_centres_tiles('lattice')
    r, t = combo_plan(x[hit[2]], y[hit[2]], 'rocket', 'measured'), combo_plan(x[hit[2]], y[hit[2]], 'tornado', 'measured')
    assert hit[5] == ('tornado' if t[1] - t[0] > r[1] - r[0] else 'rocket') and hit[3] == (t if hit[5] == 'tornado' else r)


def test_live_tornado_first_taps_the_tornado_and_plans_the_rocket():
    calls = []
    d = combo_pilot(DecisionOptions(**ONLY, **V2), near_king_split(), calls).decide(live_frame(0, 1092, 1092))
    assert d['play'] and d['name'] == 'Tornado' and d['why'] == 'rocket_tornado' and d['hand_pos'] == 3
    assert d['rocket_tornado_order'] == 'tornado'
    (first, name, xy, after, within), = calls
    assert (first, name) == ('Tornado', 'Rocket') and xy == d['xy'] and (after, within) == rocket_tornado_timing(d['rocket_tornado_window'])


# ---- 3. lone vs combo ----------------------------------------------------------------------------------------------------------
def test_only_mode_no_longer_leaves_a_lone_rocket_clump_with_neither_play():
    one = board(*pups(), elixir=9.5)                            # one blast holds the 7 elixir of pups
    assert sim_run(DecisionOptions(**ONLY), one).get('why') not in ('rocket_value', 'rocket_tornado')        # the old block
    out = sim_run(DecisionOptions(**ONLY, rocket_tornado_lone='best'), board(*pups(), elixir=9.5))
    assert out['why'] == 'rocket_value' and out['slot'] == 1 and 'follow_ups' not in out
    bs = board(*pups(), elixir=9.5)
    bs.my_hand = HAND_IDS
    hit = rocket_tornado_choice(DecisionOptions(**ONLY, rocket_tornado_lone='best'), DECK, [True] * 8, bs, 'lattice')
    assert hit[5] == 'lone' and hit[2] is None and hit[4] == pytest.approx(7.0)


def test_the_combo_wins_when_its_pull_gathers_more_than_the_lone_blast_else_the_lone_rocket():
    near = pups(6, x=4.0, y=22.0)                               # 7 elixir in one blast
    o = DecisionOptions(rocket_value=7.0, rocket_tornado='only', rocket_tornado_lone='best')
    bs = board(*near, unit('knight', 8.5, 22.0), elixir=9.5)   # + a Knight ~4.5 tiles away: only a pull gathers both (10 vs 7)
    bs.my_hand = HAND_IDS
    single = best_rocket_clump(rocket_bodies(bs, 'cost'), 'lattice')[0]
    value = best_tornado_centre(rocket_bodies(bs, 'cost'), 'lattice')[0]
    assert value > single + COMBO_GAIN_MIN
    assert rocket_tornado_choice(o, DECK, [True] * 8, bs, 'lattice')[5] == 'rocket'
    one = board(*near, elixir=9.5)                              # the pull adds nothing to the one blast: the lone Rocket
    one.my_hand = HAND_IDS
    assert rocket_tornado_choice(o, DECK, [True] * 8, one, 'lattice')[5] == 'lone'


def test_measured_affordability_reads_the_board_elixir_as_26_ticks_ahead():
    o = DecisionOptions(rocket_value=7.0, rocket_tornado='only', rocket_tornado_window='measured')
    for elixir, fires in ((9.0, False), (9.6, True)):          # Rocket first at y 22: due ~10 ticks, 1x regen 1/56 per tick
        bs = board(*split_pups(), elixir=elixir)
        bs.my_hand = HAND_IDS
        hit = rocket_tornado_choice(o, DECK, [True] * 8, bs, 'lattice')
        assert (hit is not None) is fires, elixir
        if hit:
            due = rocket_tornado_timing(hit[3])[0]
            assert elixir + (due + 6 - 26) / 56 >= 9.0
    bs = board(*split_pups(), elixir=9.0)                      # v1 (unchanged): 9.0 - 6 + 4 / 56 >= 3 -> fires
    bs.my_hand = HAND_IDS
    assert rocket_tornado_choice(DecisionOptions(rocket_value=7.0, rocket_tornado='only'), DECK, [True] * 8, bs, 'lattice') is not None


def test_live_only_best_plays_the_lone_rocket():
    d = combo_pilot(DecisionOptions(**ONLY, rocket_tornado_lone='best'), board(*pups(), elixir=9.5), []).decide(live_frame(0, 1092, 1092))
    assert d['why'] == 'rocket_value' and d['name'] == 'Rocket' and 'follow_ups' not in d
    d = combo_pilot(DecisionOptions(**ONLY), board(*pups(), elixir=9.5), []).decide(live_frame(0, 1092, 1092))
    assert d.get('why') not in ('rocket_value', 'rocket_tornado')                                           # skip: the old block


# ---- 4. enemy half, princess value, never the king -----------------------------------------------------------------------------
def test_the_enemy_half_is_reached_only_below_16_and_never_near_the_king():
    x, y = cell_centres_tiles('lattice')
    back = board(*[unit('knight', 9.0 + .4 * i, 5.0 + .3 * i) for i in range(4)], unit('wizard', 9.5, 9.0), unit('musketeer', 8.5, 9.5))
    b = rocket_bodies(back, 'cost')
    assert best_rocket_clump(b, 'lattice')[1] is None and best_tornado_centre(b, 'lattice')[1] is None    # my half only (default)
    v, eligible = best_rocket_clump(b, 'lattice', min_y=0.0)
    (kx, ky), cells = ENEMY_TOWERS_TILES[0], np.flatnonzero(eligible)
    assert v > 0 and (np.hypot(x[cells] - kx, y[cells] - ky) > 3.4 - 1e-9).all()                          # Rocket: 2.0 + king 1.4
    _, c = best_tornado_centre(b, 'lattice', min_y=0.0)
    assert math.hypot(x[c] - kx, y[c] - ky) > tornado_radius_tiles() + 1.4 - 1e-9                          # the pull never reaches it
    assert y[c] >= 1.0


def test_an_alive_enemy_princess_in_the_blast_adds_its_value_only_with_a_clump():
    tx, ty = ENEMY_TOWERS_TILES[1]                              # the enemy left princess (3.5, 6.5)
    near = board(unit('knight', tx + .5, ty + 2.4), unit('knight', tx + 1.0, ty + 2.6), towers=towers6())
    b = rocket_bodies(near, 'cost')
    off, _ = best_rocket_clump(b, 'lattice', min_y=0.0)
    on, eligible = best_rocket_clump(b, 'lattice', min_y=0.0, towers=(True, True))
    x, y = cell_centres_tiles('lattice')
    cells = np.flatnonzero(eligible)
    assert off == pytest.approx(6.0) and on == pytest.approx(6.0 + ROCKET_TOWER_VALUE)
    assert (np.hypot(x[cells] - tx, y[cells] - ty) <= 2.0 + 1.0 + 1e-9).all()                              # every aim also hits it
    assert best_rocket_clump(b, 'lattice', min_y=0.0, towers=(False, True))[0] == pytest.approx(6.0)        # a fallen princess: no bonus
    assert best_rocket_clump(rocket_bodies(board(towers=towers6()), 'cost'), 'lattice', min_y=0.0, towers=(True, True))[0] == 0.0
    o = DecisionOptions(rocket_value=8.0, rocket_value_min_y=0.0, rocket_value_towers='on')
    from pipeline.decision_options import rocket_value_choice
    assert rocket_value_choice(o, ['Knight', 'Rocket', 'Log', 'Tesla'], [True] * 4, near, 'lattice') is not None
    assert rocket_value_choice(DecisionOptions(rocket_value=8.0, rocket_value_min_y=0.0), ['Knight', 'Rocket', 'Log', 'Tesla'],
                               [True] * 4, near, 'lattice') is None


# ---- 5. tornado_river full: pull paths, banks and bridge edges -----------------------------------------------------------------
def test_water_stop_tiles_is_extrapolate_water_stop():
    rng = np.random.default_rng(7)
    p = rng.uniform((0, 13, 0, 13), (18, 19, 18, 19), size=(4000, 4))
    p[::3, 0] = rng.choice([2.5, 3.5, 4.5, 13.5, 14.0, 15.5], size=len(p[::3]))   # plenty of bridge starts
    p[::3, 1] = rng.uniform(15.1, 16.9, size=len(p[::3]))
    xs, ys = water_stop_tiles(p[:, 0], p[:, 1], p[:, 2], p[:, 3])
    for (x0, y0, x1, y1), a, b in zip(p, xs, ys):
        ex, ey = water_stop(x0 * 1000, y0 * 1000, x1 * 1000, y1 * 1000)
        assert (a, b) == pytest.approx((ex / 1000, ey / 1000), abs=1e-9)


# the live board of live_play_20261017_182814 at the combo decision t3008 (L74/combo/dump_live_board.py; enemy: Mega Knight on the right
# bridge's edge, the Ram Rider -- two reader bodies -- entering the left bridge). The v1 rule centred the combo at (8.5, 16.0), in the
# river rows: the pull held the Ram Rider at the bridge edge x 4.5, 4 tiles off, and the Rocket hit nothing (live_pull.py)
BOARD_182814_T3008 = [('mega_knight', 13.23, 15.09, 3473 / 6380), ('ram_rider', 3.50, 14.50, 1.0), ('ram_rider', 3.50, 14.50, 1.0)]
LIVE_COMBO = dict(rocket_value=9.0, rocket_value_mode='damage', rocket_value_hitbox='edge', rocket_tornado='only', tornado_river='on')


def test_live_182814_t3008_fires_on_the_bridge_edge_with_on_and_not_with_full():
    # 2:30 = double elixir; the live board's elixir is the 24-tick look-ahead one (--extrapolate 24): 8.43 raw + 24 x 2/56
    bs = board(*(unit(n, x, y, h) for n, x, y, h in BOARD_182814_T3008), elixir=8.43 + 24 * 2 / 56, t=150.4)
    bs.double_elixir = True
    names = ['Rocket', 'Log', 'Tornado', 'Knight']
    hit = rocket_tornado_choice(DecisionOptions(**LIVE_COMBO), names, [True] * 4, bs, 'lattice')
    x, y = cell_centres_tiles('lattice')
    # the raw frame (not the look-ahead bodies) puts the centre one tile left of the logged (8.5, 16.0): the same river row, between the lanes
    assert hit is not None and y[hit[2]] == 16.0 and abs(x[hit[2]] - 8.5) <= 1.0 and hit[4] == pytest.approx(11.0, abs=.01)
    b = rocket_bodies(bs, 'damage')
    full, cell = best_tornado_centre(b, 'lattice', 'edge', river='full')
    assert full < 9.0                                           # nothing it could gather into one blast is worth V
    assert rocket_tornado_choice(DecisionOptions(**dict(LIVE_COMBO, tornado_river='full')), names, [True] * 4, bs, 'lattice') is None


def test_full_follows_the_bridge_and_the_bank_where_the_body_really_goes():
    knight = lambda x, y: rocket_bodies(board(unit('knight', x, y)), 'cost')       # noqa: E731
    x, y = cell_centres_tiles('lattice')
    at = lambda cx, cy: int(np.argmin((x - cx) ** 2 + (y - cy) ** 2))               # noqa: E731
    from pipeline.decision_options import pull_river_ends, rocket_radius_tiles
    for body, centre, counted in (((3.5, 16.0), (8.5, 16.0), False),   # on the bridge, centre in the river rows: held at x 4.5 (probe)
                                  ((3.5, 16.0), (3.5, 18.5), True),    # pulled along the bridge onto my land
                                  ((3.5, 16.0), (6.0, 18.5), True),    # off the bridge exit, onto land beside it (probe: arrives)
                                  ((6.5, 14.4), (8.5, 16.0), True),    # enemy bank off the bridge: held at y 15, slides to ~(8.3, 15)
                                  ((12.0, 13.0), (12.0, 19.0), False), # enemy bank, a centre 4 tiles past the bank: held 4 off
                                  ((9.0, 19.0), (9.0, 11.0), False)):  # my bank, an enemy-half centre: held at y 17 (both banks)
        b = knight(*body)
        c = at(*centre)
        inside = np.ones((len(x), 1), bool)
        dist = np.hypot(x[:, None] - b[None, :, 1], y[:, None] - b[None, :, 2])
        ins, _ = pull_river_ends(b, x, y, inside, dist, rocket_radius_tiles() + b[:, 4], np.zeros(1, bool))
        assert bool(ins[c, 0]) is counted, (body, centre)
    air = rocket_bodies(board(unit('minions', 3.5, 16.0)), 'cost')
    assert best_tornado_centre(air, 'lattice', river='full')[0] == best_tornado_centre(air, 'lattice')[0]     # air crosses


# ---- rocket_tornado_lead drift: an enemy-half push keeps walking for the ~50-80 ticks to the Tornado ----------------------------
def test_drift_walks_enemy_half_ground_to_its_bridge_and_leaves_my_half_and_buildings():
    from pipeline.decision_options import combo_drift
    b = rocket_bodies(board(unit('knight', 9.5, 10.0), unit('knight', 14.5, 12.0), unit('minions', 9.0, 10.0),
                            unit('knight', 9.0, 22.0), unit('tesla', 9.0, 10.0)), 'cost')
    m = combo_drift(b, 40)                                       # a Knight: 40 ticks x 0.05 = 2 tiles of walk
    assert m[0, 1] > 9.5 and m[0, 2] > 10.0 and math.hypot(m[0, 1] - 9.5, m[0, 2] - 10.0) == pytest.approx(2.0)   # toward the right bridge
    assert (m[1, 1], m[1, 2]) == pytest.approx((14.5, 14.0))     # straight down its lane
    assert (m[2, 1], m[2, 2]) == pytest.approx((9.0, 10.0 + 40 * b[2, 6]))     # air (Minions, fast): straight at my side
    assert (m[3, 1:3] == b[3, 1:3]).all() and (m[4, 1:3] == b[4, 1:3]).all()     # my half / a building: unchanged
    long = combo_drift(b, 200)                                   # 10 tiles: reaches the bridge, then walks along it
    assert 13.5 <= long[1, 1] <= 15.5 and long[1, 2] > 17.0


def test_drift_moves_an_enemy_half_combo_toward_where_the_push_will_be():
    push = board(*[unit('musketeer', 14.0 + .4 * i, 6.0 + .5 * i) for i in range(2)], unit('wizard', 11.5, 7.5),
                 unit('valkyrie', 11.0, 8.5), elixir=10.0)
    push.my_hand = HAND_IDS
    o = dict(rocket_value=14.0, rocket_tornado='only', rocket_value_min_y=0.0, **V2)    # one blast holds 13, the pull 17
    static = rocket_tornado_choice(DecisionOptions(**o), DECK, [True] * 8, push, 'lattice')
    drift = rocket_tornado_choice(DecisionOptions(**o, rocket_tornado_lead='drift'), DECK, [True] * 8, push, 'lattice')
    x, y = cell_centres_tiles('lattice')
    assert static is not None and drift is not None and y[drift[2]] > y[static[2]]          # judged further down the lane


def test_lone_combo_mode_keeps_the_combo_but_never_forces_the_lone_rocket():
    near = pups(6, x=4.0, y=22.0)
    o = DecisionOptions(rocket_value=7.0, rocket_tornado='only', rocket_tornado_lone='combo')
    bs = board(*near, unit('knight', 8.5, 22.0), elixir=9.5)   # the pull adds the Knight: the combo, as best
    bs.my_hand = HAND_IDS
    assert rocket_tornado_choice(o, DECK, [True] * 8, bs, 'lattice')[5] == 'rocket'
    one = board(*near, elixir=9.5)                              # the pull adds nothing: no rule play (best would play the lone Rocket)
    one.my_hand = HAND_IDS
    assert rocket_tornado_choice(o, DECK, [True] * 8, one, 'lattice') is None
    assert sim_run(o, board(*pups(), elixir=9.5)).get('why') not in ('rocket_value', 'rocket_tornado')
    d = combo_pilot(o, board(*pups(), elixir=9.5), []).decide(live_frame(0, 1092, 1092))
    assert d.get('why') not in ('rocket_value', 'rocket_tornado')
