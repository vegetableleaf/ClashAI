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


def _cfg(**over):
    """A Config with `sim.<key>` overridden -- the trainer reads these through cfg.get, so a copy of
    the loaded dict is the honest way to flip a flag in a test."""
    import copy
    cfg = Config.load()
    data = copy.deepcopy(cfg.data)
    data.setdefault("sim", {}).update(over)
    return Config(data=data, root=cfg.root)


class AggroWiringTests(unittest.TestCase):
    """The `sim.aggro_drills` flag (HANDOFF §5ca): off = the gate05 pool exactly; on = the lock-state
    drills in, the two old aggro drills out. And `Scenario.noise=False` really keeps distractors off."""

    def test_flag_off_is_the_old_pool(self):
        from clashrl.sim.drill_env import DrillMixEnv
        env = DrillMixEnv(_cfg(aggro_drills=False), seed=1)
        names = {s.name for s in env._pool}
        self.assertIn("knight_guards_the_bow", names)
        self.assertIn("nado_the_sneaky_lock", names)
        # `register_all` may have run in another test of this process: the flag must still hide them
        self.assertNotIn("tank_for_bow", names)
        self.assertNotIn("bow_lane_choice", names)

    def test_flag_on_swaps_the_aggro_drills(self):
        from clashrl.sim.drill_env import DrillMixEnv
        env = DrillMixEnv(_cfg(aggro_drills=True), seed=1)
        names = {s.name for s in env._pool}
        for n in aggro_drills.RETIRED:
            self.assertNotIn(n, names)
            self.assertIn(n, scenarios._REGISTRY)          # retired from the pool, not unregistered
        for s in aggro_drills.ALL:
            self.assertIn(s.name, names)
        self.assertIn("nado_king_activation", names)       # the real tornado-aggro drill stays

    def test_noise_field_keeps_distractors_off_this_drill_only(self):
        from clashrl.sim.drill_env import DrillEnv
        cfg = _cfg(drill_noise=1.5)                        # one or two distractors per episode
        self.assertIs(aggro_drills.BOW_LANE_CHOICE.noise, False)
        self.assertIsNone(aggro_drills.TANK_FOR_BOW.noise)
        seen_noise = {"bow": 0, "tank": 0}
        for seed in range(12):
            for key, sc in (("bow", aggro_drills.BOW_LANE_CHOICE), ("tank", aggro_drills.TANK_FOR_BOW)):
                env = DrillEnv(cfg, sc, seed=seed); env.reset()
                seen_noise[key] += sum(1 for u in env.eng.units if getattr(u, "drill_noise", False))
        self.assertEqual(seen_noise["bow"], 0)
        self.assertGreater(seen_noise["tank"], 0)


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
