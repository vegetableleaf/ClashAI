"""Offline test for ``pipeline.engine_play``: the cell -> engine (x, y) inverse round-trips through
``obs_contract._engine_xy`` on both sides. No engine, no torch model."""
import unittest

import numpy as np

from pipeline import engine_play as ep
from pipeline.model_v3 import GRID_X, GRID_Y, N_CELLS, cell_index
from pipeline.obs_contract import _engine_xy


class TestCellEngineInverse(unittest.TestCase):
    def test_board_to_engine_round_trip(self):
        rng = np.random.default_rng(0)
        pts = rng.uniform(0.0, 1.0, size=(2000, 2))
        for mirror in (False, True):
            worst = 0.0
            for x, y in pts:
                X, Y = ep.board_to_engine(float(x), float(y), mirror)
                x2, y2 = _engine_xy(X, Y, mirror)
                worst = max(worst, abs(x2 - x), abs(y2 - y))
            self.assertLess(worst, 1e-6, f"mirror={mirror}")

    def test_engine_round_trip(self):
        """engine -> board -> engine on the corners and a grid of engine points."""
        for mirror in (False, True):
            for X in np.linspace(0, 18000, 19):
                for Y in np.linspace(0, 32000, 33):
                    x, y = _engine_xy(float(X), float(Y), mirror)
                    X2, Y2 = ep.board_to_engine(x, y, mirror)
                    self.assertLess(max(abs(X2 - X), abs(Y2 - Y)), 1e-6 * 32000)

    def test_cell_center_maps_back_to_its_cell(self):
        import torch
        cells = np.arange(N_CELLS)
        xy = torch.tensor([ep.cell_center(int(c)) for c in cells], dtype=torch.float32)
        self.assertTrue(bool((cell_index(xy).numpy() == cells).all()))
        for mirror in (False, True):
            for c in (0, GRID_X - 1, N_CELLS - GRID_X, N_CELLS - 1, 1234):
                X, Y = ep.cell_to_engine(c, mirror)
                self.assertTrue(0 <= X <= 18000 and 0 <= Y <= 32000)
                x, y = _engine_xy(X, Y, mirror)
                self.assertEqual(int(cell_index(torch.tensor([[x, y]]))[0]), c)


if __name__ == "__main__":
    unittest.main()
