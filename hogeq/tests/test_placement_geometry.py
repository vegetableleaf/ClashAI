"""The two geometric placement rules, and the discrepancy that made them worth computing.

Both come from the defensive-fundamentals research (2026-08-16). Both are stated in every guide as
tile numbers to memorise -- "4 tiles from the river, dead centre", "7-2 avoids Rocket value on the
tower and the building" -- and both are really consequences of the arena's geometry, so they are
computed from the engine's own tower positions, ranges and spell radii.

Computing rather than transcribing immediately paid for itself: the existing Tesla pull spot,
named for the centre-pull crossfire, turned out to sit outside BOTH towers' range.
"""
from __future__ import annotations

import math
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from clashrl.config import Config              # noqa: E402
from clashrl.sim import doctrine as D          # noqa: E402
from clashrl.sim.engine import build_spec      # noqa: E402
from clashrl.sim.env import SimMatchEnv        # noqa: E402


class _Unit:
    def __init__(self, spec, x, y, hp=1000):
        self.x, self.y, self.hp, self.team, self.spec = x, y, hp, 1, spec


def _env():
    e = SimMatchEnv(Config.load())
    e.reset()
    return e


class TestDoubleCover(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.env = _env()

    def test_the_old_pull_spot_is_covered_by_neither_tower(self):
        """The finding. (0.48, 0.585) is 8.51 tiles from BOTH princess towers, past the engine's
        configured 8.0-tile reach -- so the rule collected the pull and none of the crossfire
        meant to pay for it."""
        rng = float(self.env.cfg.get("sim", "tower_range", default=7.5) or 7.5)
        self.assertFalse(D._double_cover(self.env, 0.48, 0.585))
        for t in D._my_princesses(self.env):
            self.assertGreater(D._tiles(0.48, 0.585, t.x, t.y), rng)

    def test_the_new_spot_is_covered_by_both(self):
        self.assertTrue(D._double_cover(self.env, 0.50, 0.645))

    def test_the_boundary_is_derived_from_the_configured_reach(self):
        """Derived, not transcribed -- and the two differ, which is the point.

        The guides say "four tiles from the river"; that is correct for the real game's 7.5-tile
        towers. This engine is configured at 8.0, where the same computation gives 3.69. Copying
        the folk number would have been wrong here by two thirds of a tile, and silently, because
        the resulting cell still looks reasonable. Assert against the closed form, so the rule
        follows sim.tower_range if it is ever retuned.
        """
        rng = float(self.env.cfg.get("sim", "tower_range", default=7.5) or 7.5)
        dx = (0.50 - D._my_princesses(self.env)[0].x) * 18.0
        want = (D._my_princesses(self.env)[0].y - math.sqrt(rng ** 2 - dx ** 2) / 32.0)
        lo, hi = 0.50, 0.80                       # bisect the centre column for the boundary
        for _ in range(60):
            mid = (lo + hi) / 2
            if D._double_cover(self.env, 0.50, mid):
                hi = mid
            else:
                lo = mid
        self.assertAlmostEqual(hi, want, places=3)
        self.assertAlmostEqual((hi - 0.5) * 32.0, 3.69, places=1)   # the value at today's 8.0

    def test_a_lone_surviving_tower_cannot_double_cover(self):
        """With one princess down there is no crossfire to place into, whatever the geometry."""
        env = _env()
        env.eng.towers[0][0].hp = 0
        self.assertFalse(D._double_cover(env, 0.50, 0.645))


class TestSpellPairRisk(unittest.TestCase):
    def test_a_spot_beside_our_tower_is_flagged_against_a_rocket_deck(self):
        """One spell covers two points only within 2r of each other; rocket r=2.0 tiles."""
        env = _env()
        env.opponent.cards = ["rocket"]
        t = D._my_princesses(env)[0]
        self.assertTrue(D._spell_pair_risk(env, t.x, t.y + 2.0 / 32.0))

    def test_a_spot_far_from_our_towers_is_not_flagged(self):
        env = _env()
        env.opponent.cards = ["rocket"]
        self.assertFalse(D._spell_pair_risk(env, 0.50, 0.52))

    def test_nothing_is_flagged_when_their_deck_is_unknown(self):
        env = _env()
        env.opponent.cards = []
        t = D._my_princesses(env)[0]
        self.assertFalse(D._spell_pair_risk(env, t.x, t.y + 2.0 / 32.0))

    def test_radii_come_from_the_engine_not_a_transcribed_table(self):
        """If these drift the placements silently go wrong, so pin them to the engine's specs."""
        env = _env()
        for base, want in (("rocket", 2.0), ("fireball", 2.5), ("lightning", 3.5)):
            with self.subTest(base=base):
                self.assertAlmostEqual(build_spec(env.db, base, 11).spell_radius, want, places=2)


class TestShapingIsApplied(unittest.TestCase):
    def test_tesla_prior_offers_a_double_covered_spot(self):
        env = _env()
        # PIN A SPELL-FREE OPPONENT. Which deck the env samples comes from the meta pool, and the
        # deep double-covered spot is deliberately down-weighted (x0.6) when one of THEIR spells
        # could cover it and a tower together -- so re-weighting the pool (sim.meta_deck_boost /
        # meta_deck_top_n) changed the sampled opponent, a 3.5-tile spell appeared in its deck, and
        # this read 4.62 (= 7.7 x 0.6) instead of leading. That is the shaping working; the test
        # simply has to say which opponent it means.
        env.opponent.cards = ["knight", "musketeer", "hog_rider", "skeletons",
                              "archers", "cannon", "ice_spirit", "bats"]
        env.eng.units.append(_Unit(build_spec(env.db, "hog_rider", 11), 0.30, 0.55))
        tid = next(i for i, k in enumerate(env.deck_keys) if k.startswith("tesla"))
        got = D.doctrine_cells(env, tid)
        self.assertTrue(got)
        gw = int(env.actions.gw)
        covered = [wt for c, wt in got
                   if D._double_cover(env, *env.actions.cell_center(c % gw, c // gw))]
        self.assertTrue(covered, "no double-covered cell in the tesla prior")
        self.assertEqual(max(wt for _, wt in got), max(covered),
                         "the double-covered spot should lead the prior")

    def test_shaping_leaves_troops_alone(self):
        """A troop is gone in seconds; only structures stand around to be spell-punished."""
        env = _env()
        w = {5: 1.0}
        D._shape_placement(w, env, "knight")
        self.assertEqual(w, {5: 1.0})


class TestBowDefence(unittest.TestCase):
    """Keeping a standing X-Bow alive: knight tanks, skeletons distract, ice wizard stalls,
    tesla holds. A bow that fires its whole life is worth about a tower; one that dies at three
    seconds is six elixir gifted -- and nothing in the rule table asked what was walking at it."""

    @staticmethod
    def _board(attacker_y=0.60, bow=(0.30, 0.56)):
        env = _env()
        env.eng.units.append(_Unit(build_spec(env.db, "x_bow", 15), bow[0], bow[1], hp=1500))
        env.eng.units[-1].team = 0
        env.eng.units.append(_Unit(build_spec(env.db, "knight", 11), bow[0] + 0.02, attacker_y))
        return env

    def _spot(self, env, card):
        ids = [i for i, k in enumerate(env.deck_keys) if k == card or k == card + "_evo"]
        got = D.doctrine_cells(env, ids[0]) if ids else None
        if not got:
            return None
        gw = int(env.actions.gw)
        cell = max(got, key=lambda t: t[1])[0]
        return cell, env.actions.cell_center(cell % gw, cell // gw)

    def test_the_bow_and_its_attackers_are_found(self):
        env = self._board()
        bow = D._my_bow(env)
        self.assertIsNotNone(bow)
        self.assertEqual([u.spec.base for u in D._bow_attackers(env, bow)], ["knight"])

    def test_every_role_lands_on_a_DEPLOYABLE_cell(self):
        """The bug this caught: "behind the bow" was written relative to the THREAT, so once an
        attacker walked past the bow it resolved to the far side of the river -- row 10, enemy
        half, silently masked away to nothing."""
        env = self._board()
        mask = env.actions.deployable_mask(False)
        for card in ("knight", "skeletons", "ice_wizard", "tesla"):
            with self.subTest(card=card):
                got = self._spot(env, card)
                self.assertIsNotNone(got, "%s produced no bow-defence spot" % card)
                self.assertTrue(mask[got[0]], "%s -> undeployable cell" % card)

    def test_the_ice_wizard_goes_BEHIND_the_bow_even_when_the_attacker_is_past_it(self):
        env = self._board(attacker_y=0.68)          # attacker deeper in our half than the bow
        bow = D._my_bow(env)
        _, (_, iy) = self._spot(env, "ice_wizard")
        self.assertGreater(iy, bow.y, "ice wizard must sit deeper in OUR half than the bow")

    def test_the_knight_goes_between_the_bow_and_the_threat(self):
        env = self._board(attacker_y=0.66)
        bow = D._my_bow(env)
        _, (_, ky) = self._spot(env, "knight")
        self.assertGreater(ky, bow.y)               # toward the attacker

    def test_offsets_clear_a_grid_row(self):
        """One grid row is 1/24 = 0.0417 normalised. The natural "one row in front" written as
        0.04 quantises back onto the bow's own cell, and the geometry silently disappears."""
        self.assertGreaterEqual(D._ROW, 1.0 / 24.0 - 1e-9)
        env = self._board()
        bow = D._my_bow(env)
        bow_cell = env.actions.cell_at(bow.x, bow.y)
        self.assertNotEqual(self._spot(env, "knight")[0], bow_cell)
        self.assertNotEqual(self._spot(env, "ice_wizard")[0], bow_cell)

    def test_no_bow_means_no_bow_rules(self):
        env = _env()
        env.eng.units.append(_Unit(build_spec(env.db, "knight", 11), 0.30, 0.60))
        self.assertIsNone(D._my_bow(env))
        w = {}
        self.assertFalse(D._bow_defence_cells(env, "knight", w))
        self.assertEqual(w, {})

    def test_a_distant_enemy_does_not_count_as_attacking_the_bow(self):
        env = self._board(attacker_y=0.86)          # far behind the bow, walking at the tower
        bow = D._my_bow(env)
        self.assertEqual(D._bow_attackers(env, bow), [])

    def test_the_cards_are_nominated_when_the_bow_is_under_threat(self):
        env = self._board()
        got = D.doctrine_cards(env) or {}
        named = {env.deck_keys[k] for k in got}
        self.assertTrue(named & {"skeletons", "tesla", "knight", "knight_evo", "ice_wizard"},
                        "no bow-defence card nominated: %s" % named)


if __name__ == "__main__":
    unittest.main()
