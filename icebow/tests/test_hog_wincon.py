"""The Hog Rider could not earn win-condition reward AT ALL, so PPO stopped playing it.

User, 2026-08-20: "the PPO training for hogeq has collapsed into 0 uses for hog rider... which
means a wincon_exec term should be factored in for hog rider, but make it slightly different from
icebow's wincon exec. Still don't play hog into a large enemy push though."

The collapse was correct behaviour from an incorrect reward. `_wincon_exec` branched only on
xbow_ids / rocket_ids / miner_ids -- every one of them EMPTY for this deck -- so a Hog play fell
through to `return 0.0` while a bad one was still charged by threat_response. wincon_exec is the
largest positive term in the ledger, and the deck's own win condition was the single card that
could never earn it. A policy that never plays the Hog strictly dominates under that reward.

WHY THIS TERM IS NOT THE X-BOW'S. The bow is a SIEGE BUILDING judged on standing geometry -- is it
forward and in range, or back-centre on defence. The Hog is four elixir that WALKS, so it is judged
on timing and lane: bridge only, never into a committed push, and a bonus for the punish lane.
"""
from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from clashrl.config import Config                       # noqa: E402
from clashrl.sim.engine import Unit, build_spec         # noqa: E402
from clashrl.sim.env import SimMatchEnv                 # noqa: E402


class HogWinconTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.env = SimMatchEnv(Config.load(), seed=9)
        cls.env.reset()
        cls.hid = next((i for i, s in enumerate(cls.env.specs) if s.base == "hog_rider"), None)

    def setUp(self):
        if self.hid is None:
            self.skipTest("this deck holds no rush win condition")
        self.env.eng.units.clear()

    def enemy(self, base, x, y):
        sp = build_spec(self.env.eng.db, base, 11)
        u = Unit(spec=sp, team=1, x=x, y=y, hp=sp.hp)
        u.deploy_left = 0.0
        self.env.eng.units.append(u)
        return u

    def val(self, x, y):
        return self.env._wincon_exec(self.hid, x, y)

    # ---- the bug itself ------------------------------------------------------------
    def test_a_bridge_hog_earns_win_condition_reward_at_all(self):
        """THE REGRESSION GUARD. This returned exactly 0.0 for every placement on the board,
        which is why PPO collapsed to zero Hog plays."""
        self.assertGreater(self.val(0.75, 0.47), 0.0,
                           "the deck's win condition earns nothing again -- PPO will stop "
                           "playing it, exactly as it did on 2026-08-20")

    def test_the_win_condition_is_in_wincon_ids(self):
        self.assertIn(self.hid, self.env.wincon_ids)

    # ---- the user's explicit rule --------------------------------------------------
    def test_never_into_a_committed_push(self):
        """"Still don't play hog into a large enemy push." Four elixir at their tower while a real
        push is on our half is how a one-crown deficit becomes three."""
        self.enemy("giant", 0.30, 0.55)
        self.enemy("musketeer", 0.30, 0.58)
        self.assertLess(self.val(0.75, 0.47), 0.0,
                        "the Hog was sent into a committed push and paid for it")

    def test_triage_decides_what_counts_as_a_push(self):
        """A couple of Skeletons over the river is not a push -- the same group_ignore_frac gate
        every other tier in this project uses, so the veto cannot become 'never counter-push'."""
        self.enemy("skeletons", 0.30, 0.55)
        self.assertGreater(self.val(0.75, 0.47), 0.0,
                           "a lone ignorable unit blocked the send")

    # ---- what makes it different from the X-Bow's term -----------------------------
    def test_bridge_only_never_from_the_back(self):
        self.assertLess(self.val(0.75, 0.70), 0.0,
                        "a Hog from our own half walks the length of the board and is answered "
                        "twice on the way -- it must not score like a bridge send")

    def test_the_opposite_lane_to_their_mass_is_the_punish(self):
        self.enemy("giant", 0.25, 0.30)
        self.enemy("musketeer", 0.25, 0.26)
        opposite = self.val(0.75, 0.47)
        same = self.val(0.25, 0.47)
        self.assertGreater(opposite, same,
                           "sending into the lane they have committed to scored as well as the "
                           "punish lane")

    def test_the_punish_bonus_is_bounded(self):
        """It multiplies wincon_exec; it must not dwarf it, or the lane read outweighs the send."""
        self.assertLessEqual(self.env.hog_punish_mult, 2.0)
        self.assertGreater(self.env.hog_punish_mult, 1.0)


class LiveTwinTests(unittest.TestCase):
    """Live must implement the same three rules, or a sim-trained policy meets a different
    referee the moment it plays for real -- the exact failure mode that lost the tornado combo."""

    def _live_src(self):
        import io
        p = os.path.join(os.path.dirname(__file__), "..", "src", "clashrl", "env.py")
        with io.open(p, encoding="utf-8") as fh:
            return fh.read()

    def test_live_has_the_rush_branch(self):
        src = self._live_src()
        self.assertIn("_hog_wincon_live", src, "live has no rush win-condition term")
        self.assertIn("rush_wincon_ids", src)

    def test_live_keeps_all_three_rules(self):
        src = self._live_src()
        i = src.index("def _hog_wincon_live")
        body = src[i:i + 2000]
        self.assertIn("group_ignore_frac", body, "the never-into-a-push rule is gone live")
        self.assertIn("hog_bridge_y", body, "the bridge-only rule is gone live")
        self.assertIn("hog_punish_mult", body, "the punish-lane bonus is gone live")


if __name__ == "__main__":
    unittest.main(verbosity=1)
