"""SOFT overtime flip (owner 2026-09-02, HANDOFF §5bo): the offence->defence phase is a weight
`_defensive_w` in [0, 1] that ramps through overtime, not a switch. Tested on a stub the way
test_doctrine_wheels does it -- LiveMatchEnv needs a window and a detector.
"""
from __future__ import annotations

import os
import sys
import time
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from clashrl.config import Config                       # noqa: E402
from clashrl.clock import ElixirClock                   # noqa: E402
from clashrl.env import LiveMatchEnv                    # noqa: E402
from clashrl.reward import _anchors                     # noqa: E402


class _Tower:
    def __init__(self, alive):
        self.enemy_alive = list(alive)


class _Stub:
    _defensive = LiveMatchEnv._defensive                # the property, so assignment pins the weight

    def __init__(self, cfg, alive=(True, True), w=0.0):
        self.cfg = cfg
        self.tower = _Tower(alive)
        self.xbow_ids = {0}
        self.xbow_range = float(cfg.get("env", "xbow_range", default=0.36))
        self.xbow_defense_front = float(cfg.get("env", "xbow_defense_front", default=0.52))
        self.xbow_defense_back = float(cfg.get("env", "xbow_defense_back", default=0.62))
        self.xbow_deep_frac = 0.25
        self.w_wincon = 3.0
        self.w_wincon_mis = -1.0
        self._xbow_play_t = None
        self.xbow_lifetime = 30.0
        self._defensive_w = w


class DefensiveRampTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cfg = Config.load()
        _, enemy_a, _ = _anchors(cls.cfg)
        ax, ay = enemy_a[0]
        cls.forward = (ax, ay + 0.30)                   # in reach of princess 0 only
        cls.band = (0.48, 0.5 * (0.52 + 0.62))          # back-centre defensive band

    def _wc(self, stub, cell):
        stub._xbow_play_t = None                        # each call is a fresh bow (repeat-credit gate off)
        return LiveMatchEnv._wincon_exec_live(stub, 0, cell[0], cell[1])

    def test_w0_and_w1_are_the_old_branches(self):
        s = _Stub(self.cfg, w=0.0)
        self.assertAlmostEqual(self._wc(s, self.forward), 3.0)          # offensive: in range = full credit
        self.assertAlmostEqual(self._wc(s, self.band), 3.0 * 0.4)       # offensive: band = 40%
        s._defensive_w = 1.0
        self.assertAlmostEqual(self._wc(s, self.forward), -1.0)         # defensive: forward = misplace
        self.assertAlmostEqual(self._wc(s, self.band), 3.0)             # defensive: band = full

    def test_blend_is_monotone_in_w(self):
        s = _Stub(self.cfg)
        fwd, band = [], []
        for w in (0.0, 0.25, 0.5, 0.75, 1.0):
            s._defensive_w = w
            fwd.append(self._wc(s, self.forward))
            band.append(self._wc(s, self.band))
        self.assertEqual(fwd, sorted(fwd, reverse=True))
        self.assertEqual(band, sorted(band))
        self.assertAlmostEqual(fwd[2], 0.5 * 3.0 + 0.5 * -1.0)          # w=0.5: halfway

    def test_dead_princess_earns_no_offensive_credit(self):
        s = _Stub(self.cfg, alive=(False, True), w=0.0)
        self.assertAlmostEqual(self._wc(s, self.forward), -1.0)         # only the dead one in reach

    def test_property_pins_the_weight(self):
        s = _Stub(self.cfg, w=0.5)
        self.assertFalse(s._defensive)
        s._defensive = True
        self.assertEqual(s._defensive_w, 1.0)
        s._defensive = False
        self.assertEqual(s._defensive_w, 0.0)

    def test_clock_overtime_seconds(self):
        cfg = self.cfg
        c = ElixirClock(cfg, None)
        ot = float(cfg.get("elixir", "overtime_time_s", default=180.0))
        c._start = time.time() - (ot - 10.0)
        self.assertEqual(c.overtime_s, 0.0)
        c._start = time.time() - (ot + 30.0)
        self.assertGreaterEqual(c.overtime_s, 29.9)
        self.assertTrue(c.overtime)


if __name__ == "__main__":
    unittest.main()
