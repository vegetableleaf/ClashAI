"""RULING 31a -- the Electro Giant's Zap Pack answers EVERY attacker, not only melee troops.

Sources: Electro_Giant.wikitext revid 436724 ("Enemy units who damage the Electro Giant while
being within a 3-tile radius of him will be damaged and stunned for 0.5 seconds with each hit";
level table columns "Reflected Damage" reflect_11 192 and "Reflected Tower Damage" crown_11 97;
History 16/12/2024 "fixed a bug where Electro Giant's Zap Pack would not deal reduced damage to
the King Tower") + the owner report 2026-08-27: "electro giant's reflection stun/damage applies
to anything inside the reflection radius. this includes buildings and crown towers", clarified
per-attacker-on-damage: each hit zaps ITS OWN attacker; a bystander in the zone who is not
hitting him takes nothing; there is no zone blast.

MEASURED before the fix (engine at 1143af2): the three melee attackers each took 192 + 0.5 s stun
(that shape already existed), but a Musketeer firing from 2.0 tiles took 0.0 back, a Cannon
firing from 2.0 tiles took 0.0, and a Princess Tower shooting him point-blank took 0.0 and was
never stunned -- every projectile path discarded the firer. His NORMAL swing was also
crown-reduced to 97.0 per hit (vs hit_dmg 163.8 @ L11) because the reflect-crown figure was
parked on the generic crown_tower_damage field; the page's Trivia reduces only his REFLECTING
damage.

SHARED, byte-identical in both decks: every assertion is about the ENGINE and the KB, not a deck.
"""
from __future__ import annotations

import random
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
for _p in (str(SRC), str(ROOT / "tests")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from clashrl.cards import CardDB                                   # noqa: E402
from clashrl.sim.engine import (SimEngine, Unit, build_spec,       # noqa: E402
                                _TILES_X, _TILES_Y, _dist)

from test_sim_status_effects import DummyCfg                       # noqa: E402


def _engine() -> SimEngine:
    return SimEngine(DummyCfg(), CardDB(path=ROOT / "config" / "cards.yaml"), random.Random(0))


def _giant(eng, x=0.5, y=0.55, team=1, hp=4000.0) -> Unit:
    u = Unit(spec=build_spec(eng.db, "electro_giant", 11), team=team, x=x, y=y, hp=hp)
    eng.units.append(u)
    return u


def _body(eng, base, team, x, y, hp=2000.0, level=11) -> Unit:
    u = Unit(spec=build_spec(eng.db, base, level), team=team, x=x, y=y, hp=hp)
    eng.units.append(u)
    return u


class ZapPackPerAttackerTests(unittest.TestCase):
    """The owner-clarified shape: per-attacker, on damage -- pinned so no later pass can drift it
    back toward a zone blast (or forward into one)."""

    def test_three_attackers_each_take_their_own_reflection_and_the_bystander_none(self):
        eng = _engine()
        eg = _giant(eng)
        atk = [_body(eng, "knight", 0, eg.x + 1.5 / _TILES_X, eg.y),
               _body(eng, "knight", 0, eg.x - 1.5 / _TILES_X, eg.y),
               _body(eng, "knight", 0, eg.x, eg.y + 1.5 / _TILES_Y)]
        bystander = _body(eng, "knight", 0, eg.x, eg.y - 2.0 / _TILES_Y)
        outside = _body(eng, "musketeer", 0, eg.x + 5.0 / _TILES_X, eg.y)
        for u in atk:
            eng._land_hit(0, "unit", eg, u.spec, u.spec.hit_dmg, u.spec.hit_dmg, attacker=u)
        # the out-of-zone attacker DOES damage him -- and is not zapped, because it is outside
        eng._land_hit(0, "unit", eg, outside.spec, outside.spec.hit_dmg,
                      outside.spec.hit_dmg, attacker=outside)
        for u in atk:
            self.assertAlmostEqual(2000.0 - u.hp, eg.spec.reflect_dmg, places=1,
                                   msg="each attacker takes its OWN reflection on its own hit")
            self.assertAlmostEqual(u.stun_left, eg.spec.reflect_stun, places=3)
        self.assertAlmostEqual(bystander.hp, 2000.0, places=3,
                               msg="a bystander inside the zone who never hit him takes NOTHING "
                                   "(owner clarification: no zone blast)")
        self.assertAlmostEqual(outside.hp, 2000.0, places=3,
                               msg="an attacker outside reflect_r is untouched")
        self.assertEqual(outside.stun_left, 0.0)

    def test_a_ranged_attacker_firing_from_inside_the_zone_is_zapped_through_its_projectile(self):
        """"the Electro Wizard and the Executioner ... effectively hitting themselves" -- ranged
        attackers inside the radius take the reflection per hit. Before the fix the projectile
        impact path dropped the firer and this was 0.0."""
        eng = _engine()
        eg = _giant(eng)
        mus = _body(eng, "musketeer", 0, eg.x + 2.0 / _TILES_X, eg.y, hp=720.0)
        eng._attack(mus, "unit", eg)
        for _ in range(40):
            eng._tick_projectiles(0.1)
        self.assertAlmostEqual(720.0 - mus.hp, eg.spec.reflect_dmg, places=1)
        self.assertGreater(mus.stun_left, 0.0)

    def test_a_defending_building_shooting_him_from_inside_the_zone_is_zapped(self):
        """Owner: "this includes buildings". A building is a Unit body, so it takes the full 192
        through the unit path -- what makes walking onto a Cannon or Tesla expensive for it."""
        eng = _engine()
        eg = _giant(eng)
        can = _body(eng, "cannon", 0, eg.x + 2.0 / _TILES_X, eg.y, hp=800.0)
        eng._attack(can, "unit", eg)
        for _ in range(40):
            eng._tick_projectiles(0.1)
        self.assertAlmostEqual(800.0 - can.hp, eg.spec.reflect_dmg, places=1)
        self.assertGreater(can.stun_left, 0.0)

    def test_the_zap_pack_is_off_while_he_is_stunned_or_frozen(self):
        """"The Electro Giant does not inflict any reflected damage if he is frozen." """
        eng = _engine()
        eg = _giant(eng)
        eg.stun_left = 1.0
        atk = _body(eng, "knight", 0, eg.x + 1.5 / _TILES_X, eg.y)
        eng._land_hit(0, "unit", eg, atk.spec, atk.spec.hit_dmg, atk.spec.hit_dmg, attacker=atk)
        self.assertAlmostEqual(atk.hp, 2000.0, places=3)

    def test_the_zap_does_not_reset_a_charge(self):
        """"even if the Sparky is in the zap radius, her attack would still charge up and not be
        reset by the reflect damage" -- unlike _apply_status's stun, the zap wipes neither the
        target lock nor charge progress."""
        eng = _engine()
        eg = _giant(eng)
        atk = _body(eng, "knight", 0, eg.x + 1.5 / _TILES_X, eg.y)
        atk.charge_dist = 2.5
        eng._land_hit(0, "unit", eg, atk.spec, atk.spec.hit_dmg, atk.spec.hit_dmg, attacker=atk)
        self.assertLess(atk.hp, 2000.0)
        self.assertAlmostEqual(atk.charge_dist, 2.5, places=3,
                               msg="the reflect stun must NOT wipe charge progress")


class ZapPackTowerTests(unittest.TestCase):
    def test_a_crown_tower_shooting_him_point_blank_takes_the_reduced_97_and_is_stunned(self):
        """Towers go through the tower-damage path at the page's published crown_11 = 97, NOT the
        full 192 -- the "Reflected Tower Damage" column is its own number."""
        eng = _engine()
        tw = eng.towers[0][0]
        eg = _giant(eng, x=tw.x, y=tw.y - 3.0 / _TILES_Y)     # edge-distance 1.5: inside the zone
        hp0 = tw.hp
        eng._tower_fire(0, tw, 1.0)                            # engage + wind-up
        zapped_stun = 0.0
        for _ in range(30):
            eng._tower_fire(0, tw, 0.1)
            eng._tick_projectiles(0.1)
            zapped_stun = max(zapped_stun, tw.stun_left)
        shots = round((hp0 - tw.hp) / eg.spec.reflect_crown)
        self.assertGreaterEqual(shots, 1, "the tower landed shots and took the zap back")
        self.assertAlmostEqual(hp0 - tw.hp, shots * eg.spec.reflect_crown, places=1,
                               msg="crown towers take reflect_crown (97 @ L11) per hit, not 192")
        self.assertAlmostEqual(zapped_stun, eg.spec.reflect_stun, places=3,
                               msg="and the zap stuns the tower (the page's King-stun strategy "
                                   "note depends on towers being stunnable)")

    def test_the_king_towers_4x4_body_is_inside_the_zone_when_he_is_adjacent(self):
        """History 16/12/2024 fixed the Zap Pack "not dealing reduced damage to the King Tower" --
        so the King MUST be zappable. His centre sits ~3.2 tiles from an adjacent Electro Giant
        (2.0 half-size + melee stand-off), which centre-to-centre distance can never reach: zone
        membership is centre-to-EDGE, the same convention _gap uses for range."""
        eng = _engine()
        king = eng.towers[0][2]
        self.assertTrue(king.king)
        eg = _giant(eng, x=king.x, y=king.y - 3.4 / _TILES_Y)
        self.assertGreater(_dist(king.x, king.y, eg.x, eg.y), eg.spec.reflect_r,
                           "the probe is only honest if the CENTRE really is outside 3 tiles")
        hp0 = king.hp
        king.active = True
        eng._tower_fire(0, king, 1.0)
        for _ in range(30):
            eng._tower_fire(0, king, 0.1)
            eng._tick_projectiles(0.1)
        self.assertGreater(hp0 - king.hp, 0.0, "the King's own shots zap back at him")
        self.assertAlmostEqual((hp0 - king.hp) % eg.spec.reflect_crown, 0.0, places=1)


class ZapPackCrownSwingTests(unittest.TestCase):
    def test_his_normal_swing_hits_towers_at_full_damage_again(self):
        """The page's Trivia reduces only his REFLECTING damage against Crown Towers; his swing is
        NOT a Miner. Before ruling 31a the parked crown_tower_damage: 97 fed tower_hit_dmg and his
        swing chipped towers at 97.0 instead of 163.8 (L11) -- measured, now un-nerfed."""
        spec = build_spec(CardDB(path=ROOT / "config" / "cards.yaml"), "electro_giant", 11)
        self.assertAlmostEqual(spec.tower_hit_dmg, spec.hit_dmg, places=3)
        self.assertAlmostEqual(spec.reflect_crown, 97.0, places=3)
        self.assertAlmostEqual(spec.reflect_dmg, 192.0, places=3)


if __name__ == "__main__":
    unittest.main()
