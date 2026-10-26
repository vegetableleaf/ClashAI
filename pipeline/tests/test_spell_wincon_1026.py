"""Owner 10-26: a defensive Rocket on a 5-elixir win condition (Ram Rider / Balloon / Royal Hogs) can be the best defence even
at -1 elixir: spell_value_wincon_mult values a target_only_buildings body x mult when the Rocket lands on MY half."""
import pytest

from pipeline import spell_value as SV

P = dict(SV.DEFAULTS)


def _ev(bodies, aim_y=24.0, princess=False):
    kill = sum(v * f for _, v, f, k in bodies if k)
    dmg = sum(v * f for _, v, f, k in bodies if not k)
    return {"kill": kill, "dmg": dmg, "bodies": bodies, "aim": (4.0, aim_y), "princess": princess, "cost": 6}


def test_is_wincon():
    for n in ("RamRider", "RoyalHog", "RoyalHogs", "HogRider_EV1", "Balloon", "ElectroGiant", "Giant"):
        assert SV.is_wincon(n), n
    for n in ("Knight", "Witch", "Skeleton", "MegaKnight", ""):
        assert not SV.is_wincon(n), n


def test_default_is_the_old_reward():
    ev = _ev([["RamRider", 5.0, 1.0, True]])
    assert SV.event_reward(ev, P) == pytest.approx((5.0, 5.0, P["spell_value_w"] * (5.0 - 6.0)))


def test_defensive_wincon_rocket_pays():
    p = {**P, "spell_value_wincon_mult": 2.0}
    v, g, r = SV.event_reward(_ev([["RamRider", 5.0, 1.0, True]]), p)
    assert v == pytest.approx(10.0) and r == pytest.approx(p["spell_value_w"] * 4.0) and r > 0
    hogs = [["RoyalHog", 1.25, 1.0, True]] * 4
    assert SV.event_reward(_ev(hogs), p)[2] > 0


def test_scope():
    p = {**P, "spell_value_wincon_mult": 2.0}
    off_half = SV.event_reward(_ev([["RamRider", 5.0, 1.0, True]], aim_y=8.0), p)
    assert off_half[0] == pytest.approx(5.0)                     # enemy half: an offensive Rocket, unchanged
    knight = SV.event_reward(_ev([["Knight", 3.0, 1.0, True]]), p)
    assert knight[0] == pytest.approx(3.0)                       # not a win condition: unchanged
    mixed = SV.event_reward(_ev([["RamRider", 5.0, 0.5, False], ["Knight", 3.0, 1.0, True]]), p)
    assert mixed[0] == pytest.approx(3.0 + P["spell_value_dmg_w"] * 5.0 * 0.5 * 2.0)
