"""The Hog EQ placement rules added from DOCTRINE_RESEARCH.md (2026-08-18).

Before this tranche the card prior nominated the Hog on a quiet board but there was NO cell rule
for hog_rider (or mighty_miner / firecracker / ice_spirit): a nominated Hog explored uniformly
over all 432 cells, mostly rows the card has no business on. These tests pin the researched
placements the new branches encode -- and the abstentions, which matter as much (a Mighty Miner
nominated into a swarm is exactly the waste the guides warn about).

The grid decode is 18 columns x 24 rows, cell = gy * 18 + gx (ActionSpace order).
"""
from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from clashrl.config import Config                       # noqa: E402
from clashrl.sim import doctrine as D                   # noqa: E402
from clashrl.sim.engine import Unit, build_spec         # noqa: E402
from clashrl.sim.env import SimMatchEnv                 # noqa: E402

GW = 18


def _cols_rows(cells):
    return [c % GW for c, _ in cells], [c // GW for c, _ in cells]


class _Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.env = SimMatchEnv(Config.load())

    def fresh(self):
        self.env.reset()
        e = self.env.eng
        e.units.clear()
        e.spells.clear()
        e.projectiles.clear()
        return e

    def cid(self, base):
        for i, k in enumerate(self.env.deck_keys):
            if k == base or k == base + "_evo":
                return i
        raise AssertionError("%s not in deck" % base)

    def enemy(self, key, x, y, lvl=11):
        e = self.env.eng
        sp = build_spec(e.db, key, lvl)
        u = Unit(spec=sp, team=1, x=x, y=y, hp=sp.hp)
        u.deploy_left = 0.0
        e.units.append(u)
        return u

    def mine(self, key, x, y, lvl=11):
        e = self.env.eng
        sp = build_spec(e.db, key, lvl)
        u = Unit(spec=sp, team=0, x=x, y=y, hp=sp.hp)
        u.deploy_left = 0.0
        e.units.append(u)
        return u


class HogCellTests(_Base):
    def test_quiet_board_hog_cells_are_at_the_bridges_front_row(self):
        self.fresh()
        got = D.doctrine_cells(self.env, self.cid("hog_rider"))
        self.assertTrue(got, "no hog cells on a quiet board")
        cols, rows = _cols_rows(got)
        # every cell on the shallowest deployable rows -- the bridge line, not the back
        self.assertLessEqual(max(rows) - min(rows), 2, "hog cells span deep rows")
        self.assertLess(max(rows), 16, "a hog cell landed in our back half")
        # both bridge lanes represented (quiet board, no mass to punish)
        self.assertTrue(any(c <= 6 for c in cols), "no left-lane bridge cell")
        self.assertTrue(any(c >= 11 for c in cols), "no right-lane bridge cell")

    def test_hog_avoids_the_lane_whose_princess_is_dead(self):
        e = self.fresh()
        e.towers[1][0].hp = 0.0                          # their LEFT princess is gone
        got = D.doctrine_cells(self.env, self.cid("hog_rider"))
        self.assertTrue(got)
        cols, _ = _cols_rows(got)
        self.assertTrue(all(c >= 9 for c in cols),
                        "a hog cell aimed at the dead lane: %s" % cols)

    def test_hog_pressures_opposite_the_committed_mass(self):
        self.fresh()
        self.enemy("golem", 0.75, 0.30)                  # heavy commitment on THEIR right
        got = D.doctrine_cells(self.env, self.cid("hog_rider"))
        self.assertTrue(got)
        w_left = sum(wt for c, wt in got if c % GW < 9)
        w_right = sum(wt for c, wt in got if c % GW >= 9)
        self.assertGreater(w_left, w_right,
                           "the hog prior did not favour the lane opposite the Golem")


class MightyMinerCellTests(_Base):
    def test_miner_goes_on_the_tank(self):
        self.fresh()
        t = self.enemy("giant", 0.30, 0.58)
        got = D.doctrine_cells(self.env, self.cid("mighty_miner"))
        self.assertTrue(got, "no MM cells against a deep Giant")
        best = max(got, key=lambda cw: cw[1])[0]
        self.assertLess(abs(best % GW - int(t.x * GW)), 3, "MM mass is not on the tank's column")

    def test_miner_abstains_against_a_swarm(self):
        """No splash, stage-1 hit cannot one-shot Skeletons: nominating him here would teach
        the exact waste the guides warn about. Abstention -> the uniform floor, not a spot."""
        self.fresh()
        self.enemy("skeleton_army", 0.50, 0.60)
        got = D.doctrine_cells(self.env, self.cid("mighty_miner"))
        self.assertFalse(got, "MM was given a placement prior against a swarm")


class FirecrackerCellTests(_Base):
    def test_kite_band_vs_a_melee_chaser_staggered_to_the_other_lane(self):
        self.fresh()
        self.enemy("mini_pekka", 0.30, 0.55)             # left-lane chaser
        got = D.doctrine_cells(self.env, self.cid("firecracker"))
        self.assertTrue(got)
        cols, rows = _cols_rows(got)
        self.assertTrue(all(13 <= r <= 18 for r in rows),
                        "kite cells outside the 4th-6th-tile band: rows %s" % rows)
        self.assertGreater(min(cols), int(0.30 * GW),
                           "the stagger did not move her toward the other lane")

    def test_air_threat_puts_her_behind_our_line_off_the_tower_column(self):
        self.fresh()
        self.enemy("balloon", 0.25, 0.40)
        got = D.doctrine_cells(self.env, self.cid("firecracker"))
        self.assertTrue(got)
        _, rows = _cols_rows(got)
        # the one-ring neighbourhood spread is deliberate ("the policy learns the AREA"), so the
        # DEPTH claim is asserted on the PEAK cell; the ring may touch one row shallower.
        best_row = max(got, key=lambda cw: cw[1])[0] // GW
        self.assertGreaterEqual(best_row, 15, "her main anti-air cell sits at the bridge")
        self.assertGreaterEqual(min(rows), 13, "a ring cell crossed our front row")
        tower_col = int(self.env.eng.towers[0][0].x * GW)
        best = max(got, key=lambda cw: cw[1])[0] % GW
        self.assertNotEqual(best, tower_col,
                            "her main cell shares the tower column -- one Fireball hits both")

    def test_offense_layers_her_behind_a_crossing_hog(self):
        self.fresh()
        self.mine("hog_rider", 0.745, 0.44)              # our Hog already over the river
        got = D.doctrine_cells(self.env, self.cid("firecracker"))
        self.assertTrue(got, "no FC cells behind our crossing Hog")
        cols, rows = _cols_rows(got)
        self.assertTrue(all(r >= 12 for r in rows), "an FC cell crossed the river")
        self.assertLess(abs(max(cols, key=cols.count) - int(0.745 * GW)), 3,
                        "she is not layered in the Hog's lane")


class IceSpiritCellTests(_Base):
    def test_escorts_our_crossing_hog(self):
        self.fresh()
        self.mine("hog_rider", 0.25, 0.46)
        got = D.doctrine_cells(self.env, self.cid("ice_spirit"))
        self.assertTrue(got)
        best = max(got, key=lambda cw: cw[1])[0]
        self.assertLess(abs(best % GW - int(0.25 * GW)), 3, "escort is in the wrong lane")

    def test_quiet_board_probe_is_at_the_bridges(self):
        self.fresh()
        got = D.doctrine_cells(self.env, self.cid("ice_spirit"))
        self.assertTrue(got, "no probe cells -- the escalation ladder has no opener")
        cols, rows = _cols_rows(got)
        self.assertLess(max(rows), 16, "a probe cell sits in our back half")
        self.assertTrue(any(c <= 6 for c in cols) and any(c >= 11 for c in cols))


class SkeletonsDashKiteTests(_Base):
    def test_bandit_gets_the_centreline_kite_spot(self):
        """The video short's tile-exact rule: centreline one tile toward her lane, on the
        princess-tower-front row -- NOT a surround at her position."""
        self.fresh()
        b = self.enemy("bandit", 0.25, 0.55)
        got = D.doctrine_cells(self.env, self.cid("skeletons"))
        self.assertTrue(got)
        best = max(got, key=lambda cw: cw[1])[0]
        bc, br = best % GW, best // GW
        self.assertIn(bc, (8, 9), "kite cell is not at the centreline: col %d" % bc)
        self.assertGreaterEqual(br, 13, "kite cell is not deep enough")
        self.assertGreater(abs(bc - int(b.x * GW)), 2,
                           "the kite spot degenerated into a surround at the Bandit")


class CardPriorPressureTests(_Base):
    def test_quiet_board_nominates_the_hog_over_holding(self):
        # UPDATED to DOCTRINE_RESEARCH.md SS6 C8 (which this file predated by a few hours): the
        # quiet single-elixir bar is 7 -- after the 4-cost Hog the bank keeps the 3-elixir floor
        # -- while 6 holds. The punish/x2 paths at 4 live in test_hogeq_pressure_doctrine.
        e = self.fresh()
        e.elixir[0] = 7.0
        got = D.doctrine_cards(self.env)
        self.assertTrue(got, "no card prior on a quiet board")
        hog = self.cid("hog_rider")
        if hog in self.env._hand_ids():
            self.assertIn(hog, got, "the Hog was not nominated on a quiet board at 7 elixir")
            self.assertEqual(max(got, key=got.get), hog,
                             "something outweighed the Hog on a quiet board")
        e.elixir[0] = 6.0
        got6 = D.doctrine_cards(self.env) or {}
        self.assertNotIn(hog, got6, "a quiet x1 send at 6 breaks the 3-elixir floor (C8)")


if __name__ == "__main__":
    unittest.main(verbosity=1)
