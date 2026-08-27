"""RULING 31b -- the Evo Firecracker's IMPACT spark zone is larger than the shrapnel zones.

Sources: Firecracker/Evolution revid 437259, Evolution Attributes table -- Big Spark Duration
3 sec / Big Spark Radius 2.5 / Small Spark Duration 2.5 sec / Small Spark Radius 1.2 / Small
Spark Count x5 / Spark Hit Speed 0.25 sec -- plus the owner report 2026-08-27: the primary
spark at the main projectile's impact has a LARGER radius than the secondary sparks.

MEASURED before the fix (engine at the fix-1 commit): every zone the attack left -- the carrier's
impact zone AND all five shrapnel-end zones -- carried the same curated radius 0.75 and the same
2.5 s lifetime, so the impact zone was 1/11th of its published area and outlived its published
3 s by -0.5 s. The damage split was already right (impact zone ticking 48 = 192 dps, shrapnel
zones 12 = 48 dps); only the geometry was shared.

SHARED, byte-identical in both decks: every assertion is about the ENGINE and the KB, not a deck.
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

from clashrl.cards import CardDB                                   # noqa: E402
from clashrl.sim.engine import (SimEngine, Unit, build_spec,       # noqa: E402
                                _TILES_X, _TILES_Y)

from test_sim_status_effects import DummyCfg                       # noqa: E402


def _engine() -> SimEngine:
    return SimEngine(DummyCfg(), CardDB(path=ROOT / "config" / "cards.yaml"), random.Random(0))


class SparkZoneGeometryTests(unittest.TestCase):
    def test_the_kb_publishes_both_radii_and_both_durations(self):
        spec = build_spec(CardDB(path=ROOT / "config" / "cards.yaml"), "firecracker_evo", 11)
        self.assertAlmostEqual(spec.spark_r_big, 2.5, places=3)     # Big Spark Radius
        self.assertAlmostEqual(spec.spark_r, 1.2, places=3)         # Small Spark Radius
        self.assertAlmostEqual(spec.spark_dur_big, 3.0, places=3)   # Big Spark Duration
        self.assertAlmostEqual(spec.spark_dur, 2.5, places=3)       # Small Spark Duration

    def test_one_attack_leaves_one_big_zone_on_the_impact_and_five_small_at_bolt_ends(self):
        """The whole attack, fired for real: the carrier's zone must carry the BIG geometry and
        each shrapnel bolt's the SMALL -- before the fix all six were 0.75-tile / 2.5 s."""
        eng = _engine()
        fc = Unit(spec=build_spec(eng.db, "firecracker_evo", 11), team=0, x=0.5, y=0.50, hp=304.0)
        tgt = Unit(spec=build_spec(eng.db, "knight", 11), team=1,
                   x=0.5, y=0.50 + 6.0 / _TILES_Y, hp=1e6)
        eng.units += [fc, tgt]
        eng._attack(fc, "unit", tgt)
        for _ in range(60):
            eng._tick_projectiles(0.1)
        self.assertEqual(len(eng.spark_zones), 6, "one carrier zone + five shrapnel zones")
        big = [z for z in eng.spark_zones if abs(z[2] - 2.5) < 1e-6]
        small = [z for z in eng.spark_zones if abs(z[2] - 1.2) < 1e-6]
        self.assertEqual(len(big), 1, "exactly ONE large zone, on the impact point")
        self.assertEqual(len(small), 5, "and five small ones")
        bz = big[0]
        self.assertAlmostEqual((bz[0] - tgt.x) * _TILES_X, 0.0, places=1)
        self.assertAlmostEqual((bz[1] - tgt.y) * _TILES_Y, 0.0, places=1,
                               msg="the large zone sits ON the impact point")
        self.assertAlmostEqual(bz[4], 3.0, places=2, msg="Big Spark Duration is its own 3 s")
        for z in small:
            self.assertAlmostEqual(z[4], 2.5, places=2, msg="Small Spark Duration 2.5 s")
        self.assertAlmostEqual(bz[5], 192.0 * 0.25, places=3,
                               msg="the big zone still ticks the big dps")
        for z in small:
            self.assertAlmostEqual(z[5], 48.0 * 0.25, places=3)

    def test_the_two_radii_gate_damage_at_their_own_edges(self):
        """A body between the two radii takes big-zone ticks and NO small-zone ticks -- the
        distances are computed from the body's own radius so the probe cannot drift when a
        collision size changes."""
        eng = _engine()
        eng.towers = ([], eng.towers[1]) if False else eng.towers   # keep towers; we stay mid-board
        body = build_spec(eng.db, "knight", 11)
        r_body = body.radius

        def probe(zone_r, dist):
            e = _engine()
            victim = Unit(spec=body, team=1, x=0.5 + dist / _TILES_X, y=0.5, hp=10000.0)
            victim.stun_left = 60.0                     # stand still for the whole probe
            e.units.append(victim)
            e.spark_zones.append([0.5, 0.5, zone_r, 0, e.t + 5.0, 48.0, e.t])
            for _ in range(4):
                e.advance(0.1)
            return 10000.0 - victim.hp

        big_in = probe(2.5, 2.5 + r_body - 0.2)
        big_out = probe(2.5, 2.5 + r_body + 0.3)
        small_in = probe(1.2, 1.2 + r_body - 0.2)
        small_out = probe(1.2, 1.2 + r_body + 0.3)
        self.assertGreater(big_in, 0.0, "inside the 2.5-tile edge: ticks land")
        self.assertEqual(big_out, 0.0, "outside it: nothing")
        self.assertGreater(small_in, 0.0)
        self.assertEqual(small_out, 0.0,
                         "a body 1.2+r..2.5+r tiles out is exactly the band the owner reported: "
                         "hit by the impact spark, missed by the shrapnel sparks")


if __name__ == "__main__":
    unittest.main()
