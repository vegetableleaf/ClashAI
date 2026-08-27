"""Board-space deploy-row rule (2026-08-14): the mask/clamp must never permit a cell whose
WARPED tap lands on the river or the enemy side (measured live: 23/70 plays refused at row 11,
frame y=0.40, against a real river line of 0.410 -- the 'card shuffle' freeze)."""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for p in (str(ROOT / "src"), str(ROOT / "tests")):
    if p not in sys.path:
        sys.path.insert(0, p)

from clashrl.config import Config          # noqa: E402
from clashrl.actions import ActionSpace    # noqa: E402
from clashrl.sim.env import _board_action_space   # noqa: E402


class DeployRowTests(unittest.TestCase):
    def setUp(self):
        self.cfg = Config.load()
        self.live = ActionSpace(self.cfg)
        self.sim = _board_action_space(self.cfg)

    def test_first_legal_row_clears_the_water_band(self):
        gw = int(self.live.gw)
        legal_rows = sorted({c // gw for c, ok in enumerate(self.live.deployable_mask(False)) if ok})
        self.assertGreaterEqual(legal_rows[0], 13, "rows 11-12 tap the river/enemy side (refused)")

    def test_every_legal_tap_lands_below_the_real_river(self):
        gw = int(self.live.gw)
        river_ny = self.live.warp.board_to_frame(0.5, 0.5)[1]
        for c, ok in enumerate(self.live.deployable_mask(False)):
            if not ok:
                continue
            _, ny = self.live.cell_center(c % gw, c // gw)
            self.assertGreater(ny, river_ny + 0.02,
                               "legal cell %d taps at %.3f, on/above the river (%.3f)" % (c, ny, river_ny))

    def test_clamp_pulls_enemy_cells_to_a_deployable_row(self):
        gw = int(self.live.gw)
        cell = self.live.deploy_clamp(False, 5 * gw + 9)          # deep enemy-half pick
        self.assertGreaterEqual(cell // gw, 13, "clamp must land on a row the game accepts")

    def test_sim_and_live_agree_on_the_row_set(self):
        self.assertEqual(self.live.min_own_gy, self.sim.min_own_gy,
                         "board-space rule: one river, one row set, two referees")
        self.assertEqual(self.live.deployable_mask(False).index(True),
                         self.sim.deployable_mask(False).index(True))


class RiverLedgeTests(unittest.TestCase):
    """The field is not a rectangle (user-verified): the outermost SINGLE column at the river
    rows is decorative ledge, each back row is playable only in the 1x6 strip behind its king,
    and the king platforms are structures -- excluded everywhere, sim and live alike."""

    def setUp(self):
        self.cfg = Config.load()
        self.live = ActionSpace(self.cfg)

    def test_ledge_cells_are_masked_one_column_deep(self):
        gw = int(self.live.gw)
        m = self.live.deployable_mask(False)
        for gx in (0, gw - 1):
            self.assertFalse(m[13 * gw + gx], "ledge cell (%d, 13) must be unplaceable" % gx)
        self.assertTrue(m[13 * gw + 1], "the pocket is ONE tile deep: column 1 is real floor")

    def test_back_row_is_the_king_strip_only(self):
        gw, gh = int(self.live.gw), int(self.live.gh)
        m = self.live.deployable_mask(False)
        for gx in (6, 8, 11):
            self.assertTrue(m[(gh - 1) * gw + gx], "behind-the-king strip cell (%d) is real" % gx)
        for gx in (0, 3, 5, 12, 14, 17):
            self.assertFalse(m[(gh - 1) * gw + gx], "back-row corner (%d) is walkway decor" % gx)

    def test_king_platform_blocked_but_row_behind_open(self):
        gw = int(self.live.gw)
        m = self.live.deployable_mask(False)
        self.assertFalse(m[22 * gw + 8], "row 22 center is ON your king's platform")
        self.assertFalse(m[21 * gw + 8], "row 21 center is ON your king's platform")
        self.assertTrue(m[20 * gw + 8], "the row in FRONT of the platform is placeable")
        self.assertTrue(m[22 * gw + 3], "BESIDE the platform is placeable")

    def test_clamp_snaps_off_the_ledge(self):
        gw = int(self.live.gw)
        cell = self.live.deploy_clamp(False, 13 * gw + 0)
        self.assertEqual(cell // gw, 13)
        self.assertEqual(cell % gw, 1, "clamp moves a ledge pick one column in, onto real floor")

    def test_engine_snaps_scripted_deploys_inward(self):
        from clashrl.sim.env import SimMatchEnv
        from clashrl.sim.engine import build_spec
        env = SimMatchEnv(self.cfg, seed=7)
        env.reset()
        env.eng.elixir[1] = 10.0
        assert env.eng.deploy(1, build_spec(env.eng.db, "knight", 11), 0.03, 0.5)
        foe = [u for u in env.eng.units if u.team == 1][-1]
        self.assertGreater(foe.x, 1.0 / 18.0, "an opponent's ledge deploy lands on real tiles")

    def test_engine_snaps_back_corner_and_platform(self):
        from clashrl.sim.env import SimMatchEnv
        from clashrl.sim.engine import build_spec
        env = SimMatchEnv(self.cfg, seed=8)
        env.reset()
        env.eng.elixir[0] = 10.0
        assert env.eng.deploy(0, build_spec(env.eng.db, "knight", 11), 0.05, 0.99)
        corner = [u for u in env.eng.units if u.team == 0][-1]
        self.assertLess(corner.y, 31.0 / 32.0, "a back-row CORNER deploy pulls forward")
        assert env.eng.deploy(0, build_spec(env.eng.db, "knight", 11), 0.5, 0.9)
        plat = [u for u in env.eng.units if u.team == 0][-1]
        self.assertLess(plat.y, 1.0 - 4.0 / 32.0, "a king-PLATFORM deploy lands in front of it")
        assert env.eng.deploy(0, build_spec(env.eng.db, "knight", 11), 0.5, 0.99)
        behind = [u for u in env.eng.units if u.team == 0][-1]
        self.assertGreater(behind.y, 31.0 / 32.0, "BEHIND the king (center strip) is legal, untouched")

    def test_warp_anchors_stay_monotonic(self):
        for anchors in (self.live.warp.ya, self.live.warp.xa):
            for (a0, b0), (a1, b1) in zip(anchors, anchors[1:]):
                self.assertLess(a0, a1)
                self.assertLess(b0, b1, "frame values must rise with board values")


if __name__ == "__main__":
    unittest.main(verbosity=1)


class KingKeepOutTests(unittest.TestCase):
    """A spell must not be able to select the enemy KING tower.

    Waking their king early is not a bad play to be priced -- it is a self-inflicted penalty that
    hands the opponent a third defensive tower for the rest of the match. The sim already charged
    it as a misplace, but live exploration picked uniformly over every cell, so raising epsilon
    put a rocket on the king within minutes (user, 2026-08-16). A reward cannot restrain a random
    choice; only a mask can.
    """

    def setUp(self):
        from clashrl.config import Config
        from clashrl.actions import ActionSpace
        self.acts = ActionSpace(Config.load())

    # ⚠ UNITS. `king_xy` is BOARD-space (it is `sim.board.king_tile` over the tile counts) while
    # `cell_center` returns FRAME coordinates here -- so every comparison has to go through
    # `warp.frame_to_board` first. Both tests below USED TO OMIT THAT, in exactly the same way
    # `no_king_mask` itself did, which is why they passed against a mask that was blocking 12 cells
    # where the sim blocked 22 and leaving ten cells 1.54-2.69 true tiles from the king selectable.
    # A test written in the same wrong units as its subject can never catch the subject's bug.
    # conflicts.md RS-4, third sighting.
    def _board(self, c):
        return self.acts.warp.frame_to_board(
            *self.acts.cell_center(c % self.acts.gw, c // self.acts.gw))

    def test_king_cell_is_not_selectable_by_anywhere_cards(self):
        m = self.acts.deployable_mask(True)
        gx, gy = self.acts.coords_to_grid(*self.acts.warp.board_to_frame(*self.acts.king_xy))
        self.assertFalse(m[gy * self.acts.gw + gx], "their king's own cell must be masked out")

    def test_keep_out_has_real_clearance(self):
        import math
        m = self.acts.deployable_mask(True)
        tx, ty = self.acts.king_tiles
        kx, ky = self.acts.king_xy
        closest = min(math.hypot((self._board(c)[0] - kx) * tx, (self._board(c)[1] - ky) * ty)
                      for c in range(self.acts.gw * self.acts.gh) if m[c])
        self.assertGreaterEqual(closest, self.acts.king_clear,
                                "every legal cell must clear the king by the configured margin")

    def test_the_keep_out_is_small(self):
        """It must cost a handful of cells, not a region -- the enemy half is still rocket country."""
        m = self.acts.deployable_mask(True)
        blocked = len(m) - sum(m)
        self.assertGreater(blocked, 0)
        self.assertLess(blocked, 0.10 * len(m), "keep-out should be a few percent of the board")

    def test_your_half_mask_is_unaffected(self):
        own = self.acts.deployable_mask(False)
        self.assertGreater(sum(own), 0, "troop placement must be untouched by the king keep-out")
