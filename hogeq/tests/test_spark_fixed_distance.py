"""OWNER RULING 2026-08-28 -- the shrapnel bolts travel a FIXED distance.

Owner, verbatim: *"firecracker and evo firecracker's secondary projectiles travel a fixed
distance, no matter how far the primary projectile travels ... in the sim when the primary
projectile travels a shorter distance, the secondary ones travel a longer distance to 'make up
for' the primary projectile. Don't do that."*

MEASURED BEFORE THE FIX: `_spark_burst` set the bolt run to `proj_range - flown`, an 11-tile
budget shared with the carrier, so a point-blank shot handed each bolt ~9 tiles while a
max-range shot gave it ~2.5. The compensation the owner describes was exactly that subtraction.

The assertion that matters is not the value -- it is the INDEPENDENCE: the same bolt distance
whether the carrier flew 2 tiles or 8. A test that only pinned the constant would still pass if
someone reintroduced a budget with a different total.

SHARED, byte-identical in both decks: this is an ENGINE property.
"""
from __future__ import annotations

import random
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
for _p in (str(SRC), str(ROOT / "tests")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from clashrl.cards import CardDB                                    # noqa: E402
from clashrl.sim.engine import (SimEngine, Unit, build_spec,        # noqa: E402
                                _SPARK_TILES, _TILES_Y)

from test_sim_status_effects import DummyCfg                        # noqa: E402


def _engine() -> SimEngine:
    return SimEngine(DummyCfg(), CardDB(path=ROOT / "config" / "cards.yaml"), random.Random(0))


def _bolt_runs(card: str, gap_tiles: float) -> list:
    """Fire `card` at a target `gap_tiles` away; return each shrapnel bolt's assigned run."""
    eng = _engine()
    fc = Unit(spec=build_spec(eng.db, card, 11), team=0, x=0.5, y=0.50, hp=304.0)
    tgt = Unit(spec=build_spec(eng.db, "knight", 11), team=1,
               x=0.5, y=0.50 + gap_tiles / _TILES_Y, hp=1e6)
    eng.units += [fc, tgt]
    eng._attack(fc, "unit", tgt)
    # step until the carrier lands and splits; the shards are the ones labelled *_spark
    runs = []
    for _ in range(80):
        eng._tick_projectiles(0.05)
        runs = [p.left for p in eng.projectiles if p.label.endswith("_spark")]
        if runs:
            break
    return runs


class ShrapnelFixedDistanceTests(unittest.TestCase):

    def test_bolt_run_does_not_depend_on_how_far_the_carrier_flew(self):
        """THE RULING. Near shot and far shot must hand the bolts the SAME run."""
        for card in ("firecracker", "firecracker_evo"):
            near = _bolt_runs(card, 2.0)
            far = _bolt_runs(card, 8.0)
            self.assertTrue(near and far, f"{card}: no shrapnel spawned")
            self.assertAlmostEqual(
                near[0], far[0], places=6,
                msg=f"{card}: bolt run changed with carrier distance "
                    f"({near[0]:.3f} near vs {far[0]:.3f} far) -- the range budget is back")

    def test_the_fixed_run_is_the_published_constant(self):
        for card in ("firecracker", "firecracker_evo"):
            for gap in (1.0, 3.0, 5.0, 8.0):
                runs = _bolt_runs(card, gap)
                self.assertTrue(runs, f"{card} @ {gap}: no shrapnel")
                for r in runs:
                    self.assertAlmostEqual(r, _SPARK_TILES, places=6)

    def test_every_bolt_in_one_burst_shares_the_run(self):
        """All five fan out equally; a per-bolt difference would mean the cone is skewing range."""
        runs = _bolt_runs("firecracker", 4.0)
        self.assertGreaterEqual(len(runs), 2)
        self.assertAlmostEqual(min(runs), max(runs), places=6)

    def test_a_point_blank_shot_no_longer_sprays_nine_tiles(self):
        """The measured pre-fix symptom, pinned as a regression guard: at 1 tile the old model
        gave each bolt ~10 tiles of run. Anything near that means the subtraction returned."""
        runs = _bolt_runs("firecracker", 1.0)
        self.assertTrue(runs)
        # Threshold sits BETWEEN the fixed run (5.0) and the old model's ~10 tiles at 1 tile of
        # carrier flight, so it still fails if the budget subtraction returns.
        self.assertLess(runs[0], 7.0,
                        "a point-blank shot is spraying shrapnel far downfield again")


if __name__ == "__main__":
    unittest.main()
