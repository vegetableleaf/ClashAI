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


if __name__ == "__main__":
    unittest.main()
