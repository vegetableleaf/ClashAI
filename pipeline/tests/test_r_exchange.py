import numpy as np

from pipeline import r_exchange as RX

KNIGHT, XBOW, SPIRIT = 1, 2, 3
VALUES = {KNIGHT: (3.0, 0.0, False), XBOW: (6.0, 1 / 600, False), SPIRIT: (1.0, 0.0, True)}
F = list(RX.FEATURES)


def towers(own=(1000, 1000, 2000), opp=(1000, 1000, 2000)):
    keys = ("pl", "pr", "k")
    return ([(0, -1, h, m, "o" + k) for k, h, m in zip(keys, own, (1000, 1000, 2000)) if h is not None] +
            [(1, -1, h, m, "e" + k) for k, h, m in zip(keys, opp, (1000, 1000, 2000)) if h is not None])


def frame(t, ents=(), side=0, elixir=5.0, opp_e=5.0, **tw):
    return {"tick": t, "side": side, "elixir": elixir, "opp_elixir": opp_e, "ents": towers(**tw) + list(ents)}


def last(frames):
    return RX.running_losses(frames, VALUES)[1][-1]


def test_damage_and_kill_count_elixir_and_dropout_does_not():
    fr = [frame(0, [(1, KNIGHT, 100, 100, "a")]), frame(2, [(1, KNIGHT, 50, 100, "a")])]
    assert np.isclose(last(fr)[1, F.index("elixir")], 1.5)
    gone = fr + [frame(t) for t in range(4, 4 + 2 * RX.GRACE, 2)]                 # vanished: the rest counts
    assert np.isclose(last(gone)[1, F.index("elixir")], 3.0)
    blip = fr + [frame(4), frame(6, [(1, KNIGHT, 50, 100, "a")])] + [frame(t, [(1, KNIGHT, 50, 100, "a")])
                                                                       for t in range(8, 40, 2)]
    assert np.isclose(last(blip)[1, F.index("elixir")], 1.5)                    # reader dropout: no kill


def test_building_decay_and_kamikaze_are_not_destruction():
    fr = [frame(t, [(0, XBOW, 600 - t, 600, "x")]) for t in range(0, 100, 2)]  # 1/600 of max per tick = decay
    assert abs(last(fr)[0, F.index("elixir")]) < 1e-9
    fr = [frame(0, [(1, SPIRIT, 10, 10, "s")])] + [frame(t) for t in range(2, 40, 2)]
    assert last(fr)[1, F.index("elixir")] == 0


def test_towers_crowns_king_activation_and_symmetry():
    fr = [frame(0), frame(2, opp=(500, 1000, 2000)), frame(4, opp=(None, 1000, 2000))] + \
         [frame(t, opp=(None, 1000, 2000)) for t in range(6, 40, 2)]
    L = last(fr)
    assert np.allclose(L[1, :4], [1.0, 0.0, 1.0, 1.0]) and np.allclose(L[0, :4], 0)
    mirrored = [dict(f, side=1) for f in fr]                                    # same board, other observer
    assert np.allclose(RX.features(last(mirrored)), -RX.features(L))


def test_leak_counts_own_and_opp_at_full_elixir_only():
    fr = [frame(t, elixir=10.0, opp_e=4.0) for t in range(0, 58, 2)]
    L = last(fr)
    assert np.isclose(L[0, F.index("leak")], 56 / 56) and L[1, F.index("leak")] == 0


def test_idle_earns_nothing_leak_costs_and_cap_holds():
    beta = np.tile(np.ones(len(F)), (3, 1))
    ticks, r = RX.r_exchange([frame(t) for t in range(0, 200, 2)], VALUES, beta)
    assert np.allclose(r, 0)                                                     # nothing happens -> 0, no intercept
    ticks, r = RX.r_exchange([frame(t, elixir=10.0) for t in range(0, 200, 2)], VALUES, beta)
    assert r.sum() < 0                                                           # holding at 10 is never free
    big = [frame(0)] + [frame(t, opp=(None, None, 2000)) for t in range(2, 60, 2)]
    ticks, r = RX.r_exchange(big, VALUES, 50 * beta, cap=0.5)
    assert np.isclose(r.sum(), 0.5) and np.all(np.abs(np.cumsum(r)) <= 0.5 + 1e-12)


def test_spawned_bodies_are_not_deployed_elixir():
    witch = [(1, KNIGHT, 1000, 1000, "w"), (1, KNIGHT, 100, 100, "s")]          # main body then a spawn, same card id
    fr = [frame(0, witch[:1]), frame(2, witch)] + [frame(t, witch[:1]) for t in range(4, 40, 2)]
    assert last(fr)[1, F.index("elixir")] == 0                                   # a spawn (100 < 0.5 x 1000)


def test_public_streams_commits_and_threat_leak():
    fr = [frame(0, elixir=8.0, opp_e=10.0), frame(2, elixir=5.0, opp_e=10.0)]                 # we played a 3
    fr += [dict(frame(t, elixir=10.0, opp_e=10.0), threat=(t >= 30, False)) for t in range(4, 60, 2)]
    _, C, LT = RX.public_streams(fr)
    assert np.isclose(C[-1, 0], 3.0 + 2 / 56) and C[-1, 1] == 0
    assert np.isclose(LT[-1, 0], 30 / 56) and LT[-1, 1] == 0                                  # only while threatened
