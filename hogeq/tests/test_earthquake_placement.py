"""Where the Earthquake goes.

User report: "it's playing EQ in the center of its own side, which makes zero sense". There was no
cell rule for the card at all, so its placement was whatever the head happened to output.

The doctrine, in the user's words: it is offensive ~90% of the time -- chip a princess tower and
take out their building in the SAME cast -- so "positioning shouldn't vary much, as long as it hits
both princess tower and the opponent's building/ground swarm, but prioritising the latter if hitting
both isn't an option".

That is a spot, not a search, and the geometry says why: their princess sits at y=0.2031 and the
blast reaches 3.5 tiles, so a single cast covers the tower plus anything within 7 tiles of it --
which is every standard defensive-building placement.
"""
from __future__ import annotations

import math
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from clashrl.config import Config                                      # noqa: E402
from clashrl.sim import doctrine as D                                  # noqa: E402
from clashrl.sim.engine import Unit, build_spec, _TILES_X, _TILES_Y    # noqa: E402
from clashrl.sim.env import SimMatchEnv                                # noqa: E402


def _tiles(ax, ay, bx, by):
    return math.hypot((ax - bx) * _TILES_X, (ay - by) * _TILES_Y)


class EarthquakePlacementTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.env = SimMatchEnv(Config.load())
        cls.env.reset()
        cls.eq_id = next(i for i, k in enumerate(cls.env.deck_keys) if k == "earthquake")
        cls.reach = build_spec(cls.env.db, "earthquake", 13).spell_radius

    def _cast(self, units):
        env = self.env
        env.eng.units.clear()
        for base, x, y in units:
            sp = build_spec(env.db, base, 11)
            env.eng.units.append(Unit(spec=sp, team=1, x=x, y=y, hp=sp.hp))
        cells = D.doctrine_cells(env, self.eq_id)
        if not cells:
            return None
        d = cells if isinstance(cells, dict) else dict(cells)
        best = max(d.items(), key=lambda kv: kv[1])[0]
        return env.actions.cell_center(best % env.gw, best // env.gw)

    def _tower_gap(self, xy):
        return min(_tiles(xy[0], xy[1], t.x, t.y) for t in self.env.eng.towers[1][:2])

    # -- the reported bug -------------------------------------------------------------
    def test_it_never_casts_on_our_own_half(self):
        """The whole complaint. Their half is y < 0.5; ours is the far side of the river."""
        for units in ([("tesla", 0.22, 0.28)], [("cannon", 0.30, 0.30)], [],
                      [("skeletons", 0.20, 0.26)] * 3):
            xy = self._cast(units)
            self.assertIsNotNone(xy)
            self.assertLess(xy[1], 0.5, "Earthquake cast on our own side: %s" % (xy,))

    # -- hit both ---------------------------------------------------------------------
    def test_a_building_near_their_tower_is_hit_together_with_the_tower(self):
        xy = self._cast([("tesla", 0.22, 0.28)])
        self.assertLessEqual(_tiles(xy[0], xy[1], 0.22, 0.28), self.reach, "missed the building")
        self.assertLessEqual(self._tower_gap(xy), self.reach + 1.0, "missed the tower")

    def test_a_building_further_out_is_still_paired_with_the_tower(self):
        xy = self._cast([("cannon", 0.30, 0.30)])
        self.assertLessEqual(_tiles(xy[0], xy[1], 0.30, 0.30), self.reach)
        self.assertLessEqual(self._tower_gap(xy), self.reach + 1.0)

    def test_a_ground_swarm_counts_as_a_prize_too(self):
        swarm = [("skeletons", 0.20, 0.26), ("skeletons", 0.21, 0.27),
                 ("skeletons", 0.19, 0.27), ("skeletons", 0.20, 0.28)]
        xy = self._cast(swarm)
        self.assertLessEqual(min(_tiles(xy[0], xy[1], x, y) for _, x, y in swarm), self.reach)
        self.assertLessEqual(self._tower_gap(xy), self.reach + 1.0)

    def test_a_lone_troop_is_not_worth_aiming_at(self):
        """EQ's troop damage is poor; one body must not pull the cast off the tower."""
        xy = self._cast([("knight", 0.30, 0.30)])
        self.assertLessEqual(self._tower_gap(xy), self.reach + 1.0)

    # -- prioritise the building when both is impossible --------------------------------
    def test_an_unpairable_building_wins_over_the_tower(self):
        """User doctrine: prioritise the building -- it is what stops the Hog, the chip is a bonus."""
        xy = self._cast([("cannon", 0.50, 0.46)])
        self.assertLessEqual(_tiles(xy[0], xy[1], 0.50, 0.46), self.reach, "abandoned the building")
        self.assertGreater(self._tower_gap(xy), self.reach + 1.0, "claimed a tower it cannot reach")

    # -- pure chip ----------------------------------------------------------------------
    def test_an_empty_board_still_chips_a_tower(self):
        xy = self._cast([])
        self.assertLessEqual(self._tower_gap(xy), self.reach + 1.0)

    def test_it_chips_the_WEAKER_tower_when_there_is_no_prize(self):
        env = self.env
        env.eng.towers[1][0].hp = env.eng.towers[1][0].max_hp * 0.3
        try:
            xy = self._cast([])
            self.assertLess(_tiles(xy[0], xy[1], env.eng.towers[1][0].x, env.eng.towers[1][0].y),
                            _tiles(xy[0], xy[1], env.eng.towers[1][1].x, env.eng.towers[1][1].y))
        finally:
            env.eng.towers[1][0].hp = env.eng.towers[1][0].max_hp

    def test_no_rule_once_both_their_princesses_are_down(self):
        env = self.env
        for t in env.eng.towers[1][:2]:
            t.hp = 0.0
        try:
            self.assertIsNone(self._cast([("cannon", 0.30, 0.30)]))
        finally:
            for t in env.eng.towers[1][:2]:
                t.hp = t.max_hp

    def test_flyers_are_never_the_prize(self):
        """It is an EARTHquake -- aiming it at a Minion Horde would waste the cast."""
        xy = self._cast([("minions", 0.30, 0.30)])
        self.assertLessEqual(self._tower_gap(xy), self.reach + 1.0)


if __name__ == "__main__":
    unittest.main()
