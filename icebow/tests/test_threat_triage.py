"""Triage: is a threat worth spending a card on?

The gap this closes was reported from live play -- the model "defending" a lone Skeletons. Every
counter rule in the project answered "what beats X"; none asked "is X worth beating". The answer
is computable from our own card DB, so it is code, not prose in a prompt, and it is tested here
rather than left to a 7B model that got it wrong repeatedly on tools/llm_eval.py.
"""
from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from clashrl import threat_value as tv          # noqa: E402
from clashrl.cards import CardDB                # noqa: E402
from clashrl.config import Config               # noqa: E402


class TestIgnoreCost(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.db = CardDB(Config.load())

    def test_a_lone_skeletons_is_not_worth_a_card(self):
        """The reported bug, as a number: under half a percent of a tower."""
        self.assertLess(tv.ignore_cost_frac(self.db, "skeletons"), 0.01)
        self.assertEqual(tv.triage(self.db, "skeletons"), "ignore")

    def test_small_support_is_ignorable(self):
        for base in ("spear_goblins", "bats", "bomber", "guards"):
            with self.subTest(base=base):
                self.assertEqual(tv.triage(self.db, base), "ignore")

    def test_real_threats_must_be_answered(self):
        for base in ("giant", "hog_rider", "golem", "balloon", "mini_pekka"):
            with self.subTest(base=base):
                self.assertEqual(tv.triage(self.db, base), "must_answer")

    def test_outranging_units_are_never_ignorable(self):
        """The correction the naive model needed. A Princess has almost no health, so a
        tower-trade model calls her free -- but she outranges the tower by 1.5 tiles and never
        enters the trade at all. Same for siege: it chips from across the river forever."""
        for base in ("princess", "x_bow", "mortar"):
            with self.subTest(base=base):
                self.assertEqual(tv.ignore_cost_frac(self.db, base), float("inf"))
                self.assertEqual(tv.triage(self.db, base), "must_answer")

    def test_unknown_cards_are_never_ignorable(self):
        self.assertEqual(tv.ignore_cost_frac(self.db, "not_a_real_card"), float("inf"))

    def test_threats_add_up(self):
        """Three ignorable units arriving together are one real push -- reading the push as a
        whole is the entire skill, so triage is a property of the GROUP."""
        one = tv.group_ignore_frac(self.db, ["skeletons"])
        many = tv.group_ignore_frac(self.db, ["skeletons"] * 3 + ["bats", "spear_goblins"])
        self.assertGreater(many, one)
        self.assertGreater(many, tv.ignore_cost_frac(self.db, "skeletons"))

    def test_a_group_containing_a_real_threat_is_unbounded_or_answerable(self):
        got = tv.group_ignore_frac(self.db, ["skeletons", "giant"])
        self.assertGreaterEqual(got, tv.IGNORE_FRAC)


if __name__ == "__main__":
    unittest.main()
