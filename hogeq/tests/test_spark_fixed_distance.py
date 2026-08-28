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

    def test_the_carrier_detonates_on_the_targets_FRONT_EDGE_not_its_centre(self):
        """OWNER 2026-08-28. The firework explodes on impact, and impact with a 1.5-radius Crown
        Tower happens at its face -- the carrier was flying THROUGH the hitbox to the centre and
        handing the shards 1.5 free tiles of penetration.

        The payload property must survive: all five bolts still land on the tower it hit, which is
        the published "totaling 320 if all shards hit the same target".
        """
        import random as _r
        from clashrl.sim.engine import SimEngine as _E, Unit as _U, _TILES_X as _TX
        from test_sim_status_effects import DummyCfg as _D
        eng = _E(_D(), CardDB(path=ROOT / "config" / "cards.yaml"), _r.Random(0))
        eng.reset()
        ps = [t for t in eng.towers[1] if not t.king]
        p0 = sum(t.hp for t in ps)
        fc = _U(spec=build_spec(eng.db, "firecracker_evo", 11), team=0,
                x=3.5 / _TX, y=11.0 / _TILES_Y, hp=304.0)
        eng.units.append(fc)
        eng._attack(fc, "tower", ps[0])
        for _ in range(120):
            eng._tick_projectiles(0.05)
        self.assertAlmostEqual(p0 - sum(t.hp for t in ps), 320.0, places=1,
                               msg="the five bolts no longer all land on the target it hit")
        shard = [q for q in eng.projectiles if q.label.endswith("_spark")]
        if shard:
            self.assertGreater(shard[0].oy * _TILES_Y, 6.5,
                               "shards still originate at the tower CENTRE (y=6.5), not its face")

    def test_attacking_a_princess_tower_does_NOT_damage_the_king(self):
        """THE REPORTED BUG (owner 2026-08-28), and the reason the zone centre pulls back.

        The shrapnel's 5 tiles are its REACH, so the spark circle's FAR EDGE sits at the 5-tile mark
        and its centre one radius short. Geometry, outermost bolt of the 70-degree cone measured
        from the tower face:
            centre at 5.0 -> 2.78 tiles from the king centre -> inside 1.2 + 2.0, it connects
            centre at 3.8 -> 3.82 -> clears
        The centre has to be within 4.50 tiles of the face to clear; the old model sat at 5.00.

        Asserted on BOTH lanes: the cone is mirrored, so a right-lane shot is a real second case.
        """
        import random as _r
        from clashrl.sim.engine import SimEngine as _E, Unit as _U, _TILES_X as _TX
        from test_sim_status_effects import DummyCfg as _D
        for fx, lane in ((3.5, 3.5), (5.5, 3.5), (14.5, 14.5), (12.5, 14.5)):
            eng = _E(_D(), CardDB(path=ROOT / "config" / "cards.yaml"), _r.Random(0))
            eng.reset()
            king = [t for t in eng.towers[1] if t.king][0]
            ps = [t for t in eng.towers[1] if not t.king]
            tgt = min(ps, key=lambda t: abs(t.x * _TX - lane))
            k0 = king.hp
            fc = _U(spec=build_spec(eng.db, "firecracker_evo", 11), team=0,
                    x=fx / _TX, y=11.0 / _TILES_Y, hp=304.0)
            eng.units.append(fc)
            eng._attack(fc, "tower", tgt)
            for _ in range(90):
                eng.advance(0.05)
            self.assertAlmostEqual(k0 - king.hp, 0.0, places=6,
                                   msg=f"from x={fx} the sparks reached the KING tower")

    def test_the_carriers_own_zone_is_NOT_pulled_back(self):
        """Only the shrapnel pulls back. The carrier's large zone belongs on the point it struck --
        if it moved too, the impact DoT would drift off the tower it just hit."""
        import random as _r
        from clashrl.sim.engine import SimEngine as _E, Unit as _U, _TILES_X as _TX
        from test_sim_status_effects import DummyCfg as _D
        eng = _E(_D(), CardDB(path=ROOT / "config" / "cards.yaml"), _r.Random(0))
        eng.reset()
        ps = [t for t in eng.towers[1] if not t.king]
        fc = _U(spec=build_spec(eng.db, "firecracker_evo", 11), team=0,
                x=3.5 / _TX, y=11.0 / _TILES_Y, hp=304.0)
        eng.units.append(fc)
        eng._attack(fc, "tower", ps[0])
        for _ in range(40):
            eng.advance(0.05)
        big = [z for z in eng.spark_zones if abs(z[2] - 2.5) < 1e-6]
        self.assertTrue(big, "the carrier's large zone is missing")
        for z in big:
            gap = ((z[0] - ps[0].x) ** 2 * _TX ** 2 + (z[1] - ps[0].y) ** 2 * _TILES_Y ** 2) ** 0.5
            self.assertLess(gap, 2.0, "the carrier's zone drifted off the tower it hit")


if __name__ == "__main__":
    unittest.main()
