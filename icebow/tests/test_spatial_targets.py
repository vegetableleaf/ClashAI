"""Soft placement targets: partial credit for a neighbouring tile, zero for an illegal one.

Exact one-hot on a 432-cell grid calls a strategically identical neighbour completely wrong, and
the placement head has collapsed twice in this project while the headline win rate rose:

    champion (shared cell head)    row 13 = 78.7% of plays,  48/432 cells,  top cell 41%
    per-card head, fresh           row 13 = 41.2%,           62/432 cells,  top cell 20.5%
    per-card head, 19k matches     row 13 = 84.5%,           28/432 cells,  top cell 36.8%
"""
from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import torch  # noqa: E402

from clashrl import spatial_targets as st  # noqa: E402

GW, GH = 18, 24
G = GW * GH


def _legal(b=1, allow=None):
    m = torch.zeros(b, G, dtype=torch.bool)
    if allow is None:
        m[:] = True
    else:
        for c in allow:
            m[:, c] = True
    return m


class SoftTargetTests(unittest.TestCase):
    def test_sums_to_one_over_legal_cells(self):
        t = st.gaussian_spatial_target(torch.tensor([200]), _legal(), GW, GH, 1.0)
        self.assertAlmostEqual(float(t.sum()), 1.0, places=5)

    def test_illegal_cells_get_exactly_zero(self):
        cell = 200
        allow = [cell, cell + 1, cell - 1]
        t = st.gaussian_spatial_target(torch.tensor([cell]), _legal(allow=allow), GW, GH, 1.0)
        illegal = [i for i in range(G) if i not in allow]
        self.assertEqual(float(t[0, illegal].abs().sum()), 0.0)
        self.assertAlmostEqual(float(t.sum()), 1.0, places=5)

    def test_probability_decreases_with_distance(self):
        cell = 12 * GW + 9
        t = st.gaussian_spatial_target(torch.tensor([cell]), _legal(), GW, GH, 1.5)[0]
        self.assertGreater(float(t[cell]), float(t[cell + 1]))
        self.assertGreater(float(t[cell + 1]), float(t[cell + 3]))

    def test_the_demonstrated_cell_keeps_the_most_mass(self):
        cell = 300
        t = st.gaussian_spatial_target(torch.tensor([cell]), _legal(), GW, GH, 1.0)[0]
        self.assertEqual(int(t.argmax()), cell)

    def test_tiny_sigma_approaches_one_hot(self):
        cell = 250
        t = st.gaussian_spatial_target(torch.tensor([cell]), _legal(), GW, GH, 0.01)[0]
        self.assertAlmostEqual(float(t[cell]), 1.0, places=5)

    def test_per_sample_sigma_is_batched(self):
        cells = torch.tensor([200, 200])
        sig = torch.tensor([0.3, 3.0])
        t = st.gaussian_spatial_target(cells, _legal(2), GW, GH, sig)
        self.assertGreater(float(t[0, 200]), float(t[1, 200]),
                           "the tighter sigma must concentrate more mass on the target")

    def test_an_illegal_demonstrated_cell_raises(self):
        """Stale grid metadata, not a wide target. Smearing the mass over unrelated legal cells
        would teach a placement nobody demonstrated."""
        with self.assertRaises(ValueError):
            st.gaussian_spatial_target(torch.tensor([5]), _legal(allow=[400]), GW, GH, 0.5)

    def test_shape_errors_are_loud(self):
        with self.assertRaises(ValueError):
            st.gaussian_spatial_target(torch.tensor([1]), torch.zeros(G, dtype=torch.bool),
                                       GW, GH, 1.0)
        with self.assertRaises(ValueError):
            st.gaussian_spatial_target(torch.tensor([1]), _legal(), 7, 7, 1.0)


class SoftLossTests(unittest.TestCase):
    def test_loss_is_minimised_by_matching_logits(self):
        cell = 100
        tgt = st.gaussian_spatial_target(torch.tensor([cell]), _legal(), GW, GH, 1.0)
        good = torch.log(tgt.clamp_min(1e-9))
        bad = torch.zeros(1, G)
        self.assertLess(float(st.soft_cell_loss(good, tgt)), float(st.soft_cell_loss(bad, tgt)))

    def test_a_neighbour_beats_a_distant_cell(self):
        """The whole point: near-misses must cost less than being across the arena."""
        cell = 12 * GW + 9
        tgt = st.gaussian_spatial_target(torch.tensor([cell]), _legal(), GW, GH, 1.0)
        near, far = torch.full((1, G), -9.0), torch.full((1, G), -9.0)
        near[0, cell + 1] = 9.0
        far[0, cell + 200] = 9.0
        self.assertLess(float(st.soft_cell_loss(near, tgt)), float(st.soft_cell_loss(far, tgt)))


class ReportTests(unittest.TestCase):
    def test_within_one_credits_the_neighbourhood(self):
        r = st.placement_report([100, 101, 300], [100, 100, 100], GW)
        self.assertAlmostEqual(r["exact"], 1 / 3)
        self.assertAlmostEqual(r["within_1"], 2 / 3)

    def test_empty_input_is_safe(self):
        self.assertEqual(st.placement_report([], [], GW), {})


if __name__ == "__main__":
    unittest.main()
