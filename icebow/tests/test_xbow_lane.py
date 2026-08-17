"""Put the offensive X-Bow in the lane that still has a tower.

Reported from live overtime (user, 2026-08-16), one tower down on each side: the model placed a
technically perfect offensive bow several times, and every one was in the lane whose enemy
princess was ALREADY DESTROYED. Six elixir, a good spot, nothing to chip -- the bow can then only
fall through to the king, which is far tankier and further away.

Nothing existing caught it. `xbow_lock_cell` snaps to the NEARER tower's lane, which is exactly
wrong when the nearer one is the dead one, and the depth assist only sets the row. Neither ever
asked whether the target was alive.
"""
from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from clashrl.actions import ActionSpace                  # noqa: E402
from clashrl.config import Config                        # noqa: E402
from clashrl.reward import xbow_target_lane_cell         # noqa: E402

# left / right enemy princess anchors, mirroring reward._anchors' layout
LEFT, RIGHT = (0.25, 0.205), (0.745, 0.205)
ANCHORS = [LEFT, RIGHT]
DEFENSE_Y = 0.52                     # below this row a bow is OFFENSIVE
FULL = 2500.0


class XbowLaneTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.acts = ActionSpace(Config.load())

    def _lane_of(self, cell):
        gw = int(self.acts.gw)
        cx, _ = self.acts.cell_center(cell % gw, cell // gw)
        return "left" if abs(cx - LEFT[0]) < abs(cx - RIGHT[0]) else "right"

    def _call(self, cx, cy=0.50, hp=(FULL, FULL), alive=(True, True)):
        return xbow_target_lane_cell(cx, cy, ANCHORS, list(hp) if hp else None,
                                     list(alive), DEFENSE_Y, self.acts)

    # -- rule 1: never bow a dead lane ------------------------------------------------
    def test_a_bow_aimed_at_a_DEAD_left_tower_moves_right(self):
        got = self._call(cx=0.25, alive=(False, True))
        self.assertIsNotNone(got, "a bow in the dead lane must be moved")
        self.assertEqual(self._lane_of(got), "right")

    def test_a_bow_aimed_at_a_DEAD_right_tower_moves_left(self):
        got = self._call(cx=0.745, alive=(True, False))
        self.assertIsNotNone(got)
        self.assertEqual(self._lane_of(got), "left")

    def test_a_bow_already_on_the_live_tower_is_left_alone(self):
        self.assertIsNone(self._call(cx=0.745, alive=(False, True)))

    def test_both_towers_down_leaves_the_placement_alone(self):
        """Only the king is left; this rule has no opinion and must not thrash the placement."""
        self.assertIsNone(self._call(cx=0.25, alive=(False, False)))

    def test_the_dead_lane_rule_ignores_hp_entirely(self):
        """A destroyed tower cannot be chipped at any margin, so no HP gap can justify staying."""
        got = self._call(cx=0.25, hp=(0.0, FULL), alive=(False, True))
        self.assertEqual(self._lane_of(got), "right")

    # -- rule 2: concentrate on the weaker tower --------------------------------------
    def test_it_moves_to_the_clearly_weaker_tower(self):
        got = self._call(cx=0.25, hp=(FULL, FULL * 0.5))
        self.assertIsNotNone(got, "should concentrate on the weaker (right) tower")
        self.assertEqual(self._lane_of(got), "right")

    def test_a_near_tie_does_NOT_move_the_bow(self):
        """Without a margin the lane would flap between placements on ordinary chip damage."""
        self.assertIsNone(self._call(cx=0.25, hp=(FULL, FULL * 0.96)))

    def test_it_stays_when_already_on_the_weaker_tower(self):
        self.assertIsNone(self._call(cx=0.25, hp=(FULL * 0.4, FULL)))

    # -- scope --------------------------------------------------------------------
    def test_a_DEFENSIVE_bow_is_never_touched(self):
        """Deep in our half the bow is a second pull building, not a tower aim."""
        self.assertIsNone(self._call(cx=0.25, cy=0.60, alive=(False, True)))

    def test_missing_hp_readings_disable_only_the_weaker_rule(self):
        """The live digit read can fail; the dead-lane rule must still work without HP."""
        self.assertIsNone(self._call(cx=0.25, hp=None))
        got = xbow_target_lane_cell(0.25, 0.50, ANCHORS, None, [False, True], DEFENSE_Y, self.acts)
        self.assertEqual(self._lane_of(got), "right")

    def test_the_depth_row_is_preserved(self):
        """Depth belongs to xbow_offense_depth_cell; this rule only changes the lane."""
        gw = int(self.acts.gw)
        for cy in (0.47, 0.50):
            with self.subTest(cy=cy):
                got = self._call(cx=0.25, cy=cy, alive=(False, True))
                self.assertEqual(got // gw, self.acts.cell_at(0.745, cy) // gw)


if __name__ == "__main__":
    unittest.main()
