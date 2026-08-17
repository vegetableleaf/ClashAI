"""Tests for the obs-canvas flip (observation.use_detector_canvas).

The canvas is the ONE observation block that exists twice: the sim renders it from ground truth
(sim/view.semantic_channels) and live play renders it from detections (detect_obs.detection_channels).
If the two disagree about which channel a role lands in, the sim prior trains one layout and the bot
plays another -- silently, because both are just float maps. These tests pin the layout contract and
the mirroring, which is exactly how the self-play mirror has drifted before.
"""
from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from clashrl import detect_obs
from clashrl.sim import view
from clashrl.sim.engine import Unit, build_spec

try:                                     # discovered as a package (python -m unittest discover)
    from .test_sim_status_effects import _make_engine
except ImportError:                      # ...or run as a plain script
    from test_sim_status_effects import _make_engine


class ObsCanvasLayoutTests(unittest.TestCase):
    def test_sim_and_live_agree_on_channel_count(self):
        self.assertEqual(view.CANVAS_DIM, detect_obs.N_CHANNELS,
                         "sim ground-truth canvas and the live detector canvas must be the same width")

    def test_enemy_ground_troop_lights_the_enemy_ground_channel(self):
        eng = _make_engine()
        eng.units.append(Unit(spec=build_spec(eng.db, "skeletons"), team=1, x=0.5, y=0.3, hp=100.0))

        ch = view.semantic_channels(eng, 96, 64, team=0)

        self.assertEqual(ch.shape, (96, 64, view.CANVAS_DIM))
        self.assertEqual(int(ch[:, :, 0].max()), 255, "an enemy ground troop belongs in channel 0")
        self.assertEqual(int(ch[:, :, 3].max()), 0, "...and must not appear in MY ground channel")

    def test_canvas_is_mirrored_for_the_self_play_opponent(self):
        """The same unit is 'enemy' to team 0 and 'mine' to team 1 -- that flip is what lets a frozen
        snapshot pilot team 1 with a policy that only ever learned team 0's point of view."""
        eng = _make_engine()
        eng.units.append(Unit(spec=build_spec(eng.db, "skeletons"), team=1, x=0.5, y=0.3, hp=100.0))

        mine = view.semantic_channels(eng, 96, 64, team=1)

        self.assertEqual(int(mine[:, :, 3].max()), 255, "team 1 must see its own troop as 'mine'")
        self.assertEqual(int(mine[:, :, 0].max()), 0)

    def test_building_uses_the_building_channel(self):
        eng = _make_engine()
        eng.units.append(Unit(spec=build_spec(eng.db, "tesla"), team=1, x=0.5, y=0.3, hp=100.0))

        ch = view.semantic_channels(eng, 96, 64, team=0)

        self.assertEqual(int(ch[:, :, 2].max()), 255, "an enemy building belongs in channel 2")
        self.assertEqual(int(ch[:, :, 0].max()), 0)

    def test_a_still_deploying_unit_is_not_drawn(self):
        """Live, the detector cannot box a unit that has not appeared yet."""
        eng = _make_engine()
        u = Unit(spec=build_spec(eng.db, "skeletons"), team=1, x=0.5, y=0.3, hp=100.0)
        u.deploy_left = 1.0
        eng.units.append(u)

        ch = view.semantic_channels(eng, 96, 64, team=0)

        self.assertEqual(int(ch.max()), 0)

    def test_presence_recall_drops_units_like_a_missed_detection(self):
        import random

        eng = _make_engine()
        for i in range(20):
            eng.units.append(
                Unit(spec=build_spec(eng.db, "skeletons"), team=1, x=0.1 + i * 0.04, y=0.3, hp=100.0))

        blind = view.semantic_channels(eng, 96, 64, team=0, rng=random.Random(0),
                                       presence_recall=0.0)
        perfect = view.semantic_channels(eng, 96, 64, team=0, rng=random.Random(0),
                                         presence_recall=1.0)

        self.assertEqual(int(blind.max()), 0, "recall 0 = the detector saw nothing")
        self.assertEqual(int(perfect[:, :, 0].max()), 255)


class ObsWidthTests(unittest.TestCase):
    def test_obs_in_channels_follows_the_gate(self):
        class Cfg:
            def __init__(self, on):
                self.on = on

            def get(self, *path, default=None):
                return self.on if path == ("observation", "use_detector_canvas") else default

        self.assertEqual(detect_obs.obs_in_channels(Cfg(False)), 3)
        self.assertEqual(detect_obs.obs_in_channels(Cfg(True)), 3 + detect_obs.N_CHANNELS)


if __name__ == "__main__":
    unittest.main()
