"""The aggro drills grade the LOCK, not the hp total (HANDOFF §5bu).

`tank_for_bow`: the scripted knight-in-front line takes the Valkyrie's lock; doing nothing means her first
hit lands on the bow. `bow_lane_choice`: the scripted opposite-lane bow first-locks a tower; doing nothing
never passes; a same-lane bow first-locks the knight and FAILS -- the cell decides, not the level roll.
All runs use the ladder enemy roll (13-16), the board the trainer would see.
"""
from __future__ import annotations

import dataclasses
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from clashrl.config import Config                                         # noqa: E402
from clashrl.sim import aggro_drills, scenarios                           # noqa: E402
from clashrl.sim.drill_env import run_drill, scripted_policy              # noqa: E402

REPS, SEED = 20, 5


def rate(sc, policy=None):
    return run_drill(Config.load(), sc, policy=policy, reps=REPS, seed=SEED)["pass_rate"]


class AggroDrillTests(unittest.TestCase):
    def test_register_all_is_idempotent(self):
        first = aggro_drills.register_all()
        self.assertEqual(aggro_drills.register_all(), 0)
        for s in aggro_drills.ALL:
            self.assertIs(scenarios._REGISTRY[s.name], s)
        self.assertLessEqual(first, len(aggro_drills.ALL))

    def test_tank_for_bow_scripted_takes_the_lock_and_nothing_does_not(self):
        sc = aggro_drills.TANK_FOR_BOW
        self.assertGreaterEqual(rate(sc, scripted_policy(sc)), 0.9)
        self.assertEqual(rate(sc), 0.0)

    def test_tank_for_bow_late_knight_fails(self):
        # she first hits the bow 3.7 s after spawning (§5bu); a knight ordered at 4.2 s lands after
        # the lock is kept, from the very cell that works at 0.6 s
        sc = dataclasses.replace(aggro_drills.TANK_FOR_BOW, reference=(("knight", 0.25, 0.5625, 4.2),))
        self.assertLessEqual(rate(sc, scripted_policy(sc)), 0.1)

    def test_bow_lane_choice_opposite_lane_locks_the_tower_same_lane_locks_the_knight(self):
        sc = aggro_drills.BOW_LANE_CHOICE
        self.assertGreaterEqual(rate(sc, scripted_policy(sc)), 0.9)
        self.assertEqual(rate(sc), 0.0)
        same = dataclasses.replace(sc, reference=(("x_bow", 0.25, 0.5625, 0.6),))
        self.assertEqual(rate(same, scripted_policy(same)), 0.0)


if __name__ == "__main__":
    unittest.main()
