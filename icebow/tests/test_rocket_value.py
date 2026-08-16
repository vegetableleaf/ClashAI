"""Conditional rocket value + the card-side doctrine prior.

The rocket went unplayed for 14,300 training matches and four evaluations. Probing showed the
reward was not the problem -- a tower + support 2-for-1 already paid wincon_exec x 3 -- but that
the card head never SELECTED the rocket, so no rocket reward was reachable at all. These tests pin
both halves of the fix:

  * the value is CONDITIONAL and correctly ORDERED (a tornado-bundled rocket beats a tiebreak
    chip beats a regulation chip beats six elixir on Skeletons, which is negative);
  * the prior NOMINATES the rocket in rocket situations and stays quiet otherwise, because a
    prior that always fires is just a higher rocket rate, not a taught one.
"""
from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from clashrl.config import Config              # noqa: E402
from clashrl.sim.env import SimMatchEnv        # noqa: E402
from clashrl.sim.engine import build_spec      # noqa: E402
from clashrl.sim.doctrine import doctrine_cards  # noqa: E402


def _env(seed=3):
    e = SimMatchEnv(Config.load(), seed=seed)
    e.reset()
    return e


def _rid(env):
    return env.deck_keys.index("rocket")


def _enemy_tower(env):
    return [t for t in env.eng.towers[1][:2] if t.alive][0]


class RocketValueTests(unittest.TestCase):
    def test_waste_on_cheap_bodies_is_negative(self):
        """Six elixir on Skeletons is a misplace, not merely a zero -- the user's own example."""
        env = _env()
        for dx in (-0.01, 0.0, 0.01):
            env.eng.elixir[1] = 10.0
            env.eng.deploy(1, build_spec(env.db, "skeletons", 11), 0.30 + dx, 0.40)
        u = [x for x in env.eng.units if x.team == 1 and x.hp > 0][-1]
        self.assertLess(env._rocket_value(u.x, u.y, 9.0), 0.0)

    def test_valuable_clump_beats_cheap_clump(self):
        env = _env()
        for key in ("musketeer", "wizard"):
            env.eng.elixir[1] = 10.0
            env.eng.deploy(1, build_spec(env.db, key, 11), 0.30, 0.40)
        u = [x for x in env.eng.units if x.team == 1 and x.hp > 0][-1]
        self.assertGreater(env._rocket_value(u.x, u.y, 9.0), 0.0)

    def test_tiebreak_chip_outranks_regulation_chip(self):
        """Chipping is a luxury while the bow is the plan and the win condition once it is not."""
        env = _env()
        tw = _enemy_tower(env)
        env._defensive = False
        env.eng.t = 10.0
        early = env._rocket_value(tw.x, tw.y, 0.0)
        env._defensive = True
        late = env._rocket_value(tw.x, tw.y, 0.0)
        self.assertGreater(late, early)

    def test_being_ahead_on_the_tiebreak_lowers_chip_value(self):
        env = _env()
        tw = _enemy_tower(env)
        env._defensive = True
        for t in env.eng.towers[0][:2]:                 # our towers healthy...
            t.hp = t.max_hp
        for t in env.eng.towers[1][:2]:                 # ...theirs already lower = we lead
            t.hp = t.max_hp * 0.4
        ahead = env._rocket_value(tw.x, tw.y, 0.0)
        for t in env.eng.towers[0][:2]:                 # now we are the lower one
            t.hp = t.max_hp * 0.2
        behind = env._rocket_value(tw.x, tw.y, 0.0)
        self.assertGreater(behind, ahead)

    def test_tiebreak_gap_sign(self):
        env = _env()
        for t in env.eng.towers[0][:2]:
            t.hp = t.max_hp * 0.3
        for t in env.eng.towers[1][:2]:
            t.hp = t.max_hp
        self.assertLess(env._tiebreak_gap(), 0.0, "negative = OUR tower is the lower one")

    def test_tornado_bundle_is_the_best_rocket(self):
        """The combo the deck is built around must outrank an ordinary tiebreak chip."""
        env = _env()
        env._defensive = True
        tw = _enemy_tower(env)
        chip = env._rocket_value(tw.x, tw.y, 0.0)
        ids = []
        for key, dx in (("musketeer", 0.0), ("wizard", 0.02)):
            env.eng.elixir[1] = 10.0
            env.eng.deploy(1, build_spec(env.db, key, 11), 0.50 + dx, 0.55)
            ids.append(env.eng.units[-1])
        env._nado_watch.append({"t0": env.eng.t, "cx": 0.51, "cy": 0.55,
                                "pulled": ids, "targeters": [],
                                "king_was_asleep": False, "early_done": False})
        combo = env._rocket_value(0.51, 0.55, 9.0)
        self.assertGreater(combo, chip)

    def test_stale_tornado_does_not_pay(self):
        """It is a timing play: a pull that has already dispersed is not a combo."""
        env = _env()
        ids = []
        for key, dx in (("musketeer", 0.0), ("wizard", 0.02)):
            env.eng.elixir[1] = 10.0
            env.eng.deploy(1, build_spec(env.db, key, 11), 0.50 + dx, 0.55)
            ids.append(env.eng.units[-1])
        env._nado_watch.append({"t0": env.eng.t - 30.0, "cx": 0.51, "cy": 0.55,
                                "pulled": ids, "targeters": [],
                                "king_was_asleep": False, "early_done": False})
        fresh = env.w_wincon * env.rocket_nado_mult
        self.assertLess(env._rocket_value(0.51, 0.55, 9.0), fresh)


class RocketPriorTests(unittest.TestCase):
    def test_quiet_when_there_is_no_rocket_situation(self):
        env = _env()
        env.eng.elixir[0] = 0.0                          # cannot afford it -> never nominate
        self.assertIsNone(doctrine_cards(env))

    def test_nominates_on_a_fresh_pump(self):
        env = _env()
        env.eng.elixir[0] = 10.0
        env.cycle = [env.slot_of[_rid(env)]] + [s for s in env.cycle if s != env.slot_of[_rid(env)]]
        env.eng.elixir[1] = 10.0
        env.eng.deploy(1, build_spec(env.db, "elixir_collector", 11), 0.5, 0.30)
        got = doctrine_cards(env)
        self.assertIsNotNone(got)
        self.assertIn(_rid(env), got)

    def test_never_nominates_an_unaffordable_rocket(self):
        env = _env()
        env.eng.elixir[0] = 2.0
        env.eng.elixir[1] = 10.0
        env.eng.deploy(1, build_spec(env.db, "elixir_collector", 11), 0.5, 0.30)
        self.assertIsNone(doctrine_cards(env))


if __name__ == "__main__":
    unittest.main()
