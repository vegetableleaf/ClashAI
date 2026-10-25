"""Plan A 10-25: reward_terms rocket_cycle (free chip Rockets only) and king_redirect (own king HP absorbed after a redirect
Tornado). Pure learner-side tests on synthetic crown records (row_terms), the bound, crown_cfg, and off == unchanged."""
import pytest

from pipeline import reward_terms as RT
from pipeline.rl_royale import crown_cfg

BASE = {"advantage": "gae", "league": True}


def _crown(**kw):
    c = {"lost": [], "falls": [], "tornados": [], "rockets": [], "end": {}, "rocket_hits": [], "king_lost": [], "troop_lost": []}
    c.update(kw)
    return c


def _play(tick, card, el, land=None):
    return {"tick": tick, "card": card, "accepted": True, "elixir_exact": el, "land_tick": tick + 20 if land is None else land}


def test_off_is_unchanged():
    c = _crown(rocket_hits=[{"seen": 3000, "dmg": 0.1}])
    plays, ticks = [_play(2970, "Rocket", 9.0)], [100, 2970, 3100]
    a = RT.row_terms(c, plays, ticks, {})
    assert set(a) == {"phi", "lead", "redirect", "tornado", "unmapped", "r"} and not a["r"].any()


def test_rocket_cycle_pays_free_chips_only():
    p = crown_cfg({**BASE, "rocket_cycle": True})
    hits = [{"seen": 3000, "dmg": 0.1},      # free: 2x, 9 elixir, no own damage before -> paid
            {"seen": 1000, "dmg": 0.1},      # 1x -> not paid
            {"seen": 4000, "dmg": 0.1},      # 6 elixir -> not paid
            {"seen": 5000, "dmg": 0.1}]      # own princess hit 2 s before the decision -> not paid
    plays = [_play(2970, "Rocket", 9.0), _play(970, "Rocket", 9.5), _play(3970, "Rocket", 6.0), _play(4970, "Rocket", 9.0)]
    ticks = [970, 2970, 3970, 4970]
    c = _crown(rocket_hits=hits, troop_lost=[[4930, 0.05]], lost=[[2950, 0.04], [4930, 0.09]])   # 2950 = enemy spell
    out = RT.row_terms(c, plays, ticks, p)
    assert out["r"][1] == pytest.approx(0.05) and out["r"][[0, 2, 3]].sum() == 0
    assert out["rocket_cycle"] == pytest.approx(0.05) and out["rocket_cycle_free"] == 1


def test_rocket_cycle_cap():
    p = crown_cfg({**BASE, "rocket_cycle": True})
    hits = [{"seen": 3000 + 100 * i, "dmg": 0.2} for i in range(6)]
    plays = [_play(2970 + 100 * i, "Rocket", 9.0) for i in range(6)]
    out = RT.row_terms(_crown(rocket_hits=hits), plays, [q["tick"] for q in plays], p)
    assert out["rocket_cycle"] == pytest.approx(RT.ROCKET_MATCH_CAP)


def test_king_redirect_pays_redirects_only():
    p = crown_cfg({**BASE, "king_redirect": True})
    tor = [{"seen": 2000, "end": 2050, "down": 0, "toward": 2.0, "n": 1},    # redirect, king took 0.08 -> 0.04
           {"seen": 3000, "end": 3050, "down": 1, "toward": 2.0, "n": 1},    # a princess down -> no
           {"seen": 4000, "end": 4050, "down": 0, "toward": 0.5, "n": 1}]    # pulled < 1 tile -> no
    kl = [[2060, 0.03], [2120, 0.08], [3060, 0.2], [4060, 0.3]]
    plays = [_play(1980, "Tornado", 5.0), _play(2980, "Tornado", 5.0), _play(3980, "Tornado", 5.0)]
    out = RT.row_terms(_crown(tornados=tor, king_lost=kl), plays, [1980, 2980, 3980], p)
    assert out["r"][0] == pytest.approx(0.5 * 0.08) and out["r"][1:].sum() == 0
    assert out["king_redirect"] == pytest.approx(0.04)


def test_king_redirect_event_cap_and_missing_record():
    p = crown_cfg({**BASE, "king_redirect": True})
    tor = [{"seen": 2000, "end": 2050, "down": 0, "toward": 3.0, "n": 2}]
    out = RT.row_terms(_crown(tornados=tor, king_lost=[[2100, 0.9]]), [_play(1980, "Tornado", 5.0)], [1980], p)
    assert out["king_redirect"] == pytest.approx(RT.KING_EVENT_CAP)
    c = _crown(tornados=tor)
    del c["king_lost"]
    with pytest.raises(ValueError):
        RT.row_terms(c, [_play(1980, "Tornado", 5.0)], [1980], p)


def test_bound_and_cfg():
    assert RT.bound({"rocket_cycle": True, "king_redirect": True}) == pytest.approx(RT.ROCKET_MATCH_CAP + RT.KING_MATCH_CAP)
    p = crown_cfg({**BASE, "rocket_cycle": True, "rocket_cycle_w": 0.4})
    assert p["rocket_cycle_w"] == 0.4 and "king_redirect" not in p
    with pytest.raises(SystemExit):
        crown_cfg({**BASE, "king_redirect_w": 0.3})     # weight without its switch


def test_rocket_cycle_ignores_enemy_spell_damage():
    p = crown_cfg({**BASE, "rocket_cycle": True})
    hits, plays = [{"seen": 3000, "dmg": 0.1}], [_play(2970, "Rocket", 9.0)]
    spell_only = _crown(rocket_hits=hits, lost=[[2940, 0.05]], troop_lost=[])          # their Rocket hit us 1.5 s before
    assert RT.row_terms(spell_only, plays, [2970], p)["rocket_cycle"] == pytest.approx(0.05)
    troop = _crown(rocket_hits=hits, lost=[[2940, 0.05]], troop_lost=[[2940, 0.05]])   # a troop hit us -> defence owed
    assert RT.row_terms(troop, plays, [2970], p)["rocket_cycle"] == 0.0
    c = _crown(rocket_hits=hits)
    del c["troop_lost"]
    with pytest.raises(ValueError):
        RT.row_terms(c, plays, [2970], p)
