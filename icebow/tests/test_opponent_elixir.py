from __future__ import annotations

import unittest

from clashrl.opponent_elixir import OpponentElixirEstimator


class _FakeDB:
    def __init__(self, costs):
        self._costs = dict(costs)

    def elixir(self, base):
        return self._costs.get(base)


class _Det:
    def __init__(self, base, cx, gy, team):
        self.base = base
        self.cx = cx
        self.gy = gy
        self.team = team


class OpponentElixirEstimatorTests(unittest.TestCase):
    def test_tracks_own_and_enemy_spend(self):
        est = OpponentElixirEstimator(_FakeDB({"ice_wizard": 3, "skeletons": 1}))
        est.reset(my_elixir=5.0)
        est.record_my_play("ice_wizard")
        val = est.update(5.0, [_Det("skeletons", 0.5, 0.5, "enemy")], now=1.0)
        self.assertGreater(val, 0.0)
        self.assertLessEqual(val, 1.0)


if __name__ == "__main__":
    unittest.main()