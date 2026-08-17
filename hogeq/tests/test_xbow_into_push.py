"""Price a forward X-Bow planted into a committed push.

WHY IT EXISTS, measured before writing it. The same board branched three ways over ~24 steps, a
Giant + Musketeer + Knight committed into our left lane at 10 elixir:

    bow ON the push      -25.56     leak -1.6, wincon_exec +0.42
    hold                 -29.15     leak -4.8
    bow OPPOSITE lane    -25.34     leak -1.6, wincon_exec +0.42

Planting into the push beat holding by +3.59; the CORRECT lane beat the wrong one by 0.22. Nearly
the whole gap was `leak` -- sitting at capacity bleeds -0.2 a step and playing anything stops it,
so the 6-elixir bow was simply the biggest leak-stopper in hand. `threat_miss_idle` was -23.0 in
all three branches, identical, so wasting the bow while the push killed us cost what holding did.

The reward was teaching "play something" at +3.2 against "play the right thing in the right place"
at +/-0.4. That does not fade with training, it sharpens.
"""
from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from clashrl.config import Config                        # noqa: E402
from clashrl.sim.engine import Unit, build_spec          # noqa: E402
from clashrl.sim.env import SimMatchEnv                  # noqa: E402
from clashrl.sim import view                            # noqa: E402
from clashrl import card_threat                         # noqa: E402

PUSH = (("giant", 0.56), ("musketeer", 0.50), ("knight", 0.54))
FORWARD_Y = 13.5 / 24.0          # row 13 -- where the deploy clamp puts every forward bow
DEEP_Y = 15.5 / 24.0             # row 15 -- the defensive centre band


class XbowIntoPushTests(unittest.TestCase):
    def setUp(self):
        self.env = SimMatchEnv(Config.load(), seed=5)
        self.env.reset()
        self.env.eng.units.clear()
        self.xid = next(i for i, k in enumerate(self.env.deck_keys) if k.startswith("x_bow"))

    def _put(self, units, x=0.28):
        for base, y in units:
            sp = build_spec(self.env.db, base, 11)
            self.env.eng.units.append(Unit(spec=sp, team=1, x=x, y=y, hp=sp.hp))

    def _charge(self, nx=0.28, ny=FORWARD_Y, card=None):
        return self.env._xbow_into_push(self.xid if card is None else card, nx, ny)

    def test_a_forward_bow_into_a_committed_push_is_charged(self):
        self._put(PUSH)
        self.assertLess(self._charge(), 0.0)

    def test_the_clamped_frontmost_ROW_counts_as_forward(self):
        """The bug this caught. The reward sees the POST-CLAMP position, and the clamp puts every
        legal forward bow on row 13 at y=0.5625 -- already past xbow_front (0.56). Gating on that
        threshold made the branch unreachable, so the term read 0.0 for exactly the placement it
        exists to price, and the diagnostic measurement came back completely unchanged."""
        self._put(PUSH)
        self.assertGreaterEqual(FORWARD_Y, self.env.xbow_front,
                                "row 13 sits past xbow_front -- that is why it cannot be the gate")
        self.assertLess(self._charge(ny=FORWARD_Y), 0.0)

    def test_a_DEFENSIVE_bow_is_not_charged(self):
        """Behind the forward band the bow is a second pull building, which is a real play."""
        self._put(PUSH)
        self.assertEqual(self._charge(ny=DEEP_Y), 0.0)

    def test_an_empty_board_is_not_charged(self):
        self.assertEqual(self._charge(), 0.0)

    def test_a_push_in_the_OTHER_lane_is_not_charged(self):
        """The whole point is the bow can survive elsewhere -- the opposite-lane play must keep
        its full credit or this becomes a blanket tax on ever playing the win condition."""
        self._put(PUSH, x=0.28)
        self.assertEqual(self._charge(nx=0.75), 0.0)

    def test_units_too_slight_to_kill_a_bow_are_not_charged(self):
        """A couple of Skeletons beside a bow is not the failure being described, and the same
        triage that decides 'is this worth answering' decides it here."""
        self._put((("skeletons", 0.54),))
        self.assertEqual(self._charge(), 0.0)

    def test_other_cards_are_untouched(self):
        self._put(PUSH)
        for i, k in enumerate(self.env.deck_keys):
            if not k.startswith("x_bow"):
                with self.subTest(card=k):
                    self.assertEqual(self._charge(card=i), 0.0)

    def test_the_penalty_outweighs_the_leak_relief_that_caused_this(self):
        """It has to beat the measured +3.59 that planting into a push earned over holding, or
        the behaviour survives the fix."""
        self._put(PUSH)
        self.assertLess(self._charge(), -3.59)


class XbowOverAggressionTests(unittest.TestCase):
    """Don't buy chip with the elixir the defence needed.

    The hole this closes, measured: threat_miss_idle charges -1.0 a step at 3 elixir or more and
    GOES SILENT below 3 -- the cheapest counter's cost. So spending down to 2 does not merely fail
    to answer the push, it stops the penalty for not answering it, and a 6-elixir bow from 8 buys
    that silence outright. Over-aggression was an escape hatch from the defensive term.
    """

    # A HOG push, not the Giant one. The Giant is absent from observation.detector_cards, so a
    # Giant push lights the identity block with EVERY role flag zero -- card_threat.counters then
    # matches nothing, threat_miss_idle is silent too, and this term correctly abstains rather
    # than blaming the model for not casting an answer the role table cannot name. That is the
    # labelling blind spot, not an over-aggression hole, so the invariant is tested on a threat
    # the table CAN name.
    NAMED_PUSH = (("hog_rider", 0.56), ("musketeer", 0.52))

    def _env(self, left, opp_elixir=6.0, push=None):
        push = self.NAMED_PUSH if push is None else push
        env = SimMatchEnv(Config.load(), seed=5)
        env.reset()
        env.eng.units.clear()
        for base, y in push:
            sp = build_spec(env.db, base, 11)
            env.eng.units.append(Unit(spec=sp, team=1, x=0.28, y=y, hp=sp.hp))
        env.eng.elixir[0] = float(left)          # POST-spend, as the charge site sees it
        env.eng.elixir[1] = float(opp_elixir)
        env._threat_id_true = card_threat.identity_threat_vector(
            view.identity_items(env.eng, 0, env.detector_cards, env.identity_front),
            env.db, prev_depth=0.0, dt=env.agent_dt, horizon=env.predict_horizon)
        env._xid = next(i for i, k in enumerate(env.deck_keys) if k.startswith("x_bow"))
        return env

    @staticmethod
    def _charge(env, ny=FORWARD_Y, nx=0.75):
        return env._xbow_overaggression(env._xid, nx, ny)

    def test_charged_when_the_bow_leaves_us_unable_to_answer(self):
        self.assertLess(self._charge(self._env(left=2)), 0.0)

    def test_not_charged_while_a_counter_is_still_affordable(self):
        self.assertEqual(self._charge(self._env(left=4)), 0.0)

    def test_it_covers_exactly_the_window_where_the_MISS_penalty_goes_silent(self):
        """The invariant worth keeping: at no elixir level can we ignore a live push for free."""
        for left in (6, 4, 3, 2, 1, 0):
            with self.subTest(left=left):
                env = self._env(left=left)
                quiet = env._threat_miss_idle() == 0.0
                charged = self._charge(env) < 0.0
                self.assertTrue((not quiet) or charged,
                                "at %d elixir neither term fires -- free to ignore the push" % left)

    def test_a_DEFENSIVE_bow_is_not_charged(self):
        self.assertEqual(self._charge(self._env(left=1), ny=DEEP_Y), 0.0)

    def test_an_ignorable_board_is_not_charged(self):
        env = self._env(left=1, push=(("skeletons", 0.54),))
        self.assertEqual(self._charge(env), 0.0)

    # -- what counts as an ANSWER rather than support --------------------------------
    def _contrib(self, env, card, push):
        from clashrl.sim.engine import Unit as _U
        units = [_U(spec=build_spec(env.db, b, 11), team=1, x=0.28, y=y,
                    hp=build_spec(env.db, b, 11).hp) for b, y in push]
        cid = next(i for i, k in enumerate(env.deck_keys) if k == card)
        return env._counter_contribution(cid, units)

    def test_skeletons_are_support_once_the_push_has_SUPPORT_troops(self):
        """The user's ask: Skeletons alone do not defend a real push."""
        env = self._env(left=10)
        self.assertLess(self._contrib(env, "skeletons", self.NAMED_PUSH), env.counter_min_share)

    def test_skeletons_DO_count_against_a_building_targeter_with_no_support(self):
        """The correction that rebuilt this rule (user, 2026-08-17). Giant and Hog are BUILDING-
        TARGETING -- they never swing at Skeletons, which simply DPS them down unharassed. An
        earlier version asked "does it survive a hit from the threat", which measured an attack
        the push does not make and wrote Skeletons off everywhere."""
        env = self._env(left=10)
        self.assertGreaterEqual(self._contrib(env, "skeletons", (("giant", 0.56),)),
                                env.counter_min_share)

    def test_support_troops_are_what_flip_skeletons_to_insufficient(self):
        env = self._env(left=10)
        alone = self._contrib(env, "skeletons", (("giant", 0.56),))
        escorted = self._contrib(env, "skeletons", (("giant", 0.56), ("musketeer", 0.52)))
        self.assertLess(escorted, alone / 2.0,
                        "a musketeer clearing them should collapse their contribution")

    def test_the_ice_wizards_SLOW_is_credited_not_just_his_damage(self):
        """He is the deck's force multiplier; scored on damage alone he rated 0.04-0.15 against
        every push -- never an answer -- which would fire the penalty whenever he was all we had."""
        env = self._env(left=10)
        self.assertGreater(self._contrib(env, "ice_wizard", self.NAMED_PUSH), 0.3)

    def test_a_building_always_counts(self):
        """A building's job is to survive and pull; per-body damage does not describe it."""
        env = self._env(left=10)
        self.assertGreaterEqual(self._contrib(env, "tesla", self.NAMED_PUSH), 1.0)

    def test_a_punish_window_is_exempt(self):
        """The counterattack this deck is built on: if they cannot answer the bow, spending on it
        is the plan, not over-aggression."""
        env = self._env(left=1, opp_elixir=0.0)
        if env._punish_window(spend=float(env.specs[env._xid].elixir)):
            self.assertEqual(self._charge(env), 0.0)


if __name__ == "__main__":
    unittest.main()
