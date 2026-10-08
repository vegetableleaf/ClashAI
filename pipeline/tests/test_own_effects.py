"""own_effects (W1, owner 2026-10-08): the look-ahead applies MY OWN Log / Tornado / Rocket / hero Ice Wizard freeze.

    icebow/.venv/Scripts/python.exe -m pytest -q pipeline/tests/test_own_effects.py
"""
import pytest

from pipeline.extrapolate import extrapolate, ladder

H = 26


def ent(eid, x, y, name, side=1, cid=1):
    return {"entity_id": eid, "side": side, "x": float(x), "y": float(y), "name": name, "card_id": cid, "hp": 1, "max_hp": 1}


def obs(tick, ents):
    return {"tick": tick, "entities": ents, "players": [{"side": 0, "elixir_exact": 5.0}, {"side": 1, "elixir_exact": 5.0}]}


def pos(out, eid):
    e = next(e for e in out["entities"] if e["entity_id"] == eid)
    return e["x"], e["y"]


def test_ladder_matches_the_calibration_law():
    assert ladder(700) == [150, 125, 100, 75, 50, 25, 0, -25]          # the Log; measured Giant ladder (v0 175)
    assert sum(ladder(1800)) == 1600 and ladder(1800)[:2] == [250, 250]  # calibration: the 2018 Fireball's 1800 -> 1600


def test_default_off_and_untouched_bodies_are_byte_identical():
    prev = obs(990, [ent(1, 9000, 15200, "HogRider"), ent(2, 2000, 28000, "Knight")])
    cur = obs(1000, [ent(1, 9000, 14000, "HogRider"), ent(2, 2000, 27400, "Knight")])
    base = extrapolate(cur, prev, H, 0)
    assert extrapolate(cur, prev, H, 0, own_effects=None) == base
    assert extrapolate(cur, prev, H, 0, own_effects=[]) == base
    far = [dict(card="Tornado", x=16000, y=4000, tick=1000)]           # nobody near it
    assert extrapolate(cur, prev, H, 0, own_effects=far) == base
    old = [dict(card="the-log", x=9000, y=12000, tick=700)]            # rolled out long ago
    assert extrapolate(cur, prev, H, 0, own_effects=old) == base


def test_log_pushes_a_ground_unit_back_and_costs_its_walk_air_untouched():
    prev = obs(990, [ent(1, 9000, 15200, "HogRider"), ent(3, 9500, 15200, "Minions")])
    cur = obs(1000, [ent(1, 9000, 14000, "HogRider"), ent(3, 9500, 14000, "Minions")])
    log = [dict(card="The Log", x=9000, y=12000, tick=1000)]           # my side 0: rolls toward +y
    base = extrapolate(cur, prev, H, 0)
    out = extrapolate(cur, prev, H, 0, own_effects=log)
    # roll from 1000 + 3000/360; Hog (r 600) touched at 1009, ladder 1010..1017 (+500), walks 9 + 9 ticks at 120
    assert pos(out, 1) == pytest.approx((9000, 14000 - 120 * 18 + 500))
    assert pos(base, 1) == pytest.approx((9000, 14000 - 120 * 26))
    assert pos(out, 3) == pos(base, 3)                                 # Minions fly: the Log ignores them


def test_a_hit_between_the_observations_is_not_read_as_walking_backwards():
    # Hog at y 15000 at 990 walks 120/tick for 2 ticks, is hit at 992 (roll centre 13150 + 200 * (992 - 988.3) is
    # within 600 + 600 of its interpolated 15026, at 991 not yet), slides back 500 over 993..1000: observed +260
    log = [dict(card="the-log", x=9000, y=13150, tick=980)]
    prev, cur = obs(990, [ent(1, 9000, 15000, "HogRider")]), obs(1000, [ent(1, 9000, 15260, "HogRider")])
    base = pos(extrapolate(cur, prev, H, 0), 1)
    y = pos(extrapolate(cur, prev, H, 0, own_effects=log), 1)[1]
    assert base[1] > 15260                                             # plain dead reckoning: walking backwards
    assert y == pytest.approx(15260 - 120 * H)                         # its 120 / tick walk, recovered


def test_tornado_pulls_ground_and_air_to_its_centre():
    prev = obs(990, [ent(1, 6000, 10000, "Knight"), ent(3, 12000, 10000, "Minions")])
    cur = obs(1000, [ent(1, 6000, 10000, "Knight"), ent(3, 12000, 10000, "Minions")])   # both standing
    out = extrapolate(cur, prev, H, 0, own_effects=[dict(card="tornado", x=9000, y=10000, tick=1000)])
    kx, _ = pos(out, 1)
    mx, _ = pos(out, 3)
    assert abs(kx - 9000) <= 216 and abs(mx - 9000) <= 400          # Knight 216 / tick for 21 ticks, overshooting


def test_rocket_pushes_a_light_unit_not_an_ignore_pushback_one():
    prev = obs(990, [ent(1, 9000, 20000, "Knight"), ent(2, 9300, 20000, "Giant")])
    cur = obs(1000, [ent(1, 9000, 20000, "Knight"), ent(2, 9300, 20000, "Giant")])
    out = extrapolate(cur, prev, 60, 0, own_effects=[dict(card="Rocket", x=9000, y=19000, tick=1000)])
    assert pos(out, 1) == pytest.approx((9000, 20000 + 1600))         # flight 16000/350 -> impact 1046, ladder 13 ticks
    assert pos(out, 2) == (9300, 20000)                                # Giant: IgnorePushback


def test_hero_ice_wizard_freeze_stops_the_target_clump():
    prev = obs(990, [ent(9, 9000, 8000, "IceWizard", side=0), ent(1, 9000, 11600, "Knight")])
    cur = obs(1000, [ent(9, 9000, 8000, "IceWizard", side=0), ent(1, 9000, 11000, "Knight")])
    fz = [dict(card="IceWizard", ability=True, tick=995)]              # frozen [1005, 1065)
    assert pos(extrapolate(cur, prev, H, 0, own_effects=fz), 1) == pytest.approx((9000, 11000 - 60 * 4))
    assert pos(extrapolate(cur, prev, H, 0), 1) == pytest.approx((9000, 11000 - 60 * H))


def test_reader_frames_resolve_bodies_by_card_id():
    hog = 26000021                                                     # reader Hog Rider id (live catalog)
    f = lambda t, y: {"game_tick": t, "entities": [{"address": "0x1", "side": 1, "x": 9000.0, "y": y,  # noqa: E731
                                                     "card_id": hog, "kind": 15, "hp": 1, "max_hp": 1}], "players": []}
    log = [dict(card="the-log", x=9000, y=16000, tick=1000)]           # my side 0: rolls toward +y
    out = extrapolate(f(1000, 18000.0), f(990, 19200.0), H, 0, own_effects=log)
    assert out["entities"][0]["y"] == pytest.approx(18000 - 120 * 18 + 500)   # as the SIM-shaped Hog above
