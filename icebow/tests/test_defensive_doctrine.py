"""The defensive tranche from DOCTRINE_RESEARCH.md SS2-SS3 (2026-08-19, Hunter CR).

Four rules, each of which the sim was missing entirely. Three of them are ANTI-rules -- cases
where the old doctrine confidently proposed a play that a professional calls a mistake -- which is
why they are tested as suppressions rather than as new spots.

The X-Bow one is the highest-value item in the whole corpus: `xbow_into_push` measures **-276.0
over 69 fires and is never once positive**, the largest reward term by 4x. That term prices a
FORWARD bow dropped into a committed push and explicitly EXEMPTS a defensive bow. Hunter's rule
covers precisely the exempted case, and keys off the opponent's DECK rather than the board.
"""
from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from clashrl.config import Config                       # noqa: E402
from clashrl.sim import doctrine as D                   # noqa: E402
from clashrl.sim.engine import Unit, build_spec         # noqa: E402
from clashrl.sim.env import SimMatchEnv                 # noqa: E402

GW = 18


class _Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.env = SimMatchEnv(Config.load())

    def fresh(self):
        self.env.reset()
        e = self.env.eng
        e.units.clear()
        e.spells.clear()
        e.projectiles.clear()
        e.vortices.clear()
        return e

    def cid(self, base):
        for i, k in enumerate(self.env.deck_keys):
            if k == base or k == base + "_evo":
                return i
        raise AssertionError("%s not in deck" % base)

    def enemy(self, key, x, y, lvl=11):
        e = self.env.eng
        sp = build_spec(e.db, key, lvl)
        u = Unit(spec=sp, team=1, x=x, y=y, hp=sp.hp)
        u.deploy_left = 0.0
        e.units.append(u)
        return u

    def opp_deck(self, *bases):
        """Pin what the opponent is known to hold. `_opp_cards` reads env.opponent.cards."""
        self.env.opponent.cards = list(bases)
        return bases


class MidMapBowVsRocketDeckTests(_Base):
    """SS3 THE CENTRAL LESSON -- and the doctrine counterpart to xbow_into_push = -276."""

    def _bow_cells(self):
        return D.doctrine_cells(self.env, self.cid("x_bow")) or []

    def test_the_defensive_bow_exists_against_a_deck_without_rocket(self):
        """The control: suppressing this everywhere would just delete a good rule."""
        self.fresh()
        self.env._defensive = True
        self.opp_deck("hog_rider", "earthquake", "musketeer", "cannon")
        self.assertTrue(self._bow_cells(),
                        "the defensive bow vanished against a deck holding no Rocket")

    def test_no_defensive_bow_is_offered_against_a_rocket_deck(self):
        """'They rocket the bow, then your tower, then you rocket back' -- six elixir donated,
        and the deficit means no bow lock all game."""
        self.fresh()
        self.env._defensive = True
        self.opp_deck("hog_rider", "rocket", "musketeer", "cannon")
        self.assertFalse(self._bow_cells(),
                         "a mid-map defensive bow was offered against a Rocket deck")

    def test_the_offensive_bow_is_untouched_by_the_rule(self):
        """The prohibition is specifically about the mid-map/defensive bow; the offensive lock
        spots already have their own edge-column handling for rocket decks."""
        self.fresh()
        self.env._defensive = False
        self.opp_deck("hog_rider", "rocket", "musketeer", "cannon")
        self.assertTrue(self._bow_cells(),
                        "the offensive bow was suppressed, which is not the rule")


class TornadoKingActivationTests(_Base):
    """The king-activation pull itself still works. The 'do not do it to every hog' THROTTLE is
    deliberately NOT encoded -- see DOCTRINE_RESEARCH.md SS6.15: the spot is already gated on
    `king_asleep`, and a king that wakes STAYS awake, so the sim can offer that pull at most once
    per match. A throttle would price a repetition the engine cannot produce."""

    def test_a_deep_attacker_with_the_king_asleep_gets_the_activation_pull(self):
        e = self.fresh()
        e.towers[0][2].active = False
        self.enemy("hog_rider", 0.30, 0.60)
        self.assertTrue(D.doctrine_cells(self.env, self.cid("tornado")),
                        "no king-activation pull was offered at all")

    def test_no_activation_pull_once_the_king_is_already_awake(self):
        """This IS the throttle, and it is structural rather than a tuned rule: the activation
        spots are offered while the king sleeps and are gone once it wakes."""
        e = self.fresh()
        e.towers[0][2].active = False
        self.enemy("hog_rider", 0.30, 0.60)
        asleep = {c for c, _ in (D.doctrine_cells(self.env, self.cid("tornado")) or [])}
        self.assertTrue(asleep, "no activation cells offered while the king slept")
        e.towers[0][2].active = True
        awake = {c for c, _ in (D.doctrine_cells(self.env, self.cid("tornado")) or [])}
        self.assertTrue(asleep - awake,
                        "waking the king removed no cells -- the activation spots were never "
                        "gated on it, so the pull could repeat")


class TornadoBackForAirTests(_Base):
    """SS2.3 -- pull the flock BACKWARD so our own tower re-targets it."""

    def test_an_air_swarm_past_our_line_is_pulled_toward_our_tower(self):
        self.fresh()
        a = self.enemy("minions", 0.30, 0.60)
        self.enemy("minions", 0.32, 0.61)
        got = D.doctrine_cells(self.env, self.cid("tornado")) or []
        self.assertTrue(got, "no tornado cells against an air swarm in our half")
        best = max(got, key=lambda cw: cw[1])[0]
        best_row = best // GW
        flock_row = int(a.y * 24)
        self.assertGreaterEqual(best_row, flock_row,
                                "the pull aimed FORWARD of the flock, away from our tower")


class TeslaKingActivationTests(_Base):
    """SS2.2 -- 'if I didn't put that Tesla, we would have had king tower.'"""

    def _tesla_rows(self):
        got = D.doctrine_cells(self.env, self.cid("tesla")) or []
        return [c // GW for c, _ in got], got

    def test_the_tesla_moves_off_the_activator_while_the_king_sleeps(self):
        e = self.fresh()
        e.towers[0][2].active = True                      # king already awake -> normal placement
        self.enemy("hog_rider", 0.48, 0.66)
        awake_rows, got = self._tesla_rows()
        self.assertTrue(got, "no tesla cells at all")
        e.towers[0][2].active = False                     # activation is LIVE -> clear the line
        asleep_rows, _ = self._tesla_rows()
        self.assertLess(min(asleep_rows), min(awake_rows),
                        "the Tesla did not move toward the river to spare the king activation")

    def test_no_shift_when_the_deep_attacker_is_air(self):
        """A flyer will not wake the king by attacking it the same way; the ground case is the
        one Hunter describes, so the shift must not fire on every deep unit."""
        e = self.fresh()
        e.towers[0][2].active = True
        self.enemy("hog_rider", 0.48, 0.66)
        ground_rows, _ = self._tesla_rows()
        self.fresh()
        e.towers[0][2].active = False
        self.enemy("baby_dragon", 0.48, 0.66)
        air_rows, got = self._tesla_rows()
        if got:
            self.assertEqual(min(ground_rows), min(air_rows),
                             "an AIR unit triggered the king-activation clearance")


if __name__ == "__main__":
    unittest.main(verbosity=1)
