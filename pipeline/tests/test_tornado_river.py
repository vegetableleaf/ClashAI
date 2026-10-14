"""--tornado-river (owner 2026-10-14): a Tornado cannot drag GROUND troops over the river (RoyaleSim 0.1.33, measured in
L74/reward/TORNADO_RIVER.md); air crosses; bridges are walkable. Default off = unchanged (the other Tornado tests)."""
import numpy as np

from pipeline import vocab
from pipeline.decision_options import best_tornado_centre, log_air_traits, river_held
from pipeline.extrapolate import own_effect_list, water_stop

IDS = {vocab.base_key(n): i for i, n in enumerate(vocab.UNIT_VOCAB)}


def body(name, x, y, value=3.0):
    return [float(IDS[name]), x, y, value, 0.5, 0.0, 0.05]


def test_water_stop_banks_bridges_and_dry_land():
    assert water_stop(9000, 17400, 9000, 16200) == (9000, 17000)          # from the far bank: held at its edge
    assert water_stop(9000, 14600, 9100, 15800) == (9100, 15000)          # from the near bank: held at its edge
    assert water_stop(3500, 16000, 2000, 16100) == (2500, 16100)          # on a bridge, pulled sideways: held at its edge
    assert water_stop(3500, 17200, 3600, 16500) == (3600, 16500)          # onto a bridge: walkable
    assert water_stop(9000, 20000, 9500, 19000) == (9500, 19000)          # dry land: untouched


def test_river_held_marks_far_bank_ground_off_bridge_only():
    assert log_air_traits()[IDS["knight"]][0] is False and log_air_traits()[IDS["minions"]][0] is True
    b = np.array([body("knight", 9.0, 12.0), body("knight", 3.5, 12.0), body("minions", 9.0, 12.0), body("knight", 9.0, 20.0)])
    assert river_held(b).tolist() == [True, False, False, False]          # far-bank ground / bridge column / air / my bank


def test_combo_aim_stops_counting_far_bank_ground_it_cannot_gather():
    # a group on my bank and a far-bank pair off to the side: one Tornado reaches both (off counts 13), but the river holds the
    # pair at the bank ~5 tiles from a centre that also reaches my-bank group, outside the Rocket blast (on: < 13)
    b = np.array([body("knight", 12.0, 19.0, 3.0), body("knight", 5.0, 13.0, 5.0), body("knight", 5.5, 13.2, 5.0)])
    v_off, c_off = best_tornado_centre(b, "lattice")
    v_on, c_on = best_tornado_centre(b, "lattice", river=True)
    assert v_off >= 13.0 - 1e-9 and v_on < v_off                           # the far-bank pair no longer comes over the river
    air = np.array([body("knight", 12.0, 19.0, 3.0), body("minions", 5.0, 13.0, 5.0), body("minions", 5.5, 13.2, 5.0)])
    assert best_tornado_centre(air, "lattice", river=True)[0] == best_tornado_centre(air, "lattice")[0]   # air still crosses


def test_own_effects_carry_the_river_flag_to_the_pull():
    fx = own_effect_list([dict(card="Tornado", x=9000.0, y=19000.0, tick=100, river=True)], [], 0, 99, 140)
    assert fx and fx[0]["kind"] == "pull" and fx[0]["river"] is True
    fx = own_effect_list([dict(card="Tornado", x=9000.0, y=19000.0, tick=100)], [], 0, 99, 140)
    assert fx and fx[0]["river"] is False


def test_lookahead_holds_a_far_bank_knight_at_the_bank_only_with_the_flag():
    from pipeline.extrapolate import extrapolate
    knight = dict(side=1, card_id=26000000, x=9000.0, y=18200.0, hp=1000, max_hp=1000, kind=0, address="k1")
    obs = dict(game_tick=200, entities=[knight])
    prev = dict(game_tick=190, entities=[dict(knight, y=18300.0)])
    tornado = dict(card="Tornado", x=9000.0, y=14000.0, tick=195)
    ys = {}
    for flag in (False, True):
        out = extrapolate(obs, prev, 26, 0, own_effects=[dict(tornado, river=True) if flag else tornado])
        ys[flag] = next(e["y"] for e in out["entities"] if e.get("address") == "k1")
    assert ys[False] < 17000.0 and ys[True] == 17000.0, ys      # dragged over the river vs held at its bank
