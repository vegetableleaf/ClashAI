"""reward_shaping tower_phat (LOOP-LRN): record, antisymmetry, bound, and the potential-shaping identities through
rl_royale's own shaping path (collate's ``shaping_rewards``): with Phi(terminal) = 0 the shaping telescopes,
sum_t F_t = Phi(T) - Phi(0) = -Phi(0) at gamma 1, and sum_t (prod_{i<t} gamma_i) F_t = -Phi(0) with per-row gamma_tick.

    icebow/.venv/Scripts/python.exe -m unittest pipeline.tests.test_shaping_tower_phat -v
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from pipeline import reward_shaping as RS                       # noqa: E402
from pipeline import rl_royale as RL                            # noqa: E402


def state(own, foe, tick, side=0):
    """own / foe = (king hp frac, princess L, princess R); 0 = destroyed."""
    tw = []
    for s, (k, a, b) in ((side, own), (1 - side, foe)):
        for typ, f in (("king", k), ("princess", a), ("princess", b)):
            tw.append({"side": s, "type": typ, "hp": 1000.0 * f, "max_hp": 1000.0, "destroyed": f <= 0})
    return {"episode": {"crown_towers": tw}, "tick": tick}


def match(rng, n):
    """A random monotone tower history from both sides' views (rows, rows of the mirror), ticks strictly increasing."""
    hp = np.ones((2, 3))
    ticks = np.cumsum(rng.integers(5, 40, n))
    rows, mrows = [], []
    for t in ticks:
        hp = np.maximum(0.0, hp - rng.random((2, 3)) * (rng.random((2, 3)) < 0.1) * 0.3)
        hp[:, 0] = np.maximum(hp[:, 0], 0.05)                  # the king stands (the match would end)
        s = state(tuple(hp[0]), tuple(hp[1]), int(t))
        rows.append(RS.state_record("tower_phat", s, 0, None, {}))
        mrows.append(RS.state_record("tower_phat", s, 1, None, {}))
    return np.array(rows), np.array(mrows), ticks


class TestTowerPhat(unittest.TestCase):
    def test_record(self):
        r = RS.tower_phat_record(state((1.0, 0.5, 0.0), (0.8, 1.0, 1.0), 1234), 0)
        np.testing.assert_allclose(r, [1.5, 0.0, 1.0, 1.0, 0.0, 0.2, 1.0, 0.0, 1234.0], atol=1e-12)   # own: a princess down -> king active, 1 crown conceded
        self.assertEqual(RS.tower_phat_record(state((1, 1, 1), (1, 1, 1), 0), 1), [0.0] * 8 + [0.0])

    def test_even_zero_antisymmetric_bounded(self):
        rows, mrows, _ = match(np.random.default_rng(1), 300)
        p, q = RS.phi_tower_phat(rows, {}), RS.phi_tower_phat(mrows, {})
        np.testing.assert_allclose(p, -q, atol=1e-12)          # zero-sum: my Phi = -the opponent's
        even = [0.6, 0.3, 1.0, 1.0, 0.6, 0.3, 1.0, 1.0, 3000.0]      # equal losses both sides -> exactly 0
        self.assertEqual(float(RS.phi_tower_phat([even], {})[0]), 0.0)
        self.assertTrue((np.abs(p) < 0.5).all())
        self.assertEqual(RS.phi_bound("tower_phat", {}), 0.5)
        self.assertGreater(np.abs(p).max(), 0.05)              # the fitted potential is not flat

    def test_more_damage_dealt_is_better(self):
        a = RS.tower_phat_record(state((1, 1, 1), (1, 0.6, 1), 2000), 0)
        b = RS.tower_phat_record(state((1, 1, 1), (1, 0.3, 1), 2000), 0)
        self.assertGreater(RS.phi_tower_phat([b], {})[0], RS.phi_tower_phat([a], {})[0])

    def test_telescoping_through_rl_royale(self):
        rng = np.random.default_rng(2)
        for n in (1, 2, 57):
            rows, _, ticks = match(rng, n)
            phi = RS.phi_tower_phat(rows, {})
            sh1 = RL.shaping_rewards(rows, {"mode": "tower_phat", "gamma": 1.0, "params": {}})
            self.assertAlmostEqual(float(sh1["F"].sum()), 0.0 - float(phi[0]), places=12)   # Phi(T) - Phi(0), Phi(T) = 0
            np.testing.assert_allclose(sh1["phi"], phi, atol=0)
            g = RL.row_gammas(ticks, 0.99994)
            sh = RL.shaping_rewards(rows, {"mode": "tower_phat", "gamma": g, "params": {}})
            disc = np.r_[1.0, np.cumprod(g[:-1])]
            self.assertAlmostEqual(float((disc * sh["F"]).sum()), -float(phi[0]), places=12)
            for t in range(n):                                  # return-to-go of the shaping from t = -Phi(s_t)
                d = np.r_[1.0, np.cumprod(g[t:-1])]
                self.assertAlmostEqual(float((d * sh["F"][t:]).sum()), -float(phi[t]), places=12)

    def test_adv_cfg_bound(self):
        base = {"advantage": "gae", "shaping": "tower_phat", "critic_warmup_updates": 5}
        self.assertEqual(RL.adv_cfg({**base, "shaping_critic_scale": 1.5})["shaping"], "tower_phat")
        with self.assertRaises(SystemExit):
            RL.adv_cfg({**base, "shaping_critic_scale": 1.4})


if __name__ == "__main__":
    unittest.main()
