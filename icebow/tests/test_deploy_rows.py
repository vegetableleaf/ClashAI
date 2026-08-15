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


if __name__ == "__main__":
    unittest.main(verbosity=1)
