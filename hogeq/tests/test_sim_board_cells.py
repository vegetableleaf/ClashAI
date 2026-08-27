"""THE SIM'S ACTION SPACE MUST ADDRESS THE SIM'S BOARD (measured 2026-08-27, both decks).

`sim/env.py::_board_action_space` rebuilds `ActionSpace` with board-true overrides, but three of
the config values it did NOT override are LIVE-SCREEN safety constants that `cell_center` applies
to whatever space it is in:

    label.arena_top / label.arena_bottom   keep a TAP off the card tray
    buttons.chat_avoid_box                 keeps a TAP off the emote icon

Applied to BOARD coordinates they clamped the sim's own 432-cell action space. MEASURED before the
fix, identically in icebow and hogeq:

    96 of 432 cells (22.2%) deployed somewhere other than their own board centre, worst 6.37 tiles
    only 372 DISTINCT deploy points existed -> 60 cells were exact duplicates of another cell
    board tile-y outside 3.20 .. 27.52 was UNREACHABLE (the arena is 0 .. 32)
    -> all 36 cells of grid rows 0-1 sat within 0.2 tiles of the ENEMY KING's row (tile-y 3.0)

And the clamps were inert where they belong: in the LIVE ActionSpace all three fire on 0 of 432
cells, because the warped grid already lands inside them. This is the mirror image of the section
4.2 trap -- a live-screen constant applied to the board, rather than an offline tool reading live
coordinates.
"""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for p in (str(ROOT / "src"), str(ROOT / "tests")):
    if p not in sys.path:
        sys.path.insert(0, p)

from clashrl.config import Config                  # noqa: E402
from clashrl.actions import ActionSpace            # noqa: E402
from clashrl.sim.env import _board_action_space    # noqa: E402

TILES_X, TILES_Y = 18.0, 32.0


class SimBoardCellTests(unittest.TestCase):
    def setUp(self):
        self.cfg = Config.load()
        self.sim = _board_action_space(self.cfg)
        self.gw, self.gh = int(self.sim.gw), int(self.sim.gh)

    def test_every_cell_deploys_at_its_own_board_centre(self):
        """96 cells were displaced, one of them by 6.37 tiles."""
        bad = []
        for gy in range(self.gh):
            for gx in range(self.gw):
                want = ((gx + 0.5) / self.gw, (gy + 0.5) / self.gh)
                got = self.sim.cell_center(gx, gy)
                if abs(got[0] - want[0]) > 1e-9 or abs(got[1] - want[1]) > 1e-9:
                    bad.append((gx, gy, want, got))
        self.assertEqual([], bad[:5], f"{len(bad)} cells do not deploy at their own centre")

    def test_all_432_deploy_points_are_distinct(self):
        """60 cells were exact duplicates -- five grid rows all deploying to tile (0.50, 24.96).
        The cell head cannot learn to distinguish actions that are literally the same action."""
        pts = {self.sim.cell_center(c % self.gw, c // self.gw) for c in range(self.gw * self.gh)}
        self.assertEqual(self.gw * self.gh, len(pts),
                         f"only {len(pts)} distinct deploy points for {self.gw * self.gh} cells")

    def test_the_whole_arena_is_reachable(self):
        """The back 3.2 tiles of the enemy end and the back 4.5 of ours were unreachable."""
        ys = [self.sim.cell_center(self.gw // 2, gy)[1] * TILES_Y for gy in range(self.gh)]
        self.assertLess(min(ys), 1.0, "the enemy back row must be reachable")
        self.assertGreater(max(ys), TILES_Y - 1.0, "our own back row must be reachable")

    def test_grid_rows_0_and_1_are_not_both_on_the_enemy_king(self):
        """Both rows clamped to board tile-y 3.20 and the enemy king sits at tile-y 3.0, so 36 of
        432 cells landed on it -- and the trainer masks NONE of them (`allcells_mask` is all-ones)."""
        y0 = self.sim.cell_center(9, 0)[1] * TILES_Y
        y1 = self.sim.cell_center(9, 1)[1] * TILES_Y
        self.assertNotAlmostEqual(y0, y1, places=6, msg="rows 0 and 1 deploy to the same point")
        self.assertLess(y0, 2.0, "row 0 is the enemy back row, not the king's row")

    def test_the_live_space_is_UNTOUCHED_by_this_fix(self):
        """The three clamps are correct and necessary in LIVE. They must keep firing there -- and
        they must keep firing on nothing, which is what they already did."""
        live = ActionSpace(self.cfg)
        for gy in range(self.gh):
            for gx in range(self.gw):
                raw = live.warp.board_to_frame((gx + 0.5) / self.gw, (gy + 0.5) / self.gh)
                self.assertGreaterEqual(raw[1], live.a_top)
                self.assertLessEqual(raw[1], live.a_bot)
        self.assertIsNotNone(live.chat_box, "live must keep its emote-icon keep-out")
        self.assertEqual(0.1, live.a_top)
        self.assertEqual(0.86, live.a_bot)


if __name__ == "__main__":
    unittest.main()
