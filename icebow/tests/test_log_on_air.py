"""L67ae (owner report, run15/16): the live Log is never cast into a corridor that holds only AIR units.

`log_corridor_cell` drops flyers when it aims, but when no ground enemy is near it leaves the model's own aim alone --
so a Log could roll straight under Minions / Bats. `reward.log_only_hits_air` judges the final cast corridor; play.py
skips the play when it returns True.
"""
from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from clashrl.reward import log_only_hits_air                              # noqa: E402

PLAY = os.path.join(os.path.dirname(__file__), "..", "src", "clashrl", "play.py")
AIR = {"minions", "bats", "balloon", "baby_dragon"}
HW, ROLL = 0.064, 0.28


class LogOnAir(unittest.TestCase):
    def test_only_air_in_the_corridor_is_vetoed(self):
        tracks = [(0.50, 0.40, 0, 0, "minions"), (0.52, 0.35, 0, 0, "bats")]
        self.assertTrue(log_only_hits_air(0.50, 0.50, tracks, HW, ROLL, AIR))

    def test_a_ground_unit_in_the_corridor_allows_the_cast(self):
        tracks = [(0.50, 0.40, 0, 0, "minions"), (0.49, 0.42, 0, 0, "goblins")]
        self.assertFalse(log_only_hits_air(0.50, 0.50, tracks, HW, ROLL, AIR))

    def test_an_empty_corridor_is_left_to_the_model(self):
        tracks = [(0.90, 0.40, 0, 0, "minions")]                           # air, but well outside the corridor
        self.assertFalse(log_only_hits_air(0.50, 0.50, tracks, HW, ROLL, AIR))
        self.assertFalse(log_only_hits_air(0.50, 0.50, [], HW, ROLL, AIR))

    def test_air_behind_the_cast_point_does_not_count(self):
        tracks = [(0.50, 0.60, 0, 0, "bats")]                               # behind (larger y) by more than half a width
        self.assertFalse(log_only_hits_air(0.50, 0.50, tracks, HW, ROLL, AIR))

    def test_a_base_less_track_counts_as_ground(self):
        tracks = [(0.50, 0.40, 0, 0)]
        self.assertFalse(log_only_hits_air(0.50, 0.50, tracks, HW, ROLL, AIR))


class PlayWiring(unittest.TestCase):
    def test_play_checks_the_final_log_cell(self):
        with open(PLAY, encoding="utf-8") as fh:
            src = fh.read()
        if "log_corridor_cell(cx, cy, _tk" not in src:
            self.skipTest("this deck's play.py has no Log assist")
        self.assertIn("log_only_hits_air(_lcx, _lcy, _tk, _log_half_w, _log_roll, _AIR_BASES)", src)
        self.assertLess(src.index("log_corridor_cell(cx, cy, _tk"), src.index("log_only_hits_air(_lcx"))


if __name__ == "__main__":
    unittest.main()
