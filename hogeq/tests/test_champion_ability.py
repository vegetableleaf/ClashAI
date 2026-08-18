"""Explosive Escape: the Mighty Miner's ability as a real, learnable action.

The engine already had an ability block, but it modelled ONE shape -- invisibility plus a backward
nudge, fired automatically below a random HP fraction. That is the Boss Bandit / Archer Queen
pattern: opponent behaviour. Explosive Escape is none of those things. It is a lane MIRROR, it
leaves a damaging bomb, and it is a PLAYER CHOICE, so it needed an engine path and an action-space
slot of its own.

The slot is a pseudo-card: it costs elixir and it is a decision, but it has no placement, so its
cell is ignored. Two properties matter enough to pin down here, because breaking either is silent:
it must NOT rotate the cycle (it is not a card leaving the hand), and the sim's identity list must
stay byte-identical to the live one (11 vs 10 outputs = a checkpoint that will not load to play).
"""
from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from clashrl.cards import CardDB                 # noqa: E402
from clashrl.config import Config                # noqa: E402
from clashrl.sim import doctrine as D            # noqa: E402
from clashrl.sim.engine import Unit, build_spec  # noqa: E402
from clashrl.sim.env import SimMatchEnv          # noqa: E402


class ChampionAbilityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cfg = Config.load()
        cls.env = SimMatchEnv(cls.cfg)
        cls.env.reset()

    def _board(self, swarm=0, elixir=10.0, champ_x=0.25, champ_y=0.60):
        env = self.env
        env.eng.units.clear()
        env.eng.spells.clear()
        mm = build_spec(env.db, "mighty_miner", 14)
        champ = Unit(spec=mm, team=0, x=champ_x, y=champ_y, hp=mm.hp)
        env.eng.units.append(champ)
        sk = build_spec(env.db, "skeleton_army", 11)
        for i in range(swarm):
            env.eng.units.append(Unit(spec=sk, team=1, x=champ_x + 0.005 * i, y=champ_y, hp=sk.hp))
        env.eng.elixir[0] = elixir
        return env, champ

    # -- the identity ------------------------------------------------------------------
    def test_the_ability_is_its_own_identity(self):
        env = self.env
        self.assertGreaterEqual(env.ability_id, 0)
        self.assertEqual(env.deck_keys[env.ability_id], "mighty_miner_ability")
        self.assertEqual(env.specs[env.ability_id].elixir, 1.0)

    def test_sim_and_live_action_spaces_are_identical(self):
        """A mismatch here means a sim-trained checkpoint silently fails to load for live play."""
        self.assertEqual(CardDB(self.cfg).policy_identities(), list(self.env.deck_keys))

    def test_policy_identities_is_the_action_space_and_deck_identities_is_not(self):
        """The distinction that broke train-rl: the deck has 10 CARDS but the policy has 11 ACTIONS,
        and the deck guard compared the checkpoint against the card list."""
        db = CardDB(self.cfg)
        self.assertEqual(len(db.deck_identities()) + 1, len(db.policy_identities()))
        self.assertNotIn("mighty_miner_ability", db.deck_identities())
        self.assertEqual("mighty_miner_ability", db.policy_identities()[-1])

    def test_the_ability_is_not_a_physical_card(self):
        """It must never reach deck_slots -- it has no hand position and does not cycle."""
        db = CardDB(self.cfg)
        self.assertEqual(8, len(db.deck_slots()))
        self.assertNotIn("mighty_miner_ability", [s["base"] for s in db.deck_slots()])

    def test_the_ability_costs_its_OWN_elixir(self):
        """It has no card row, so this returned None and the callers' `or 0` made it read as FREE;
        folding the suffix to the champion instead would have priced it at his 4."""
        db = CardDB(self.cfg)
        self.assertEqual(1, db.elixir("mighty_miner_ability"))
        self.assertEqual(4, db.elixir("mighty_miner"))

    def test_the_live_affordability_vector_prices_it(self):
        """This is the vector play.py masks card logits with -- a 0 here means the bot would fire
        the ability with an empty bar, and the game would simply refuse the tap."""
        db = CardDB(self.cfg)
        keys = db.policy_identities()
        costs = [(db.elixir(k) or db.elixir(k[:-4] if k.endswith("_evo") else k) or 0) for k in keys]
        self.assertEqual(1, costs[keys.index("mighty_miner_ability")])
        self.assertTrue(all(c > 0 for c in costs), "some identity has no cost: %s" % costs)

    def test_it_is_not_in_the_cycle(self):
        """It is not a card leaving the hand, so playing it must not rotate the deck."""
        env, _ = self._board(swarm=4)
        self.assertNotIn(env.ability_id, env.slot_of)
        before = list(env.cycle)
        env.step((1, env.ability_id, 0))
        self.assertEqual(before, list(env.cycle))

    # -- availability ------------------------------------------------------------------
    def test_unavailable_with_no_champion_on_the_board(self):
        env = self.env
        env.eng.units.clear()
        self.assertNotIn(env.ability_id, env._hand_ids())

    def test_the_engine_refuses_it_with_no_champion(self):
        """Guarded in BOTH layers on purpose: the hand check keeps it out of the action space, and
        this keeps a hand-desync or a hand-crafted action from firing an ability with no body."""
        env = self.env
        env.eng.units.clear()
        env.eng.elixir[0] = 10.0
        self.assertFalse(env.eng.champion_ability(0))

    def test_a_forced_ability_action_with_no_champion_costs_nothing(self):
        """The failure that would matter in training: elixir quietly spent on a no-op."""
        env = self.env
        env.reset()
        env.eng.units.clear()
        env.eng.elixir[0] = 10.0
        env.step((1, env.ability_id, 200))
        self.assertEqual(10.0, env.eng.elixir[0])

    def test_only_OUR_champion_counts(self):
        """An enemy Mighty Miner on the board must not arm our ability."""
        env = self.env
        env.reset()
        env.eng.units.clear()
        mm = build_spec(env.db, "mighty_miner", 14)
        env.eng.units.append(Unit(spec=mm, team=1, x=0.5, y=0.3, hp=mm.hp))
        env.eng.elixir[0] = 10.0
        self.assertNotIn(env.ability_id, env._hand_ids())
        self.assertFalse(env.eng.champion_ability(0))

    def test_a_DEAD_champion_does_not_arm_it(self):
        env, champ = self._board(swarm=0)
        champ.hp = 0.0
        self.assertNotIn(env.ability_id, env._hand_ids())
        self.assertFalse(env.eng.champion_ability(0))

    def test_available_once_the_champion_is_out(self):
        env, _ = self._board()
        self.assertIn(env.ability_id, env._hand_ids())

    def test_it_is_SINGLE_USE(self):
        """4/8/2026 balance: "no longer have a cooldown timer in-between abilities. Instead, his
        ability will now be single use." Every champion but the Boss Bandit gets exactly one."""
        env, champ = self._board(swarm=4)
        self.assertEqual(1, champ.spec.ability_uses)
        self.assertTrue(env.eng.champion_ability(0))
        self.assertFalse(env.eng.champion_ability(0), "the ability fired a second time")
        self.assertNotIn(env.ability_id, env._hand_ids())

    def test_a_spent_ability_never_comes_back(self):
        """There is no cooldown to wait out any more -- waiting must not refill it."""
        env, _ = self._board(swarm=4)
        env.eng.champion_ability(0)
        for _ in range(300):                       # 30 s, well past the old 13 s cooldown
            env.eng.advance(0.1)
        self.assertNotIn(env.ability_id, env._hand_ids())
        self.assertFalse(env.eng.champion_ability(0))

    def test_a_REDEPLOYED_champion_brings_a_fresh_use(self):
        """One use per BODY, not per match: he dies, he cycles back, he has it again."""
        env, _ = self._board(swarm=4)
        env.eng.champion_ability(0)
        env, champ2 = self._board(swarm=4)         # a new Mighty Miner on the board
        self.assertEqual(1, env.eng._ability_uses_left(champ2))
        self.assertIn(env.ability_id, env._hand_ids())
        self.assertTrue(env.eng.champion_ability(0))

    def test_the_spent_ability_leaves_the_action_space(self):
        """It must not linger in hand_vec as a legal action the policy can never take."""
        env, _ = self._board(swarm=4)
        env.step((1, env.ability_id, 0))
        env._update_vectors()
        self.assertEqual(0.0, float(env.hand_vec[env.ability_id]))

    def test_it_will_not_fire_without_the_elixir(self):
        env, _ = self._board(swarm=4, elixir=0.0)
        self.assertFalse(env.eng.champion_ability(0))

    # -- the effect --------------------------------------------------------------------
    def test_he_mirrors_to_the_opposite_lane(self):
        env, champ = self._board(swarm=4, champ_x=0.25)
        env.eng.champion_ability(0)
        self.assertAlmostEqual(champ.x, 0.75, places=6)

    def test_the_bomb_stays_where_he_LEFT(self):
        """The whole point of the escape: the blast is behind him, on what he walked away from."""
        env, _ = self._board(swarm=4, champ_x=0.25, champ_y=0.60)
        env.eng.champion_ability(0)
        bomb = env.eng.spells[-1]
        self.assertAlmostEqual(bomb.x, 0.25, places=6)
        self.assertAlmostEqual(bomb.y, 0.60, places=6)

    def test_the_bomb_is_fused_not_instant(self):
        env, _ = self._board(swarm=4)
        env.eng.champion_ability(0)
        self.assertGreater(env.eng.spells[-1].t, 0.0)
        self.assertEqual(4, sum(1 for u in env.eng.units if u.team == 1 and u.hp > 0),
                         "the swarm must still be alive before the fuse burns down")

    def test_the_bomb_clears_the_swarm_it_was_left_for(self):
        env, _ = self._board(swarm=4)
        env.eng.champion_ability(0)
        for _ in range(30):
            env.eng.advance(0.1)
        self.assertEqual(0, sum(1 for u in env.eng.units if u.team == 1 and u.hp > 0))

    def test_the_bomb_damage_matches_the_published_figure(self):
        """440 at level 13 (user-supplied). No integer level-1 base gives exactly that; base 143 --
        the nearest real entry on the game's table -- gives 441, stored as 366 at the KB's L11."""
        self.assertAlmostEqual(build_spec(self.env.db, "mighty_miner", 13).ability_bomb_dmg,
                               441.0, delta=1.0)

    def test_it_carries_no_automatic_invisibility_behaviour(self):
        """Declaring ability_invis_s would hand our champion the Boss Bandit's reaction, firing his
        escape at a random HP threshold nobody chose."""
        self.assertEqual(0.0, build_spec(self.env.db, "mighty_miner", 14).ability_invis)

    # -- the action path ---------------------------------------------------------------
    def test_step_spends_exactly_the_ability_cost(self):
        """A step also REGENERATES elixir, so the cost is only visible against a step that did
        nothing. Starting BELOW the cap matters: from a full bar the idle step's regen is clipped
        away and the comparison silently measures the cap instead of the cost."""
        env, _ = self._board(swarm=4, elixir=8.0)
        env.step((0, -1, 0))                              # wait: regen only
        idle = env.eng.elixir[0]
        env, _ = self._board(swarm=4, elixir=8.0)
        env.step((1, env.ability_id, 0))                  # same step, but the ability fires
        self.assertAlmostEqual(idle - env.eng.elixir[0], 1.0, places=3)

    def test_the_chosen_cell_is_ignored(self):
        """No placement: every cell must produce the same outcome."""
        outs = []
        for cell in (0, 200, 431):
            env, champ = self._board(swarm=4)
            env.step((1, env.ability_id, cell))
            outs.append(round(champ.x, 6))
        self.assertEqual(1, len(set(outs)), "the cell changed the result: %s" % outs)

    def test_a_wasted_escape_is_charged(self):
        env, _ = self._board(swarm=0)
        env.eng.champion_ability(0)
        self.assertLess(env._ability_value(), 0.0)

    def test_catching_their_answer_pays(self):
        env, _ = self._board(swarm=4)
        env.eng.champion_ability(0)
        self.assertGreater(env._ability_value(), 0.0)

    # -- doctrine ----------------------------------------------------------------------
    def test_doctrine_holds_it_until_their_answer_is_on_him(self):
        """Every guide makes this the whole skill: triggering early is how the ability is wasted."""
        env, _ = self._board(swarm=1)
        self.assertNotIn("mighty_miner_ability",
                         {env.deck_keys[k] for k in (D.doctrine_cards(env) or {})})

    def test_doctrine_nominates_it_against_a_swarm_standing_on_him(self):
        env, _ = self._board(swarm=4)
        self.assertIn("mighty_miner_ability",
                      {env.deck_keys[k] for k in (D.doctrine_cards(env) or {})})

    def test_doctrine_asks_for_no_placement(self):
        env, _ = self._board(swarm=4)
        self.assertIsNone(D.doctrine_cells(env, env.ability_id))


if __name__ == "__main__":
    unittest.main()
