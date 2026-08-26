"""The Rocket decision gates from DOCTRINE_RESEARCH.md (2026-08-19).

THE MEASURED PROBLEM (policy-stats, 40 greedy matches, policy_sim_ppo_best.pt):
Rocket was played **2 times out of 1288 plays (0.2%)** while The Log took 18.9%. The card prior
already nominated Rocket, but its "no cheaper answer" gate required that NOTHING else in hand was
affordable -- a board state that essentially never happens -- so the one trigger a professional
actually uses was unreachable.

Hunter CR (pro X-Bow specialist) states the trigger as a HAND condition, not a value judgement:
rocket a committed body when the deck's designated answers (Knight, Tesla) are out of rotation.
That matters mechanically here: `sim/doctrine.py` is rollout-only, so the prior has been sampling
Rocket for 14,300+ matches without the policy learning to value it -- the payoff is too rare and
too precise to find by sampling, but a hand condition is learnable.

These tests pin the CAST triggers and, just as importantly, the VETOES -- the "misuse" half of
the user's complaint. Several vetoes exist because an adversarial verification pass caught the
research pool misreading its own sources (see DOCTRINE_RESEARCH.md SS6).
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


class _Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.env = SimMatchEnv(Config.load())

    def fresh(self, elixir=10.0):
        self.env.reset()
        e = self.env.eng
        e.units.clear()
        e.spells.clear()
        e.projectiles.clear()
        e.elixir[0] = elixir
        # NEUTRALISE THE TIEBREAK-RACE RULE (prior rule 5), which bumps rocket to 4.5 whenever we
        # are defensive and level-or-behind on the lowest-tower race -- true at every fresh board,
        # so it would mask every gate under test. Worth stating plainly: that rule alone means the
        # prior ALREADY nominates rocket at 4.5 in most defensive states, and the policy still
        # played it 2 times in 1288. The prior was never the bottleneck; the gates are.
        self.env._defensive = False
        return e

    def win_the_tiebreak(self):
        """The OTHER half of neutralising prior rule 5, needed once a test moves into overtime.

        `_defensive = False` only disarms rule 5 while `t < _double_time`; past that its second
        trigger re-arms it, and it then bumps rocket to 4.5 whenever `op_low >= my_low`. Whether
        that holds on a fresh board is decided by the RANDOMLY SAMPLED enemy tower level (measured:
        ours 4424 vs theirs 4858 under one seed, the reverse under another), so an overtime test
        that does not pin the race is really testing the deal -- it went red the moment an unrelated
        change (I3, one extra draw from the same RNG) shifted the sampled level. Making our lowest
        tower the healthier one puts rule 5 off for a stated reason instead of a lucky one."""
        e = self.env.eng
        low = min(t.hp for t in e.towers[0][:2] if t.alive)
        for t in e.towers[1][:2]:
            t.hp = min(t.hp, low - 1.0)
        return e

    def cid(self, base):
        for i, k in enumerate(self.env.deck_keys):
            if k == base or k == base + "_evo":
                return i
        raise AssertionError("%s not in deck" % base)

    def hand(self, *bases):
        """Pin the hand to exactly these cards (plus rocket), so 'in rotation' is controlled."""
        ids = [self.cid(b) for b in bases]
        self.env._hand_ids = lambda: ids
        return ids

    def enemy(self, key, x, y, lvl=11, hp_mult=1.0):
        e = self.env.eng
        sp = build_spec(e.db, key, lvl)
        u = Unit(spec=sp, team=1, x=x, y=y, hp=sp.hp * hp_mult)
        u.deploy_left = 0.0
        e.units.append(u)
        return u

    def rocket_weight(self):
        got = D.doctrine_cards(self.env) or {}
        return got.get(self.cid("rocket"), 0.0)


class CycleStateTriggerTests(_Base):
    """R1 -- the fix for the 0.2% number."""

    def test_rocket_is_nominated_when_knight_and_tesla_are_out_of_rotation(self):
        self.fresh()
        self.hand("rocket", "skeletons", "ice_wizard", "the_log")
        self.enemy("prince", 0.50, 0.58)                  # a committed 5-elixir body
        self.assertGreater(self.rocket_weight(), 3.5,
                           "rocket not nominated with both designated answers out of hand")

    def test_rocket_is_not_the_answer_while_the_knight_is_in_hand(self):
        """The cheap answer exists, so the 6-elixir spell must not outrank it."""
        self.fresh()
        self.hand("rocket", "knight", "skeletons", "the_log")
        self.enemy("prince", 0.50, 0.58)
        self.assertLessEqual(self.rocket_weight(), 3.5,
                             "rocket outranked an in-hand Knight against one body")

    def test_the_tesla_alone_also_counts_as_a_designated_answer(self):
        self.fresh()
        self.hand("rocket", "tesla", "skeletons", "the_log")
        self.enemy("prince", 0.50, 0.58)
        self.assertLessEqual(self.rocket_weight(), 3.5)

    def test_a_quiet_board_still_does_not_nominate_rocket_on_cycle_state(self):
        """No committed threat -> the cycle-state rule must not fire at all."""
        self.fresh()
        self.hand("rocket", "skeletons", "ice_wizard", "the_log")
        self.assertLessEqual(self.rocket_weight(), 3.0,
                             "rocket nominated at an empty board")


class OverspendTestTests(_Base):
    """R3 -- Hunter's own worst play of a match was a rocket he did NOT cast."""

    def test_chaining_seven_plus_elixir_of_chip_loses_to_the_rocket(self):
        """Ice Wizard (3) + Tornado (3) is 6; add the Log and the stack passes 7. With no
        Knight/Tesla the deck cannot stop a heavy body cheaply, so 6 on the rocket wins."""
        self.fresh()
        self.hand("rocket", "ice_wizard", "tornado", "the_log")
        self.enemy("pekka", 0.50, 0.58)
        self.assertGreater(self.rocket_weight(), 3.0)


class LethalityAndVetoTests(_Base):
    """The MISUSE half of the complaint -- every veto here comes from a verifier correction."""

    def test_a_royal_giant_next_to_the_tower_is_not_a_two_for_one(self):
        """SS1.1 R4: the Rocket does NOT kill a Royal Giant. The pool generalised '4+ elixir
        supports will be one-shot'; the verifier rejected it. Removal rules need a real kill."""
        e = self.fresh()
        self.hand("rocket", "knight", "tesla", "the_log")
        t = e.towers[1][0]
        rg = self.enemy("royal_giant", t.x, t.y + 0.02)
        self.assertGreater(rg.hp, float(self.env.specs[self.cid("rocket")].spell_dmg),
                           "probe invalid: this RG would actually die to the rocket")
        self.assertLessEqual(self.rocket_weight(), 3.5,
                             "rocket nominated as a 2-for-1 on a body it cannot kill")

    def test_a_musketeer_next_to_the_tower_still_is_a_two_for_one(self):
        """The control: the rule must keep firing where the body genuinely dies."""
        e = self.fresh()
        self.hand("rocket", "knight", "tesla", "the_log")
        t = e.towers[1][0]
        mk = self.enemy("musketeer", t.x, t.y + 0.02)
        self.assertLess(mk.hp, float(self.env.specs[self.cid("rocket")].spell_dmg),
                        "probe invalid: this musketeer would survive")
        self.assertGreaterEqual(self.rocket_weight(), 4.0)

    def test_giant_skeleton_is_answered_by_the_building_not_the_spell(self):
        """N3: Hunter's measured error -- Rocket+Log instead of Tesla, tower lost."""
        self.fresh()
        self.hand("rocket", "tesla", "skeletons", "the_log")
        self.enemy("giant_skeleton", 0.50, 0.58)
        self.assertLessEqual(self.rocket_weight(), 3.0,
                             "rocket nominated against a Giant Skeleton while Tesla was in hand")

    def test_a_lone_sparky_is_tornadoed_into_the_knight_not_rocketed(self):
        """N6: the quote is 'rocket the sparkies anytime he puts value WITH them' -- conditioned
        on accompanying investment. The pool read it as 'on sight', which is the opposite."""
        self.fresh()
        self.hand("rocket", "tornado", "knight", "the_log")
        self.enemy("sparky", 0.50, 0.58)
        self.assertLessEqual(self.rocket_weight(), 3.0,
                             "rocket nominated on an UNSUPPORTED sparky")

    def test_a_supported_sparky_is_a_rocket_again(self):
        self.fresh()
        self.hand("rocket", "tornado", "knight", "the_log")
        self.enemy("sparky", 0.50, 0.58)
        self.enemy("musketeer", 0.53, 0.55)               # the accompanying investment
        self.assertGreater(self.rocket_weight(), 0.0,
                           "a SUPPORTED sparky must still be rocket-worthy")


class PumpGateTests(_Base):
    """R5 -- the existing fresh-pump rule had no overtime or board-threat gate."""

    def test_a_fresh_pump_on_a_clear_board_is_still_rocketed(self):
        self.fresh()
        self.hand("rocket", "knight", "tesla", "the_log")
        self.enemy("elixir_collector", 0.30, 0.30)
        self.assertGreaterEqual(self.rocket_weight(), 4.0)

    def test_the_pump_is_not_rocketed_in_overtime(self):
        """'Once overtime starts you stop rocketing pumps -- the tower is worth more.'"""
        e = self.fresh()
        self.win_the_tiebreak()          # else prior rule 5 re-arms in overtime and masks this one
        self.hand("rocket", "knight", "tesla", "the_log")
        self.enemy("elixir_collector", 0.30, 0.30)
        before = self.rocket_weight()
        e.t = self.env._double_time + 1.0
        self.assertLess(self.rocket_weight(), before,
                        "the pump rule ignored overtime")

    def test_the_pump_is_not_rocketed_while_a_real_push_is_committed(self):
        """He declined a pump rocket at 7 elixir because he could not survive what came next."""
        self.fresh()
        self.hand("rocket", "knight", "tesla", "the_log")
        self.enemy("elixir_collector", 0.30, 0.30)
        clean = self.rocket_weight()
        self.enemy("golem", 0.50, 0.55)                   # a push that must be answered
        self.enemy("mega_minion", 0.52, 0.53)
        self.assertLess(self.rocket_weight(), clean,
                        "the pump rule ignored a committed push")


class NeverTheKingTests(_Base):
    """N4 -- REJECTED from the pool. No crown, ~4.8k HP, and it ACTIVATES their king."""

    def test_no_rocket_cell_ever_targets_the_enemy_king(self):
        e = self.fresh()
        self.hand("rocket", "knight", "tesla", "the_log")
        self.enemy("musketeer", e.towers[1][0].x, e.towers[1][0].y + 0.02)
        got = D.doctrine_cells(self.env, self.cid("rocket")) or []
        self.assertTrue(got, "no rocket cells in a 2-for-1 state")
        king = e.towers[1][2]
        gw = 18
        for cell, _wt in got:
            col, row = cell % gw, cell // gw
            near_king = abs(col - int(king.x * gw)) <= 1 and abs(row - int(king.y * 24)) <= 1
            self.assertFalse(near_king, "a rocket cell aimed at the enemy KING tower")


if __name__ == "__main__":
    unittest.main(verbosity=1)
