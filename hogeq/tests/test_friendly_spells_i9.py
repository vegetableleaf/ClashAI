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
from dataclasses import replace                                          # noqa: E402
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


class ZeroDamageTowerHitTests(unittest.TestCase):
    """A ZERO-DAMAGE HIT IS NOT A HIT (I9, measured while routing Clone).

    `_damage_tower` woke the King Tower on ANY call, including calls carrying 0 damage. Five
    spells publish no Crown Tower damage at all -- goblin_barrel, goblin_barrel_evo,
    goblin_barrel_decoy, royal_delivery and mirror -- because on those cards the BODIES do the
    work, and every one of them was activating the enemy King the instant it landed, for nothing.
    Royal Delivery is the sharpest case: decisions.md #11 ruled that it "cannot hit crown towers"
    and I5 discarded its `crown_tower_damage` for exactly that reason.
    """

    ZERO_CROWN = ("goblin_barrel", "goblin_barrel_evo", "royal_delivery", "mirror")

    def _king_asleep(self, eng):
        king = next(tw for tw in eng.towers[1] if tw.king)
        king.active = False
        return king

    def test_the_landing_itself_never_wakes_the_king(self):
        for key in self.ZERO_CROWN:
            with self.subTest(card=key):
                eng = _quiet(_make_engine())
                king = self._king_asleep(eng)
                sp = build_spec(eng.db, key, LVL)
                self.assertAlmostEqual(sp.spell_tower_dmg, 0.0, places=6,
                                       msg="%s publishes no crown damage" % key)
                eng._resolve_spell(_Spell(0, king.x, king.y, sp, 0.0))
                self.assertFalse(king.active,
                                 "%s landing on the King must not activate him for 0 chip" % key)
                self.assertAlmostEqual(eng.chip[0], 0.0, places=6)

    def test_the_bodies_it_leaves_still_wake_him(self):
        """The guard removes a FREE activation, not the card's real one: MEASURED, the Goblin
        Barrel now wakes him at 1.2 s with 372.9 chip on the board instead of at 0.0 s with none."""
        eng = _quiet(_make_engine())
        king = self._king_asleep(eng)
        eng._resolve_spell(_Spell(0, king.x, king.y, build_spec(eng.db, "goblin_barrel", LVL), 0.0))
        for _ in range(60):
            eng.advance(0.1)
            if king.active:
                break
        self.assertTrue(king.active, "the goblins themselves must still activate him")
        self.assertGreater(eng.chip[0], 0.0, "...and only once they have actually hit something")

    def test_a_spell_that_does_publish_crown_damage_is_untouched(self):
        eng = _quiet(_make_engine())
        king = self._king_asleep(eng)
        sp = build_spec(eng.db, "fireball", LVL)
        self.assertGreater(sp.spell_tower_dmg, 0.0)
        eng._resolve_spell(_Spell(0, king.x, king.y, sp, 0.0))
        self.assertTrue(king.active)

    def test_a_zero_damage_spell_can_still_apply_its_status(self):
        """`_apply_status` is a separate call at every site, so the guard removes the phantom
        activation without touching a tower stun."""
        eng = _quiet(_make_engine())
        tw = eng.towers[1][0]
        zap = build_spec(eng.db, "zap", LVL)
        eng._apply_status(0, zap, tw)
        self.assertGreater(tw.stun_left, 0.0)


class BaseBarbarianBarrelTests(unittest.TestCase):
    """THE BASE BARBARIAN BARREL'S BARBARIAN (I9). The card's whole second half.

    I8 fixed `_resolve_roll` to drop a rolling spell's `spawn_spec` and deliberately left the data
    half alone, because declaring it changes 198 pool decks (24.95% of deck weight). MEASURED
    before this: a full deploy of the base card left **0 bodies**.

    Barbarian Barrel revid 437163 states it twice -- card text "then breaks open and out pops a
    Barbarian!", lead "Once the spell reaches its destination, it spawns a single Barbarian" --
    and the Strategy section is built on the body: it "can follow up and attack anything while
    alive", and "the spell can be used to separate a building-targeting troop from a regular
    troop". Barbarian Attributes: First Hit Speed 0.4 / Speed Medium (60) / Deploy Time 0.5 /
    Range Melee: Short (0.5) / Ground / x1.

    ⚠ THE BODY'S NUMBERS MOVED UNDER RULING 25 (owner, in-game 2026-08-27): "the barbarian spawned
    by the barrel should have the same stats as normal barbarians", and a Barbarian is 716 hp at
    L11. This page's own hp_11 670 / Hit Speed 1.3 are TWO balance updates behind -- 2/3/2026 (+3%
    hp, hit speed 1.4 from 1.3) and 4/8/2026 (+4% hp) -- and neither was ever applied here. The two
    barrel bodies are now numerically one `barbarians`: 716 / 190.4 / 1.4. See
    `test_barbarian_stats_r25.py`, which owns the evidence and the before/after.
    """

    def test_the_base_card_declares_its_barbarian(self):
        sp = build_spec(_make_engine().db, "barbarian_barrel", LVL)
        self.assertTrue(sp.rolls, "it is still a rolling corridor")
        self.assertIsNotNone(sp.spawn_spec, "the base card leaves a Barbarian")
        self.assertEqual(sp.spawn_count, 1, "x1")
        b = sp.spawn_spec
        self.assertAlmostEqual(b.hp, 716.0, places=1)          # ruling 25 (MEASURED BEFORE: 670)
        # `hit_dmg` is DERIVED as dps x hit_speed engine-wide, so a KB row whose `dps` is the
        # wiki's rounded 136 lands at 190.4 rather than exactly 191 -- a pre-existing convention,
        # and now the SAME 190.4 the `barbarians` card itself builds to.
        self.assertAlmostEqual(b.hit_dmg, 191.0, delta=0.7)    # dmg_11
        self.assertAlmostEqual(b.hit_speed, 1.4, places=3)     # ruling 25 (MEASURED BEFORE: 1.3)
        self.assertAlmostEqual(b.reach, 0.5, places=3)
        self.assertAlmostEqual(b.speed, 1.0, places=3)
        self.assertAlmostEqual(b.deploy_time, 0.5, places=3)
        self.assertFalse(b.attacks_air, "Target Ground")

    def test_the_hero_barrel_keeps_its_own_ROW_even_though_the_numbers_now_match(self):
        """I9 kept these as two rows because reusing the hero's `barrel_barbarian` (716 / 192)
        would have handed the base card a 6.9% hitpoint buff nobody published. RULING 25 then ruled
        that the base card's 670 was simply stale -- so the numbers ARE the same now, and the rows
        stay separate for a different reason: two wiki pages, two revids, two provenances, and a
        hero page that has diverged before and was the RIGHT one when it did. What still differs is
        the BUTTON."""
        db = _make_engine().db
        base = build_spec(db, "barbarian_barrel", LVL).spawn_spec
        hero = build_spec(db, "barbarian_barrel_hero", LVL).spawn_spec
        self.assertEqual(base.key, "base_barrel_barbarian")
        self.assertEqual(hero.key, "barrel_barbarian")
        self.assertAlmostEqual(hero.hp, 716.0, places=1)
        self.assertAlmostEqual(base.hp, hero.hp, places=1, msg="ruling 25: one Barbarian")
        self.assertEqual(base.ability_kind, "",
                         "only the HERO's barbarian carries the Rowdy Reroll button")
        self.assertEqual(hero.ability_kind, "reroll")

    def test_a_full_deploy_leaves_exactly_one_body(self):
        eng = _quiet(_make_engine())
        eng.elixir[1] = 10.0
        self.assertTrue(eng.deploy(1, build_spec(eng.db, "barbarian_barrel", LVL), 0.5, 0.45))
        for _ in range(30):
            eng.advance(0.1)
        bodies = [u for u in eng.units if u.team == 1]
        self.assertEqual(len(bodies), 1, "MEASURED 0 -> 1")
        self.assertEqual(bodies[0].spec.key, "base_barrel_barbarian")
        self.assertAlmostEqual(bodies[0].hp, 716.0, places=1)  # ruling 25 (MEASURED BEFORE: 670)

    def test_the_roll_still_damages_along_its_corridor(self):
        """The body is an addition, not a replacement: the corridor is what the card is FOR.

        RULING 21 made the corridor SWEEP, so `_resolve_spell` now only LAUNCHES it and the damage
        arrives as the leading edge reaches the body -- this used to assert immediately, and the
        advance loop below is the whole of the change. MEASURED: the foe sits 0.96 tiles ahead of
        the cast and takes the hit 0.30 s in, where before it took it at t=0.
        """
        eng = _quiet(_make_engine())
        sp = build_spec(eng.db, "barbarian_barrel", LVL)
        foe = Unit(spec=replace(build_spec(eng.db, "knight", LVL), speed=0.0),
                   team=0, x=0.5, y=0.42, hp=3000.0)
        eng.units.append(foe)
        eng._resolve_spell(_Spell(1, 0.5, 0.45, sp, 0.0))
        self.assertAlmostEqual(3000.0 - foe.hp, 0.0, places=3, msg="not at t=0 any more")
        for _ in range(40):
            eng.advance(0.05)
            if foe.hp < 3000.0:
                break
        self.assertAlmostEqual(3000.0 - foe.hp, sp.spell_dmg, places=3)
        self.assertGreater(sp.spell_dmg, 0.0)


if __name__ == "__main__":
    unittest.main()
