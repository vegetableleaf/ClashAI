"""The LIVE -> SimEngine bridge, and the size of what it cannot see.

HANDOFF ruled live search out on four grounds, only one of which was compute. This module exists
because the owner accepted the measured ceiling deliberately ("a gain is a gain") -- so the job is
to make the capped gain reachable AND to keep the cap measurable.

The test that matters is not "the bridge builds an engine". It is "the bridge reports how wrong it
is", because in live play there is no ground truth to diff against and this is the only place the
error can be sized honestly.
"""
from __future__ import annotations

import random
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for _p in (str(ROOT / "src"), str(ROOT / "tests")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from clashrl.cards import CardDB                                  # noqa: E402
from clashrl.sim import live_bridge as LB                         # noqa: E402
from clashrl.sim.engine import SimEngine, Unit, build_spec        # noqa: E402
from test_sim_status_effects import DummyCfg                      # noqa: E402

_DB = CardDB(path=ROOT / "config" / "cards.yaml")


def _truth():
    """A real engine with bodies at REAL (partial) hp -- the thing live cannot see."""
    eng = SimEngine(DummyCfg(), _DB, random.Random(0))
    eng.reset()
    eng.units.clear()
    for k, team, x, y, frac in (("knight", 1, 0.40, 0.35, 0.40),
                                ("musketeer", 1, 0.60, 0.30, 1.00),
                                ("giant", 1, 0.50, 0.25, 0.55),
                                ("skeletons", 0, 0.50, 0.62, 1.00)):
        sp = build_spec(_DB, k, 11)
        u = Unit(spec=sp, team=team, x=x, y=y, hp=sp.hp * frac)
        u.deploy_left = 0.0
        eng.units.append(u)
    return eng


class LiveBridgeTests(unittest.TestCase):

    def test_it_rebuilds_every_body_it_was_shown(self):
        eng = _truth()
        obs = LB.observe_as_detector(eng, rng=random.Random(1))
        rb = LB.build_engine(DummyCfg(), _DB, random.Random(0), obs)
        e = LB.reconstruction_error(eng, rb)
        self.assertEqual(e["bodies_rebuilt"], e["bodies_true"])
        self.assertEqual(e["bodies_missing"], 0.0)

    def test_HP_IS_THE_DOMINANT_ERROR_and_it_is_reported(self):
        """THE POINT OF THIS MODULE. Live cannot read troop HP, so the bridge gives every body its
        spec maximum. MEASURED on a board holding a 40%-hp Knight and a 55%-hp Giant: the rebuilt
        state carries +77% more hitpoints than reality -- with PERFECT positions and NO dropout.

        HANDOFF led with the quarter-tile position error (62% of the gain, saturating). This says
        the HP blocker may bite harder still, and it is total by construction rather than a
        parameter that can be improved. Any live-search result has to be read against it.
        """
        eng = _truth()
        obs = LB.observe_as_detector(eng, rng=random.Random(1))
        rb = LB.build_engine(DummyCfg(), _DB, random.Random(0), obs)
        e = LB.reconstruction_error(eng, rb)
        self.assertAlmostEqual(e["pos_err_mean_tiles"], 0.0, places=6)
        self.assertGreater(e["hp_overstate_frac"], 0.5,
                           "the bridge is not over-stating HP -- has it started reading real HP?")
        self.assertGreater(e["hp_rebuilt"], e["hp_true"])

    def test_position_error_is_reported_faithfully(self):
        """The bridge must not flatter itself: injected jitter has to show up in the report."""
        eng = _truth()
        prev = -1.0
        for sigma in (0.0, 0.25, 0.5):
            obs = LB.observe_as_detector(eng, pos_sigma=sigma, rng=random.Random(1))
            rb = LB.build_engine(DummyCfg(), _DB, random.Random(0), obs)
            err = LB.reconstruction_error(eng, rb)["pos_err_mean_tiles"]
            self.assertGreater(err, prev, f"error did not rise with sigma={sigma}")
            prev = err

    def test_dropout_is_reported_as_missing_bodies(self):
        eng = _truth()
        obs = LB.observe_as_detector(eng, drop=1.0, rng=random.Random(3))
        rb = LB.build_engine(DummyCfg(), _DB, random.Random(0), obs)
        e = LB.reconstruction_error(eng, rb)
        self.assertEqual(e["bodies_rebuilt"], 0.0)
        self.assertEqual(e["bodies_missing"], e["bodies_true"])

    def test_spells_and_non_bodies_never_become_units(self):
        """A detector class with no KB row, or a spell, must not be deployed as a troop."""
        class _A:
            @staticmethod
            def frame_to_board(fx, fy):
                return 0.5, 0.5
        rows = LB.tracks_to_bodies(_DB, [{"base": "fireball", "x": 1, "y": 1},
                                         {"base": "not_a_real_card", "x": 1, "y": 1},
                                         {"base": "king_tower", "x": 1, "y": 1},
                                         {"base": "knight", "x": 1, "y": 1}], _A())
        self.assertEqual([r["key"] for r in rows], ["knight"])


if __name__ == "__main__":
    unittest.main()
