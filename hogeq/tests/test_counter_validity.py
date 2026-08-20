"""The advisor suggested impossible counters (user, 2026-08-20): "placing knight on a balloon
(knight can't even see the balloon) or rocketing wall breakers (a horrible elixir trade)".

Both were already forbidden IN WORDS by the advisor prompt, and both shipped anyway -- the same
lesson as the triage tier: qwen ignores the rule in capitals, the KB does not. So the veto is
CODE (clashrl.threat_value.pick_invalid), shared by the live advisor pick gate and the sim's
doctrine prior so neither side can offer what the other refuses.

These assertions are KB-grounded, not opinion: `attacks_air` and `is_flying` come from the card
database, so a card that literally cannot reach a flying unit can never be nominated against one.
"""
from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from clashrl import threat_value as tv        # noqa: E402
from clashrl.cards import CardDB              # noqa: E402
from clashrl.config import Config             # noqa: E402


class _Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.db = CardDB(Config.load())

    def invalid(self, card, threat):
        return tv.pick_invalid(self.db, card, threat)


class AirReachTests(_Base):
    """You cannot counter what you cannot touch."""

    def test_the_reported_bug_knight_on_a_balloon(self):
        self.assertIsNotNone(self.invalid("knight", ["balloon"]),
                             "the exact reported suggestion is still legal")

    def test_ground_only_spells_cannot_answer_air(self):
        """the_log ROLLS and earthquake SHAKES THE GROUND -- neither reaches a balloon, however
        much a guide's prose implies 'spells answer everything'."""
        for spell in ("the_log", "earthquake"):
            self.assertIsNotNone(self.invalid(spell, ["balloon"]),
                                 "%s was allowed against a flying unit" % spell)

    def test_air_capable_cards_are_allowed(self):
        for card in ("tesla", "ice_wizard", "rocket"):
            self.assertIsNone(self.invalid(card, ["balloon"]),
                              "%s was wrongly vetoed against air" % card)

    def test_tornado_is_allowed_against_air(self):
        """It deals no meaningful damage but it REPOSITIONS flying units -- dragging a balloon
        into an activated king tower is the deck's actual answer."""
        self.assertIsNone(self.invalid("tornado", ["balloon"]))

    def test_a_mixed_group_does_not_veto_ground_cards(self):
        """Only an ALL-flying group is untouchable. A balloon escorted by a hog still has a hog
        in it, and the knight has real work to do."""
        self.assertIsNone(self.invalid("knight", ["balloon", "hog_rider"]))

    def test_swarms_cannot_answer_a_minion_horde(self):
        self.assertIsNotNone(self.invalid("skeletons", ["minion_horde"]))

    def test_an_empty_group_vetoes_nothing(self):
        """No threat = an offensive play (a bow on a quiet board); the veto must not fire."""
        self.assertIsNone(self.invalid("knight", []))
        self.assertIsNone(self.invalid("rocket", []))


class TradeSanityTests(_Base):
    """A spell that costs far more than everything it erases is a losing move by itself."""

    def test_the_reported_bug_rocket_on_wall_breakers(self):
        self.assertIsNotNone(self.invalid("rocket", ["wall_breakers"]),
                             "6 elixir on a 2-elixir pair is still allowed")

    def test_the_cheap_answer_is_allowed(self):
        self.assertIsNone(self.invalid("the_log", ["wall_breakers"]))

    def test_skeletons_on_wall_breakers_stays_legal(self):
        """User, 2026-08-20: skeletons DO answer wall breakers when placed so the princess tower
        helps. A body is not spent the way a spell is, so the trade rule must not touch it."""
        self.assertIsNone(self.invalid("skeletons", ["wall_breakers"]))

    def test_a_rocket_on_a_real_group_is_allowed(self):
        """The rocket is not banned -- it is banned on CHEAP groups. Three Musketeers is exactly
        what it is for."""
        self.assertIsNone(self.invalid("rocket", ["three_musketeers"]))

    def test_a_rocket_on_a_stacked_push_is_allowed(self):
        self.assertIsNone(self.invalid("rocket", ["musketeer", "musketeer", "witch"]))

    def test_troops_are_never_trade_vetoed(self):
        """A defending troop survives and keeps working; only spells are judged on price."""
        self.assertIsNone(self.invalid("knight", ["skeletons"]))

    def test_a_spawn_spell_answer_is_not_trade_vetoed(self):
        """Graveyard/goblin_barrel are not 'answers' in this sense; the rule targets damage
        spells being thrown at cheap bodies."""
        self.assertIsNone(self.invalid("graveyard", ["skeletons"]))


class SharedRulesTests(_Base):
    """The live gate and the sim prior must veto identically -- that is why this lives in a
    module rather than in either caller's closure."""

    def test_the_sim_doctrine_imports_the_same_function(self):
        import inspect
        from clashrl.sim import doctrine
        src = inspect.getsource(doctrine._veto_impossible)
        self.assertIn("threat_value.pick_invalid", src,
                      "the sim veto drifted off the shared rule")

    def test_the_live_gate_imports_the_same_function(self):
        import io
        p = os.path.join(os.path.dirname(__file__), "..", "src", "clashrl", "train_rl.py")
        with io.open(p, encoding="utf-8") as fh:
            src = fh.read()
        self.assertIn("threat_value.pick_invalid", src,
                      "the live advisor gate drifted off the shared rule")

    def test_the_sim_veto_spares_offensive_nominations(self):
        """A nomination with nothing committed on our half is an ATTACK (rocket at their
        collector, the quiet-board bow) and must pass through untouched."""
        import inspect
        from clashrl.sim import doctrine
        src = inspect.getsource(doctrine._veto_impossible)
        self.assertIn("if not committed:", src,
                      "the sim veto no longer exempts offensive nominations")


if __name__ == "__main__":
    unittest.main(verbosity=1)


class PrimaryThreatTests(_Base):
    """A group is not one threat -- it has a PRIMARY, and the answer must reach THAT one.

    `pick_invalid` only rejects a card that can touch NOTHING in the group, which is the right
    rule for a hard veto and the wrong one for choosing an answer: one skeleton walking beside a
    Balloon made The Log a "legal" answer to a Balloon. Since a Balloon essentially never arrives
    alone, the all-air test almost never fired on the board it was written for.
    """

    def primary(self, group):
        return tv.primary_threat(self.db, group)

    def misses(self, base, group):
        return tv.misses_primary(self.db, base, group)

    def test_the_reported_bug_log_on_a_balloon_with_chaff(self):
        """THE user report. A lone Balloon was already vetoed; a Balloon plus anything on the
        ground was not, and that is the board the play actually happens on."""
        self.assertEqual(self.primary(["balloon", "skeletons"]), "balloon")
        self.assertIsNotNone(self.misses("the_log", ["balloon", "skeletons"]))
        self.assertIsNotNone(self.misses("the_log", ["balloon", "goblin_gang"]))

    def test_the_primary_is_the_costliest_thing_to_ignore(self):
        """Ranked by the project's own triage number per card, not a hand-written list."""
        self.assertEqual(self.primary(["hog_rider", "skeletons"]), "hog_rider")
        self.assertEqual(self.primary(["giant", "musketeer"]), "giant")

    def test_a_card_that_reaches_the_primary_is_allowed(self):
        """The Log against minions+knight is fine: the KNIGHT is the primary and it walks."""
        self.assertEqual(self.primary(["minions", "knight"]), "knight")
        self.assertIsNone(self.misses("the_log", ["minions", "knight"]))

    def test_air_capable_answers_are_never_blocked(self):
        for base in ("tornado", "rocket", "ice_wizard", "tesla"):
            self.assertIsNone(self.misses(base, ["balloon", "skeletons"]),
                              "%s can reach the balloon" % base)

    def test_an_empty_group_has_no_primary(self):
        self.assertIsNone(self.primary([]))
        self.assertIsNone(self.misses("the_log", []))


class AdvisorGateWiringTests(_Base):
    """The veto has to be ASKED. It was correct all along and simply never consulted.

    `_situation` describes every corroborated enemy to the advisor; `_counted_threats` also
    requires `gy >= 0.42`. A Balloon still on their own side is therefore in the PROMPT and not in
    the group -- so `threat_bases` was empty, `needs_answer` was False, and the gate read
    `why = _pick_invalid(...) if needs_answer else None`, accepting the pick unvalidated. That is
    the lone-Balloon report: not a wrong rule, an unasked one.

    Source-level because the gate is a closure inside train_rl and cannot be imported; the
    behaviour it guards is covered by the threat_value tests above.
    """

    def setUp(self):
        import pathlib
        p = pathlib.Path(__file__).resolve().parents[1] / "src" / "clashrl" / "train_rl.py"
        self.src = p.read_text(encoding="utf-8")

    def test_the_pick_is_validated_against_what_the_advisor_was_shown(self):
        self.assertIn("_visible_enemy_bases", self.src,
                      "the advisor's pick must be checkable against the enemies it was DESCRIBED")
        self.assertIn("_val = tuple(threat_bases) or tuple(seen_bases or ())", self.src,
                      "an empty triage group must fall back to the described enemies")

    def test_validity_is_not_gated_on_worth(self):
        """'Can this card touch it' must not be conditional on 'is it worth a card'."""
        self.assertNotIn("_pick_invalid(pbase, threat_bases) if needs_answer else None", self.src,
                         "the veto is gated on needs_answer again -- a quiet board skips it")
