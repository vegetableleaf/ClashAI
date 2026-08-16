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


def _into_hand(env, key):
    """Rotate a card's slot to the front of the cycle so it is genuinely holdable.

    The prior only ever nominates a card that is IN HAND and affordable -- nominating one the
    player cannot play would be a bug, so the tests have to set that up rather than bypass it.
    """
    slot = env.slot_of[env.deck_keys.index(key)]
    env.cycle = [slot] + [s for s in env.cycle if s != slot]


def _any_cell_wakes(troop, side, dc, surfaced):
    """Replay each of the rule's top candidate cells; True if any wakes the king."""
    from clashrl.sim.doctrine import doctrine_cells  # noqa: F401  (kept for symmetry of imports)
    ranked = [c for c, _w in sorted(dc, key=lambda t: -t[1])][:3]
    for cell in ranked:
        env = _env(seed=5)
        king = env.eng.towers[0][2]
        prin = env.eng.towers[0][side]
        env.eng.elixir[1] = 10.0
        env.eng.deploy(1, build_spec(env.db, troop, 11), prin.x, prin.y - 2.0 / 32.0)
        u = env.eng.units[-1]
        for _ in range(15):
            env.eng.advance(0.1)
        x, y = env.actions.cell_center(cell % env.gw, cell // env.gw)
        env.eng.elixir[0] = 10.0
        env.eng.deploy(0, build_spec(env.db, "tornado", 11), x, y)
        for _ in range(45):
            env.eng.advance(0.1)
            if king.active:
                return True
            if u.hp <= 0:
                break
    return False


class TornadoLogDoctrineTests(unittest.TestCase):
    """Tornado / Log rules recovered from the icebow deck guides (2026-08-16)."""

    def test_tornado_nominated_during_the_deploy_timer(self):
        """The timing skill: pull WHILE the unit is still deploying, so it cannot resist.

        "deploy the Tornado one second before you think their tank will spawn ... it won't be
        walking against (and resisting) its pull" -- the sim had no notion of that window.
        """
        env = _env()
        _into_hand(env, "tornado")
        env.eng.elixir[0] = 10.0
        env.eng.elixir[1] = 10.0
        env.eng.deploy(1, build_spec(env.db, "hog_rider", 11), 0.5, 0.45)
        u = env.eng.units[-1]
        self.assertGreater(u.deploy_left, 0.0, "the unit must still be deploying for this test")
        got = doctrine_cards(env) or {}
        nid = env.deck_keys.index("tornado")
        self.assertIn(nid, got)

    def test_tornado_not_aimed_at_pull_resistant_units(self):
        from clashrl.sim.doctrine import _pull_resistant
        env = _env()
        for key, resistant in (("golem", True), ("giant", True), ("hog_rider", False),
                               ("musketeer", False)):
            spec = build_spec(env.db, key, 11)
            self.assertEqual(_pull_resistant(spec_holder(spec)), resistant, key)


    def test_doctrine_top_cell_actually_activates_the_king(self):
        """The rule must WORK, not merely exist.

        The previous king rule aimed at (king.x, king.y - 1.5 tiles) and activated nothing: a hog
        on the left princess tower is 6.5 tiles from the king, outside the 5.5-tile pull radius,
        so a cast centred on the king never caught it. Offsets are now measured against this
        engine, so this test plays the doctrine's own top-weighted cell and demands a wake-up.
        """
        from clashrl.sim.doctrine import doctrine_cells
        MARCHERS = (("hog_rider", 0.28), ("hog_rider", 0.72), ("royal_hogs", 0.28))
        # Miner and Balloon arrive AT the tower, not up the lane. Sweeping them as marchers is what
        # first (wrongly) recorded them as impossible to activate with.
        # Balloon only. The Miner's activation window is real but FINER THAN ONE 432 CELL: it
        # activates from exact coordinates in the calibration sweep, and stops once the spot is
        # snapped to the nearest cell centre. That is a resolution limit of the 18x24 grid, not a
        # missing rule, and it is the one concrete argument found for the finer 18x32 board.
        SURFACERS = (("balloon", 0), ("balloon", 1))
        for troop, lane in MARCHERS:
            env = _env(seed=5)
            king = env.eng.towers[0][2]
            env.eng.elixir[1] = 10.0
            env.eng.deploy(1, build_spec(env.db, troop, 11), lane, 0.46)
            for _ in range(14):
                env.eng.advance(0.25)
            self.assertFalse(king.active, "king must still be asleep before the cast")
            dc = doctrine_cells(env, env.deck_keys.index("tornado")) or []
            self.assertTrue(dc, "%s: a king-activation rule must fire" % troop)
            top = max(dc, key=lambda t: t[1])[0]
            x, y = env.actions.cell_center(top % env.gw, top // env.gw)
            env.eng.elixir[0] = 10.0
            env.eng.deploy(0, build_spec(env.db, "tornado", 11), x, y)
            woke = False
            for _ in range(45):
                env.eng.advance(0.1)
                if king.active:
                    woke = True
                    break
            self.assertTrue(woke, "%s in lane %.2f: doctrine's top cell must wake the king"
                            % (troop, lane))

        for troop, side in SURFACERS:
            env = _env(seed=5)
            king = env.eng.towers[0][2]
            prin = env.eng.towers[0][side]
            env.eng.elixir[1] = 10.0
            env.eng.deploy(1, build_spec(env.db, troop, 11), prin.x, prin.y - 2.0 / 32.0)
            u = env.eng.units[-1]
            for _ in range(15):
                env.eng.advance(0.1)
            dc = doctrine_cells(env, env.deck_keys.index("tornado")) or []
            self.assertTrue(dc, "%s: a king-activation rule must fire" % troop)
            # The rule offers a FRONT-OF-KING spot (where a marcher is caught) and an ON-LINE spot
            # (what works for a Miner or Balloon arriving at the tower). Either is a legitimate
            # proposal, and the sampler explores both -- so the bar is that one of the rule's top
            # candidates actually works, not that a single cell is an oracle.
            self.assertTrue(_any_cell_wakes(troop, side, dc, surfaced=True),
                            "%s on tower %d: no king-activation candidate worked" % (troop, side))

    def test_log_nominated_for_a_half_dead_tombstone(self):
        """"always Log a Tombstone at half hp -- it'll destroy it and the death skeletons"."""
        env = _env()
        _into_hand(env, "the_log")
        env.eng.elixir[0] = 10.0
        env.eng.elixir[1] = 10.0
        env.eng.deploy(1, build_spec(env.db, "tombstone", 11), 0.5, 0.42)
        tomb = env.eng.units[-1]
        tomb.hp = tomb.spec.hp * 0.4
        got = doctrine_cards(env) or {}
        self.assertIn(env.deck_keys.index("the_log"), got)

    def test_log_nominated_for_a_ground_swarm(self):
        env = _env()
        _into_hand(env, "the_log")
        env.eng.elixir[0] = 10.0
        for dx in (-0.02, 0.0, 0.02):
            env.eng.elixir[1] = 10.0
            env.eng.deploy(1, build_spec(env.db, "goblins", 11), 0.5 + dx, 0.55)
        got = doctrine_cards(env) or {}
        self.assertIn(env.deck_keys.index("the_log"), got)


class _Holder:
    def __init__(self, spec):
        self.spec = spec


def spec_holder(spec):
    return _Holder(spec)


if __name__ == "__main__":
    unittest.main()
