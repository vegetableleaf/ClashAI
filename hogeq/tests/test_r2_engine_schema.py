"""R2 ADJUDICATION #8 -- ENGINE/SCHEMA. The seven items the owner pulled forward from Phase I.

Every number below is off an archived wiki revision (research/sim_parity/webcache/) and every
change is an owner ruling recorded in research/sim_parity/decisions.md, section
"2026-08-26 -- R2 ADJUDICATION". The "MEASURED BEFORE" lines are what the sim actually did on
the unpatched tree, not estimates.
"""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
for _p in (str(SRC), str(ROOT / "tests")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from test_sim_status_effects import _make_engine                     # noqa: E402
from clashrl.sim.engine import Unit, build_spec, _TILES_Y            # noqa: E402

LVL = 11


class ThreeMusketeersReworkTests(unittest.TestCase):
    """Three Musketeers, the 3/11/2025 "Elite Musketeers" rework.

    Wiki (Three_Musketeers.wikitext rev 437182): "It spawns three single-target, air-targeting,
    long-ranged, ground troops ... If enemy troops are close to them, they switch to being
    single-target, ground-targeting, melee, ground troops with the same hitpoints and very high
    damage, and switch back to their ranged form when enemies are far from them."
    Ranged Attack row: Range 6, Target Air & Ground, 'range dmg_11' = 204.
    Melee Attack row:  Range "Melee: Long" (1.6 tiles), Target Ground, 'melee dmg_11' = 314.
    Shared: hp_11 883, atk_speed 1.3, Count x3.

    Owner: R2 #8 item 1 -- "a 9-elixir card dealing ZERO".
    MEASURED BEFORE: build_spec dps 0.0, hit_dmg 0.0, attacks_air False.
    """

    def spec(self):
        eng = _make_engine()
        return eng, build_spec(eng.db, "three_musketeers", LVL)

    def test_the_card_fields_three_separate_bodies(self):
        eng, s = self.spec()
        eng.elixir = [10.0, 10.0]
        self.assertTrue(eng.deploy(0, s, 0.50, 0.70))
        mine = [u for u in eng.units if u.team == 0]
        self.assertEqual(len(mine), 3, "the card is Count x3")
        for u in mine:
            self.assertAlmostEqual(u.hp, 883.0, delta=1.0,
                                   msg="all three bodies share hp_11 883 -- they are not a mixed squad")

    def test_they_are_not_a_mixed_squad(self):
        """The history line's "three DIFFERENT troops ... different damage statistics from the
        Musketeer" contrasts them with the MUSKETEER card, not with each other, so `components`
        (Goblin Gang / Rascals / Goblinstein) is the wrong machinery here."""
        _eng, s = self.spec()
        self.assertEqual(len(s.components), 0)
        self.assertEqual(s.squad_count, 0)

    def test_the_published_ranged_attack(self):
        _eng, s = self.spec()
        self.assertAlmostEqual(s.hit_dmg, 204.0, delta=0.5)      # 'range dmg_11'
        self.assertEqual(s.reach, 6.0)                           # Ranged Attack row, Range 6
        self.assertTrue(s.attacks_air, "Ranged Attack targets Air & Ground")
        self.assertAlmostEqual(s.hit_speed, 1.3, delta=1e-6)

    def test_the_published_melee_attack(self):
        _eng, s = self.spec()
        self.assertAlmostEqual(s.melee_dmg, 314.0, delta=0.5)    # 'melee dmg_11'
        self.assertEqual(s.melee_reach, 1.6)                     # "Melee: Long (1.6)"

    def _dealt(self, tiles, target="knight"):
        """One swing at a target whose HITBOX EDGE is `tiles` from the attacker's centre -- the
        same ruler `_gap` uses, so `tiles` is exactly the distance the melee switch tests."""
        eng = _make_engine()
        s = build_spec(eng.db, "three_musketeers", LVL)
        t = build_spec(eng.db, target, LVL)
        atk = Unit(spec=s, team=0, x=0.50, y=0.55, hp=s.hp)
        gap = tiles + t.radius
        tgt = Unit(spec=t, team=1, x=0.50, y=0.55 - gap / _TILES_Y, hp=t.hp * 500)
        eng.units += [atk, tgt]
        before = tgt.hp
        eng._attack(atk, "unit", tgt)
        return before - tgt.hp

    def test_a_ground_enemy_that_closes_in_takes_the_melee_hit(self):
        self.assertAlmostEqual(self._dealt(0.5), 314.0, delta=1.0)

    def test_a_ground_enemy_at_range_takes_the_ranged_hit(self):
        self.assertAlmostEqual(self._dealt(4.0), 204.0, delta=1.0)

    def test_the_switch_happens_at_the_published_melee_range(self):
        self.assertAlmostEqual(self._dealt(1.5), 314.0, delta=1.0)
        self.assertAlmostEqual(self._dealt(1.7), 204.0, delta=1.0)

    def test_air_never_gets_the_melee_hit(self):
        """The Melee Attack row's Target column reads Ground, so a Minion hovering on top of
        them is still answered with the 204 ranged shot."""
        self.assertAlmostEqual(self._dealt(0.5, target="minions"), 204.0, delta=1.0)

    def test_they_actually_hurt_something_over_time(self):
        """The headline defect: a 9-elixir card that could not damage anything."""
        eng = _make_engine()
        s = build_spec(eng.db, "three_musketeers", LVL)
        t = build_spec(eng.db, "giant", LVL)
        atk = Unit(spec=s, team=0, x=0.50, y=0.55, hp=s.hp)
        tgt = Unit(spec=t, team=1, x=0.50, y=0.55 - 4.0 / _TILES_Y, hp=t.hp * 100)
        eng.units += [atk, tgt]
        before = tgt.hp
        for _ in range(60):
            eng.advance(0.1)
        self.assertGreater(before - tgt.hp, 0.0, "MEASURED BEFORE: exactly 0 over any interval")

    def test_ordinary_single_mode_cards_are_untouched(self):
        """The melee switch is opt-in per card: nothing else in the KB declares one."""
        eng = _make_engine()
        for name in ("musketeer", "knight", "archers", "wizard", "hog_rider"):
            with self.subTest(card=name):
                self.assertEqual(build_spec(eng.db, name, LVL).melee_dmg, 0.0)


if __name__ == "__main__":
    unittest.main()
