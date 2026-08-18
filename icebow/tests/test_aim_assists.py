"""Aiming: the grid round-trip, the Log's corridor, and the Tornado king pull.

Three user reports that turned out to share a root cause and a gap:

    "the model doesn't really know how to aim log, rocket, or tornado ... it seems to play them in
     really off locations in live training"
    "log should be played so that the target is directly in front of it, and not to the side"
    "i haven't seen it attempt a king activation pull at all yet"
    "model seems to be collapsing towards the front row again"

THE ROUND TRIP WAS BROKEN. ``cell_center`` maps grid -> frame through the perspective warp, but
``coords_to_grid`` rescaled the arena box LINEARLY, so the two were only inverses when the warp was
off. Measured live with it on: wrong on 22 of 24 rows, up to 3 rows out, ALWAYS toward the enemy
end. That direction matters, because the reverse mapping is what the labeller uses to turn a
recorded human tap into a training cell, and what every aim assist uses to turn a computed target
point into a cell. A demonstration tapped at y=0.600 was stored as the cell that taps at 0.527 --
teaching the policy to play two rows further forward than the human did.

AND TWO CARDS HAD NO ASSIST AT ALL. The rocket, the X-Bow and the Tesla each had one; the Log and
the Tornado had none, which is why the Log kept landing beside its target and the king-activation
pull never appeared.
"""
from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from clashrl.actions import ActionSpace                                  # noqa: E402
from clashrl.config import Config                                        # noqa: E402
from clashrl.reward import _anchors, log_corridor_cell, nado_king_cell   # noqa: E402


class GridRoundTripTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cfg = Config.load()
        cls.acts = ActionSpace(cls.cfg)

    def test_every_cell_survives_the_round_trip(self):
        """cell -> tap point -> cell must be the identity, or the labeller stores the wrong cell
        for a tap and every aim assist lands somewhere other than where it aimed."""
        a = self.acts
        wrong = []
        for gy in range(a.gh):
            for gx in range(a.gw):
                nx, ny = a.cell_center(gx, gy)
                back = a.coords_to_grid(nx, ny)
                if back != (gx, gy):
                    wrong.append(((gx, gy), back))
        self.assertEqual([], wrong[:12], "%d cells do not round-trip" % len(wrong))

    def test_the_row_mapping_is_exact_down_the_centre(self):
        a = self.acts
        for gy in range(a.gh):
            nx, ny = a.cell_center(9, gy)
            self.assertEqual(gy, a.coords_to_grid(nx, ny)[1], "row %d" % gy)

    def test_it_goes_through_the_warp_when_one_is_active(self):
        """The specific defect: a linear rescale against a warped forward map."""
        a = self.acts
        if not getattr(a.warp, "ok", False):
            self.skipTest("no perspective warp configured")
        nx, ny = a.cell_center(9, 18)
        linear_fy = (ny - a.by0) / (a.by1 - a.by0)
        linear_row = min(a.gh - 1, max(0, int(linear_fy * a.gh)))
        self.assertEqual(18, a.coords_to_grid(nx, ny)[1])
        self.assertNotEqual(linear_row, 18, "warp is active but the linear map already agreed")


class LogCorridorTests(unittest.TestCase):
    """The Log is a corridor, not a blast: a cast a tile to the side does nothing at all."""

    @classmethod
    def setUpClass(cls):
        cls.acts = ActionSpace(Config.load())

    def _xy(self, cell):
        a = self.acts
        return a.cell_center(cell % a.gw, cell // a.gw)

    def _aim(self, x, y):
        a = self.acts
        c = a.cell_at(x, y)
        return a.cell_center(c % a.gw, c // a.gw)

    def test_it_lines_the_corridor_up_with_the_push(self):
        push = [(0.30, 0.50, 0.0, 0.02, "knight"), (0.31, 0.52, 0.0, 0.02, "skeletons")]
        cx, cy = self._aim(0.42, 0.52)                       # policy aimed well to the side
        got = log_corridor_cell(cx, cy, push, self.acts)
        self.assertIsNotNone(got)
        self.assertLess(abs(self._xy(got)[0] - 0.305), 0.064,
                        "the push is still outside the corridor")

    def test_it_actually_moves_the_aim(self):
        push = [(0.30, 0.50, 0.0, 0.02, "knight"), (0.31, 0.52, 0.0, 0.02, "skeletons")]
        cx, cy = self._aim(0.42, 0.52)
        self.assertGreater(abs(self._xy(log_corridor_cell(cx, cy, push, self.acts))[0] - cx), 0.05)

    def test_an_already_aligned_cast_is_left_close_to_where_it_was(self):
        push = [(0.30, 0.50, 0.0, 0.02, "knight")]
        cx, cy = self._aim(0.30, 0.52)
        got = log_corridor_cell(cx, cy, push, self.acts)
        self.assertLess(abs(self._xy(got)[0] - cx), 0.064)

    def test_it_refuses_to_aim_at_flyers(self):
        """The Log rolls underneath them -- aiming there wastes the card entirely."""
        cx, cy = self._aim(0.42, 0.52)
        self.assertIsNone(log_corridor_cell(cx, cy, [(0.30, 0.50, 0.0, 0.02, "minions")],
                                            self.acts, air={"minions"}))

    def test_a_mixed_push_still_aims_at_the_ground_half(self):
        tracks = [(0.30, 0.50, 0.0, 0.02, "knight"), (0.60, 0.50, 0.0, 0.02, "minions")]
        got = log_corridor_cell(*self._aim(0.45, 0.52), tracks, self.acts, air={"minions"})
        self.assertIsNotNone(got)
        self.assertLess(abs(self._xy(got)[0] - 0.30), 0.064)

    def test_an_empty_board_leaves_the_aim_alone(self):
        self.assertIsNone(log_corridor_cell(*self._aim(0.42, 0.52), [], self.acts))

    def test_a_push_nowhere_near_the_aim_is_ignored(self):
        far = [(0.05, 0.20, 0.0, 0.0, "knight")]
        self.assertIsNone(log_corridor_cell(*self._aim(0.90, 0.60), far, self.acts))


class NadoKingTests(unittest.TestCase):
    """The king-activation pull: drag an attacker into our sleeping king so it wakes up."""

    @classmethod
    def setUpClass(cls):
        cls.cfg = Config.load()
        cls.acts = ActionSpace(cls.cfg)
        cls.mine, _, _ = _anchors(cls.cfg)

    def _xy(self, cell):
        a = self.acts
        return a.cell_center(cell % a.gw, cell // a.gw)

    def test_a_deep_attacker_gets_a_cast(self):
        got = nado_king_cell([(0.42, 0.66, 0.0, 0.02)], self.mine, self.acts)
        self.assertIsNotNone(got, "no king-activation cast offered for a deep attacker")

    def test_the_cast_sits_in_FRONT_of_our_king(self):
        kx, ky = self.mine[2]
        x, y = self._xy(nado_king_cell([(0.42, 0.66, 0.0, 0.02)], self.mine, self.acts))
        self.assertLess(y, ky, "the pull point must be on the arena side of the king")
        self.assertLess(abs(x - kx), 0.10, "and close to the king's column")

    def test_the_two_lanes_mirror_each_other(self):
        """The arena is symmetric, so an asymmetric rule is a bug in the rule."""
        kx = self.mine[2][0]
        lx, ly = self._xy(nado_king_cell([(0.42, 0.66, 0.0, 0.02)], self.mine, self.acts))
        rx, ry = self._xy(nado_king_cell([(0.56, 0.66, 0.0, 0.02)], self.mine, self.acts))
        self.assertAlmostEqual(ly, ry, places=6)
        self.assertAlmostEqual(kx - lx, rx - kx, delta=0.02)

    def test_an_attacker_up_the_field_gets_nothing(self):
        """Waking the king early is a cost, not a bonus -- the window has to be real."""
        self.assertIsNone(nado_king_cell([(0.30, 0.30, 0.0, 0.0)], self.mine, self.acts))

    def test_an_empty_board_gets_nothing(self):
        self.assertIsNone(nado_king_cell([], self.mine, self.acts))

    def test_missing_anchors_are_handled(self):
        self.assertIsNone(nado_king_cell([(0.42, 0.66, 0.0, 0.02)], [], self.acts))


if __name__ == "__main__":
    unittest.main()
