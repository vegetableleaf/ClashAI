"""Tests for exact Clash Royale level scaling.

These pin the two claims levels.py makes, because both are the kind of thing that looks fine
until a breakpoint quietly flips:

  1. the card table is the GAME's, not 1.1^n -- verified against real per-level arrays lifted
     from the game files, so a "simplification" back to the 10% rule fails here rather than in
     a training run three days later;
  2. towers do not use the card table, and the King does not use the Princess's.

The arrays below are transcribed from the game data (and cross-checked against the current
wiki, which publishes the same level-11 values). They are deliberately literal: the point of
the test is to compare against numbers that did NOT come out of the code under test.
"""
from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from clashrl import levels  # noqa: E402

# card -> exact hitpoints, levels 1..19
ARCHER = [119, 130, 143, 158, 173, 190, 209, 229, 252, 277, 304, 334, 367, 403, 442, 486, 535,
          589, 648]
ARCHER_DMG = [42, 46, 50, 55, 61, 67, 73, 81, 89, 97, 107, 118, 129, 142, 156, 171, 189, 207, 228]
KNIGHT = [690, 759, 834, 917, 1007, 1104, 1214, 1331, 1462, 1607, 1766, 1938, 2132, 2339, 2566,
          2822, 3105, 3415, 3760]
KNIGHT_DMG = [79, 86, 95, 105, 115, 126, 139, 152, 167, 184, 202, 221, 244, 267, 293, 323, 355,
              391, 430]


class LevelScalingTests(unittest.TestCase):
    def test_reproduces_game_arrays_from_the_level_1_base(self):
        for name, arr in (("archer hp", ARCHER), ("archer dmg", ARCHER_DMG),
                          ("knight hp", KNIGHT), ("knight dmg", KNIGHT_DMG)):
            got = [levels.at_level(arr[0], L) for L in range(1, len(arr) + 1)]
            self.assertEqual(got, arr, name)

    def test_is_not_the_ten_percent_rule(self):
        """The whole reason this module exists -- guard against a 'simplification' back to 1.1^n."""
        self.assertEqual(levels.PERCENT[11], 256)          # 1.1^10 would say 259
        self.assertEqual(levels.PERCENT[16], 409)          # 1.1^15 would say 418
        naive = ARCHER[10] * 1.1 ** 5
        self.assertGreater(abs(naive - ARCHER[15]), 3.0,
                           "1.1^n must visibly disagree at level 16, else this test proves nothing")
        self.assertEqual(levels.scale(ARCHER[10], 16), ARCHER[15])

    def test_scaling_from_our_level_11_reference_is_exact(self):
        for arr in (ARCHER, KNIGHT, ARCHER_DMG, KNIGHT_DMG):
            for L in range(1, 20):
                self.assertEqual(levels.scale(arr[10], L), arr[L - 1], "level %d" % L)

    def test_inversion_is_unique_or_absent(self):
        for arr in (ARCHER, KNIGHT, ARCHER_DMG, KNIGHT_DMG):
            self.assertEqual(levels.base_for(arr[10]), arr[0])
        # a value the game could not have produced must return None rather than a guess
        self.assertIsNone(levels.base_for(0))
        self.assertIsNone(levels.base_for(1766.5))

    def test_uninvertible_values_fall_back_to_the_ratio(self):
        got = levels.scale(1000.5, 13)                      # non-integer: no integer base exists
        self.assertAlmostEqual(got, 1000.5 * 309 / 256, places=6)

    def test_ref_level_is_identity(self):
        self.assertEqual(levels.scale(1766, 11), 1766.0)


class TowerScalingTests(unittest.TestCase):
    PRINCESS = [1400, 1512, 1624, 1750, 1890, 2030, 2184, 2352, 2534, 2786, 3052, 3346, 3668,
                4032, 4424, 4858]
    KING = [2400, 2568, 2736, 2904, 3096, 3312, 3528, 3768, 4008, 4392, 4824, 5304, 5832, 6408,
            7032, 7704]
    DMG = [50, 54, 58, 62, 67, 72, 78, 84, 90, 99, 109, 119, 131, 144, 158, 173]

    def test_published_tables_are_intact(self):
        self.assertEqual(list(levels.PRINCESS_HP[1:]), self.PRINCESS)
        self.assertEqual(list(levels.KING_HP[1:]), self.KING)
        self.assertEqual(list(levels.TOWER_DMG[1:]), self.DMG)

    def test_level_16_princess_is_present(self):
        """4858 was very nearly lost: the wiki writes that one row in a different cell format, and
        dropping it silently caps towers at level 15 and makes L16 enemies 9% too weak."""
        self.assertEqual(levels.PRINCESS_HP[16], 4858)

    def test_towers_scale_on_their_own_table_not_the_cards(self):
        for L in range(1, 17):
            self.assertAlmostEqual(levels.tower_scale(self.PRINCESS[14], L, 15),
                                   self.PRINCESS[L - 1], places=6, msg="princess L%d" % L)
            self.assertAlmostEqual(levels.tower_scale(self.KING[14], L, 15, king=True),
                                   self.KING[L - 1], places=6, msg="king L%d" % L)

    def test_king_and_princess_differ(self):
        self.assertNotAlmostEqual(levels.tower_scale(1.0, 11, 15),
                                  levels.tower_scale(1.0, 11, 15, king=True), places=4)

    def test_damage_is_shared_between_both_towers(self):
        for L in range(1, 17):
            self.assertAlmostEqual(levels.tower_scale(self.DMG[14], L, 15, damage=True),
                                   self.DMG[L - 1], places=6)
            self.assertAlmostEqual(levels.tower_scale(self.DMG[14], L, 15, king=True, damage=True),
                                   self.DMG[L - 1], places=6)

    def test_tower_table_is_not_the_card_table(self):
        self.assertNotAlmostEqual(levels.tower_scale(1.0, 1, 11), levels.ratio(1, 11), places=3)


if __name__ == "__main__":
    unittest.main()
