"""Three owner-reported Goblin fixes (2026-08-28).

1. GOBLIN GIANT's BACKPACK. Wiki, Goblin Giant page: "He also carries two Spear Goblins on his
   back, that can attack independently on the Goblin Giant. When he is defeated, the Spear Goblins
   spawn and continue attacking." MEASURED BEFORE: the giant died leaving NOTHING and dealt no
   ranged damage at all. `backpack_spear_goblins` existed in the KB on the EVO row only, and the
   engine read it NOWHERE -- inert data, the same class as the `support:` bug.

2. GOBLIN DEMOLISHER does NOT knock back on his attack. MEASURED BEFORE: knockback 1.0 tiles.
   WARNING: the `knockback` FLAG had to be removed -- `knockback_tiles: 0` does not work, because
   build_spec re-applies _KNOCKBACK_DEFAULT whenever the flag is present. His DEATH explosion is a
   separate key (`death_knockback_tiles`) and is untouched.

SHARED, byte-identical in both decks: every assertion is about the ENGINE and the KB.
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

from clashrl.cards import CardDB                                   # noqa: E402
from clashrl.sim.engine import (SimEngine, Unit, build_spec,       # noqa: E402
                                _TILES_Y)
from test_sim_status_effects import DummyCfg                       # noqa: E402

_DB = CardDB(path=ROOT / "config" / "cards.yaml")


def _engine():
    return SimEngine(DummyCfg(), _DB, random.Random(0))


class GoblinGiantBackpackTests(unittest.TestCase):

    def test_both_rows_carry_two_spear_goblins(self):
        """The BASE card carries them too -- the field was on the Evo row only."""
        for key in ("goblin_giant", "goblin_giant_evo"):
            s = build_spec(_DB, key, 11)
            self.assertEqual(s.bp_count, 2, f"{key} is not carrying its two Spear Goblins")
            self.assertIsNotNone(s.bp_spec)
            self.assertEqual(s.bp_spec.base, "spear_goblins")
            self.assertAlmostEqual(s.bp_range, 5.0, places=3)

    def test_they_get_bodies_when_he_dies(self):
        eng = _engine()
        eng.reset()
        gg = Unit(spec=build_spec(_DB, "goblin_giant", 11), team=0, x=0.5, y=0.5, hp=10.0)
        eng.units.append(gg)
        before = {id(u) for u in eng.units}
        gg.hp = 0.0
        for _ in range(20):
            eng.advance(0.1)
        spawned = [u for u in eng.units if id(u) not in before]
        self.assertEqual(len(spawned), 2, "two Spear Goblins must spawn on his death")
        for u in spawned:
            self.assertEqual(u.spec.base, "spear_goblins")

    def test_they_attack_while_riding_and_are_not_bound_by_his_targeting(self):
        """He is buildings-only, so ANY damage to a troop at range is the backpack. That
        independence is the mechanic: it is why a Goblin Giant chips defenders on the way in."""
        eng = _engine()
        eng.reset()
        gg = Unit(spec=build_spec(_DB, "goblin_giant", 11), team=0, x=0.5, y=0.5, hp=3000.0)
        foe = Unit(spec=build_spec(_DB, "knight", 11), team=1,
                   x=0.5, y=0.5 - 3.0 / _TILES_Y, hp=4000.0)
        eng.units += [gg, foe]
        gg.deploy_left = foe.deploy_left = 0.0
        hp0 = foe.hp
        for _ in range(30):
            eng.advance(0.1)
        self.assertGreater(hp0 - foe.hp, 0.0,
                           "the riding Spear Goblins dealt nothing to a troop 3 tiles away")

    def test_a_carrier_without_a_backpack_has_none(self):
        """NEGATIVE CONTROL: the field must not leak onto every card."""
        for key in ("knight", "giant", "spear_goblins"):
            self.assertEqual(build_spec(_DB, key, 11).bp_count, 0, key)


class GoblinDemolisherKnockbackTests(unittest.TestCase):

    def test_his_attack_does_not_knock_back(self):
        self.assertEqual(build_spec(_DB, "goblin_demolisher", 11).knockback, 0.0)

    def test_the_flag_is_gone_not_merely_zeroed(self):
        """`knockback_tiles: 0` would NOT have worked -- build_spec re-applies the default whenever
        the flag is present, so a future edit that re-adds the flag silently restores the bug."""
        import yaml
        raw = yaml.safe_load((ROOT / "config" / "cards.yaml").read_text(encoding="utf-8"))
        row = (raw.get("cards") or {}).get("goblin_demolisher") or {}
        self.assertTrue(row, "goblin_demolisher row not found -- the check is not running")
        self.assertNotIn("knockback", row.get("flags") or [],
                         "the knockback FLAG is back; knockback_tiles cannot override it")

    def test_his_death_explosion_is_untouched(self):
        s = build_spec(_DB, "goblin_demolisher", 11)
        self.assertGreater(s.death_dmg, 0.0, "the death explosion was removed with the knockback")


if __name__ == "__main__":
    unittest.main()
