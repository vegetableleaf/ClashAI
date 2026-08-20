"""The SIM judged spells at CAST time, so it taught aim-where-they-stand.

User, 2026-08-20 (reporting it a second time): "the model is determining spell hit/miss based on
the targeting area, and not the presence of the target when the spell actually lands."

The live env was fixed first; the sim -- which is where PPO actually learns -- was still charging
spell_waste immediately from `_spell_no_target(nx, ny, spec)`, i.e. "is anything within the waste
radius of the aim RIGHT NOW". The engine resolves a spell later (`_Spell.t` counts down; a rocket's
cast plus travel runs over a second at range) and troops walk the whole time. So every rollout
taught the policy to aim where the target STANDS and charged it for leading -- which is the same
"doesn't lead its target" behaviour reported separately.

The verdict is now the user's own test: "if nothing gets damaged... the spell was a miss". Damage
dealt, not proximity -- which also makes it indifferent to HOW the spell works, so a rolling Log,
a lingering Poison zone, a Tornado's spread damage and an instant Rocket are judged by one
question.
"""
from __future__ import annotations

import io
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from clashrl.config import Config                   # noqa: E402
from clashrl.sim.engine import Unit, build_spec     # noqa: E402
from clashrl.sim.env import SimMatchEnv             # noqa: E402


class ImpactVerdictTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.env = SimMatchEnv(Config.load(), seed=4)
        cls.env.reset()
        cls.spec = next((s for s in cls.env.specs if getattr(s, "spell_delay", 0.0)), None)

    def setUp(self):
        if self.spec is None:
            self.skipTest("this deck holds no delayed damage spell")
        self.env.eng.units.clear()
        self.env._pending_spell_checks = []

    def _fires(self):
        t = self.env.rw_stats.run.get("spell_waste")
        return int(getattr(t, "fires", 0) or 0) if t is not None else 0

    def _target(self, hp_mult=1.0):
        sp = build_spec(self.env.eng.db, "knight", 11)
        u = Unit(spec=sp, team=1, x=0.50, y=0.30, hp=sp.hp * hp_mult)
        u.deploy_left = 0.0
        self.env.eng.units.append(u)
        return u

    def _settle(self):
        self.env.eng.t += 10.0          # the check comes due
        self.env._settle_spell_casts()

    def test_a_spell_that_damaged_something_is_not_a_waste(self):
        u = self._target()
        before = self._fires()
        self.env._arm_spell_check(0.50, 0.30, self.spec)
        u.hp -= 200.0                    # it landed and hurt something
        self._settle()
        self.assertEqual(before, self._fires())

    def test_a_spell_that_damaged_nothing_IS_a_waste(self):
        self._target()
        before = self._fires()
        self.env._arm_spell_check(0.50, 0.30, self.spec)
        self._settle()                   # nothing lost any HP
        self.assertEqual(before + 1, self._fires())

    def test_a_spell_that_KILLED_its_target_counts_as_a_hit(self):
        """A dead unit is removed from the engine entirely, so a naive HP lookup would find
        nothing and call the kill a miss -- the worst possible inversion."""
        u = self._target()
        before = self._fires()
        self.env._arm_spell_check(0.50, 0.30, self.spec)
        self.env.eng.units.remove(u)
        self._settle()
        self.assertEqual(before, self._fires())

    def test_tower_chip_counts_as_a_hit(self):
        """Chipping a tower is a legitimate target for the spells whose doctrine says so, and it
        must not read as an empty cast."""
        before = self._fires()
        self.env._arm_spell_check(0.50, 0.30, self.spec)
        tw = self.env.eng.towers[1][0]
        tw.hp = max(1.0, tw.hp - 300.0)
        self._settle()
        self.assertEqual(before, self._fires())

    def test_the_verdict_is_not_settled_before_the_spell_lands(self):
        """The whole bug: judging early is judging the aim rather than the impact."""
        self._target()
        before = self._fires()
        self.env._arm_spell_check(0.50, 0.30, self.spec)
        self.env._settle_spell_casts()          # no time has passed
        self.assertEqual(before, self._fires())
        self.assertTrue(self.env._pending_spell_checks, "the check was consumed early")


class NoCastTimeVerdictTests(unittest.TestCase):
    """Guard the regression itself: nothing may charge spell_waste at cast again."""

    def _src(self):
        p = os.path.join(os.path.dirname(__file__), "..", "src", "clashrl", "sim", "env.py")
        with io.open(p, encoding="utf-8") as fh:
            return fh.read()

    def test_the_cast_path_arms_a_check_instead_of_judging(self):
        src = self._src()
        i = src.index("if card_id in self.damage_spell_ids:")
        # CODE ONLY: the comment in that block quotes the old call to explain the bug, so a raw
        # substring search matches the explanation and fails on a correct file.
        window = chr(10).join(ln for ln in src[i:i + 1600].splitlines()
                              if not ln.lstrip().startswith("#"))
        self.assertIn("_arm_spell_check", window,
                      "the cast path no longer defers the verdict")
        self.assertNotIn("_spell_no_target(nx, ny, spec)", window,
                         "spell_waste is being charged at CAST again -- that judges the aim, not "
                         "the impact, and teaches the policy never to lead a moving target")

    def test_the_settle_step_runs_every_decision(self):
        src = self._src()
        self.assertIn("self._settle_spell_casts()", src,
                      "landed spells are never settled, so spell_waste can never fire")


if __name__ == "__main__":
    unittest.main(verbosity=1)
