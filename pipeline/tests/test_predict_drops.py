"""predict_drops (L73 Skeleton Barrel audit): the look-ahead shows an observed balloon's 7 skeletons once T + 12 <= t + H.

    icebow/.venv/Scripts/python.exe -m pytest -q pipeline/tests/test_predict_drops.py
"""
import copy
import math
from collections import deque

import pytest
import torch

from pipeline import vocab
from pipeline.dataset_gen import card_key
from pipeline.extrapolate import DROP_DELAY, DROP_TTL, DropTracker, extrapolate
from pipeline.live_gen import GenPilot
from pipeline.live_mem import deck_of
from pipeline.tests.test_live_mem import FRAME

SB, SB_EVO, KNIGHT = 26000056, 13000056, 26000000
H = 26


def ent(addr, x, y, side=0, cid=SB, hp=532, mhp=532, kind=15):
    return {"address": addr, "side": side, "x": x, "y": y, "card_id": cid, "kind": kind, "hp": hp, "max_hp": mhp}


def fr(tick, ents):
    f = copy.deepcopy(FRAME)
    f["game_tick"] = tick
    f["entities"] = f["entities"] + ents       # FRAME: my side 1 (hand visible), enemy side 0
    return f


def kids(out):
    return [e for e in out["entities"] if str(e["address"]).startswith("predicted_drop")]


def test_balloon_gone_at_T_shows_seven_skeletons_only_when_T_plus_12_within_horizon():
    d = DropTracker()
    d.observe(fr(1000, [ent("0xb", 5000, 9000)]), 1)
    assert d.pending == []
    d.observe(fr(1002, []), 1)                                        # first absent tick T = 1002
    (p,) = d.pending
    assert (p["t0"], p["x"], p["y"]) == (1002, 5000.0, 9000.0)
    f = fr(1002, [])
    assert kids(extrapolate(f, None, 9, 1, drops=d.pending)) == []   # T + 12 = 1014 > 1002 + 9
    assert kids(extrapolate(f, None, 10, 1, drops=d.pending)) == []  # 1014 > 1012
    out = extrapolate(f, None, 12, 1, drops=d.pending)               # 1014 <= 1014
    assert len(kids(out)) == 7
    out = extrapolate(f, None, H, 1, drops=d.pending)
    ks = kids(out)
    assert len(ks) == 7 and {e["card_id"] for e in ks} == {SB} and {e["side"] for e in ks} == {0}
    assert {e["max_hp"] for e in ks} == {81.0} and {e["hp"] for e in ks} == {81.0}
    for e in ks:                                                      # age 14 ticks: on the full ring, past deploying
        assert math.hypot(e["x"] - 5000, e["y"] - 9000) == pytest.approx(1460, abs=1e-6) and e["kind"] == 15
    fresh = kids(extrapolate(f, None, 12, 1, drops=d.pending))        # age 0: still at the drop point, deploying
    assert {round(math.hypot(e["x"] - 5000, e["y"] - 9000)) for e in fresh} == {250} and {e["kind"] for e in fresh} == {14}
    assert len({e["address"] for e in ks}) == 7
    assert f["entities"] == FRAME["entities"]                         # the input observation is untouched


def test_default_off_is_byte_identical():
    prev, cur = fr(990, [ent("0xk", 100, 100, cid=KNIGHT, hp=1, mhp=1)]), fr(1000, [ent("0xk", 200, 100, cid=KNIGHT, hp=1, mhp=1)])
    base = extrapolate(cur, prev, H, 1)
    assert extrapolate(cur, prev, H, 1, drops=None) == base
    assert extrapolate(cur, prev, H, 1, drops=[]) == base
    d = DropTracker()
    for f in (prev, cur):
        d.observe(f, 1)
    assert d.pending == [] and extrapolate(cur, prev, H, 1, drops=d.pending) == base


def test_other_cards_and_own_balloons_do_not_drop():
    d = DropTracker()
    d.observe(fr(1000, [ent("0xk", 100, 100, cid=KNIGHT, hp=1400, mhp=1400), ent("0xm", 300, 300, side=1)]), 1)
    d.observe(fr(1002, []), 1)                                        # the enemy Knight and MY barrel vanish
    assert d.pending == []
    assert kids(extrapolate(fr(1002, []), None, H, 1, drops=d.pending)) == []


def test_skeletons_of_a_barrel_do_not_count_as_a_balloon():
    d = DropTracker()
    d.observe(fr(1000, [ent("0xs", 100, 100, hp=81, mhp=81)]), 1)    # a skeleton (card id = barrel, low max_hp)
    d.observe(fr(1002, []), 1)
    assert d.pending == []


def test_pending_clears_when_real_skeletons_appear_and_after_ttl_and_on_flicker():
    d = DropTracker()
    d.observe(fr(1000, [ent("0xb", 5000, 9000)]), 1)
    d.observe(fr(1002, []), 1)
    assert len(d.pending) == 1
    d.observe(fr(1014, [ent("0xc%d" % i, 5000 + 100 * i, 9000, hp=81, mhp=81) for i in range(7)]), 1)
    assert d.pending == []                                            # real skeletons observed
    # a skeleton a long way off does not clear it, the TTL does
    d.reset()
    d.observe(fr(1000, [ent("0xb", 5000, 9000)]), 1)
    d.observe(fr(1002, []), 1)
    d.observe(fr(1020, [ent("0xs", 15000, 25000, hp=81, mhp=81)]), 1)
    assert len(d.pending) == 1
    d.observe(fr(1002 + DROP_TTL, []), 1)
    assert len(d.pending) == 1
    d.observe(fr(1002 + DROP_TTL + 1, []), 1)
    assert d.pending == []
    # flicker: the balloon is back next frame -> not a death
    d.reset()
    d.observe(fr(1000, [ent("0xb", 5000, 9000)]), 1)
    d.observe(fr(1002, []), 1)
    d.observe(fr(1004, [ent("0xb", 5050, 9000)]), 1)
    assert d.pending == []


def test_new_match_resets_and_evo_and_level_hp():
    d = DropTracker()
    d.observe(fr(5000, [ent("0xb", 5000, 9000, cid=SB_EVO, hp=881, mhp=881)]), 1)
    d.observe(fr(5002, []), 1)
    ks = kids(extrapolate(fr(5002, []), None, H, 1, drops=d.pending))
    assert {e["max_hp"] for e in ks} == {108.0} and {e["card_id"] for e in ks} == {SB_EVO}     # evo L14: 881 -> 108
    for mhp, child in ((532, 81), (586, 89), (642, 98), (705, 108), (773, 119)):
        d.reset()
        d.observe(fr(100, [ent("0xb", 5000, 9000, mhp=mhp, hp=mhp)]), 1)
        d.observe(fr(102, []), 1)
        assert {e["max_hp"] for e in kids(extrapolate(fr(102, []), None, H, 1, drops=d.pending))} == {float(child)}
    d.observe(fr(50, []), 1)                                          # tick went backwards: new match
    assert d.pending == []


def _pilot(drops):
    p = object.__new__(GenPilot)
    _, names = deck_of(FRAME, 1)
    p.gid = {card_key(n): i + 1 for i, n in enumerate(names)}
    p.grid, p.dev, p.gate_tau = "lattice", torch.device("cpu"), 0.5
    p.past, p.history, p.opp, p.opp_est = [], {}, None, None
    p.ext_h, p.frames = H, deque(maxlen=30)
    p.drops = DropTracker() if drops else None
    return p


def test_live_pilot_row_board_has_the_skeletons_only_with_the_flag():
    barrel = vocab.engine_unit_id("SkeletonBalloon")
    seen = []
    for flag in (False, True):
        p = _pilot(flag)
        p.observe(fr(1000, [ent("0xb", 5000, 9000)]))
        f = fr(1002, [])
        p.observe(f)
        seen.append(sum(u.cls == barrel for u in p.row(f)[1]["bs"].units))
    assert seen == [0, 7]


# ---- SIM: e1_eval cfg["predict_drops"] (decisions every 10 ticks, extrapolate 26) --------------------------------
from pipeline.tests.test_e1_action_delay import _Env, _scripted            # noqa: E402
from pipeline.tests.test_e1_opp_counter import T                           # noqa: E402


class _BarrelEnv(_Env):
    """An enemy Skeleton Barrel balloon on the board until T + 30; its real 7 skeletons from T + 30 + 12."""

    def _state(self):
        st = super()._state()
        base = dict(side=1, card_id=SB, name="SkeletonBalloon", kind=15)
        if self.tick < T + 30:
            st["entities"].append(dict(base, entity_id=9001, x=9000, y=16000, hp=532, max_hp=532))
        elif self.tick >= T + 42:
            st["entities"] += [dict(base, entity_id=9100 + k, x=9000 + 100 * k, y=16000, hp=81, max_hp=81) for k in range(7)]
        return st


def _barrels(views):
    barrel = vocab.engine_unit_id("SkeletonBalloon")
    return [sum(u.cls == barrel and u.side == 1 for u in v.units) for v in views]


def test_sim_decisions_see_the_skeletons_only_with_the_flag_and_never_twice():
    base = {"extrapolate_ticks": H}
    off = _scripted([], None, env=_BarrelEnv(), **base)[0].views
    assert _scripted([], None, env=_BarrelEnv(), predict_drops=False, **base)[0].views == off    # default-off: same boards
    on = _scripted([], None, env=_BarrelEnv(), predict_drops=True, **base)[0].views
    n_off, n_on = _barrels(off), _barrels(on)
    assert n_off[:6] == [1, 1, 1, 0, 0, 7]                            # balloon at T..T+20; real 7 seen from T+50
    assert n_on[:3] == n_off[:3]                                      # decisions T..T+20: balloon alive, identical boards
    assert n_on[3:5] == [7, 7]                                        # T+30 (first absent -> predicted), T+40 (real ones not out)
    assert n_on[5:] == n_off[5:] and set(n_on[5:]) == {7}             # T+50 on: the real 7, not 14 (pending cleared)


def test_sim_flag_without_barrels_is_a_noop():
    base = {"extrapolate_ticks": H}
    plain = _scripted([], None, **base)[0].views
    assert _scripted([], None, predict_drops=True, **base)[0].views == plain
    assert _scripted([], None, predict_drops=True)[0].views == _scripted([], None)[0].views   # no extrapolate: ignored
