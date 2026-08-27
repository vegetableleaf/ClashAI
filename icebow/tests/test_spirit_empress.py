"""Spirit Empress -- the 2-in-1 card (user-reported as wrongly represented, fixed 2026-08-19).

What the sim had: a 4-elixir, 1798-HP flying melee-curated hybrid. The 1798/309 came from the
2026-08-14 wiki import catching the Fandom page MID-EDIT-WAR (hp cycled 1697->2046->2023->1798
across Aug 9-14 with no balance change behind any value); the 4 elixir was a default because no
layer supplied one; a stray `range: melee` curation fought the imported ranged stats.

What she is (Supercell balance posts back-chained to 2026-05-04, cross-checked against live
aggregator values): ONE card, TWO forms, picked automatically at cast by the caster's CURRENT
elixir -- under 3 uncastable, [3, 6) the 3-elixir GROUND form, >= 6 the 6-elixir AIR form, and
exactly 6.0 is AIR (RoyaleAPI: "From 3 to 5.9 elixir: ground form. With 6 or more: flying form").
"""
from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from clashrl.config import Config                       # noqa: E402
from clashrl.sim.engine import build_spec               # noqa: E402
from clashrl.sim.env import SimMatchEnv                 # noqa: E402


class _Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.env = SimMatchEnv(Config.load())

    def fresh(self, elixir):
        self.env.reset()
        e = self.env.eng
        e.units.clear()
        e.elixir[1] = float(elixir)
        return e

    def cast(self, elixir):
        e = self.fresh(elixir)
        spec = build_spec(e.db, "spirit_empress", 11)
        ok = e.deploy(1, spec, 0.5, 0.3)
        if not ok:
            return e, None, 0.0
        u = [u for u in e.units if u.team == 1][-1]
        return e, u, float(elixir) - e.elixir[1]


class FormStatsTests(_Base):
    def test_ground_form_stats(self):
        g = build_spec(self.env.eng.db, "spirit_empress", 11)
        self.assertEqual(3, g.elixir)
        self.assertAlmostEqual(1121, g.hp, delta=1)
        self.assertAlmostEqual(309, g.hit_dmg, delta=1)   # I5, decisions.md #5: 309 is correct
        self.assertAlmostEqual(1.2, g.hit_speed, places=2)
        self.assertAlmostEqual(1.2, g.reach, places=2)     # melee: medium
        self.assertFalse(g.flying)
        self.assertFalse(g.attacks_air, "the ground form cannot hit air")
        self.assertAlmostEqual(1.5, g.speed, places=2)     # Fast (90) since 2026-03-02

    def test_air_form_stats(self):
        a = build_spec(self.env.eng.db, "spirit_empress_air", 11)
        self.assertEqual(6, a.elixir)
        self.assertAlmostEqual(1121, a.hp, delta=1)        # equal to ground since 2026-05-04
        self.assertAlmostEqual(309, a.hit_dmg, delta=1)    # same as ground; I5 #5: 309, not 307
        self.assertAlmostEqual(1.4, a.hit_speed, places=2)  # 1.5 -> 1.4 on 2025-07-10
        self.assertAlmostEqual(5.0, a.reach, places=2)     # 4.5 -> 5 on 2025-08-04
        self.assertTrue(a.flying)
        self.assertTrue(a.attacks_air)
        self.assertAlmostEqual(1.0, a.speed, places=2)     # Medium (60)

    def test_the_edit_war_values_are_gone(self):
        """1798 hp / 309 dmg / 4 elixir was the corrupted import; none may survive the curation."""
        for key in ("spirit_empress", "spirit_empress_air"):
            sp = build_spec(self.env.eng.db, key, 11)
            self.assertNotAlmostEqual(1798, sp.hp, delta=5)
            self.assertNotEqual(4, sp.elixir)


class FormSelectionTests(_Base):
    """The elixir gate, through the REAL deploy path (covers our side, scripted opponents and
    self-play alike -- deploy is the single choke point)."""

    def test_under_three_elixir_is_uncastable(self):
        _, u, _ = self.cast(2.9)
        self.assertIsNone(u)

    def test_three_elixir_casts_the_ground_form_for_three(self):
        _, u, charged = self.cast(3.0)
        self.assertIsNotNone(u)
        self.assertFalse(u.spec.flying)
        self.assertAlmostEqual(3.0, charged, places=3)

    def test_five_point_nine_is_still_ground(self):
        _, u, charged = self.cast(5.9)
        self.assertFalse(u.spec.flying)
        self.assertAlmostEqual(3.0, charged, places=3)

    def test_exactly_six_is_the_air_form_for_six(self):
        """The boundary the user asked about: at exactly 6.0 the AIR form casts."""
        _, u, charged = self.cast(6.0)
        self.assertTrue(u.spec.flying)
        self.assertAlmostEqual(6.0, charged, places=3)

    def test_ten_elixir_is_air(self):
        _, u, charged = self.cast(10.0)
        self.assertTrue(u.spec.flying)
        self.assertAlmostEqual(6.0, charged, places=3)

    def test_passing_the_air_key_below_six_still_yields_ground(self):
        """The form follows the ELIXIR, not the key the caller happened to hold."""
        e = self.fresh(4.0)
        spec = build_spec(e.db, "spirit_empress_air", 11)
        self.assertTrue(e.deploy(1, spec, 0.5, 0.3))
        u = [u for u in e.units if u.team == 1][-1]
        self.assertFalse(u.spec.flying)
        self.assertAlmostEqual(3.0, 4.0 - e.elixir[1], places=3)

    def test_the_ground_form_ignores_a_flying_attacker(self):
        """Ground-only targeting is the form's defining weakness -- a balloon overhead must not
        be acquired."""
        e = self.fresh(3.0)
        g = build_spec(e.db, "spirit_empress", 11)
        self.assertTrue(e.deploy(1, g, 0.5, 0.3))
        emp = [u for u in e.units if u.team == 1][-1]
        b = build_spec(e.db, "balloon", 11)
        from clashrl.sim.engine import Unit
        e.units.append(Unit(spec=b, team=0, x=0.5, y=0.32, hp=b.hp))
        for _ in range(30):
            e.advance(0.1)
        self.assertNotIn(getattr(emp.target, "spec", None) and emp.target.spec.base, ("balloon",))


if __name__ == "__main__":
    unittest.main(verbosity=1)
