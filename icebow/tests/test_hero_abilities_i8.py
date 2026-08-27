"""I8 -- HERO abilities, enemy-side, at FULL fidelity. Bare-engine, deck-agnostic.

This file is BYTE-IDENTICAL in icebow and hogeq (parity_check enforces it). It covers the sixteen
LIVE heroes' abilities through `SimEngine.champion_ability`, the three-slot loadout the scripted
opponent draws them with, and the tower-troop wiring that landed in the same stage -- in the house
bare-engine idiom: a `_make_engine()` SimEngine, bodies placed by hand, and an `advance` loop.

Sources, per class. Wiki revids are the LIVE revisions the I4 `/Hero` scrape recorded in
`config/cards_stats.json` (`_src.revid`, fetched 2026-08-26); the frozen prose archives are
`research/sim_parity/abilities/<key>.yaml`, which carry the verbatim quotes and the open_questions
each choice below answers. Owner rulings are `research/sim_parity/decisions.md`; every conflict
resolved from contradictory evidence, and every deliberate non-implementation, is in
`research/sim_parity/conflicts.md` under "I8".

THE THREE RULES that settle most of the page conflicts, each with an I7 precedent:
  (a) a dated HISTORY entry naming the OLD value beats an un-updated table or prose (I7-6);
  (b) an attributes table / level-table column beats PROSE (I7-2);
  (c) the activation delay is 1 s unless the page publishes an agreed one (I7-1).
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for _p in (str(ROOT / "src"), str(ROOT / "tests")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from test_sim_status_effects import _make_engine                       # noqa: E402
from clashrl.sim.engine import (ABILITY_KINDS, Unit, build_spec,       # noqa: E402
                                replace, _gap, _TILES_X, _TILES_Y)
from clashrl.sim.meta_decks import (has_hero, hero_candidates,         # noqa: E402
                                    load_meta_decks)

LVL = 11

# The sixteen LIVE heroes and the shape each one's KB row declares. The 2 ANNOUNCED heroes
# (mega_knight, battle_healer -- 7/9/2026) are deliberately absent from every list in the project.
HERO_KINDS = {
    "balloon": "summon_seek",
    "barbarian_barrel": "reroll",
    "berserker": "buff_self",
    "bowler": "buff_self",
    "dark_prince": "summon",
    "giant": "throw_displace",
    "goblins": "summon_banner",
    "ice_golem": "zone_pulse",
    "knight": "taunt_shield",
    "magic_archer": "decoy_blink",
    "mega_minion": "warp",
    "mini_pekka": "transform_levelup",
    "musketeer": "summon",
    "tombstone": "summon",
    "valkyrie": "buff_self",
    "wizard": "flight_nado",
}


def _quiet(eng):
    """Disarm the crown towers WITHOUT killing them -- the same trap I7 documented. Every test here
    measures ONE ability, and a tower volley in the same ledger reads as ability damage. Setting
    `alive = False` would END the match, and `advance` then returns at its `self.done` guard with
    every timer under test frozen."""
    for side in (eng.towers[0], eng.towers[1]):
        for tw in side:
            tw.hit_dmg = 0.0
            tw.max_hp = tw.hp = 1e9
    return eng


def _mute(spec):
    """The same body with its NORMAL attack silenced, so a hero's own swing cannot be read as his
    ability's output. They are separate fields, so muting one leaves the other untouched."""
    return replace(spec, hit_dmg=0.0, tower_hit_dmg=0.0, splash=False, dmg_stages=())


def _hero(eng, base, x=0.5, y=0.5, team=1, mute=True, still=False, lvl=LVL):
    """One hero body, deployed and ready. `still` pins it in place: several of these tests measure
    an aura or a stance around a fixed point, and a body that walks out of its own radius mid-test
    measures the walk instead (MEASURED: a moving Hero Ice Golem landed 1 of its 3 blizzard pulses
    on a dummy 3 tiles away, because he had covered 3 of the aura's 4 tiles by the second pulse)."""
    s = build_spec(eng.db, base + "_hero", lvl)
    if mute:
        s = _mute(s)
    if still:
        s = replace(s, speed=0.0)
    u = Unit(s, team, x, y, s.hp)
    u.deploy_left = 0.0
    eng.units.append(u)
    eng.elixir[team] = 10.0
    return u


def _dummy(eng, team, x, y, hp=100000.0, base="knight", still=True):
    """A harmless, effectively unkillable target: it neither shoots back nor dies mid-measurement."""
    s = build_spec(eng.db, base, LVL)
    s = replace(s, hit_dmg=0.0, tower_hit_dmg=0.0, hp=hp, dmg_stages=())
    if still:
        s = replace(s, speed=0.0)
    u = Unit(s, team, x, y, hp)
    u.deploy_left = 0.0
    eng.units.append(u)
    return u


def _run(eng, seconds, dt=0.1):
    for _ in range(int(round(seconds / dt))):
        eng.advance(dt)


class HeroRowTests(unittest.TestCase):
    """The KB half: all sixteen live heroes build, name a kind the engine implements, and carry
    the body of their base card."""

    def test_all_sixteen_live_heroes_build_and_name_an_implemented_kind(self):
        eng = _make_engine()
        for base, kind in HERO_KINDS.items():
            with self.subTest(hero=base):
                s = build_spec(eng.db, base + "_hero", LVL)
                self.assertEqual(s.base, base, "a hero's spec.base must be its BASE card, so every "
                                               "base-keyed rule in the engine still applies to it")
                if s.kind == "spell":
                    # a SPELL hero has no body to press a button from, so build_spec hands its
                    # whole ability block to the troop it leaves behind (the Hero Barbarian Barrel
                    # is the only one). See RerollTests.
                    self.assertEqual(s.ability_kind, "")
                    s = s.spawn_spec
                    self.assertIsNotNone(s)
                self.assertEqual(s.ability_kind, kind)
                self.assertIn(s.ability_kind, ABILITY_KINDS,
                              "a kind the registry does not implement makes champion_ability "
                              "REFUSE the activation, which is a silent dead card")
                self.assertGreater(s.ability_cost, 0.0)
                self.assertEqual(s.ability_uses, 1,
                                 "Heroes revid 437509, History 4/8/2026: 'made every ability "
                                 "single-use'. Eight subject pages never say it; the master does.")

    def test_the_two_ANNOUNCED_heroes_can_never_be_built_or_fielded(self):
        """mega_knight and battle_healer have /Hero subpages, dated 7/9/2026, that read 'Coming
        soon'. decisions.md's importer trap is about exactly this class of forward declaration."""
        eng = _make_engine()
        for base in ("mega_knight", "battle_healer"):
            with self.subTest(hero=base):
                self.assertFalse(has_hero(eng.db, base))
                with self.assertRaises(KeyError):
                    build_spec(eng.db, base + "_hero", LVL)

    def test_a_hero_body_is_its_base_card_unless_the_page_says_otherwise(self):
        """`body_stat_deltas: none stated` on nearly every spec file, so the overlay must not
        invent one. The three exceptions are the I4 import bugs this stage CORRECTED, and they are
        asserted by name so a re-import cannot quietly put the wrong table back."""
        eng = _make_engine()
        for base in ("knight", "giant", "berserker", "valkyrie", "wizard", "mini_pekka",
                     "mega_minion", "goblins", "balloon"):
            with self.subTest(hero=base):
                b, h = build_spec(eng.db, base, LVL), build_spec(eng.db, base + "_hero", LVL)
                self.assertAlmostEqual(b.hp, h.hp, places=3)
                # delta, not places: `hit_dmg` is dps x hit_speed and the import rounds dps to a
                # whole number per row, so a hero page and its base card can land a point or two
                # apart on the SAME published damage (goblins 114 vs 113, mini_pekka 472 vs 471).
                self.assertAlmostEqual(b.hit_dmg, h.hit_dmg, delta=2.5)
        # musketeer_hero carried the TURRET's vardefines (1536 hp / 140 dmg / 0.5 s hit speed)
        m = build_spec(eng.db, "musketeer_hero", LVL)
        self.assertAlmostEqual(m.hp, build_spec(eng.db, "musketeer", LVL).hp, places=3)
        self.assertAlmostEqual(m.hit_speed, 1.0, places=3)
        self.assertAlmostEqual(build_spec(eng.db, "trusty_turret", LVL).hp, 1536.0, places=1)
        # tombstone_hero carried the TOMB QUEEN's (4224 hp / 422 dmg)
        tb = build_spec(eng.db, "tombstone_hero", LVL)
        self.assertAlmostEqual(tb.hp, 529.0, places=1)
        self.assertAlmostEqual(build_spec(eng.db, "tomb_queen", LVL).hp, 4224.0, places=1)
        # barbarian_barrel_hero's `damage:` is the ROLL's, not the Barbarian's melee
        bb = build_spec(eng.db, "barbarian_barrel_hero", LVL)
        self.assertAlmostEqual(bb.spell_dmg, 232.0, places=1)
        self.assertAlmostEqual(build_spec(eng.db, "barrel_barbarian", LVL).hit_dmg, 192.4, places=1)


class BuffSelfTests(unittest.TestCase):
    """buff_self -- the biggest family by pool weight (berserker 18.5% + barbarian_barrel's
    neighbours aside, berserker + valkyrie + bowler are 38.6% of hero candidates by deck weight)."""

    def test_berserker_savage_survival_is_a_published_ATTACK_PROFILE(self):
        """Berserker/Hero revid 437529 + Heroes revid 437509: "making her attacks go rapid and
        preventing her health from going below 1 HP while dealing reduced damage to Crown Towers".

        THE CHOICE: `bear_dmg_11` 167 is her per-hit damage while the ability runs. The page never
        says what the column is (the subject page has NO PROSE AT ALL). Rule (b) decides it: the
        ability's own attributes table publishes a Hit Speed of 0.2 s and the level table publishes
        exactly one ability-damage column beside it, which is an attack profile. The alternative --
        her normal 102 at the faster cadence -- is 510 dps against this reading's 835, and it is
        recorded in conflicts.md.
        """
        eng = _quiet(_make_engine())
        b = _hero(eng, "berserker", 0.5, 0.5, mute=False, still=True)
        tgt = _dummy(eng, 0, 0.5, 0.5 + 0.6 / _TILES_Y)
        self.assertTrue(eng.champion_ability(1))
        _run(eng, 1.2)                                   # rule (c): 1 s activation delay
        self.assertAlmostEqual(b.spec.hit_speed, 0.2, places=3)     # table "Hit Speed 0.2 sec"
        self.assertAlmostEqual(b.spec.hit_dmg, 167.0, places=1)     # bear_dmg_11
        self.assertAlmostEqual(b.spec.tower_hit_dmg, 41.75, places=2)  # 167 x 0.25, "-75%"
        _run(eng, 4.5)
        self.assertIsNone(b.base_spec, "the stance must put the pre-stance spec back")
        self.assertAlmostEqual(b.spec.hit_speed, 0.6, places=3)

    def test_berserker_hp_floor_is_a_FLOOR_and_not_immunity(self):
        """"preventing her health from going below 1 HP" -- everything still lands, she just cannot
        be finished while it runs, and the moment it ends she is standing at 1 hitpoint."""
        eng = _quiet(_make_engine())
        b = _hero(eng, "berserker", 0.5, 0.5, still=True)
        self.assertTrue(eng.champion_ability(1))
        _run(eng, 1.2)
        eng._hurt(b, 1e6)
        self.assertAlmostEqual(b.hp, 1.0, places=3)
        _run(eng, 4.0)                                   # ...and the floor goes with the window
        eng._hurt(b, 10.0)
        self.assertLessEqual(b.hp, 0.0)

    def test_valkyrie_whirlwind_is_an_AREA_TICK_that_replaces_her_swing(self):
        """Valkyrie/Hero revid 437412: ability table Hit Speed 0.25 s, Radius 2.5, abdmg_11 97,
        Duration 3.5 s, Crown Tower Damage -50%.

        GROUND ONLY (her body's Target is Ground and so is the base card's), and the spin REPLACES
        her normal 1.5 s swing rather than stacking with it -- a body spinning is not also swinging,
        and stacking would double-count. Neither is stated; both are in conflicts.md.
        """
        eng = _quiet(_make_engine())
        v = _hero(eng, "valkyrie", 0.5, 0.5, still=True)
        near = _dummy(eng, 0, 0.5 + 1.5 / _TILES_X, 0.5)
        far = _dummy(eng, 0, 0.5 + 4.0 / _TILES_X, 0.5)
        air = _dummy(eng, 0, 0.5 + 1.0 / _TILES_X, 0.5, base="minions")
        n0, f0, a0 = near.hp, far.hp, air.hp
        self.assertTrue(eng.champion_ability(1))
        _run(eng, 6.0)
        self.assertEqual(v.ability_hits, 14, "3.5 s at 0.25 s is 14 turns of the spin")
        self.assertAlmostEqual(n0 - near.hp, 14 * 97.0, places=1)
        self.assertAlmostEqual(f0 - far.hp, 0.0, places=3)       # 4.0 tiles > the 2.5 radius
        self.assertAlmostEqual(a0 - air.hp, 0.0, places=3)       # Target: Ground

    def test_valkyrie_crown_damage_uses_the_published_HALF(self):
        eng = _quiet(_make_engine())
        tw = eng.towers[0][0]
        _hero(eng, "valkyrie", tw.x, tw.y - 1.0 / _TILES_Y, still=True)
        h0 = tw.hp
        self.assertTrue(eng.champion_ability(1))
        _run(eng, 6.0)
        self.assertAlmostEqual(h0 - tw.hp, 14 * 48.5, places=1)  # 97 x 0.5, fourteen times

    def test_bowler_stone_swish_fires_the_page_s_OWN_three_shots(self):
        """Bowler/Hero revid 437528: "After 2.5sec of the ability pressed, the bowler will change
        the attack to a long-ranged mortar attack for 7.3sec. Getting a total of 3 shots during
        that duration."

        THE PROSE AND THE TABLE RECONCILE, which is why no shot cap is curated anywhere: 7.3 s at a
        1.9 s cadence is FOUR shots if the first lands at t=0 and exactly THREE if the stance pays
        one of its own hit-speeds first. The engine does the latter, and that rule is what this
        test pins. His 2.5 s Cast Time is the one published activation delay in the whole stage --
        rule (c)'s 1 s default does not apply to him.
        """
        eng = _quiet(_make_engine())
        tw = eng.towers[0][0]
        b = _hero(eng, "bowler", tw.x, tw.y - 10.0 / _TILES_Y, mute=False, still=True)
        self.assertAlmostEqual(b.spec.ability_delay, 2.5, places=3)
        h0 = tw.hp
        self.assertTrue(eng.champion_ability(1))
        shots, prev = [], tw.hp
        for _ in range(130):
            eng.advance(0.1)
            if tw.hp < prev - 1e-6:
                shots.append(round(eng.t, 1))
                prev = tw.hp
        self.assertEqual(len(shots), 3, "the published shot count, from the published numbers")
        for a, z in zip(shots, shots[1:]):
            self.assertAlmostEqual(z - a, 1.9, places=1)      # the ability's own Hit Speed
        self.assertAlmostEqual(h0 - tw.hp, 3 * 254.0, places=1)   # ctdmg_11, published outright

    def test_a_stance_that_extends_REACH_extends_sight_and_the_projectile_with_it(self):
        """MEASURED, and the reason both lines exist: with only `reach` raised to the published
        11.5 the Hero Bowler fired ZERO shots at a tower 10 tiles away -- `_acquire` never noticed
        it (sight 5.5) and, once it did, his boulder expired in mid-air at its body's published
        7-tile Projectile Range. A weapon that shoots 11.5 tiles has to look 11.5 tiles and its
        shot has to fly 11.5 tiles."""
        eng = _quiet(_make_engine())
        b = _hero(eng, "bowler", 0.5, 0.5, still=True)
        base = b.spec
        self.assertTrue(eng.champion_ability(1))
        _run(eng, 2.7)
        self.assertAlmostEqual(b.spec.reach, 11.5, places=3)
        self.assertGreaterEqual(b.spec.sight, 11.5)
        self.assertGreaterEqual(b.spec.proj_range, 11.5)
        self.assertGreater(base.sight, 0.0)
        self.assertLess(base.proj_range, 11.5)               # the body's own is 7.0


class ZonePulseTests(unittest.TestCase):

    def test_ice_golem_snowstorm_lands_three_slowing_pulses(self):
        """Ice Golem/Hero revid 437514: "generates a 4-tile aura radius that has 3 pulses, with
        each one slowing down enemy troops and dealing damage."

        THE PULSE INTERVAL IS PUBLISHED NOWHERE. 2.0 s is the ability's own Slowdown Duration --
        the only cadence on the page -- and the aura window follows from it (3 x 2.0) rather than
        being a second guess. It is `[verify]`-marked in the KB and queued for an in-game count;
        this test pins the COUNT and the geometry, which the page does state, and the interval only
        as the value the KB currently carries.

        The slow is the ability's OWN published pair (30% for 2 s), not the engine-wide slow, and
        History 2/3/2026's "decreased Freeze duration to 1.5sec" is not applied to it: that entry
        says FREEZE, and the 3rd blast's freeze is what History 4/8/2026 REMOVED.
        """
        eng = _quiet(_make_engine())
        g = _hero(eng, "ice_golem", 0.5, 0.5, still=True)
        inr = _dummy(eng, 0, 0.5 + 3.0 / _TILES_X, 0.5)
        out = _dummy(eng, 0, 0.5 + 6.0 / _TILES_X, 0.5)
        air = _dummy(eng, 0, 0.5 + 2.0 / _TILES_X, 0.5, base="minions")
        i0, o0, a0 = inr.hp, out.hp, air.hp
        self.assertTrue(eng.champion_ability(1))
        seen, prev = [], inr.hp
        for _ in range(90):
            eng.advance(0.1)
            if inr.hp < prev - 1e-6:
                seen.append((round(eng.t, 1), inr.slow_mult, round(inr.slow_left, 1)))
                prev = inr.hp
        self.assertEqual(len(seen), 3, "three pulses, and never a fourth")
        self.assertEqual(g.ability_hits, 3)
        self.assertAlmostEqual(i0 - inr.hp, 3 * 69.0, places=1)   # bliz_11 x3 = the page's 207
        self.assertAlmostEqual(a0 - air.hp, 3 * 69.0, places=1)   # ability Target: Air & Ground
        self.assertAlmostEqual(o0 - out.hp, 0.0, places=3)        # 6.0 tiles > the 4-tile aura
        for _t, mult, left in seen:
            self.assertAlmostEqual(mult, 0.70, places=2)          # table "Slowdown 30%"
            self.assertGreater(left, 1.5)                         # table "Slowdown Duration 2 sec"
        for a, z in zip(seen, seen[1:]):
            self.assertAlmostEqual(z[0] - a[0], 2.0, delta=0.15)   # 0.1 s physics grid

    def test_snowstorm_does_not_touch_a_crown_tower(self):
        """Silence is read as "it does not", never as "full damage". Every hero ability that does
        hit a tower publishes a crown value; the Snowstorm table publishes none at all, and a bare
        fallback would have handed it its FULL 69 per pulse -- the same trap I5 hit with Royal
        Delivery, where "discard its crown_tower_damage" gave it full crown damage."""
        eng = _quiet(_make_engine())
        tw = eng.towers[0][0]
        _hero(eng, "ice_golem", tw.x, tw.y - 2.0 / _TILES_Y, still=True)
        h0 = tw.hp
        self.assertTrue(eng.champion_ability(1))
        _run(eng, 8.0)
        self.assertAlmostEqual(h0 - tw.hp, 0.0, places=3)


class SummonTests(unittest.TestCase):
    """summon / summon_seek / summon_banner -- five heroes, 28.4% of hero candidates by deck
    weight. Everything about a summoned body lives on its own curated row, so these tests measure
    WHERE it lands and WHAT the ability itself does around it."""

    def test_the_three_placed_summons_land_where_their_pages_say(self):
        """Musketeer/Hero 437512 "placing a turret 3 tiles forward of the Musketeer"; Dark
        Prince/Hero 437359 "Dismount ... while Rhino charges buildings" (under him); Heroes 437509
        "Tomb Queen rises from the earth" (at the tomb)."""
        eng = _make_engine()
        for base, want, off in (("musketeer", "trusty_turret", 3.0),
                                ("dark_prince", "rhino", 0.0),
                                ("tombstone", "tomb_queen", 0.0)):
            with self.subTest(hero=base):
                eng = _quiet(_make_engine())
                h = _hero(eng, base, 0.5, 0.55, still=True)
                self.assertTrue(eng.champion_ability(1))
                _run(eng, 1.6)
                got = [u for u in eng.units if u.team == 1 and u.spec.key == want]
                self.assertEqual(len(got), 1)
                # `_gap` measures to the target's hitbox EDGE, so the published centre offset comes
                # back one body radius short -- which is the same convention every reach uses.
                self.assertAlmostEqual(_gap(h.x, h.y, got[0]), max(0.0, off - got[0].spec.radius),
                                       delta=0.2)

    def test_the_trusty_turret_decays_over_its_published_lifetime(self):
        """"This turret has a lifetime of 10 seconds ... unless the building is destroyed before
        the Decay kills it" -- and 1536/10 is the page's own "Turret Hitpoints lost per second"."""
        eng = _quiet(_make_engine())
        _hero(eng, "musketeer", 0.5, 0.55, still=True)
        self.assertTrue(eng.champion_ability(1))
        _run(eng, 3.5)
        tur = [u for u in eng.units if u.spec.key == "trusty_turret"][0]
        a = tur.hp
        _run(eng, 5.0)
        self.assertAlmostEqual((a - tur.hp) / 5.0, 153.6, delta=12.0)

    def test_coffin_cadets_soars_to_the_nearest_GROUND_body_and_lands_on_it(self):
        """Balloon/Hero 437524: "a skeletropper will fly towards the closest ground unit within 6
        tiles, deling spawn damage". Range 6.5 by rule (b) (the ability table over the prose's 6);
        the landing damage is SINGLE-TARGET because no radius is published anywhere."""
        eng = _quiet(_make_engine())
        b = _hero(eng, "balloon", 0.5, 0.55, still=True)
        near = _dummy(eng, 0, 0.5 + 3.0 / _TILES_X, 0.55)
        far = _dummy(eng, 0, 0.5 + 6.0 / _TILES_X, 0.55)
        air = _dummy(eng, 0, 0.5 + 1.0 / _TILES_X, 0.55, base="minions")
        n0, f0, a0 = near.hp, far.hp, air.hp
        self.assertTrue(eng.champion_ability(1))
        _run(eng, 1.6)
        sk = [u for u in eng.units if u.team == 1 and u.spec.key == "skeletrooper"]
        self.assertEqual(len(sk), 1)
        self.assertAlmostEqual(n0 - near.hp, 263.0, places=1)   # landdmg_11
        self.assertAlmostEqual(f0 - far.hp, 0.0, places=3)      # 6.0 tiles is not the nearest...
        self.assertAlmostEqual(a0 - air.hp, 0.0, places=3)      # ...and an AIR body is not a target
        self.assertLess(_gap(sk[0].x, sk[0].y, near), 0.5)

    def test_coffin_cadets_with_nothing_in_range_still_drops_the_skeletrooper(self):
        """The page never says what happens with no ground body in the soar range. He drops beside
        the Balloon and nothing is refunded -- ruling 7 pays back a DEAD champion, not a wasted
        activation. Recorded in conflicts.md."""
        eng = _quiet(_make_engine())
        b = _hero(eng, "balloon", 0.5, 0.55, still=True)
        d = _dummy(eng, 0, 0.5 + 9.0 / _TILES_X, 0.55)
        h0 = d.hp
        self.assertTrue(eng.champion_ability(1))
        _run(eng, 1.6)
        sk = [u for u in eng.units if u.team == 1 and u.spec.key == "skeletrooper"]
        self.assertEqual(len(sk), 1)
        self.assertAlmostEqual(h0 - d.hp, 0.0, places=3)
        self.assertLess(_gap(b.x, b.y, sk[0]), 1.0)

    def test_banner_brigade_is_the_one_ability_with_no_body_to_press_it_from(self):
        """Goblins/Hero 437513: "The ability will be disabeld until the last goblin is killed. When
        the last goblin dies, a banner will be deployed that last 5sec. When the ability is pressed
        during that time, 2 Brigade Goblins will spawn a little behind."

        Four rules in one sequence, and all four are the page's: disabled while ANY goblin lives,
        armed only by the LAST death, 2 bodies (History 4/8/2026, "from 3"), and the banner is
        consumed by the press -- which is what makes it single-use without a body to count on.
        """
        eng = _quiet(_make_engine())
        g1 = _hero(eng, "goblins", 0.5, 0.55, still=True)
        g2 = _hero(eng, "goblins", 0.52, 0.55, still=True)
        self.assertFalse(eng.champion_ability(1), "disabled while both are alive")
        g1.hp = 0.0
        _run(eng, 0.2)
        self.assertFalse(eng.champion_ability(1), "disabled while ONE is alive")
        g2.hp = 0.0
        _run(eng, 0.2)
        self.assertIn(1, eng._banner)
        e0 = eng.elixir[1]
        self.assertTrue(eng.champion_ability(1))
        self.assertAlmostEqual(e0 - eng.elixir[1], 1.0, places=3)   # the published ability cost
        _run(eng, 1.6)
        brig = [u for u in eng.units if u.team == 1 and u.spec.key == "brigade_goblin"]
        self.assertEqual(len(brig), 2)
        self.assertNotIn(1, eng._banner)
        self.assertFalse(eng.champion_ability(1), "the banner is spent: single use")

    def test_the_banner_expires_on_its_published_five_seconds(self):
        eng = _quiet(_make_engine())
        g = _hero(eng, "goblins", 0.5, 0.55, still=True)
        g.hp = 0.0
        _run(eng, 0.2)
        self.assertTrue(1 in eng._banner)
        _run(eng, 5.5)
        self.assertFalse(eng.champion_ability(1))


class ThrowDisplaceTests(unittest.TestCase):

    def test_heroic_hurl_throws_the_HIGHEST_hp_troop_horizontally(self):
        """Giant/Hero 437510: "grabbing the highest HP enemy troop within 2 tiles around him and
        throws them horizontally, also dealing damage to them when they land." Table: Throwback
        Range 9, Units Affected 1, Unit Stun Duration 2 secs, imp_dmg_11 135.

        HORIZONTAL means along x, away from him -- "across the Arena", which is what takes a
        defender OUT of the lane rather than up or down it.
        """
        eng = _quiet(_make_engine())
        _hero(eng, "giant", 0.12, 0.55, still=True)
        big = _dummy(eng, 0, 0.12 + 1.0 / _TILES_X, 0.55, hp=5000.0)
        # BEHIND him on purpose: still inside the 2-tile grab, but out of the flight path, so what
        # this measures is the "Units Affected 1" cap and not a collision with the body sailing past
        small = _dummy(eng, 0, 0.12 - 1.2 / _TILES_X, 0.55, hp=300.0)
        outside = _dummy(eng, 0, 0.12 + 4.0 / _TILES_X, 0.55, hp=9000.0)
        bx, sx, ox = big.x, small.x, outside.x
        b0, s0 = big.hp, small.hp
        self.assertTrue(eng.champion_ability(1))
        _run(eng, 1.2)
        self.assertAlmostEqual((big.x - bx) * _TILES_X, 9.0, delta=0.4)   # Throwback Range
        self.assertAlmostEqual((big.y - 0.55) * _TILES_Y, 0.0, delta=0.5,
                               msg="horizontally: the throw must not move it up or down the lane")
        self.assertAlmostEqual(b0 - big.hp, 135.0, places=1)              # imp_dmg_11
        self.assertGreater(big.stun_left, 1.5)                            # Unit Stun Duration 2 s
        self.assertGreater(big.flying_left, 1.5)
        # "Units Affected 1": the SMALLER body beside it is untouched, and so is anything outside
        # the 2-tile grab -- the pick is by hitpoints, not by distance.
        self.assertAlmostEqual((small.x - sx) * _TILES_X, 0.0, delta=0.3)
        self.assertAlmostEqual(s0 - small.hp, 0.0, places=3)
        self.assertAlmostEqual((outside.x - ox) * _TILES_X, 0.0, delta=0.3)

    def test_a_thrown_body_is_AIR_while_it_flies_and_air_takes_no_landing_damage(self):
        """"While on the air, these troops are untargetable by ground-targeting troops and the
        Earthquake, but can still take damage from other spells" -- which is what being AIR already
        means in this engine, so it is one temporary flag. "Air troops can be affected by the
        ability, but will take no damage when they land"."""
        eng = _quiet(_make_engine())
        _hero(eng, "giant", 0.12, 0.55, still=True)
        m = _dummy(eng, 0, 0.12 + 1.0 / _TILES_X, 0.55, hp=5000.0, base="minions")
        mx, m0 = m.x, m.hp
        self.assertTrue(eng.champion_ability(1))
        _run(eng, 1.2)
        self.assertAlmostEqual((m.x - mx) * _TILES_X, 9.0, delta=0.4)
        self.assertAlmostEqual(m0 - m.hp, 0.0, places=3)
        # a GROUND body, mid-flight, is unreachable by a ground-only attacker
        eng = _quiet(_make_engine())
        _hero(eng, "giant", 0.12, 0.55, still=True)
        v = _dummy(eng, 0, 0.12 + 1.0 / _TILES_X, 0.55, hp=5000.0)
        self.assertTrue(eng.champion_ability(1))
        _run(eng, 1.2)
        ground_only = _dummy(eng, 1, v.x, v.y, base="knight")
        self.assertFalse(eng._valid_foe(ground_only, v),
                         "a ground-targeting troop cannot reach a body in the air")
        _run(eng, 2.5)
        self.assertTrue(eng._valid_foe(ground_only, v), "...and can again once it lands")


class TauntShieldTests(unittest.TestCase):

    def test_triumphant_taunt_drags_even_a_building_targeter_off_the_tower(self):
        """Knight/Hero 437499: "taunting every enemy troop and building in a 7.5-tiles range,
        causing them to attack him. He also gains a shield."

        RADIUS 6.5, not the 7.5 the prose AND the table print: rule (a), History 2/3/2026
        "decreased the radius of Triumphant Taunt to 6.5 tiles (from 7.5 tiles)".

        A HOG RIDER is the test case on purpose: a building-targeter ignores troops entirely, so
        the taunt has to outrank that branch or the card does not do the thing it is played for.
        """
        eng = _quiet(_make_engine())
        k = _hero(eng, "knight", 0.5, 0.45, still=True)
        hog = _dummy(eng, 0, 0.5 + 4.0 / _TILES_X, 0.45, base="hog_rider", still=False)
        far = _dummy(eng, 0, 0.5 + 8.0 / _TILES_X, 0.45, base="knight", still=False)
        self.assertTrue(eng.champion_ability(1))
        _run(eng, 1.2)
        self.assertAlmostEqual(k.shield_left, 512.0, places=1)      # vardefine Shild_11
        self.assertIs(hog.taunt_ref, k)
        self.assertIs(hog.target, k)
        self.assertIsNone(far.taunt_ref, "8 tiles is outside the 6.5-tile radius")

    def test_the_shield_expires_with_the_window_but_the_taunt_outlives_it(self):
        """"Both the shield and the taunt effect last for 5 seconds, unless the former is
        destroyed, ALTHOUGH enemy troops and buildings will still target him afterwards until he is
        defeated." Two mechanisms in one sentence, and the final clause is the observable rule --
        MEASURED with the taunt released at 5 s instead, a Hog re-acquired the tower on the NEXT
        TICK, because a building-targeter drops any lock on a body that is not a building."""
        eng = _quiet(_make_engine())
        k = _hero(eng, "knight", 0.5, 0.45, still=True)
        hog = _dummy(eng, 0, 0.5 + 4.0 / _TILES_X, 0.45, base="hog_rider", still=False)
        self.assertTrue(eng.champion_ability(1))
        _run(eng, 1.2)
        _run(eng, 6.0)
        self.assertAlmostEqual(k.shield_left, 0.0, places=3)
        self.assertIs(hog.target, k, "still on him after the window")
        k.hp = 0.0
        _run(eng, 0.4)
        self.assertNotIsInstance(hog.target, Unit, "...and released when he is defeated")


class TransformLevelUpTests(unittest.TestCase):

    def test_the_pancake_bar_buys_the_page_s_OWN_level_table(self):
        """Mini P.E.K.K.A./Hero 437522: "Every filled pancake meter increases the Levels gained
        when his ability is used by 1, except the last meter grants 2 extra Levels. With no meters
        ... 1 Level, but with a maximum of 3 meters, he can gain 5 Levels."

        ONE CLOCK IN SECONDS, because the page states both accrual rules that way: 22 s of time per
        meter, and every attack is worth another 10.
        """
        for cook, want in ((0.0, 1), (22.0, 2), (44.0, 3), (66.0, 5), (500.0, 5)):
            with self.subTest(cooked=cook):
                eng = _quiet(_make_engine())
                mp = _hero(eng, "mini_pekka", 0.5, 0.55, still=True)
                mp.cook_s = cook
                lv0 = mp.spec.level
                self.assertTrue(eng.champion_ability(1))
                _run(eng, 1.2)
                self.assertEqual(mp.spec.level - lv0, want)

    def test_the_levels_are_REAL_levels_and_the_heal_is_of_the_new_maximum(self):
        """The spec is rebuilt at `level + gain`, so hitpoints and damage move on the game's own
        percentage table rather than on a multiplier. Current hitpoints carry across unchanged -- a
        level-up is not itself a heal in this game -- and the published 30% goes on top of them."""
        eng = _quiet(_make_engine())
        mp = _hero(eng, "mini_pekka", 0.5, 0.55, still=True)
        mp.cook_s = 66.0
        base_hp, base_dmg = mp.spec.hp, mp.spec.hit_dmg
        mp.hp = base_hp * 0.4
        before = mp.hp
        self.assertTrue(eng.champion_ability(1))
        _run(eng, 1.2)
        self.assertGreater(mp.spec.hp, base_hp)
        self.assertGreater(mp.spec.hit_dmg, base_dmg)
        self.assertAlmostEqual(mp.hp, before + mp.spec.hp * 0.30, places=1)

    def test_an_attack_is_worth_ten_seconds_of_pancakes(self):
        """"he can also get 10 seconds of progress with every attack" -- on the SWING, whatever it
        lands on, which is why it is counted in `_attack` and not in `_land_hit`."""
        eng = _quiet(_make_engine())
        mp = _hero(eng, "mini_pekka", 0.5, 0.55, mute=False, still=True)
        _dummy(eng, 0, 0.5, 0.55 + 0.6 / _TILES_Y, hp=1e6)
        _run(eng, 4.0)
        self.assertGreaterEqual(mp.cook_s, 4.0 + 2 * 10.0,
                                "4 s of clock plus at least two swings at 1.6 s")


class DecoyBlinkTests(unittest.TestCase):

    def test_triple_threat_blinks_back_and_leaves_a_body_where_he_was(self):
        """Magic Archer/Hero 437520: "the Magic Archer will teleport back, while leaving a decoy in
        his place." Teleport Range 3.5 (History 6/7/2026, from 5); decoy_hp_11 271; Decoy Duration
        7 s. The teleport reuses the Boss Bandit's `ability_back_tiles` because it is the same
        mechanic, and "back" is toward his own king -- the only direction under which the page's
        own worked example (stepping out of a Fireball) works."""
        eng = _quiet(_make_engine())
        ma = _hero(eng, "magic_archer", 0.5, 0.45, still=True)
        y0 = ma.y
        self.assertTrue(eng.champion_ability(1))
        _run(eng, 1.2)
        self.assertAlmostEqual((y0 - ma.y) * _TILES_Y, 3.5, delta=0.3)   # team 1 retreats toward y=0
        dec = [u for u in eng.units if u.team == 1 and u.spec.key == "magic_archer_decoy"]
        self.assertEqual(len(dec), 1)
        self.assertAlmostEqual(dec[0].hp, 271.0, places=1)
        self.assertAlmostEqual(abs(dec[0].y - y0) * _TILES_Y, 0.0, delta=0.3)
        _run(eng, 9.0)
        self.assertEqual([u for u in eng.units if u.spec.key == "magic_archer_decoy"], [],
                         "the decoy is a TIMED, SILENT removal at its published 7 s")

    def test_the_next_attack_carries_three_arrows_and_only_the_next_one(self):
        """"The next attack now shots 3 arrows that travel longer, but with less damage."
        3 x triple_dmg_11 (48) = 144 against his normal 135, out to the ability's 13.5 tiles."""
        eng = _quiet(_make_engine())
        ma = _hero(eng, "magic_archer", 0.5, 0.45, mute=False, still=True)
        tgt = _dummy(eng, 0, 0.5, 0.45 + 2.0 / _TILES_Y, hp=1e6)
        self.assertTrue(eng.champion_ability(1))
        _run(eng, 1.2)
        self.assertEqual(ma.ability_hits, 3)
        h0 = tgt.hp
        for _ in range(60):
            eng.advance(0.1)
            if tgt.hp < h0 - 1e-6:
                break
        self.assertAlmostEqual(h0 - tgt.hp, 3 * 48.0, places=1)
        self.assertEqual(ma.ability_hits, 0, "spent -- the NEXT attack, once")
        h1 = tgt.hp
        _run(eng, 3.0)
        self.assertGreater(h1 - tgt.hp, 0.0)
        self.assertAlmostEqual((h1 - tgt.hp) % 135.3, 0.0, delta=1.0,
                               msg="every later swing is his ordinary damage again")


class WarpTests(unittest.TestCase):

    def test_wounding_warp_teleports_to_the_LOWEST_hitpoint_body_at_any_range(self):
        """Mega Minion/Hero 437518: "a marker will be deployed to the lowest hitpoint target. When
        that unit dies, the mark will move to the next unit. When the ability is preased, Mega
        Minion will teleport to that tile, dealing damage." Table: Teleport Range Infinite,
        warpdmg_11 399.

        The mark is computed at activation, which is the same thing as tracking it: a marker
        defined as "the lowest-hitpoint enemy, moving on when that one dies" always points at the
        lowest-hitpoint enemy alive right now.
        """
        eng = _quiet(_make_engine())
        mm = _hero(eng, "mega_minion", 0.5, 0.30, still=True)   # muted: he can reach `strong`
        weak = _dummy(eng, 0, 0.20, 0.80, hp=500.0)          # across the whole board
        strong = _dummy(eng, 0, 0.55, 0.35, hp=9000.0)       # ...and much nearer
        w0, s0 = weak.hp, strong.hp
        self.assertTrue(eng.champion_ability(1))
        _run(eng, 1.2)
        self.assertLess(_gap(mm.x, mm.y, weak), 1.0, "no range check: the table says Infinite")
        self.assertAlmostEqual(w0 - weak.hp, 399.0, places=1)
        self.assertAlmostEqual(s0 - strong.hp, 0.0, places=3)

    def test_the_crown_tower_penalty_is_permanent_after_the_warp(self):
        """Table "Crown Tower Damage 25%" (History 4/8/2026, "tower multiplier to x0.25 (from
        x0.5)"), and the same entry says the reduction "is now permanent" -- so it lands at the
        warp and never comes back off. The prose scopes it the same way: "Afterwards the Mega
        Minion will behave normally, but with -75% on the tower"."""
        eng = _quiet(_make_engine())
        mm = _hero(eng, "mega_minion", 0.5, 0.30, mute=False, still=True)
        _dummy(eng, 0, 0.55, 0.35, hp=9000.0)
        before = mm.spec.tower_hit_dmg
        self.assertTrue(eng.champion_ability(1))
        _run(eng, 1.2)
        self.assertAlmostEqual(mm.spec.tower_hit_dmg, before * 0.25, places=2)
        _run(eng, 12.0)
        self.assertAlmostEqual(mm.spec.tower_hit_dmg, before * 0.25, places=2)


class RerollTests(unittest.TestCase):

    def test_a_SPELL_hero_hands_its_button_to_the_body_it_leaves_behind(self):
        """The Hero Barbarian Barrel is the only card whose hero form is a SPELL, and a spell has
        no body to press a button from -- `champion_ability` selects the newest living UNIT with an
        `ability_kind`, and a `_Spell` is never one. build_spec therefore hands a spell's whole
        ability block to the troop it drops, as a RULE rather than a card check.

        MEASURED, and recorded in conflicts.md: the BASE barbarian_barrel spawns no Barbarian at
        all in this sim. `spawns_troop` is curated on the hero row only, so fixing the hero does
        not silently buff the 198 pool decks holding the base card.
        """
        eng = _quiet(_make_engine())
        spell = build_spec(eng.db, "barbarian_barrel_hero", LVL)
        self.assertEqual(spell.kind, "spell")
        self.assertEqual(spell.ability_kind, "", "the spell keeps none of it")
        self.assertIsNotNone(spell.spawn_spec)
        self.assertEqual(spell.spawn_spec.ability_kind, "reroll")
        base = build_spec(eng.db, "barbarian_barrel", LVL)
        self.assertIsNone(base.spawn_spec, "the base card's gap is recorded, not fixed here")

    def test_rowdy_reroll_rolls_a_second_corridor_and_lifesteals_half_of_it(self):
        """Barbarian Barrel/Hero 437523: "the Barbarian Barrel will roll for a second time, while
        healling the barbarian for 50% of the damage." Reroll Range 3 (History 4/5/2026, from 4),
        Width 2.6, Damage Healed 50%, and the roll's own damage is spawn_11 232.

        THE HEAL IS LIFESTEAL on what the roll actually took off, measured rather than assumed. The
        competing reading ("50% of the damage he has taken") is in conflicts.md.
        """
        eng = _quiet(_make_engine())
        spell = build_spec(eng.db, "barbarian_barrel_hero", LVL)
        eng.elixir[1] = 10.0
        self.assertTrue(eng.deploy(1, spell, 0.5, 0.45))
        _run(eng, 1.5)
        bb = [u for u in eng.units if u.team == 1 and u.spec.key == "barrel_barbarian"]
        self.assertEqual(len(bb), 1)
        b = bb[0]
        b.spec = replace(b.spec, hit_dmg=0.0, tower_hit_dmg=0.0, speed=0.0)   # mute HIS swing
        b.hp = b.spec.hp * 0.3
        hp0 = b.hp
        near = _dummy(eng, 0, b.x, b.y + 2.0 / _TILES_Y, hp=1e6)
        past = _dummy(eng, 0, b.x, b.y + 5.0 / _TILES_Y, hp=1e6)
        n0, p0 = near.hp, past.hp
        eng.elixir[1] = 10.0
        self.assertTrue(eng.champion_ability(1))
        _run(eng, 1.3)
        self.assertAlmostEqual(n0 - near.hp, 232.0, places=1)   # spawn_11, inside the 3-tile roll
        self.assertAlmostEqual(p0 - past.hp, 0.0, places=3)     # 5 tiles is past its end
        self.assertAlmostEqual(b.hp - hp0, 232.0 * 0.5, places=1)


class FlightNadoTests(unittest.TestCase):

    def test_fiery_flight_puts_him_in_the_air_and_spins_tornadoes_off_his_fireballs(self):
        """Wizard/Hero 437515: "makes him take flight for 5 seconds. While he is flying, not only
        he will get a 50% movement speed increase (now classified as fast), his fireballs also
        create 3 tile radius tornadoes, which does its own damage (reduced against crown towers),
        SIMILAR TO THE EVOLVED VALKYRIE."

        The page names the mechanic we already have, so the tornado IS the Evo Valkyrie's vortex
        behind an ability gate -- `attack_nado_ability`. Radius 4 not the prose's 3 (rule (b)), and
        the crown value is 43 x 0.36 from History 23/2/2026's published -64%.
        """
        eng = _quiet(_make_engine())
        wz = _hero(eng, "wizard", 0.5, 0.45, mute=False)
        _dummy(eng, 0, 0.5, 0.45 + 4.0 / _TILES_Y, hp=1e6)
        _run(eng, 3.0)
        self.assertEqual(len(eng.vortices), 0,
                         "his fireballs spin NOTHING until the ability is up -- Evo Valkyrie's is "
                         "permanent, his is gated")
        self.assertFalse(wz.flying_left > 0.0)
        self.assertTrue(eng.champion_ability(1))
        _run(eng, 1.2)
        self.assertGreater(wz.flying_left, 0.0)
        self.assertAlmostEqual(wz.spec.ability_move_speed, 1.5, places=3)   # +50% of medium
        _run(eng, 4.0)
        self.assertGreater(len(eng.vortices), 0, "and now they do")
        _run(eng, 5.0)
        self.assertFalse(wz.flying_left > 0.0, "5 s of flight, then he is ground again")

    def test_a_flying_wizard_is_unreachable_by_a_ground_targeting_troop(self):
        eng = _quiet(_make_engine())
        wz = _hero(eng, "wizard", 0.5, 0.45, still=True)
        ground_only = _dummy(eng, 0, 0.5, 0.46, base="knight")
        self.assertTrue(eng._valid_foe(ground_only, wz))
        self.assertTrue(eng.champion_ability(1))
        _run(eng, 1.2)
        self.assertFalse(eng._valid_foe(ground_only, wz))
        _run(eng, 5.5)
        self.assertTrue(eng._valid_foe(ground_only, wz))


class HeroSlotModelTests(unittest.TestCase):
    """The loadout half (owner ruling 2026-08-26; wiki 16/3/2026, "one Evolution, one Hero and one
    Wild"). These drive `ScriptedBot` directly rather than a whole match, because what is under
    test is the DRAW."""

    @staticmethod
    def _cfg_and_pool():
        from clashrl.config import Config
        from clashrl.cards import CardDB
        cfg = Config.load(str(ROOT / "config" / "config.yaml"))
        db = CardDB(cfg)
        return cfg, db, load_meta_decks(cfg, db)

    @staticmethod
    def _bot(cfg, db, rng, d):
        from clashrl.sim.opponents import ScriptedBot
        return ScriptedBot(cfg, db, rng, d["cards"], d["style"], [LVL] * len(d["cards"]),
                           evo=d["evo"], evo_candidates=d["evo_candidates"],
                           hero_candidates=d["hero_candidates"], support=d["support"])

    def test_hero_candidates_are_derived_and_validated_never_trusted(self):
        eng = _make_engine()
        cards = ["knight", "giant", "musketeer", "x_bow", "tesla", "archers", "skeletons", "rocket"]
        self.assertEqual(hero_candidates(eng.db, cards), ["knight", "giant", "musketeer"])
        # a card with no live hero form is not a candidate however it is spelled
        self.assertFalse(has_hero(eng.db, "x_bow"))
        self.assertFalse(has_hero(eng.db, "mega_knight"))

    def test_a_deck_with_a_candidate_ALWAYS_fields_a_hero(self):
        """The owner ruling is unconditional. MEASURED over the shipped pool: 842 of 1000 decks
        hold a candidate, and the slot fills in all but the handful whose ONE card is the sole
        candidate for the Evolution slot as well -- for those two "always" rulings cannot both
        hold, and the Evolution keeps the card."""
        import random
        cfg, db, pool = self._cfg_and_pool()
        rng = random.Random(11)
        have = [d for d in pool if d["hero_candidates"]]
        self.assertGreater(len(have), 800)
        filled = 0
        for _ in range(600):
            d = have[rng.randrange(len(have))]
            b = self._bot(cfg, db, rng, d)
            if b.hero_idx >= 0:
                filled += 1
                self.assertIn(b.cards[b.hero_idx], d["hero_candidates"])
                self.assertEqual(b.specs[b.hero_idx], b.hero_spec,
                                 "the slot is applied by SWAPPING the spec: a hero has no charge "
                                 "mechanic, it is the hero from its first play")
                self.assertEqual(b.hero_spec.key, b.cards[b.hero_idx] + "_hero")
        self.assertGreater(filled / 600.0, 0.98)

    def test_the_wild_slot_splits_one_third_each_under_a_seeded_rng(self):
        """1/3 is an UNMEASURED CHOICE, documented as such in config and in opponents.py -- no
        source publishes wild-slot frequencies. What this test pins is that the draw HONOURS the
        knobs, over the decks where both categories were still legal (`wild_choices` records that
        at draw time; deriving legality from the outcome afterwards is circular)."""
        import random
        cfg, db, pool = self._cfg_and_pool()
        rng = random.Random(3)
        got = {"evo": 0, "hero": 0, "": 0}
        n = 0
        for _ in range(4000):
            d = pool[rng.randrange(len(pool))]
            b = self._bot(cfg, db, rng, d)
            if b.wild_choices[0] > 0 and b.wild_choices[1] > 0:
                got[b.wild_kind] += 1
                n += 1
        self.assertGreater(n, 800, "not enough decks with both categories legal to measure")
        for k in ("evo", "hero", ""):
            self.assertAlmostEqual(got[k] / n, 1.0 / 3.0, delta=0.05,
                                   msg="wild split %r over n=%d: %r" % (k, n, got))

    def test_the_caps_hold_no_duplicate_card_and_never_two_from_one_slot(self):
        import random
        cfg, db, pool = self._cfg_and_pool()
        rng = random.Random(5)
        for _ in range(1500):
            d = pool[rng.randrange(len(pool))]
            b = self._bot(cfg, db, rng, d)
            idxs = [i for i in (b.evo_idx, b.hero_idx, b.wild_evo_idx, b.wild_hero_idx) if i >= 0]
            self.assertEqual(len(idxs), len(set(idxs)),
                             "one deck card cannot occupy two loadout slots")
            self.assertLessEqual(sum(1 for i in (b.evo_idx, b.wild_evo_idx) if i >= 0), 2)
            self.assertLessEqual(sum(1 for i in (b.hero_idx, b.wild_hero_idx) if i >= 0), 2)
            if b.wild_kind == "evo":
                self.assertNotEqual(b.wild_evo_idx, b.evo_idx)
            if b.wild_kind == "hero":
                self.assertNotEqual(b.wild_hero_idx, b.hero_idx)

    def test_the_wild_knobs_actually_move_the_draw(self):
        """A knob nothing reads is the thing this project keeps finding (`support:` was one for
        weeks). Zeroing both must leave the wild slot empty every time."""
        import random
        cfg, db, pool = self._cfg_and_pool()

        class _Zero:
            def __init__(self, inner):
                self._i = inner

            def get(self, *keys, **kw):
                if keys[:2] in (("sim", "wild_evo_prob"), ("sim", "wild_hero_prob")):
                    return 0.0
                return self._i.get(*keys, **kw)

            def path(self, p):
                return self._i.path(p)

        rng = random.Random(9)
        z = _Zero(cfg)
        for _ in range(300):
            d = pool[rng.randrange(len(pool))]
            b = self._bot(z, db, rng, d)
            self.assertEqual(b.wild_kind, "")
            self.assertEqual(b.wild_evo_idx, -1)
            self.assertEqual(b.wild_hero_idx, -1)


if __name__ == "__main__":                                   # pragma: no cover
    unittest.main()
