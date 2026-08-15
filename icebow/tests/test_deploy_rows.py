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
    """The field is not a rectangle: the outer ~2 columns at the river rows are decorative
    ledges (heart tiles) the game refuses -- excluded everywhere, sim and live alike."""

    def setUp(self):
        self.cfg = Config.load()
        self.live = ActionSpace(self.cfg)

    def test_ledge_cells_are_masked(self):
        gw = int(self.live.gw)
        m = self.live.deployable_mask(False)
        for gx in (0, 1, gw - 2, gw - 1):
            self.assertFalse(m[13 * gw + gx], "ledge cell (%d, 13) must be unplaceable" % gx)
        self.assertTrue(m[13 * gw + 2], "the first real tile past the ledge stays placeable")

    def test_clamp_snaps_off_the_ledge(self):
        gw = int(self.live.gw)
        cell = self.live.deploy_clamp(False, 13 * gw + 0)
        self.assertEqual(cell // gw, 13)
        self.assertGreaterEqual(cell % gw, 2, "clamp must move a ledge pick onto real tiles")

    def test_engine_snaps_scripted_deploys_inward(self):
        from clashrl.sim.env import SimMatchEnv
        from clashrl.sim.engine import build_spec
        env = SimMatchEnv(self.cfg, seed=7)
        env.reset()
        env.eng.elixir[1] = 10.0
        assert env.eng.deploy(1, build_spec(env.eng.db, "knight", 11), 0.03, 0.5)
        foe = [u for u in env.eng.units if u.team == 1][-1]
        self.assertGreater(foe.x, 2.0 / 18.0, "an opponent's ledge deploy lands on real tiles")

    def test_warp_anchors_stay_monotonic(self):
        for anchors in (self.live.warp.ya, self.live.warp.xa):
            for (a0, b0), (a1, b1) in zip(anchors, anchors[1:]):
                self.assertLess(a0, a1)
                self.assertLess(b0, b1, "frame values must rise with board values")


if __name__ == "__main__":
    unittest.main(verbosity=1)
