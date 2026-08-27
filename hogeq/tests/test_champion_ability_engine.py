"""Explosive Escape at the ENGINE level -- `SimEngine.champion_ability`, in both decks.

Deliberately deck-agnostic, and this file is byte-identical in icebow and hogeq (I1, 2026-08-26).
The engine's ability path is shared; the ACTION-SPACE slot that exposes it to the policy is not,
and must not be:

  * hogeq's deck holds the Mighty Miner, so its env gives the ability its own identity and
    `tests/test_champion_ability.py` covers that half (hand vector, cycle, step cost, reward).
  * icebow's deck holds no champion. Adding an identity there would widen the policy's card head
    from 10 to 11 and every existing checkpoint would refuse to load -- a silent, expensive break.
    `test_the_action_space_only_grows_for_a_deck_that_HAS_a_champion` pins that.

The engine path still belongs in both, because the OPPONENT can field a champion: meta decks in
the pool hold Mighty Miner, and a shared engine that behaves differently per deck is exactly the
drift this whole sim-parity pass exists to remove.

The ability's shape (wiki): after a short delay he becomes intangible and moves to the
HORIZONTALLY MIRRORED position -- same depth, opposite lane -- leaving a bomb where he stood, which
detonates for area damage to ground AND air with knockback. Escape, lane switch and swarm answer at
once, which is why firing it early is the classic way to waste it.
"""
from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from clashrl.cards import CardDB                 # noqa: E402
from clashrl.config import Config                # noqa: E402
from clashrl.sim.engine import Unit, build_spec  # noqa: E402
from clashrl.sim.env import SimMatchEnv          # noqa: E402

CHAMP = "mighty_miner"


class ChampionAbilityEngineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cfg = Config.load()
        cls.env = SimMatchEnv(cls.cfg)
        cls.env.reset()

    def _board(self, swarm=0, elixir=10.0, champ_x=0.25, champ_y=0.60, team=0):
        eng = self.env.eng
        eng.units.clear()
        eng.spells.clear()
        mm = build_spec(self.env.db, CHAMP, 14)
        champ = Unit(spec=mm, team=team, x=champ_x, y=champ_y, hp=mm.hp)
        eng.units.append(champ)
        sk = build_spec(self.env.db, "skeleton_army", 11)
        for i in range(swarm):
            eng.units.append(Unit(spec=sk, team=1 - team, x=champ_x + 0.005 * i,
                                  y=champ_y, hp=sk.hp))
        eng.elixir[team] = elixir
        return eng, champ

    # -- the spec ----------------------------------------------------------------------
    def test_the_champion_carries_the_player_triggered_shape(self):
        s = build_spec(self.env.db, CHAMP, 14)
        self.assertGreater(s.ability_bomb_dmg, 0.0)
        self.assertGreater(s.ability_bomb_radius, 0.0)
        self.assertEqual(1.0, s.ability_cost)

    def test_it_carries_no_automatic_invisibility_behaviour(self):
        """Declaring ability_invis_s would hand the champion the Boss Bandit's reaction, firing his
        escape at a random HP threshold nobody chose. The two shapes must stay distinct."""
        self.assertEqual(0.0, build_spec(self.env.db, CHAMP, 14).ability_invis)

    def test_the_bomb_damage_matches_the_published_figure(self):
        """440 at level FOURTEEN, off the published base 332 @ L11. conflicts.md C1, RESOLVED.

        The old reading of this test was the bug. It sought an integer LEVEL-1 base to reproduce
        the owner's observed 440 -- a level CHAMPIONS DO NOT HAVE. decisions.md ruling 9 fixed the
        rarity floors from the Cards page (Common 1 / Rare 3 / Epic 6 / Legendary 9 / CHAMPION 11),
        and anchored there the wiki's own integer base 332 @ L11 walks 332 -> 365 -> 402 -> 440 and
        lands on the observation exactly. The reverse-derived 366 corresponds to no level under any
        model; it was an artefact of anchoring at a nonexistent level 1.
        """
        self.assertAlmostEqual(build_spec(self.env.db, CHAMP, 11).ability_bomb_dmg,
                               332.0, delta=1.0)
        self.assertAlmostEqual(build_spec(self.env.db, CHAMP, 14).ability_bomb_dmg,
                               440.0, delta=2.0)

    # -- refusals ----------------------------------------------------------------------
    def test_the_engine_refuses_it_with_no_champion(self):
        """There is no ability without a body -- it acts on him where he stands."""
        eng = self.env.eng
        eng.units.clear()
        eng.elixir[0] = 10.0
        self.assertFalse(eng.champion_ability(0))
        self.assertEqual(10.0, eng.elixir[0], "a refused ability must not spend elixir")

    def test_only_OUR_champion_counts(self):
        """An ENEMY champion on the board must not arm our ability."""
        eng, _ = self._board(swarm=0, team=1)
        eng.elixir[0] = 10.0
        self.assertFalse(eng.champion_ability(0))

    def test_a_DEAD_champion_does_not_arm_it(self):
        eng, champ = self._board(swarm=0)
        champ.hp = 0.0
        self.assertFalse(eng.champion_ability(0))

    def test_it_will_not_fire_without_the_elixir(self):
        eng, _ = self._board(swarm=4, elixir=0.0)
        self.assertFalse(eng.champion_ability(0))

    # -- the effect --------------------------------------------------------------------
    def test_he_mirrors_to_the_opposite_lane(self):
        eng, champ = self._board(swarm=4, champ_x=0.25)
        self.assertTrue(eng.champion_ability(0))
        self.assertAlmostEqual(champ.x, 0.75, places=6)

    def test_the_mirror_keeps_his_DEPTH(self):
        """Same depth, opposite lane. Moving him up the board would make it a teleport, not a
        lane switch, and would let the ability skip the walk the card is balanced around."""
        eng, champ = self._board(swarm=4, champ_x=0.25, champ_y=0.60)
        eng.champion_ability(0)
        self.assertAlmostEqual(champ.y, 0.60, places=6)

    def test_the_bomb_stays_where_he_LEFT(self):
        """The whole point of the escape: the blast is behind him, on what he walked away from."""
        eng, _ = self._board(swarm=4, champ_x=0.25, champ_y=0.60)
        eng.champion_ability(0)
        bomb = eng.spells[-1]
        self.assertAlmostEqual(bomb.x, 0.25, places=6)
        self.assertAlmostEqual(bomb.y, 0.60, places=6)

    def test_the_bomb_is_fused_not_instant(self):
        eng, _ = self._board(swarm=4)
        eng.champion_ability(0)
        self.assertGreater(eng.spells[-1].t, 0.0)
        self.assertEqual(4, sum(1 for u in eng.units if u.team == 1 and u.hp > 0),
                         "the swarm must still be alive before the fuse burns down")

    def test_the_bomb_clears_the_swarm_it_was_left_for(self):
        eng, _ = self._board(swarm=4)
        eng.champion_ability(0)
        for _ in range(30):
            eng.advance(0.1)
        self.assertEqual(0, sum(1 for u in eng.units if u.team == 1 and u.hp > 0))

    def test_it_spends_exactly_the_ability_cost(self):
        eng, _ = self._board(swarm=4, elixir=8.0)
        eng.champion_ability(0)
        self.assertAlmostEqual(8.0 - eng.elixir[0], 1.0, places=3)

    def test_it_is_SINGLE_USE_per_body(self):
        """4/8/2026 balance: the 13 s cooldown was removed outright and every champion but the Boss
        Bandit gets exactly one activation. Counted per BODY -- see the redeploy test below."""
        eng, _ = self._board(swarm=4, elixir=10.0)
        self.assertTrue(eng.champion_ability(0))
        self.assertFalse(eng.champion_ability(0), "a second activation must be refused")

    def test_a_REDEPLOYED_champion_brings_a_fresh_use(self):
        """One use per DEPLOYMENT, not one per match: he dies, cycles back, and has his again."""
        eng, _ = self._board(swarm=4, elixir=10.0)
        self.assertTrue(eng.champion_ability(0))
        eng.units.clear()
        mm = build_spec(self.env.db, CHAMP, 14)
        eng.units.append(Unit(spec=mm, team=0, x=0.25, y=0.60, hp=mm.hp))
        eng.elixir[0] = 10.0
        self.assertTrue(eng.champion_ability(0))


class ActionSpaceStaysDeckShapedTests(unittest.TestCase):
    """The half that must NOT be shared. A card head is a checkpoint's width."""

    def test_the_action_space_only_grows_for_a_deck_that_HAS_a_champion(self):
        db = CardDB(Config.load())
        ability = db.ability_identity()
        if ability is None:
            self.assertEqual(db.deck_identities(), db.policy_identities(),
                             "this deck has no champion -- widening its card head would break "
                             "every existing checkpoint")
        else:
            self.assertEqual(db.deck_identities() + [ability], db.policy_identities())
            self.assertNotIn(ability, db.deck_identities(),
                             "an ability is an ACTION, not a physical card: the detector and the "
                             "cycle must never see it")

    def test_the_ability_identity_is_keyed_off_the_player_triggered_field(self):
        """`ability_bomb_damage` marks the PLAYER-triggered shape. The automatic Boss-Bandit
        reaction (`ability_invis_s`) is opponent behaviour and must never claim a slot."""
        db = CardDB(Config.load())
        for k in ("bandit", "boss_bandit", "archer_queen"):
            row = db.get(k) or {}
            if row.get("ability_invis_s"):
                self.assertFalse(row.get("ability_bomb_damage"),
                                 "%s would wrongly claim an action-space slot" % k)


if __name__ == "__main__":
    unittest.main()
