"""THREAT PRIORITY: rank what is on the board instead of blending it.

User, 2026-08-20: "the model needs to assign threat priorities in its detector analysis. right now
it's committing elixir to defend a small threat while leaving a large threat completely ignored."

TWO causes, both here.

1. `identity_threat_vector` OR'd every recognised threat's role bits together and took the MAXIMUM
   depth across all of them. A Golem at the bridge beside a lone Skeletons walking deep came out
   as "tank + swarm, 80% of the way in" -- a unit that is on no board anywhere, whose urgency
   belonged to the harmless card. Answer that vector and you answer the Skeletons.

2. Six KAMIKAZE cards were priced as INFINITE threats. They carry `hitpoints` and `damage` but no
   `hit_speed`, because they hit once and die; `_bodies` requires all three and returned None,
   which `ignore_cost_frac` reads as "the tower cannot resolve this" -> never ignorable. So a
   1-elixir Ice Spirit outranked a Golem, and Wall Breakers read as must-answer-at-any-cost --
   the same over-commitment behind the earlier "why is it rocketing wall breakers" report.
"""
from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from clashrl import card_threat as ct        # noqa: E402
from clashrl import threat_value as tv       # noqa: E402
from clashrl.cards import CardDB             # noqa: E402
from clashrl.config import Config            # noqa: E402

INF = float("inf")


class _Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.db = CardDB(Config.load())

    def vec(self, items):
        return ct.identity_threat_vector(items, self.db)

    def roles(self, items):
        v = self.vec(items)
        return {n for n, i in (("tank", 1), ("swarm", 2), ("air", 3), ("building", 4),
                               ("wincon", 5), ("bt", 6)) if v[i] >= 0.5}


class PriorityTests(_Base):
    """The vector must describe the threat that actually has to be answered."""

    def test_the_reported_case_a_golem_outranks_a_deep_skeletons(self):
        """The depth reported must be the GOLEM's, not the Skeletons' -- urgency is the urgency of
        the thing you have to answer."""
        v = self.vec([("golem", 0.30), ("skeletons", 0.80)])
        self.assertAlmostEqual(0.30, float(v[7]), places=2,
                               msg="depth came from the harmless card again")

    def test_a_stray_skeletons_cannot_paint_swarm_onto_a_golem(self):
        """The OR'd bits produced a chimera: tank AND swarm, which is not on the board."""
        self.assertNotIn("swarm", self.roles([("golem", 0.30), ("skeletons", 0.80)]))
        self.assertIn("tank", self.roles([("golem", 0.30), ("skeletons", 0.80)]))

    def test_a_real_multi_card_push_still_reads_as_a_push(self):
        """Only IGNORABLE cards are silenced. A Witch alongside a Golem is a real second problem
        and must still light her own bits."""
        roles = self.roles([("golem", 0.30), ("witch", 0.28)])
        self.assertIn("tank", roles)

    def test_a_lone_ignorable_threat_still_describes_itself(self):
        """When everything present is ignorable there is nothing better to report -- and triage
        refuses the board anyway, so this must not go blank."""
        v = self.vec([("skeletons", 0.80)])
        self.assertEqual(1.0, v[0])
        self.assertAlmostEqual(0.80, float(v[7]), places=2)
        self.assertIn("swarm", self.roles([("skeletons", 0.80)]))

    def test_an_empty_board_is_still_empty(self):
        self.assertEqual(0.0, float(self.vec([])[0]))

    def test_depth_follows_danger_not_position(self):
        """The whole point: the DEEPEST unit is not automatically the one to answer."""
        deep_small = self.vec([("hog_rider", 0.40), ("ice_spirit", 0.90)])
        self.assertAlmostEqual(0.40, float(deep_small[7]), places=2)


class KamikazePricingTests(_Base):
    """A card that hits once and dies is not an unanswerable threat."""

    def test_the_spirits_are_no_longer_infinite(self):
        for c in ("ice_spirit", "fire_spirit", "electro_spirit", "heal_spirit"):
            self.assertLess(tv.ignore_cost_frac(self.db, c), INF,
                            "%s is priced as an unanswerable threat again" % c)

    def test_a_one_elixir_spirit_does_not_outrank_a_golem(self):
        self.assertLess(tv.ignore_cost_frac(self.db, "ice_spirit"),
                        tv.ignore_cost_frac(self.db, "golem"))

    def test_wall_breakers_are_cheap_not_must_answer(self):
        """They were infinite, which is the over-commitment behind the earlier rocket report."""
        self.assertLess(tv.ignore_cost_frac(self.db, "wall_breakers"), INF)
        self.assertNotEqual("must_answer", tv.triage(self.db, "wall_breakers"))

    def test_what_a_kamikaze_LEAVES_BEHIND_is_counted(self):
        """A Battle Ram breaks into two Barbarians and a Skeleton Barrel drops seven Skeletons --
        those bodies are resolved by the tower, so they belong in the price. The Ram must
        therefore cost more than its bare burst."""
        self.assertGreater(tv.ignore_cost_frac(self.db, "battle_ram"),
                           tv.ignore_cost_frac(self.db, "wall_breakers"))
        self.assertLess(tv.ignore_cost_frac(self.db, "battle_ram"), INF)

    def test_genuinely_unanswerable_cards_are_still_infinite(self):
        """The rule this was masquerading as is real: anything that OUTRANGES the tower chips
        forever and can never be ignored."""
        for c in ("princess", "mortar", "x_bow"):
            self.assertEqual(INF, tv.ignore_cost_frac(self.db, c),
                             "%s must stay unbounded -- it outranges the tower" % c)

    def test_an_unknown_card_is_still_never_assumed_safe(self):
        self.assertEqual(INF, tv.ignore_cost_frac(self.db, "no_such_card_xyz"))


if __name__ == "__main__":
    unittest.main(verbosity=1)
