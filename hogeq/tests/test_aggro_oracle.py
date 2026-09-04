"""The aggro oracle answers the owner's targeting questions from the ENGINE (HANDOFF §5br / L18).

Each test is one of the questions on a fixed board: who locks onto whom, what happens after a kill, what a
tornado / knight placement changes, how long the interposition window is, who wins a duel. The oracle
must (1) never mutate the caller's engine, (2) agree with simply advancing the real engine (it is a fork,
not a second rule set), and (3) return the same answer twice (determinism is the whole premise).
"""
from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from clashrl.config import Config                       # noqa: E402
from clashrl.sim.aggro_oracle import AggroOracle, Target  # noqa: E402
from clashrl.sim.engine import Unit, build_spec         # noqa: E402
from clashrl.sim.env import SimMatchEnv                 # noqa: E402

BOW, VALK_X = 0.26, 0.26


class AggroOracleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.env = SimMatchEnv(Config.load())

    def board(self, *spawns):
        self.env.reset()
        e = self.env.eng
        e.units.clear(); e.spells.clear(); e.projectiles.clear()
        out = []
        for key, team, x, y in spawns:
            s = build_spec(e.db, key, 11)
            u = Unit(spec=s, team=team, x=x, y=y, hp=s.hp)
            e.units.append(u); out.append(u)
        e.advance(0.1)
        return e, out

    # -- who locks onto whom ---------------------------------------------------------------
    def test_target_of_and_targeted_by_agree_with_the_engine(self):
        e, (xb, vk) = self.board(("x_bow", 0, BOW, 0.53), ("valkyrie", 1, VALK_X, 0.40))
        o = AggroOracle(e)
        self.assertTrue(o.target_of(vk, 2.0).is_(xb))              # the Valkyrie walks at the bow
        self.assertTrue(o.target_of(xb, 0.0).is_(vk))              # the bow sees her (11.5 sight)
        self.assertEqual([t.ref for t in o.targeted_by(xb, 1.0)], [vk])
        # ...and the real engine, advanced the same way, says the same thing
        t0, n = e.t, len(e.units)
        for _ in range(20):
            e.advance(0.1)
        self.assertIs(vk.target, xb)
        # the oracle never touched the caller's engine (the 20 ticks above are the test's own)
        self.assertEqual(n, 2)

    def test_queries_do_not_mutate_the_engine(self):
        e, (xb, vk) = self.board(("x_bow", 0, BOW, 0.53), ("valkyrie", 1, VALK_X, 0.40))
        o = AggroOracle(e)
        t, y, hp = e.t, vk.y, xb.hp
        o.target_of(vk, 5.0); o.draws(0, "knight", BOW, 0.46); o.after_spell(0, "tornado", 0.472, 0.771)
        o.interpose_window(0, "knight", BOW, 0.46, vk, xb, max_delay_s=1.0); o.duel("knight", "valkyrie")
        self.assertEqual((t, y, hp), (e.t, vk.y, xb.hp))
        self.assertEqual(len(e.units), 2)

    def test_answers_are_deterministic(self):
        e, (xb, vk) = self.board(("x_bow", 0, BOW, 0.53), ("valkyrie", 1, VALK_X, 0.40))
        o = AggroOracle(e)
        a = (o.next_target_after_kill(vk), o.interpose_window(0, "knight", BOW, 0.46, vk, xb),
             o.duel("knight", "valkyrie"))
        b = (o.next_target_after_kill(vk), o.interpose_window(0, "knight", BOW, 0.46, vk, xb),
             o.duel("knight", "valkyrie"))
        self.assertEqual(a, b)

    # -- once it kills this, what next -----------------------------------------------------
    def test_next_target_after_the_bow_dies_is_the_princess(self):
        e, (xb, vk) = self.board(("x_bow", 0, BOW, 0.53), ("valkyrie", 1, VALK_X, 0.40))
        t, nxt = AggroOracle(e).next_target_after_kill(vk)
        self.assertIsNotNone(t)
        self.assertEqual(nxt.kind, "tower")
        self.assertIs(nxt.ref, e.towers[0][0])                      # our LEFT princess, same lane

    # -- the knight tanks for the bow ------------------------------------------------------
    def test_knight_placed_in_front_of_the_bow_draws_the_walking_valkyrie(self):
        e, (xb, vk) = self.board(("x_bow", 0, BOW, 0.53), ("valkyrie", 1, VALK_X, 0.40))
        d = AggroOracle(e).draws(0, "knight", BOW, 0.46, horizon_s=1.0)
        self.assertTrue(d.z_alive)
        self.assertTrue(d.z_target.is_(vk))                          # the knight goes for her
        self.assertIn(vk, [t.ref for t in d.drawn])                 # and she goes for the knight
        # (0.46 is across the river: the enemy princess tower shoots the knight too -- also in `drawn`)
        self.assertIn(e.towers[1][0], [t.ref for t in d.drawn])

    def test_interposition_window_closes_when_the_valkyrie_starts_swinging(self):
        e, (xb, vk) = self.board(("x_bow", 0, BOW, 0.53), ("valkyrie", 1, VALK_X, 0.40))
        latest_ok, first_fail, hit_at = AggroOracle(e).interpose_window(0, "knight", BOW, 0.46, vk, xb)
        self.assertIsNotNone(latest_ok)
        self.assertIsNotNone(hit_at)
        self.assertLess(latest_ok, hit_at + 1e-9)                    # you have until her first hit...
        self.assertIsNotNone(first_fail)
        self.assertGreaterEqual(first_fail, hit_at - 1e-9)           # ...and no longer: locked = kept

    # -- tornado king activation -----------------------------------------------------------
    def test_tornado_in_front_of_the_king_retargets_a_hog_from_princess_to_king(self):
        e, (hog,) = self.board(("hog_rider", 1, 0.25, 0.62))
        for _ in range(60):                                         # let it arrive and start chewing
            e.advance(0.1)
            if hog.locked:
                break
        self.assertTrue(hog.locked)
        o = AggroOracle(e)
        self.assertTrue(o.target_of(hog).is_(e.towers[0][0]))
        m = o.after_spell(0, "tornado", 0.472, 0.771, settle_s=2.0)
        _, before, after = m[id(hog)]
        self.assertTrue(before.is_(e.towers[0][0]))
        self.assertTrue(after.is_(e.towers[0][2]))                   # the king
        self.assertFalse(e.towers[0][2].active)                      # the caller's king untouched

    # -- duel -------------------------------------------------------------------------------
    def test_duel_reports_winner_and_hp_left(self):
        e, _ = self.board()
        o = AggroOracle(e)
        d = o.duel("mini_pekka", "knight")
        self.assertEqual(d.winner, "mini_pekka")
        self.assertGreater(d.hp_left, 0.0)
        self.assertLess(d.hp_left_frac, 1.0)
        r = o.duel("knight", "mini_pekka")                           # order does not change the answer
        self.assertEqual(r.winner, "mini_pekka")
        self.assertAlmostEqual(r.hp_left, d.hp_left, delta=max(1.0, 0.05 * d.hp_left))


if __name__ == "__main__":
    unittest.main()
