"""L67w P1 (HANDOFF 5cs.99 AB / AC): the tap path never taps a greyed / empty tray slot or a card read in two slots.

run12: 31% of student taps dropped no elixir -- a greyed X-Bow read as ice_wizard was tapped as an affordable card, and
8.6% of decisions read one card in two slots. `badge_pink` reads the game's own affordability signal (the cost badge
is pink when playable, grey when not, absent on an empty slot); `tap_tray` removes the unusable slots.
"""
from __future__ import annotations

import os
import sys
import unittest

import cv2
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from clashrl.student_live import BADGE_BOX, MIN_BADGE_PINK, badge_pink, tap_tray   # noqa: E402

SLOTS = [[0.305, 0.890], [0.499, 0.886], [0.680, 0.891], [0.870, 0.888]]
KEYS = ["tornado", "tesla_evo", "ice_wizard", "x_bow", "rocket", "knight_evo", "the_log", "skeletons", "knight"]
H, W = 1198, 657


def _frame(badges):
    """A blue tray with each slot's badge box painted: 'pink', 'grey', or None (empty slot)."""
    fr = np.zeros((H, W, 3), np.uint8)
    fr[:] = (160, 80, 20)                                                # BGR blue background
    dx, dy0, dy1 = BADGE_BOX
    for (cx, cy), kind in zip(SLOTS, badges):
        x0, x1, y0, y1 = int((cx - dx) * W), int((cx + dx) * W), int((cy + dy0) * H), int((cy + dy1) * H)
        if kind == "pink":
            fr[y0:y1, x0:x1] = (200, 40, 220)                            # BGR magenta/pink cost drop
            fr[y0 + 5:y0 + 12, x0 + 8:x0 + 14] = (255, 255, 255)         # the white cost digit
        elif kind == "grey":
            fr[y0:y1, x0:x1] = (130, 130, 130)
    return fr


class BadgePink(unittest.TestCase):
    def test_pink_grey_and_empty_badges_separate(self):
        p = badge_pink(_frame(["pink", "grey", None, "pink"]), SLOTS)
        self.assertGreater(p[0], 0.5)
        self.assertGreater(p[3], 0.5)
        self.assertLess(p[1], MIN_BADGE_PINK)
        self.assertLess(p[2], MIN_BADGE_PINK)                            # the blue empty placeholder is not pink

    def test_bgra_frames_work(self):
        fr = cv2.cvtColor(_frame(["pink", "grey", "pink", None]), cv2.COLOR_BGR2BGRA)
        p = badge_pink(fr, SLOTS)
        self.assertEqual([x > MIN_BADGE_PINK for x in p], [True, False, True, False])


class TapTray(unittest.TestCase):
    def test_a_card_read_in_two_slots_is_refused_in_both(self):
        ids, why = tap_tray([2, 4, 3, 2], KEYS)
        self.assertEqual(ids, [-1, 4, 3, -1])
        self.assertEqual(why, ["double", "ok", "ok", "double"])

    def test_evo_and_base_reads_count_as_the_same_card(self):
        ids, why = tap_tray([5, 0, 8, 6], KEYS)                          # knight_evo and knight
        self.assertEqual(ids, [-1, 0, -1, 6])

    def test_greyed_or_empty_slots_are_refused(self):
        ids, why = tap_tray([0, 3, 2, 6], KEYS, pink=[0.2, 0.0, 0.004, 0.15])
        self.assertEqual(ids, [0, -1, -1, 6])
        self.assertEqual(why, ["ok", "grey", "grey", "ok"])

    def test_the_run12_case_greyed_xbow_read_as_ice_wizard(self):
        # tray really [tornado, rocket (grey), knight_evo, x_bow (grey)]; the reader said [tornado, rocket, ?, ice_wizard]
        ids, why = tap_tray([0, 4, -1, 2], KEYS, pink=[0.18, 0.0, 0.17, 0.0])
        self.assertEqual(ids, [0, -1, -1, -1])
        self.assertEqual(why, ["ok", "grey", "unread", "grey"])

    def test_min_pink_none_keeps_greyed_slots_but_still_refuses_doubles(self):
        ids, _ = tap_tray([2, 3, 2, 6], KEYS, pink=[0.0, 0.0, 0.0, 0.0], min_pink=None)
        self.assertEqual(ids, [-1, 3, -1, 6])

    def test_no_pink_reading_means_no_grey_filter(self):
        ids, _ = tap_tray([0, 3, 2, 6], KEYS, pink=None)
        self.assertEqual(ids, [0, 3, 2, 6])


if __name__ == "__main__":
    unittest.main()
