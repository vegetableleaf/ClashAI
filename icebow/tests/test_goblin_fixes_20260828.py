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
                                _TILES_X, _TILES_Y)
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


class EvoGoblinCageSuppressionTests(unittest.TestCase):
    """OWNER 2026-08-28: the Evo Goblin Cage pulls its target INTO the cage. While inside, the
    target is suppressed -- cannot move or attack -- and can only take the cage's own damage. It
    ends when the cage breaks or the target dies.

    BEFORE: the cage reused the Fisherman hook, which pulls the body to `reach` and then hits it
    normally. There was no suppression, no damage exclusivity, and no release condition at all.
    """

    def _caged(self):
        eng = _engine()
        eng.reset()
        cage = Unit(spec=build_spec(_DB, "goblin_cage_evo", 11), team=0, x=0.5, y=0.5, hp=780.0)
        foe = Unit(spec=build_spec(_DB, "knight", 11), team=1,
                   x=0.5, y=0.5 - 2.5 / _TILES_Y, hp=2000.0)
        eng.units += [cage, foe]
        cage.deploy_left = foe.deploy_left = 0.0
        for _ in range(60):
            eng.advance(0.1)
        return eng, cage, foe

    def test_only_the_evolution_cages(self):
        self.assertTrue(build_spec(_DB, "goblin_cage_evo", 11).cage_suppress)
        self.assertFalse(build_spec(_DB, "goblin_cage", 11).cage_suppress)
        self.assertFalse(build_spec(_DB, "fisherman", 11).cage_suppress,
                         "the Fisherman shares the hook but must NOT imprison")

    def test_the_target_is_taken_prisoner(self):
        eng, cage, foe = self._caged()
        self.assertIs(foe.caged_by, cage)
        self.assertIs(cage.cage_prisoner, foe)

    def test_a_caged_body_cannot_move(self):
        eng, cage, foe = self._caged()
        px, py = foe.x, foe.y
        for _ in range(30):
            eng.advance(0.1)
        self.assertAlmostEqual(foe.x, px, places=9)
        self.assertAlmostEqual(foe.y, py, places=9)

    def test_only_the_cage_can_damage_it(self):
        eng, cage, foe = self._caged()
        hp = foe.hp
        eng._hurt(foe, 500.0)                      # a spell, another troop, the tower: refused
        self.assertEqual(foe.hp, hp, "outside damage reached a caged body")
        eng._hurt(foe, 500.0, source=cage)         # the cage itself: allowed
        self.assertAlmostEqual(hp - foe.hp, 500.0, places=6)

    def test_breaking_the_cage_releases_it(self):
        eng, cage, foe = self._caged()
        cage.hp = 0.0
        for _ in range(20):
            eng.advance(0.1)
        self.assertIsNone(foe.caged_by, "the prisoner is still caged after the cage broke")
        hp = foe.hp
        eng._hurt(foe, 100.0)
        self.assertAlmostEqual(hp - foe.hp, 100.0, places=6, msg="still immune after release")

    def test_a_dead_prisoner_frees_the_cage(self):
        eng, cage, foe = self._caged()
        foe.hp = 0.0
        for _ in range(20):
            eng.advance(0.1)
        self.assertIsNone(cage.cage_prisoner)

    def test_the_cage_can_actually_damage_its_prisoner_THROUGH_THE_ATTACK_PATH(self):
        """INTEGRATION, and the gap that shipped a broken mechanic.

        The unit test above calls `_hurt(..., source=cage)` DIRECTLY, which proves the rule but not
        the wiring. In a real match the cage swings through `_land_hit`, and `_land_hit` was not
        forwarding its `attacker` -- so the prisoner was immune to the cage as well as to everything
        else, i.e. a permanent stun with no way out. Test the path the game uses, not the helper.
        """
        eng = _engine()
        eng.reset()
        cage = Unit(spec=build_spec(_DB, "goblin_cage_evo", 11), team=0, x=0.5, y=0.5, hp=780.0)
        foe = Unit(spec=build_spec(_DB, "knight", 11), team=1,
                   x=0.5, y=0.5 - 2.5 / _TILES_Y, hp=600.0)
        eng.units += [cage, foe]
        cage.deploy_left = foe.deploy_left = 0.0
        hp0 = foe.hp
        for _ in range(200):
            eng.advance(0.1)
        self.assertLess(foe.hp, hp0,
                        "the cage cannot damage its own prisoner -- that is a permanent stun")

    def test_a_dashing_unit_landing_on_a_body_does_not_crash(self):
        """REGRESSION: `_land_leap` was handed `source=attacker`, a name that does not exist in
        that scope, so EVERY dash landing raised NameError and killed the run. Both suites passed
        through it -- no test exercised a leap onto a live body."""
        eng = _engine()
        eng.reset()
        for key in ("bandit", "mega_knight"):
            try:
                sp = build_spec(_DB, key, 11)
            except Exception:                                  # noqa: BLE001
                continue
            if sp.leap_dmg <= 0.0:
                continue
            u = Unit(spec=sp, team=0, x=0.5, y=0.5, hp=3000.0)
            foe = Unit(spec=build_spec(_DB, "knight", 11), team=1,
                       x=0.5, y=0.5 - 4.0 / _TILES_Y, hp=3000.0)
            eng.units += [u, foe]
            u.deploy_left = foe.deploy_left = 0.0
            for _ in range(120):
                eng.advance(0.05)                              # must not raise


class RoyalRecruitsLineTests(unittest.TestCase):
    """OWNER 2026-08-28: they spawn in a SINGLE LINE across the board, not a 2x3 rectangle.
    Wiki: "Their deployment is in a horizontal formation spanning the Arena" and they "take up the
    most amount of space of any card in the game, stretching across almost the entire arena".
    """

    def _drop(self, card):
        eng = _engine()
        eng.reset()
        eng.elixir[0] = 10.0
        eng.deploy(0, build_spec(_DB, card, 11), 0.5, 0.72)
        us = [u for u in eng.units if u.spec.base == card]
        return [u.x * _TILES_X for u in us], [u.y * _TILES_Y for u in us]

    def test_six_recruits_in_one_row(self):
        xs, ys = self._drop("royal_recruits")
        self.assertEqual(len(xs), 6)
        self.assertAlmostEqual(max(ys) - min(ys), 0.0, places=6,
                               msg="the recruits are in more than one row -- still a rectangle")

    def test_the_line_spans_most_of_the_arena(self):
        xs, _ = self._drop("royal_recruits")
        span = max(xs) - min(xs)
        self.assertGreater(span, 12.0, f"span {span:.2f}t is not 'almost the entire arena' (18t)")
        self.assertLess(span, 18.0, "the line is wider than the arena")

    def test_ordinary_swarms_are_unchanged(self):
        """NEGATIVE CONTROL: the flag must not turn every multi-unit card into a line."""
        for card in ("skeletons", "barbarians"):
            xs, ys = self._drop(card)
            self.assertGreater(max(ys) - min(ys), 0.0,
                               f"{card} became a single line -- the change leaked")


if __name__ == "__main__":
    unittest.main()
