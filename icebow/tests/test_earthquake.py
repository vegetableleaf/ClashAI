"""Earthquake is THREE waves with a building bonus, not one blast.

User report: "it's supposed to be 3 waves of damage, not just 1. I feel like it's just 1 right now."
It was. The sim resolved it through the ordinary instantaneous-spell path -- one hit, no duration,
and no building damage at all -- so against the card's actual job it was delivering a third of its
troop and crown damage and roughly a TENTH of its building damage.

Wiki vardefines (level 11): dmg_hits 3, dmg_11 84, build_dmg_11 287, crown_dmg_11 53, and the prose
"3.5 times damage to buildings, that is dealt every second for 3 seconds", a 50% slow, no flying
units, and it reaches a concealed Tesla.

MEASURING THIS NEEDS A CONTROL. Buildings in this engine bleed hitpoints continuously over their
lifetime, so raw HP loss counts decay as spell damage -- the first pass at this looked like the
Earthquake was hitting a Tesla thirty times. Every damage figure below is a DIFFERENCE against an
identical board with no spell cast.
"""
from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from clashrl.config import Config                          # noqa: E402
from clashrl.sim.engine import Unit, _Spell, build_spec    # noqa: E402
from clashrl.sim.env import SimMatchEnv                    # noqa: E402

LEVEL = 13          # this deck's Earthquake level


class EarthquakeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.env = SimMatchEnv(Config.load())
        cls.env.reset()
        cls.eq = build_spec(cls.env.db, "earthquake", LEVEL)

    # -- the card data ---------------------------------------------------------------
    def test_it_is_a_three_second_field_that_ticks_every_second(self):
        self.assertEqual(3.0, self.eq.zone_s)
        self.assertEqual(1.0, self.eq.zone_tick_s)

    def test_the_first_wave_lands_with_the_spell(self):
        """The play is casting it as the Hog crosses, so a wasted first second is a wasted cast."""
        self.assertTrue(self.eq.zone_first_tick_now)

    def test_buildings_take_roughly_three_and_a_half_times_troop_damage(self):
        self.assertAlmostEqual(self.eq.spell_build_dmg / self.eq.spell_dmg, 3.5, delta=0.1)

    def test_it_cannot_touch_air_and_it_reaches_concealment(self):
        self.assertTrue(self.eq.ground_only)      # "it is an EARTHquake, after all"
        self.assertTrue(self.eq.hits_hidden)      # a retracted Tesla is still hit

    # -- what it actually does on the board ------------------------------------------
    def _damage_curve(self, target, level=11, hidden=False, steps=40):
        """Per-step damage attributable to the SPELL, isolated from building lifetime decay."""
        def run(cast):
            eng = self.env.eng
            eng.units.clear(); eng.spells.clear(); eng.zones.clear()
            sp = build_spec(self.env.db, target, level)
            u = Unit(spec=sp, team=1, x=0.5, y=0.40, hp=sp.hp)
            u.hidden = hidden
            eng.units.append(u)
            if cast:
                eng.spells.append(_Spell(0, 0.5, 0.40, self.eq, 0.0))
            return [u.hp for _ in range(steps) if not eng.advance(0.1)]
        return [round(a - b, 1) for a, b in zip(run(False), run(True))]

    def _waves(self, curve):
        """Distinct cumulative damage levels = the waves. Only meaningful while the target LIVES;
        once it dies the control keeps decaying and the difference keeps drifting."""
        out = []
        for v in curve:
            if v > 0.5 and (not out or abs(v - out[-1]) > 0.5):
                out.append(v)
        return out

    def test_a_surviving_building_takes_exactly_three_waves(self):
        waves = self._waves(self._damage_curve("inferno_tower"))
        self.assertEqual(3, len(waves), "expected 3 waves, got %s" % waves)
        per = self.eq.spell_build_dmg
        for i, cum in enumerate(waves, start=1):
            self.assertAlmostEqual(cum, per * i, delta=1.0)

    def test_a_surviving_troop_takes_exactly_three_waves(self):
        waves = self._waves(self._damage_curve("knight"))
        self.assertEqual(3, len(waves), "expected 3 waves, got %s" % waves)
        for i, cum in enumerate(waves, start=1):
            self.assertAlmostEqual(cum, self.eq.spell_dmg * i, delta=1.0)

    def test_the_total_is_three_waves_not_one(self):
        """The regression this file exists for: one blast would be a third of this."""
        self.assertAlmostEqual(self._damage_curve("knight")[-1], self.eq.spell_dmg * 3, delta=1.0)

    def test_flying_troops_are_untouched(self):
        self.assertEqual([], self._waves(self._damage_curve("minions")))

    def test_it_damages_a_concealed_tesla(self):
        """The signature Earthquake property -- a hidden Tesla is otherwise untouchable."""
        self.assertGreater(self._damage_curve("tesla", hidden=True)[-1], 0.0)

    def test_it_kills_the_cheap_buildings_outright(self):
        """Wiki: "The Earthquake does enough damage to destroy a Goblin Cage by itself"."""
        for b in ("tombstone", "goblin_cage", "cannon"):
            with self.subTest(building=b):
                self.assertGreaterEqual(self.eq.spell_build_dmg * 3,
                                        build_spec(self.env.db, b, 11).hp,
                                        "%s survives a full Earthquake" % b)

    def test_it_does_NOT_delete_a_tesla_on_damage_alone(self):
        """1039 over three waves against 1152 hitpoints at equal level. It kills a Tesla in a real
        match because the Tesla is ALSO bleeding its own lifetime away -- measured below -- but a
        model that killed it on spell damage alone would overstate the card."""
        self.assertLess(self.eq.spell_build_dmg * 3, build_spec(self.env.db, "tesla", 11).hp)

    def test_a_tesla_still_dies_once_its_lifetime_decay_is_included(self):
        eng = self.env.eng
        eng.units.clear(); eng.spells.clear(); eng.zones.clear()
        sp = build_spec(self.env.db, "tesla", 11)
        u = Unit(spec=sp, team=1, x=0.5, y=0.40, hp=sp.hp)
        eng.units.append(u)
        eng.spells.append(_Spell(0, 0.5, 0.40, self.eq, 0.0))
        for _ in range(40):
            eng.advance(0.1)
        self.assertLessEqual(u.hp, 0.0)

    def test_an_inferno_tower_survives_it(self):
        """It cripples an Inferno but does not delete one -- 'Earthquake combined with a Zap can
        severely cripple, IF NOT take out' it. A model that killed it outright would make the deck
        look better than it is."""
        self.assertLess(self.eq.spell_build_dmg * 3,
                        build_spec(self.env.db, "inferno_tower", 11).hp)

    def test_crown_towers_take_three_waves(self):
        eng = self.env.eng
        self.env.reset()
        eng.units.clear(); eng.spells.clear(); eng.zones.clear()
        tw = eng.towers[1][0]
        hp0 = tw.hp
        eng.spells.append(_Spell(0, tw.x, tw.y, self.eq, 0.0))
        for _ in range(40):
            eng.advance(0.1)
        self.assertAlmostEqual(hp0 - tw.hp, self.eq.spell_tower_dmg * 3, delta=1.0)

    def test_it_applies_the_fifty_percent_slow(self):
        eng = self.env.eng
        eng.units.clear(); eng.spells.clear(); eng.zones.clear()
        kn = build_spec(self.env.db, "knight", 11)
        u = Unit(spec=kn, team=1, x=0.5, y=0.40, hp=kn.hp)
        eng.units.append(u)
        eng.spells.append(_Spell(0, 0.5, 0.40, self.eq, 0.0))
        for _ in range(3):
            eng.advance(0.1)
        self.assertAlmostEqual(0.5, u.slow_mult, places=3)
        self.assertGreater(u.slow_left, 0.0)


class ZonePathRegressionTests(unittest.TestCase):
    """The building bonus and the hidden/flying rules live in the SHARED zone tick, so the other
    lingering-field spells have to come through unchanged."""

    @classmethod
    def setUpClass(cls):
        cls.env = SimMatchEnv(Config.load())
        cls.env.reset()

    def _knight_damage(self, spell_key):
        eng = self.env.eng
        s = build_spec(self.env.db, spell_key, 11)
        eng.units.clear(); eng.spells.clear(); eng.zones.clear()
        kn = build_spec(self.env.db, "knight", 11)
        u = Unit(spec=kn, team=1, x=0.5, y=0.40, hp=kn.hp)
        eng.units.append(u)
        eng.spells.append(_Spell(0, 0.5, 0.40, s, 0.0))
        for _ in range(int((s.zone_s or 1) * 10) + 5):
            eng.advance(0.1)
        return kn.hp - u.hp, s

    def test_poison_still_ticks_repeatedly_and_gains_no_building_bonus(self):
        """Not pinned to its full 8 ticks: the Knight WALKS, and leaves the radius partway through.
        What matters for this regression is that it still ticks more than once and that the new
        building branch never fires for it."""
        dealt, s = self._knight_damage("poison")
        self.assertEqual(0.0, s.spell_build_dmg, "poison must have no building bonus")
        self.assertGreater(dealt, s.spell_dmg * 2)

    def test_void_still_ticks(self):
        dealt, _ = self._knight_damage("void")
        self.assertGreater(dealt, 0.0)


if __name__ == "__main__":
    unittest.main()
