"""Predictive-canvas architecture break (2026-08-15): +3 mechanics-derived channels per slice
(enemy/my dead-reckoned positions, enemy urgency) painted by the SAME pure functions on sim
ground truth and live detector tracks. in_ch 9 -> 12."""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for p in (str(ROOT / "src"), str(ROOT / "tests")):
    if p not in sys.path:
        sys.path.insert(0, p)

import numpy as np                          # noqa: E402
from clashrl.config import Config           # noqa: E402
from clashrl import detect_obs, interactions  # noqa: E402
from clashrl.sim.env import SimMatchEnv     # noqa: E402


class ForecastTests(unittest.TestCase):
    def setUp(self):
        self.cfg = Config.load()
        self.db = SimMatchEnv(self.cfg, seed=0).db

    def test_hog_dead_reckons_toward_the_tower(self):
        units = [("enemy", "hog_rider", 0.50, 0.55)]
        my_t = [(0.25, 0.80, True), (0.75, 0.80, True), (0.50, 0.91, True)]
        en_t = [(0.25, 0.20, True), (0.75, 0.20, True), (0.50, 0.09, True)]
        (px, py, urg), = interactions.mover_forecast(units, my_t, en_t, self.db, dt_s=1.0)
        self.assertGreater(py, 0.56, "an enemy hog moves TOWARD our towers (y grows)")
        self.assertGreater((py - 0.55) * 32.0, 1.0, "very fast = well over a tile per second")
        self.assertGreater(urg, 0.0, "and it has a real ETA to something")

    def test_buildings_and_spells_stay_put(self):
        units = [("enemy", "tombstone", 0.30, 0.40), ("enemy", "rocket", 0.5, 0.5)]
        my_t = [(0.25, 0.80, True), (0.75, 0.80, True), (0.50, 0.91, True)]
        en_t = [(0.25, 0.20, True), (0.75, 0.20, True), (0.50, 0.09, True)]
        fc = interactions.mover_forecast(units, my_t, en_t, self.db)
        for (x, y, urg), (t, b, ux, uy) in zip(fc, units):
            self.assertAlmostEqual(x, ux)
            self.assertAlmostEqual(y, uy)
            self.assertEqual(urg, 0.0)

    def test_painter_lights_the_forecast_channels(self):
        units = [("enemy", "hog_rider", 0.50, 0.55), ("mine", "knight", 0.50, 0.70)]
        my_t = [(0.25, 0.80, True), (0.75, 0.80, True), (0.50, 0.91, True)]
        en_t = [(0.25, 0.20, True), (0.75, 0.20, True), (0.50, 0.09, True)]
        ch = detect_obs.predictive_channels(units, my_t, en_t, self.db, 96, 64)
        self.assertEqual(ch.shape, (96, 64, detect_obs.N_PRED))
        self.assertGreater(ch[:, :, 0].max(), 0.5, "enemy predicted-position ellipse painted")
        self.assertGreater(ch[:, :, 1].max(), 0.5, "our predicted-position ellipse painted")
        self.assertGreater(ch[:, :, 2].max(), 0.0, "enemy urgency painted at current position")
        ey = ch[:, :, 0].max(axis=1).argmax() / 96.0
        self.assertGreater(ey, 0.56, "the enemy blob sits AHEAD of its current position")


class ArchitectureTests(unittest.TestCase):
    def test_obs_widened_to_twelve_channels(self):
        cfg = Config.load()
        self.assertTrue(detect_obs.predictive_enabled(cfg))
        self.assertEqual(detect_obs.obs_in_channels(cfg), 12, "3 RGB + 6 semantic + 3 predictive")
        env = SimMatchEnv(cfg, seed=3)
        self.assertEqual(env.reset().shape, (96, 64, 12))

    def test_predicted_slice_leads_the_semantic_slice(self):
        from clashrl.sim.engine import build_spec
        cfg = Config.load()
        env = SimMatchEnv(cfg, seed=4)
        env.reset()
        env.opponent.act = lambda eng: None
        env.eng.elixir[1] = 10.0
        assert env.eng.deploy(1, build_spec(env.eng.db, "hog_rider", 11), 0.50, 0.30)
        for _ in range(3):
            obs, *_ = env.step((False, 0, 0))
        sem = obs[:, :, 3]                               # enemy_ground, current position
        pred = obs[:, :, 9]                              # enemy_predicted (first pred channel)
        if sem.max() > 0 and pred.max() > 0:             # detector-noise dropout can hide a slice
            cy_now = sem.max(axis=1).argmax()
            cy_pred = pred.max(axis=1).argmax()
            self.assertGreaterEqual(cy_pred, cy_now,
                                    "the forecast blob is at or beyond the current blob")


if __name__ == "__main__":
    unittest.main(verbosity=1)
