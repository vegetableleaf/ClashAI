"""Phase B evolution mechanics + the goblin-barrel base fix (2026-08-14 sweep 2):
Evo Musketeer sniper ammo, Evo Archers power shot, Evo Firecracker lingering sparks,
Goblin Barrel actually dropping goblins, Evo Goblin Barrel's mirrored decoy, and the
Evo Elite Barbarians' rage-tipped javelin."""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
for p in (str(SRC), str(ROOT / "tests")):
    if p not in sys.path:
        sys.path.insert(0, p)

from test_sim_status_effects import _make_engine
from clashrl.sim.engine import build_spec


class EvoPhaseBTests(unittest.TestCase):
    def test_musketeer_sniper_ammo(self):
        eng = _make_engine()
        mk = build_spec(eng.db, "musketeer_evo", 11)
        self.assertEqual(mk.sniper_shots, 3)
        eng.elixir = [10.0, 10.0]
        self.assertTrue(eng.deploy(1, mk, 0.50, 0.30))
        musk = [u for u in eng.units if u.team == 1][-1]
        eng.elixir = [10.0, 10.0]
        self.assertTrue(eng.deploy(0, build_spec(eng.db, "x_bow", 11), 0.50, 0.70))  # ~12.8 tiles: far out of reach
        far = [u for u in eng.units if u.team == 0][-1]
        big = 0
        for _ in range(160):                                 # 8 s: enough for all three rounds
            prev = far.hp
            eng.advance(0.05)
            if prev - far.hp > 200:
                big += 1
        self.assertEqual(big, 3, "exactly her 3 sniper rounds cross the arena")
        self.assertEqual(musk.sniper_left, 0)
        drop = 0
        for _ in range(40):                                  # rounds spent -> she walks, no more snipes
            prev = far.hp
            eng.advance(0.05)
            drop = max(drop, prev - far.hp)
        self.assertLess(drop, 200, "no fourth round exists")

    def test_archers_power_shot_band(self):
        for tiles, want in ((5.0, 168.0), (2.0, 112.0)):     # >=4 tiles -> 1.5x, close -> normal
            eng = _make_engine()
            ar = build_spec(eng.db, "archers_evo", 11)
            eng.elixir = [10.0, 10.0]
            self.assertTrue(eng.deploy(0, build_spec(eng.db, "x_bow", 11), 0.50, 0.60))
            victim = [u for u in eng.units if u.team == 0][-1]
            eng.elixir = [10.0, 10.0]
            self.assertTrue(eng.deploy(1, ar, 0.50, 0.60 - tiles / 32.0))
            pair = [u for u in eng.units if u.team == 1]
            eng.units.remove(pair[-1])                       # one archer: the pair fires the same
            first = 0.0                                      # tick and doubles the measured drop
            for _ in range(120):
                prev = victim.hp
                eng.advance(0.05)
                if prev - victim.hp > 50:
                    first = prev - victim.hp
                    break
            self.assertAlmostEqual(first, want, delta=3,
                                   msg=f"swing from {tiles} tiles must deal {want}")

    def test_firecracker_spark_zones(self):
        eng = _make_engine()
        fc = build_spec(eng.db, "firecracker_evo", 11)
        self.assertGreater(fc.spark_tick, 0)
        self.assertEqual(fc.spark_dur, 2.5)
        eng.elixir = [10.0, 10.0]
        self.assertTrue(eng.deploy(0, build_spec(eng.db, "x_bow", 11), 0.45, 0.55))
        wall = [u for u in eng.units if u.team == 0][-1]
        eng.elixir = [10.0, 10.0]
        self.assertTrue(eng.deploy(1, fc, 0.45, 0.55 - 4.8 / 32.0))
        for _ in range(80):
            eng.advance(0.05)
            if eng.spark_zones:
                break
        self.assertTrue(eng.spark_zones, "her volley must leave lingering spark zones")
        # park a knight in a zone: it must tick damage and slow him
        z = eng.spark_zones[0]
        eng.elixir = [10.0, 10.0]
        self.assertTrue(eng.deploy(0, build_spec(eng.db, "knight", 11), z[0], z[1]))
        kn = [u for u in eng.units if u.team == 0][-1]
        hp0 = kn.hp
        for _ in range(10):
            eng.advance(0.05)
        self.assertLess(kn.hp, hp0, "standing in the sparks must burn")
        self.assertGreater(kn.slow_left, 0.0, "the sparks slow whoever stands in them")

    def test_goblin_barrel_drops_goblins(self):
        eng = _make_engine()
        gb = build_spec(eng.db, "goblin_barrel", 11)
        self.assertEqual(gb.spell_dmg, 0.0, "the barrel itself deals NO impact damage")
        self.assertIsNotNone(gb.spawn_spec)
        eng.elixir = [10.0, 10.0]
        self.assertTrue(eng.deploy(1, gb, 0.50, 0.70))
        eng.elixir = [10.0, 10.0]
        self.assertTrue(eng.deploy(0, build_spec(eng.db, "knight", 11), 0.50, 0.70))
        kn = [u for u in eng.units if u.team == 0][-1]
        hp0 = kn.hp
        for _ in range(10):
            eng.advance(0.1)
        gobs = [u for u in eng.units if u.team == 1 and u.spec.base == "goblins"]
        self.assertEqual(len(gobs), 3, "the barrel drops three goblins")
        self.assertEqual(kn.hp, hp0, "no blast damage on landing")

    def test_goblin_barrel_evo_decoy_mirror(self):
        eng = _make_engine()
        gb = build_spec(eng.db, "goblin_barrel_evo", 11)
        self.assertEqual(gb.decoy_mirror, "goblin_barrel_decoy")
        eng.elixir = [10.0, 10.0]
        self.assertTrue(eng.deploy(1, gb, 0.35, 0.70))
        for _ in range(10):
            eng.advance(0.1)
        mains = [u for u in eng.units if u.team == 1 and u.spec.base == "goblins"]
        decoys = [u for u in eng.units if u.team == 1 and u.spec.base == "decoy_goblin"]
        self.assertEqual(len(mains), 3, "main barrel: three real goblins")
        self.assertEqual(len(decoys), 3, "mirrored barrel: three decoy goblins")
        self.assertTrue(all(u.x > 0.5 for u in decoys), "decoys land in the MIRRORED lane")
        self.assertTrue(all(u.x < 0.5 for u in mains))

    def test_elite_barbs_javelin_and_trail(self):
        eng = _make_engine()
        eb = build_spec(eng.db, "elite_barbarians_evo", 11)
        self.assertAlmostEqual(eb.javelin_dmg, 284.0, delta=1)
        self.assertEqual(eb.javelin_cd, 5.0)
        eng.elixir = [10.0, 10.0]
        self.assertTrue(eng.deploy(1, eb, 0.50, 0.50))
        pair = [u for u in eng.units if u.team == 1]
        eng.units.remove(pair[-1])                           # one barb: both spears land the same tick
        eng.elixir = [10.0, 10.0]
        self.assertTrue(eng.deploy(0, build_spec(eng.db, "x_bow", 11), 0.50, 0.62))
        victim = [u for u in eng.units if u.team == 0][-1]
        first = 0.0
        for _ in range(80):
            prev = victim.hp
            eng.advance(0.05)
            if prev - victim.hp > 200:
                first = prev - victim.hp
                break
        self.assertAlmostEqual(first, 284.0, delta=10, msg="the spear lands before the melee does")
        self.assertTrue(eng.rage_zones, "the javelin lays a rage trail")


if __name__ == "__main__":
    unittest.main(verbosity=1)
