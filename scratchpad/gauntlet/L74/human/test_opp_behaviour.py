"""python -m pytest scratchpad/gauntlet/L74/human/test_opp_behaviour.py  (or run the file)"""
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import opp_behaviour as O

KNIGHT, SKELETONS = 26000000, 26000010            # catalog card ids (Knight 3 elixir)


def body(side, x, y, cid, addr, hp=1400):
    return dict(side=side, x=x, y=y, card_id=cid, hp=hp, max_hp=hp, kind=14, address=addr)


def test_plays_of_synthetic_bodies():
    tower = body(1, 9000, 29000, -1, "t", 7000)
    mine = body(0, 5000, 5000, KNIGHT, "m1")                       # observer is side 1: side-0 bodies are the OPPONENT's...
    # observer side 1  =>  opponent = side 0.  A side-1 body is ours and must be ignored.
    ours = body(1, 5000, 20000, KNIGHT, "o1")
    k1 = body(0, 4000, 10000, KNIGHT, "k1")                        # opponent knight, first seen tick 160
    frames = [(150, [tower]), (160, [tower, ours, k1]), (170, [tower, ours, k1]),
              (300, [tower, k1, body(0, 4000, 12000, KNIGHT, "k2")]),          # 140 ticks later: a second play
              (310, [tower, k1, body(0, 4000, 12000, KNIGHT, "k2"), body(0, 4500, 12000, KNIGHT, "k3")])]  # k3 joins k2's cast
    p = O.plays_of(frames, my_side=1)
    assert [(q[0], q[1], q[5], q[6]) for q in p] == [(160, "knight", 1, 10), (300, "knight", 2, 130)], p
    assert p[0][2] == 3.0 and p[0][3:5] == [14.0, 22.0]            # side 1 flips: (18000-4000, 32000-10000) / 1000
    del mine


def test_pre_est_uses_last_decision_strictly_before():
    p = O.pre_est([[160, "knight", 3.0, 0, 0, 1, 10], [50, "knight", 3.0, 0, 0, 1, 10]], [(150, 5.0), (160, 6.0), (170, 7.0)])
    assert p[0][7] == 5.0 and p[1][7] is None


def test_features_on_synthetic_plays():
    # [tick, key, cost, x, y, n, frame gap, pre-est]; our frame: river 16, bridge 13..19
    plays = [[300, "knight", 3.0, 9, 25.0, 1, 10, 5.0],      # own half
             [400, "the_log", 2.0, 9, 17.0, 1, 10, 4.0],          # bridge (the_log is a catalog spell)
             [700, "graveyard", 5.0, 9, 8.0, 1, 10, 9.0],     # our half, spell
             [3000, "golem", 8.0, 9, 30.0, 1, 10, 10.0]]      # 2x phase
    m = dict(plays=plays, end=3600, t0=150, mine=[200, 350], src="x", id="x", seen=[], res=1)
    f = O.features(m)
    assert f["own_half"] == 0.5 and f["bridge"] == 0.25 and f["our_half"] == 0.25
    assert f["first_tick"] == 300
    plays[0][6] = 40                                             # a sighting 40 ticks after the previous frame: out of the position shares
    g = O.features(dict(m, plays=plays))
    assert all(abs(g[k] - 1 / 3) < 1e-9 for k in ("own_half", "bridge", "our_half"))        # knight dropped: golem / the_log / graveyard
    plays[0][6] = 10
    assert math.isclose(f["ppm_1x"], 3 / ((2400 - 150) / 1200)), f["ppm_1x"]
    assert math.isclose(f["ppm_2x"], 1 / (1200 / 1200))
    assert math.isclose(f["spell_share"], 2 / 4)                # log (catalog type spell) + graveyard
    # reaction: our 200 -> their 300 (5 s), our 350 -> their 400 (2.5 s)
    assert math.isclose(f["react_s"], (5.0 + 2.5) / 2) and f["react_3s"] == 0.5
    assert math.isclose(f["react_lift"], 0.5 - 240 / 3450)       # chance: four disjoint 60-tick lead-in windows over 3450 ticks
    # 8 s windows (160 ticks) from t0=150: 21 whole windows; 300 -> w0 (3), 400 -> w1 (2), 700 -> w3 (5), 3000 -> w17 (8)
    assert math.isclose(f["push_mean"], 18 / 21) and f["push_max"] == 8.0
    assert math.isclose(f["opp_el"], (5 + 4 + 9 + 10) / 4)


def test_short_match_has_no_2x_rate_and_compare_effect_size():
    m = dict(plays=[], end=1500, t0=150, mine=[], src="x", id="x", seen=[], res=0)
    f = O.features(m)
    assert math.isnan(f["ppm_2x"]) and math.isnan(f["first_tick"]) and f["ppm_1x"] == 0.0
    L = [dict.fromkeys(O.FEATS, 0.0) | {"ppm_1x": v} for v in (1.0, 2.0, 3.0, 4.0, 5.0)]
    S = [dict.fromkeys(O.FEATS, 0.0) | {"ppm_1x": v} for v in (2.0, 3.0, 4.0, 5.0, 6.0)]
    c = O.compare(L, S)
    assert math.isclose(c["ppm_1x"][4], 1.0 / math.sqrt(2.5))   # mean diff 1, pooled SD sqrt(2.5)
    assert c["bridge"][4] != c["bridge"][4] or c["bridge"][4] == 0.0   # zero variance both sides: nan, never inf


if __name__ == "__main__":
    for k, v in list(globals().items()):
        if k.startswith("test_"):
            v(); print("ok", k)
