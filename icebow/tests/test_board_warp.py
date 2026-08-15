"""Tower-anchored sim->live placement warp (2026-08-14): the screen renders the arena with
perspective, so the old single-affine arena_box tapped ~3-4 tiles deep across our half and the
detector canvas was off by the same. BoardWarp must hit every measured tower anchor exactly,
round-trip, and reduce to the identity in the sim."""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for p in (str(ROOT / "src"), str(ROOT / "tests")):
    if p not in sys.path:
        sys.path.insert(0, p)

from clashrl.config import Config
from clashrl.actions import ActionSpace


class BoardWarpTests(unittest.TestCase):
    def setUp(self):
        self.cfg = Config.load()
        self.space = ActionSpace(self.cfg)
        self.mt = self.cfg.get("env", "my_towers")
        self.et = self.cfg.get("env", "enemy_towers")

    def test_anchors_exact(self):
        w = self.space.warp
        self.assertTrue(w.ok, "measured tower anchors must be present")
        # my princess row: board 0.797 -> measured frame y
        fx, fy = w.board_to_frame(3.5 / 18.0, 1.0 - 6.5 / 32.0)
        self.assertAlmostEqual(fy, (self.mt[0][1] + self.mt[1][1]) / 2.0, delta=1e-6)
        self.assertAlmostEqual(fx, (self.mt[0][0] + self.et[0][0]) / 2.0, delta=1e-6)
        # my king: board 0.906 -> measured frame y
        _, fy = w.board_to_frame(0.5, 1.0 - 3.0 / 32.0)
        self.assertAlmostEqual(fy, self.mt[2][1], delta=1e-6)
        # enemy princess row
        _, fy = w.board_to_frame(3.5 / 18.0, 6.5 / 32.0)
        self.assertAlmostEqual(fy, (self.et[0][1] + self.et[1][1]) / 2.0, delta=1e-6)

    def test_old_affine_was_tiles_deep(self):
        # the regression this fixes: the plain arena_box affine put board 0.797 (my princess)
        # ~0.09 frame-y BELOW the measured princess -- 3-4 tiles of warp
        bx = self.cfg.get("action", "arena_box")
        old_fy = bx[1] + (1.0 - 6.5 / 32.0) * (bx[3] - bx[1])
        true_fy = (self.mt[0][1] + self.mt[1][1]) / 2.0
        self.assertGreater(old_fy - true_fy, 0.05, "the old mapping really was deep")
        _, new_fy = self.space.warp.board_to_frame(0.5, 1.0 - 6.5 / 32.0)
        self.assertLess(abs(new_fy - true_fy), 1e-6, "the warp lands ON the princess row")

    def test_round_trip(self):
        w = self.space.warp
        for bx_, by_ in ((0.2, 0.55), (0.5, 0.5), (0.8, 0.8), (0.3, 0.15)):
            fx, fy = w.board_to_frame(bx_, by_)
            rx, ry = w.frame_to_board(fx, fy)
            self.assertAlmostEqual(rx, bx_, delta=1e-6)
            self.assertAlmostEqual(ry, by_, delta=1e-6)

    def test_sim_warp_is_identity(self):
        from clashrl.sim.env import SimMatchEnv
        env = SimMatchEnv(self.cfg, seed=1)
        w = env.actions.warp
        for bx_, by_ in ((0.194, 0.797), (0.5, 0.906), (0.3, 0.4), (0.9, 0.6)):
            fx, fy = w.board_to_frame(bx_, by_)
            self.assertAlmostEqual(fx, bx_, delta=1e-6, msg="sim x must be identity")
            self.assertAlmostEqual(fy, by_, delta=1e-6, msg="sim y must be identity")

    def test_cell_center_uses_warp(self):
        # the grid row whose board centre sits on the princess row must tap the princess frame y
        gh, gw = self.space.gh, self.space.gw
        by_ = 1.0 - 6.5 / 32.0
        gy = int(by_ * gh)                          # row containing the princess band
        nx, ny = self.space.cell_center(gw // 2, gy)
        true_fy = (self.mt[0][1] + self.mt[1][1]) / 2.0
        self.assertLess(abs(ny - true_fy), 0.025, "tap lands within a tile of the true row")


class RgbWarpTests(unittest.TestCase):
    def test_live_rgb_is_board_true(self):
        import numpy as np
        from clashrl.vision import Vision
        cfg = Config.load()
        sp = ActionSpace(cfg)
        v = Vision(cfg)
        v.set_board_warp(sp.warp)
        frame = np.zeros((1000, 500, 3), np.uint8)
        mt = cfg.get("env", "my_towers")
        fy = int(((mt[0][1] + mt[1][1]) / 2.0) * 999)
        frame[fy - 4:fy + 5, :] = 255                 # thick band at the TRUE princess frame row
        obs = v.observe(frame)
        row = int(np.argmax(obs[:, :, 0].sum(axis=1)))
        self.assertLess(abs(row / obs.shape[0] - (1.0 - 6.5 / 32.0)), 0.03,
                        "the princess band must land at BOARD y 0.797 in the observation")

    def test_identity_warp_matches_center(self):
        import numpy as np
        from clashrl.vision import Vision
        from clashrl.sim.env import SimMatchEnv
        cfg = Config.load()
        env = SimMatchEnv(cfg, seed=2)
        v = Vision(cfg)
        v.set_board_warp(env.actions.warp)            # identity anchors
        frame = np.zeros((1000, 500, 3), np.uint8)
        frame[496:505, :] = 255
        obs = v.observe(frame)
        row = int(np.argmax(obs[:, :, 0].sum(axis=1)))
        self.assertLess(abs(row / obs.shape[0] - 0.5), 0.03)


if __name__ == "__main__":
    unittest.main(verbosity=1)
