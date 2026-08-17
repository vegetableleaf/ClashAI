"""Save the Tesla for the win condition.

Reported from sim view (user, 2026-08-16): the model plants a Tesla in a GOOD SPOT on an EMPTY
board. Its 30 s lifetime then runs out, and the opponent's win condition arrives with no building
left to pull it. Nothing priced that -- spell_waste covers an empty cast and there was no
equivalent for a building, so an early Tesla was free.

Two halves, tested together because either alone is wrong: spending it on nothing must COST, and
a win condition on the board must make it the top nomination.
"""
from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from clashrl.config import Config                # noqa: E402
from clashrl.sim import doctrine as D            # noqa: E402
from clashrl.sim.engine import Unit, build_spec  # noqa: E402
from clashrl.sim.env import SimMatchEnv          # noqa: E402

WINCON_DECK = ["hog_rider", "fireball", "knight", "musketeer"]
NO_WINCON_DECK = ["knight", "fireball", "archers", "musketeer"]


class TeslaDisciplineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.env = SimMatchEnv(Config.load())
        cls.env.reset()

    def _scene(self, units, opp=WINCON_DECK, hand=()):
        env = self.env
        env.eng.units.clear()
        for base, y in units:
            sp = build_spec(env.db, base, 11)
            env.eng.units.append(Unit(spec=sp, team=1, x=0.5, y=y, hp=sp.hp))
        env.opponent.cards = list(opp)
        env.eng.elixir[0] = 10.0
        self._deal(hand)
        return env

    def _deal(self, bases):
        """Force these cards into the four-card hand.

        The nomination rules go through ``_holdable``, which requires the card to be IN HAND -- so a
        scene that does not pin the hand is really testing the deal. This suite passed on the IceBow
        deck only because that deck's opening cycle happened to contain the Tesla; on Hog EQ the deal
        is hog/skeletons/ice_spirit/firecracker_evo and every Tesla assertion failed against a
        doctrine that was working correctly.
        """
        env = self.env
        for base in reversed(list(bases)):
            cid = next(i for i, k in enumerate(env.deck_keys) if k == base)
            slot = env.slot_of[cid]
            env.cycle.remove(slot)
            env.cycle.insert(0, slot)
        if bases:
            in_hand = {env.deck_keys[i] for i in env._hand_ids()}
            missing = set(bases) - in_hand
            assert not missing, "failed to deal %s (hand is %s)" % (sorted(missing), sorted(in_hand))

    def _tesla_id(self):
        return next(i for i, k in enumerate(self.env.deck_keys) if k == "tesla")

    def _nominations(self, env):
        return {env.deck_keys[k]: v for k, v in (D.doctrine_cards(env) or {}).items()}

    # -- spending it on nothing costs -------------------------------------------------
    def test_an_empty_board_tesla_is_charged(self):
        env = self._scene([])
        self.assertLess(env._building_waste(self._tesla_id()), 0.0)

    def test_a_tesla_against_an_ignorable_board_is_charged(self):
        env = self._scene([("skeletons", 0.60)])
        self.assertLess(env._building_waste(self._tesla_id()), 0.0)

    def test_a_tesla_against_a_real_threat_is_free(self):
        env = self._scene([("hog_rider", 0.55)])
        self.assertEqual(env._building_waste(self._tesla_id()), 0.0)

    def test_no_charge_when_they_have_no_win_condition_left_to_bring(self):
        """The penalty is for spending what you are SAVING. If their deck holds no win condition,
        there is nothing to save it for and the building is just a defensive card."""
        env = self._scene([], opp=NO_WINCON_DECK)
        self.assertEqual(env._building_waste(self._tesla_id()), 0.0)

    def test_no_charge_once_their_win_condition_is_already_committed(self):
        """It is on the board, so the Tesla is answering it, not being spent early."""
        env = self._scene([("hog_rider", 0.55)], opp=WINCON_DECK)
        self.assertFalse(env._opp_holds_wincon())
        self.assertEqual(env._building_waste(self._tesla_id()), 0.0)

    def test_the_xbow_is_never_charged(self):
        """A building by kind, but it is our WIN CONDITION -- planting it on a quiet board is the
        correct play, and the siege flag is what separates the two."""
        env = self._scene([])
        for i, k in enumerate(env.deck_keys):
            if k.startswith("x_bow"):
                self.assertEqual(env._building_waste(i), 0.0)

    # -- and it gets priority for the win condition -----------------------------------
    def test_tesla_is_not_nominated_on_a_quiet_board(self):
        env = self._scene([], hand=("tesla",))
        self.assertNotIn("tesla", self._nominations(env))

    def test_tesla_tops_the_table_against_a_win_condition(self):
        for wincon in ("hog_rider", "giant", "balloon"):
            with self.subTest(wincon=wincon):
                env = self._scene([(wincon, 0.55)], hand=("tesla",))
                nom = self._nominations(env)
                self.assertIn("tesla", nom)
                self.assertEqual(max(nom.values()), nom["tesla"],
                                 "tesla should outrank every other card vs a win condition")

    def test_a_non_wincon_troop_does_not_summon_the_tesla_rule(self):
        env = self._scene([("knight", 0.55)], opp=NO_WINCON_DECK)
        self.assertNotIn("tesla", self._nominations(env))


if __name__ == "__main__":
    unittest.main()
