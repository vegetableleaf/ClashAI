"""L67ae X2 (HANDOFF 5cs.99 AJ/AK): once an enemy princess is down, the live X-Bow goes to that tower's pocket.

run16: X1 kept every X-Bow at the pros' favourite DEFENSIVE cells, 12.9 tiles from the nearest enemy princess, so no X-Bow
could hit a tower in 41 matches. Pros go forward 25.2% of the time after taking a tower (5-8% otherwise, whatever the
tower HP), 76% of those in the dead tower's lane at board y 0.391.
"""
from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from clashrl.actions import ActionSpace                                   # noqa: E402
from clashrl.config import Config                                         # noqa: E402
from clashrl.reward import xbow_pocket_cell                               # noqa: E402

PLAY = os.path.join(os.path.dirname(__file__), "..", "src", "clashrl", "play.py")


class XbowPocket(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from clashrl.cards import CardDB
        if "x_bow" not in CardDB(Config.load()).deck_identities():
            raise unittest.SkipTest("this deck has no X-Bow")
        cls.cfg = Config.load()
        cls.acts = ActionSpace(cls.cfg)
        cls.W = int(cls.cfg.get("action", "grid")[0])

    def _board(self, cell):
        fx, fy = self.acts.cell_center(cell % self.W, cell // self.W)
        return self.acts.warp.frame_to_board(fx, fy)

    def test_no_princess_down_no_pocket(self):
        self.assertIsNone(xbow_pocket_cell([True, True, True], self.acts))

    def test_left_down_goes_to_the_left_pocket_and_only_with_it_open(self):
        cell, side = xbow_pocket_cell([False, True, True], self.acts)
        self.assertEqual(side, 0)
        bx, by = self._board(cell)
        self.assertLess(bx, 0.5)
        self.assertLess(by, 0.5, "the pocket is on the enemy half")
        self.assertTrue(self.acts.deployable_mask(False, pocket=(True, False))[cell])
        self.assertFalse(self.acts.deployable_mask(False, pocket=(False, False))[cell], "not deployable without the pocket")

    def test_right_down_goes_right(self):
        cell, side = xbow_pocket_cell([True, False, True], self.acts)
        self.assertEqual(side, 1)
        self.assertGreater(self._board(cell)[0], 0.5)

    def test_both_down_keeps_the_sticky_lane_or_declines(self):
        self.assertIsNone(xbow_pocket_cell([False, False, True], self.acts))
        cell, side = xbow_pocket_cell([False, False, True], self.acts, sticky=1)
        self.assertEqual(side, 1)
        cell_l, side_l = xbow_pocket_cell([False, False, True], self.acts, sticky=0)
        self.assertEqual(side_l, 0)

    def test_a_tower_down_on_one_side_ignores_a_stale_sticky_lane(self):
        cell, side = xbow_pocket_cell([True, False, True], self.acts, sticky=0)
        self.assertEqual(side, 1, "only the dead tower's lane has a pocket")

    def test_play_tries_the_pocket_before_the_defensive_assists(self):
        with open(PLAY, encoding="utf-8") as fh:
            src = fh.read()
        if "xbow_lock_cell(" not in src:
            self.skipTest("no X-Bow block")
        self.assertLess(src.index("xbow_pocket_cell(tower_tracker.enemy_alive"), src.index("elif card_id in xbow_ids:"))
        self.assertIn('_xbow_pocket["side"] = None', src)


if __name__ == "__main__":
    unittest.main()
