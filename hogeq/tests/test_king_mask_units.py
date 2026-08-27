"""THE ENEMY-KING KEEP-OUT WAS COMPARING FRAME COORDINATES TO A BOARD ANCHOR (measured 2026-08-27).

`ActionSpace.no_king_mask` builds `king_xy` from `sim.board.king_tile` -- a BOARD coordinate,
unconditionally -- and compares it against `cell_center`, which returns FRAME coordinates in the
LIVE space (it runs `warp.board_to_frame` to produce a tap point). This is conflicts.md RS-4's
units trap in shipped code rather than in a probe: "never compare a live `cell_center` output
against a board-space threshold without `warp.frame_to_board` first".

MEASURED BEFORE THE FIX, both decks:
    live ActionSpace blocked 12 of 432 cells; the sim's board ActionSpace blocked 22
    the TEN extra cells sit 1.54 - 2.69 TRUE tiles from the enemy king, inside the 2.6-tile
    clearance the mask exists to enforce, and four of them are inside a Rocket's own 2.0-tile blast
So live could select a rocket cell that lands on the enemy king -- waking it, which is the exact
self-inflicted penalty the mask was written to make impossible (user, 2026-08-16: "a rocket landed
on the king within minutes of raising epsilon. A reward cannot stop a random choice; only a mask
can.").
"""
import math
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


class KingMaskUnitTests(unittest.TestCase):
    def setUp(self):
        self.cfg = Config.load()
        self.live = ActionSpace(self.cfg)
        self.sim = _board_action_space(self.cfg)
        self.gw, self.gh = int(self.live.gw), int(self.live.gh)

    def _board_dist(self, space, c):
        cx, cy = space.cell_center(c % self.gw, c // self.gw)
        bx, by = space.warp.frame_to_board(cx, cy)
        kx, ky = space.king_xy
        tx, ty = space.king_tiles
        return math.hypot((bx - kx) * tx, (by - ky) * ty)

    def test_live_and_sim_mask_the_SAME_cells(self):
        """The keep-out is a property of the BOARD, so the two spaces must agree exactly."""
        lm, bm = self.live.no_king_mask(), self.sim.no_king_mask()
        diff = [c for c in range(self.gw * self.gh) if lm[c] != bm[c]]
        self.assertEqual([], diff,
                         f"{len(diff)} cells differ between the live and sim king masks")

    def test_no_SELECTABLE_cell_is_inside_the_clearance(self):
        """The live mask left ten cells 1.54-2.69 true tiles from the king selectable."""
        clear = float(self.live.king_clear)
        bad = [c for c, ok in enumerate(self.live.no_king_mask())
               if ok and self._board_dist(self.live, c) <= clear]
        self.assertEqual([], bad,
                         f"{len(bad)} selectable cells are within {clear} tiles of the enemy king")

    def test_every_MASKED_cell_really_is_inside_the_clearance(self):
        """...and the mask must not go the other way and cost cells it has no claim on."""
        clear = float(self.live.king_clear)
        bad = [c for c, ok in enumerate(self.live.no_king_mask())
               if not ok and self._board_dist(self.live, c) > clear]
        self.assertEqual([], bad, f"{len(bad)} cells masked that are outside the clearance")

    def test_the_mask_still_costs_only_a_handful_of_cells(self):
        """A keep-out that eats the board would delete the enemy-half rocket. 22 of 432 = 5.1%."""
        blocked = self.gw * self.gh - sum(self.live.no_king_mask())
        self.assertGreater(blocked, 12, "the pre-fix live mask blocked only 12")
        self.assertLess(blocked, 40, f"the keep-out must stay small; it blocks {blocked}")


if __name__ == "__main__":
    unittest.main()
