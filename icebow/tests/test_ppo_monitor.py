from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from clashrl.ppo_monitor import should_intervene


class PpoMonitorTests(unittest.TestCase):
    def test_a_fresh_run_is_never_judged(self):
        """A from-scratch policy loses every match at first; treating that as a plateau made the
        trainer kill itself at 25 matches (and the watchdog relaunch it into the same wall)."""
        should, reason = should_intervene(
            winrate=0.0,
            avg_reward=-30.9,
            recent_winrates=[0.0, 0.0, 0.0],
            recent_rewards=[-30.0, -30.5, -30.9],
            matches=25,
        )
        self.assertFalse(should)
        self.assertIn("warming up", reason)

    def test_a_bad_run_is_caught_once_it_has_had_a_fair_chance(self):
        should, reason = should_intervene(
            winrate=0.0,
            avg_reward=-30.9,
            recent_winrates=[0.0, 0.0, 0.0],
            recent_rewards=[-30.0, -30.5, -30.9],
            matches=50_000,
        )
        self.assertTrue(should)
        self.assertIn("winrate", reason)

    def test_healthy_run_does_not_trigger(self):
        should, reason = should_intervene(
            winrate=58.0,
            avg_reward=12.0,
            recent_winrates=[55.0, 57.0, 58.0],
            recent_rewards=[8.0, 10.0, 12.0],
            matches=50_000,
        )
        self.assertFalse(should)
        self.assertEqual(reason, "healthy")

    def test_low_winrate_triggers(self):
        should, reason = should_intervene(
            winrate=32.0,
            avg_reward=-10.0,
            recent_winrates=[34.0, 33.0, 32.0],
            recent_rewards=[-8.0, -9.0, -10.0],
            matches=50_000,
        )
        self.assertTrue(should)
        self.assertIn("winrate", reason)
        self.assertIn("avg reward", reason)

    def test_plateauing_winrate_triggers(self):
        should, reason = should_intervene(
            winrate=38.0,
            avg_reward=2.0,
            recent_winrates=[50.0, 45.0, 38.0],
            recent_rewards=[3.0, 2.5, 2.0],
            matches=50_000,
        )
        self.assertTrue(should)
        self.assertIn("plateau", reason)


if __name__ == "__main__":
    unittest.main()
