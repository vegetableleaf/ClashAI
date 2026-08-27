"""I9 -- FRIENDLY-TARGET SPELLS, and the cross-cutting gaps that shipped with them.

This file is BYTE-IDENTICAL in icebow and hogeq (parity_check enforces it). Bare-engine and
deck-agnostic, in the house idiom: a `_make_engine()` SimEngine, bodies placed by hand, an
`advance` loop, and one measured assertion per published claim.

WHY THIS FILE EXISTS. `SimEngine._resolve_spell` only ever iterated `e.team != s.team`, so no
spell in this engine could act on the caster's own army. Three cards were wrong because of it:

  * RAGE was a bare 179-damage blast with its entire buff missing -- the card is played for the
    buff, and the blast is the footnote.
  * CLONE was a 3-elixir no-op.
  * HEAL SPIRIT was a kamikaze troop whose heal did not exist.

Sources are the frozen wikitext archives under `research/sim_parity/webcache/` at the revisions
`config/cards_stats.json` records in each row's `_src` (Rage 437309, Clone 436842, Heal Spirit
437344, Mirror 436846, all fetched 2026-08-26). Every choice made from contradictory or absent
evidence, and every deliberate non-implementation, is in `research/sim_parity/conflicts.md`
under "I9".
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for _p in (str(ROOT / "src"), str(ROOT / "tests")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from test_sim_status_effects import _make_engine                        # noqa: E402
from clashrl.sim.engine import (Unit, _Spell, build_spec, _RAGE_FALLOFF_S,   # noqa: E402
                                _TILES_X, _TILES_Y)

LVL = 11


def _quiet(eng):
    """Disarm the crown towers without killing them (the I7/I8 trap: `alive = False` ENDS the
    match and `advance` then returns at its `self.done` guard with every timer frozen)."""
    for side in (eng.towers[0], eng.towers[1]):
        for tw in side:
            tw.hit_dmg = 0.0
            tw.max_hp = tw.hp = 1e9
    return eng


def _cast(eng, key, team, x, y, level=LVL):
    """Land a spell AT ONCE at (x, y) -- no throw time, so a test measures the effect and not
    the flight. `_resolve_spell` is the entry every deploy path funnels into."""
    sp = build_spec(eng.db, key, level)
    eng._resolve_spell(_Spell(team, x, y, sp, 0.0))
    return sp


class RageSpellTests(unittest.TestCase):
    """Rage (revid 437309). Attributes table: Cost 2 | Radius 3 | Deploy Time 0.5 sec |
    Duration 4.5 sec | Boost +30% | Target "Friendly Troops & Buildings"."""

    def test_the_rage_spell_lays_a_friendly_zone_with_its_published_numbers(self):
        eng = _quiet(_make_engine())
        sp = _cast(eng, "rage", 0, 0.5, 0.7)
        self.assertEqual(len(eng.rage_zones), 1, "the spell must lay exactly one rage zone")
        zx, zy, zr, zt, t0, t1, boost = eng.rage_zones[0]
        self.assertEqual(zt, 0, "the zone belongs to the CASTER's team")
        self.assertAlmostEqual(zr, 3.0, places=6, msg="published Radius 3")
        self.assertAlmostEqual(boost, 0.30, places=6, msg="published Boost +30%")
        # "added a 0.5 second deploy timer to Rage" (12/12/2022) -- the zone arms late...
        self.assertAlmostEqual(t0 - eng.t, 0.5, places=6)
        # ...and then runs its published 4.5 s ("decreased its duration to 4.5 seconds", 4/8/2025).
        self.assertAlmostEqual(t1 - t0, 4.5, places=6)
        self.assertAlmostEqual(sp.rage_boost, 0.30, places=6)

    def test_the_boost_reaches_a_friendly_body_and_never_an_enemy_one(self):
        """"It increases the movement speed and attack speed of allied troops and buildings by
        30%" -- ALLIED. The zone carries a team and `_rage_mult` tests it."""
        eng = _quiet(_make_engine())
        mine = Unit(spec=build_spec(eng.db, "knight", LVL), team=0, x=0.5, y=0.7, hp=1000.0)
        theirs = Unit(spec=build_spec(eng.db, "knight", LVL), team=1, x=0.5, y=0.7, hp=1000.0)
        eng.units.extend([mine, theirs])
        _cast(eng, "rage", 0, 0.5, 0.7)
        eng.t += 0.6                                   # past the 0.5 s deploy timer
        self.assertAlmostEqual(eng._rage_mult(mine), 1.30, places=6)
        self.assertAlmostEqual(eng._rage_mult(theirs), 1.00, places=6,
                               msg="an enemy inside a friendly Rage must get nothing")

    def test_rage_still_blasts_because_the_card_publishes_damage(self):
        """The Target column names who Rage BUFFS; the lead calls it "an area-damage,
        air-targeting spell ... with low damage". Both halves are the same card, and the
        12/12/2022 Clashmas Update "made the spell deal area damage"."""
        eng = _quiet(_make_engine())
        foe = Unit(spec=build_spec(eng.db, "knight", LVL), team=1, x=0.5, y=0.7, hp=2000.0)
        eng.units.append(foe)
        sp = _cast(eng, "rage", 0, 0.5, 0.7)
        self.assertGreater(sp.spell_dmg, 0.0, "the KB row publishes damage")
        self.assertAlmostEqual(2000.0 - foe.hp, sp.spell_dmg, places=4,
                               msg="the enemy blast must still run for a friendly-target spell "
                                   "that publishes damage")

    def test_a_body_that_walks_out_keeps_the_published_second_of_rage(self):
        """"added a falloff effect to Rage, causing troops to lose the bonus if they are out of
        its effect for 2 seconds" (29/2/2016), "decreased ... to 1 second (from 2 seconds)"
        (4/3/2025). Without it a 3-tile bubble buffs a marching push only on the ticks it is
        standing inside."""
        eng = _quiet(_make_engine())
        u = Unit(spec=build_spec(eng.db, "knight", LVL), team=0, x=0.5, y=0.7, hp=1000.0)
        eng.units.append(u)
        _cast(eng, "rage", 0, 0.5, 0.7)
        eng.t += 0.6
        self.assertAlmostEqual(eng._rage_mult(u), 1.30, places=6)   # inside: refreshes the timer
        self.assertAlmostEqual(u.rage_left, _RAGE_FALLOFF_S, places=6)
        u.y = 0.7 + 9.0 / _TILES_Y                                  # walk clear of a 3-tile zone
        self.assertAlmostEqual(eng._rage_mult(u), 1.30, places=6,
                               msg="the second of grace is the published mechanic")
        u.rage_left = 0.0                                           # ...and once it has run out
        self.assertAlmostEqual(eng._rage_mult(u), 1.00, places=6)

    def test_the_lumberjack_bottle_still_lays_the_same_kind_of_zone(self):
        """One rage model, not two: the spell's lead says the effect "is also the same as that
        spawned by the Lumberjack", so the drop keeps working through the same list."""
        eng = _quiet(_make_engine())
        lj = Unit(spec=build_spec(eng.db, "lumberjack", LVL), team=0, x=0.5, y=0.7, hp=10.0)
        eng.units.append(lj)
        lj.hp = 0.0
        eng.advance(0.1)
        self.assertTrue(eng.rage_zones, "the death drop must still reach rage_zones")


class CloneSpellTests(unittest.TestCase):
    """Clone (revid 436842). Attributes: Cost 3 | Clone Hitpoints 1 | Clone Shield Hitpoints 1 |
    Radius 3 | Target "Friendly Troops"."""

    def test_it_duplicates_friendly_troops_at_one_hitpoint_behind_them(self):
        eng = _quiet(_make_engine())
        u = Unit(spec=build_spec(eng.db, "knight", LVL), team=0, x=0.5, y=0.7, hp=1400.0)
        eng.units.append(u)
        _cast(eng, "clone", 0, 0.5, 0.7)
        clones = [c for c in eng.units if c.cloned]
        self.assertEqual(len(clones), 1)
        c = clones[0]
        self.assertEqual(c.team, 0)
        self.assertAlmostEqual(c.hp, 1.0, places=6, msg="published Clone Hitpoints 1")
        self.assertAlmostEqual(c.spec.hp, 1.0, places=6,
                               msg="the SPEC carries the 1 hp, so the hp bar and every "
                                   "hp-threshold transform read it")
        # "BEHIND the originals" -- team 0 attacks toward y = 0, so behind is +y.
        self.assertGreater(c.y, u.y, "the duplicate spawns behind the original")
        self.assertAlmostEqual(c.deploy_left, 0.5, places=6,
                               msg="cloning time 0.5 s (History 12/6/2017, from 0.8s)")

    def test_a_clone_is_worth_no_elixir(self):
        """"Cloned troops are fragile, but pack the same punch as the original" -- and they cost
        the opponent nothing to have made. The reward layer prices every body at `spec.elixir`,
        so the zero has to live on the SPEC or a cloned Skeleton Army reads as 3 more elixir of
        enemy investment worth paying to kill."""
        eng = _quiet(_make_engine())
        u = Unit(spec=build_spec(eng.db, "knight", LVL), team=0, x=0.5, y=0.7, hp=1400.0)
        eng.units.append(u)
        self.assertGreater(u.spec.elixir, 0)
        _cast(eng, "clone", 0, 0.5, 0.7)
        c = next(c for c in eng.units if c.cloned)
        self.assertEqual(c.spec.elixir, 0)
        self.assertEqual(c.spec.key, u.spec.key, "it is still the same card by identity")

    def test_buildings_and_existing_clones_are_not_cloned(self):
        """"with buildings and existing clones not subject to the effect" / "Doesn't affect
        buildings" (card text)."""
        eng = _quiet(_make_engine())
        b = Unit(spec=build_spec(eng.db, "tesla", LVL), team=0, x=0.5, y=0.7, hp=1000.0)
        t = Unit(spec=build_spec(eng.db, "knight", LVL), team=0, x=0.5, y=0.7, hp=1400.0)
        eng.units.extend([b, t])
        self.assertEqual(b.spec.kind, "building")
        _cast(eng, "clone", 0, 0.5, 0.7)
        self.assertEqual(len([c for c in eng.units if c.cloned]), 1,
                         "only the troop is cloned")
        _cast(eng, "clone", 0, 0.5, 0.7)               # a SECOND cast over the same spot
        self.assertEqual(len([c for c in eng.units if c.cloned]), 2,
                         "the second cast clones the original again and never the clone")

    def test_an_enemy_troop_in_the_radius_is_untouched(self):
        eng = _quiet(_make_engine())
        foe = Unit(spec=build_spec(eng.db, "knight", LVL), team=1, x=0.5, y=0.7, hp=1400.0)
        eng.units.append(foe)
        _cast(eng, "clone", 0, 0.5, 0.7)
        self.assertEqual([c for c in eng.units if c.cloned], [])
        self.assertAlmostEqual(foe.hp, 1400.0, places=4,
                               msg="Clone publishes no damage column, so nothing lands on them")

    def test_a_shield_is_cloned_at_one_hitpoint_only_when_the_original_has_one(self):
        """"Shields can be cloned if they are still on the original unit. They will retain one
        hitpoint, and can still negate excess damage" -- published Clone Shield Hitpoints 1."""
        eng = _quiet(_make_engine())
        sh = Unit(spec=build_spec(eng.db, "dark_prince", LVL), team=0, x=0.5, y=0.7, hp=1000.0)
        bare = Unit(spec=build_spec(eng.db, "knight", LVL), team=0, x=0.5, y=0.7, hp=1000.0)
        eng.units.extend([sh, bare])
        self.assertGreater(sh.spec.shield_hp, 0.0)
        self.assertAlmostEqual(bare.spec.shield_hp, 0.0, places=6)
        _cast(eng, "clone", 0, 0.5, 0.7)
        by_key = {c.spec.base: c for c in eng.units if c.cloned}
        self.assertAlmostEqual(by_key["dark_prince"].shield_left, 1.0, places=6)
        self.assertAlmostEqual(by_key["knight"].shield_left, 0.0, places=6)

    def test_clone_never_lands_a_zero_damage_hit_on_a_crown_tower(self):
        """The reason the own-team path RETURNS for a card with no published damage: a
        zero-damage hit on the King Tower still activates him."""
        eng = _quiet(_make_engine())
        king = next(tw for tw in eng.towers[1] if tw.king)
        king.active = False
        _cast(eng, "clone", 0, king.x, king.y)
        self.assertFalse(king.active, "a spell that publishes no damage must not wake the King")


class HealSpiritTests(unittest.TestCase):
    """Heal Spirit (revid 437344). Healing Attributes: Heal Speed "4 pulses every 1 second" |
    Time Between Pulses 0.25 sec | Radius 2.5 | Target "Air & Ground"; `heal_11` 100.25."""

    def _harmless(self, eng, key, team, x, y, hp):
        """A body that cannot swing. Every test here measures HEALING, and a combat exchange in
        the same window is indistinguishable from it -- the first draft of these tests read a
        friendly Knight at -101 hp and called the heal broken."""
        from clashrl.sim.engine import replace
        sp = build_spec(eng.db, key, LVL)
        u = Unit(spec=replace(sp, hit_dmg=0.0, tower_hit_dmg=0.0, dps=0.0, death_dmg=0.0),
                 team=team, x=x, y=y, hp=hp)
        eng.units.append(u)
        return u

    def _leap(self, eng, spirit):
        """Run the engine until the kamikaze connects and the spirit destroys itself."""
        for _ in range(200):
            eng.advance(0.1)
            if spirit.hp <= 0.0:
                return True
        return False

    def test_the_row_publishes_the_field(self):
        sp = build_spec(_make_engine().db, "heal_spirit", LVL)
        self.assertAlmostEqual(sp.heal_amount, 100.25, places=4)
        self.assertEqual(sp.heal_pulses, 4)
        self.assertAlmostEqual(sp.heal_tick_s, 0.25, places=6)
        self.assertAlmostEqual(sp.heal_radius, 2.5, places=6)
        self.assertTrue(sp.kamikaze)

    def test_the_leap_leaves_a_field_that_heals_allied_troops_four_times(self):
        eng = _quiet(_make_engine())
        spirit = Unit(spec=build_spec(eng.db, "heal_spirit", LVL), team=0, x=0.5, y=0.55,
                      hp=215.0)
        eng.units.append(spirit)
        self._harmless(eng, "knight", 1, 0.5, 0.50, 5000.0)
        hurt = self._harmless(eng, "knight", 0, 0.5, 0.52, 100.0)
        self.assertTrue(self._leap(eng, spirit), "the spirit must connect and die")
        self.assertTrue(eng.zones, "the leap leaves a restoration field")
        for _ in range(30):
            eng.advance(0.1)
        self.assertAlmostEqual(hurt.hp, 100.0 + 4 * 100.25, places=2,
                               msg="4 published pulses of 100.25, and no fifth")

    def test_the_field_never_overheals_past_the_body_maximum(self):
        eng = _quiet(_make_engine())
        spirit = Unit(spec=build_spec(eng.db, "heal_spirit", LVL), team=0, x=0.5, y=0.55,
                      hp=215.0)
        eng.units.append(spirit)
        self._harmless(eng, "knight", 1, 0.5, 0.50, 5000.0)
        full = self._harmless(eng, "knight", 0, 0.5, 0.52, 1.0)
        full.hp = full.spec.hp
        self.assertTrue(self._leap(eng, spirit))
        for _ in range(30):
            eng.advance(0.1)
        self.assertAlmostEqual(full.hp, full.spec.hp, places=4)

    def test_it_heals_nobody_on_the_other_side_and_no_buildings(self):
        """"the healing has no effect on buildings" (Strategy -- also why the card "should not be
        used in X-Bow or Mortar decks"), and the field belongs to the spirit's own team."""
        eng = _quiet(_make_engine())
        spirit = Unit(spec=build_spec(eng.db, "heal_spirit", LVL), team=0, x=0.5, y=0.55,
                      hp=215.0)
        eng.units.append(spirit)
        foe = self._harmless(eng, "knight", 1, 0.5, 0.50, 5000.0)
        bldg = self._harmless(eng, "tesla", 0, 0.5, 0.52, 100.0)
        self.assertEqual(bldg.spec.kind, "building")
        self.assertTrue(self._leap(eng, spirit))
        hp0, bhp0 = foe.hp, bldg.hp
        for _ in range(30):
            eng.advance(0.1)
        # `<=`, not equality: a Tesla is a building with a LIFETIME and decays on its own clock.
        # What the page rules out is the field ADDING to it.
        self.assertLessEqual(bldg.hp, bhp0, "buildings take no healing")
        self.assertLessEqual(foe.hp, hp0, "an enemy body is never healed by our spirit")

    def test_a_spirit_killed_before_it_connects_heals_nothing(self):
        """The counterplay the page describes: "it is important that the barrel itself defeats
        the Heal Spirit before the Barbarian spawns"."""
        eng = _quiet(_make_engine())
        spirit = Unit(spec=build_spec(eng.db, "heal_spirit", LVL), team=0, x=0.5, y=0.55,
                      hp=215.0)
        eng.units.append(spirit)
        spirit.hp = 0.0
        eng.advance(0.1)
        self.assertEqual(eng.zones, [], "death by damage leaves no field")


class MirrorMeasurementTests(unittest.TestCase):
    """Mirror is MEASURED and deliberately not implemented (conflicts.md, I9). This pins the
    measurement that made the call, so a pool that moves makes the decision loud instead of
    leaving a silent gap."""

    def test_the_meta_pool_barely_fields_mirror_or_clone(self):
        import yaml
        decks = yaml.safe_load(
            (ROOT / "config" / "meta_decks.yaml").read_text(encoding="utf-8"))["decks"]
        total = sum(int(d["weight"]) for d in decks)
        share = {k: sum(int(d["weight"]) for d in decks if k in d["cards"]) / total
                 for k in ("mirror", "clone")}
        # MEASURED 2026-08-27: mirror 17/5947 = 0.29%, clone 7/5947 = 0.12% of deck weight.
        self.assertLess(share["mirror"], 0.01,
                        "mirror was skipped because the pool does not field it; at 1%+ of deck "
                        "weight that call needs revisiting (conflicts.md, I9)")
        self.assertLess(share["clone"], 0.01)

    def test_mirror_declares_no_own_team_effect(self):
        eng = _quiet(_make_engine())
        sp = build_spec(eng.db, "mirror", LVL)
        self.assertEqual(sp.kind, "spell")
        self.assertEqual(sp.spell_targets, "",
                         "mirror is not routed through the own-team path: it is a HAND mechanic, "
                         "and the pool does not field it (conflicts.md, I9)")


if __name__ == "__main__":
    unittest.main()
