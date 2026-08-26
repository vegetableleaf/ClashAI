"""R2 ADJUDICATION #8 -- ENGINE/SCHEMA. The seven items the owner pulled forward from Phase I.

Every number below is off an archived wiki revision (research/sim_parity/webcache/) and every
change is an owner ruling recorded in research/sim_parity/decisions.md, section
"2026-08-26 -- R2 ADJUDICATION". The "MEASURED BEFORE" lines are what the sim actually did on
the unpatched tree, not estimates.
"""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
for _p in (str(SRC), str(ROOT / "tests")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from test_sim_status_effects import _make_engine                     # noqa: E402
from clashrl.sim.engine import Unit, build_spec, _TILES_Y            # noqa: E402

LVL = 11


class ThreeMusketeersReworkTests(unittest.TestCase):
    """Three Musketeers, the 3/11/2025 "Elite Musketeers" rework.

    Wiki (Three_Musketeers.wikitext rev 437182): "It spawns three single-target, air-targeting,
    long-ranged, ground troops ... If enemy troops are close to them, they switch to being
    single-target, ground-targeting, melee, ground troops with the same hitpoints and very high
    damage, and switch back to their ranged form when enemies are far from them."
    Ranged Attack row: Range 6, Target Air & Ground, 'range dmg_11' = 204.
    Melee Attack row:  Range "Melee: Long" (1.6 tiles), Target Ground, 'melee dmg_11' = 314.
    Shared: hp_11 883, atk_speed 1.3, Count x3.

    Owner: R2 #8 item 1 -- "a 9-elixir card dealing ZERO".
    MEASURED BEFORE: build_spec dps 0.0, hit_dmg 0.0, attacks_air False.
    """

    def spec(self):
        eng = _make_engine()
        return eng, build_spec(eng.db, "three_musketeers", LVL)

    def test_the_card_fields_three_separate_bodies(self):
        eng, s = self.spec()
        eng.elixir = [10.0, 10.0]
        self.assertTrue(eng.deploy(0, s, 0.50, 0.70))
        mine = [u for u in eng.units if u.team == 0]
        self.assertEqual(len(mine), 3, "the card is Count x3")
        for u in mine:
            self.assertAlmostEqual(u.hp, 883.0, delta=1.0,
                                   msg="all three bodies share hp_11 883 -- they are not a mixed squad")

    def test_they_are_not_a_mixed_squad(self):
        """The history line's "three DIFFERENT troops ... different damage statistics from the
        Musketeer" contrasts them with the MUSKETEER card, not with each other, so `components`
        (Goblin Gang / Rascals / Goblinstein) is the wrong machinery here."""
        _eng, s = self.spec()
        self.assertEqual(len(s.components), 0)
        self.assertEqual(s.squad_count, 0)

    def test_the_published_ranged_attack(self):
        _eng, s = self.spec()
        self.assertAlmostEqual(s.hit_dmg, 204.0, delta=0.5)      # 'range dmg_11'
        self.assertEqual(s.reach, 6.0)                           # Ranged Attack row, Range 6
        self.assertTrue(s.attacks_air, "Ranged Attack targets Air & Ground")
        self.assertAlmostEqual(s.hit_speed, 1.3, delta=1e-6)

    def test_the_published_melee_attack(self):
        _eng, s = self.spec()
        self.assertAlmostEqual(s.melee_dmg, 314.0, delta=0.5)    # 'melee dmg_11'
        self.assertEqual(s.melee_reach, 1.6)                     # "Melee: Long (1.6)"

    def _dealt(self, tiles, target="knight"):
        """One swing at a target whose HITBOX EDGE is `tiles` from the attacker's centre -- the
        same ruler `_gap` uses, so `tiles` is exactly the distance the melee switch tests."""
        eng = _make_engine()
        s = build_spec(eng.db, "three_musketeers", LVL)
        t = build_spec(eng.db, target, LVL)
        atk = Unit(spec=s, team=0, x=0.50, y=0.55, hp=s.hp)
        gap = tiles + t.radius
        tgt = Unit(spec=t, team=1, x=0.50, y=0.55 - gap / _TILES_Y, hp=t.hp * 500)
        eng.units += [atk, tgt]
        before = tgt.hp
        eng._attack(atk, "unit", tgt)
        return before - tgt.hp

    def test_a_ground_enemy_that_closes_in_takes_the_melee_hit(self):
        self.assertAlmostEqual(self._dealt(0.5), 314.0, delta=1.0)

    def test_a_ground_enemy_at_range_takes_the_ranged_hit(self):
        self.assertAlmostEqual(self._dealt(4.0), 204.0, delta=1.0)

    def test_the_switch_happens_at_the_published_melee_range(self):
        self.assertAlmostEqual(self._dealt(1.5), 314.0, delta=1.0)
        self.assertAlmostEqual(self._dealt(1.7), 204.0, delta=1.0)

    def test_air_never_gets_the_melee_hit(self):
        """The Melee Attack row's Target column reads Ground, so a Minion hovering on top of
        them is still answered with the 204 ranged shot."""
        self.assertAlmostEqual(self._dealt(0.5, target="minions"), 204.0, delta=1.0)

    def test_they_actually_hurt_something_over_time(self):
        """The headline defect: a 9-elixir card that could not damage anything."""
        eng = _make_engine()
        s = build_spec(eng.db, "three_musketeers", LVL)
        t = build_spec(eng.db, "giant", LVL)
        atk = Unit(spec=s, team=0, x=0.50, y=0.55, hp=s.hp)
        tgt = Unit(spec=t, team=1, x=0.50, y=0.55 - 4.0 / _TILES_Y, hp=t.hp * 100)
        eng.units += [atk, tgt]
        before = tgt.hp
        for _ in range(60):
            eng.advance(0.1)
        self.assertGreater(before - tgt.hp, 0.0, "MEASURED BEFORE: exactly 0 over any interval")

    def test_ordinary_single_mode_cards_are_untouched(self):
        """The melee switch is opt-in per card: nothing else in the KB declares one."""
        eng = _make_engine()
        for name in ("musketeer", "knight", "archers", "wizard", "hog_rider"):
            with self.subTest(card=name):
                self.assertEqual(build_spec(eng.db, name, LVL).melee_dmg, 0.0)



class FurnaceIsATroopTests(unittest.TestCase):
    """Furnace: no lifetime. Owner ruling R2 #11 -- "FURNACE IS A TROOP NOW -- no lifetime stat."

    Wiki (Furnace, 4/8/2025): it stopped being a building and became a walking troop, and its
    attributes table no longer prints a Lifetime column at all.

    VERIFIED FIRST, and the ledger's own claim did not survive it. r2_buckets UNPUB said "the sim
    despawns the Furnace after 28 s". It does not: the HP-decay path is gated on
    `kind == "building"`, and the KB already typed the Furnace `kind: troop`. MEASURED on the
    unpatched tree: deployed at y=0.80 it WALKED 11.6 tiles in 15 s at 1.0 tiles/s and then died
    to a crown tower at t=18.7 s -- never to decay. What was actually left was the stale
    `lifetime_s: 28.0` in card_mechanics.json (the 2023 game-file dump, whose key for the card is
    still literally "FirespiritHut"), which reached threat pricing rather than the combat loop.
    """

    def specs(self):
        eng = _make_engine()
        return eng, build_spec(eng.db, "furnace", LVL), build_spec(eng.db, "furnace_evo", LVL)

    def test_neither_row_carries_a_lifetime(self):
        _eng, base, evo = self.specs()
        self.assertIsNone(base.lifetime, "MEASURED BEFORE: 28.0, from the 2023 dump")
        self.assertIsNone(evo.lifetime, "MEASURED BEFORE: 28.0, hand-curated a second time")

    def test_it_is_a_troop_that_walks(self):
        _eng, base, evo = self.specs()
        for name, s in (("furnace", base), ("furnace_evo", evo)):
            with self.subTest(card=name):
                self.assertEqual(s.kind, "troop")
                self.assertGreater(s.speed, 0.0, "a walking troop, not an anchored building")

    def test_it_does_not_bleed_hitpoints(self):
        """Pinned clear of both towers so nothing but decay could touch it. 40 s is well past the
        28 s the stale row claimed."""
        for name in ("furnace", "furnace_evo"):
            with self.subTest(card=name):
                eng = _make_engine()
                s = build_spec(eng.db, name, LVL)
                u = Unit(spec=s, team=0, x=0.50, y=0.80, hp=s.hp)
                eng.units.append(u)
                x0, y0 = u.x, u.y
                for _ in range(400):
                    u.x, u.y = x0, y0            # hold it out of every tower's reach
                    eng.advance(0.1)
                self.assertAlmostEqual(u.hp, s.hp, delta=1.0,
                                       msg="%s decayed; troops do not" % name)

    def test_the_owners_spawn_cadence_is_intact(self):
        """Owner ruling R2 #5: furnace spawn speed 5 s. The Evo's 2.4 s "Hot Spawn" is its own
        edge and is a separate field."""
        _eng, base, evo = self.specs()
        self.assertAlmostEqual(base.spawner_interval, 5.0, delta=1e-6)
        self.assertAlmostEqual(evo.spawner_interval, 2.4, delta=1e-6)
        self.assertEqual(base.spawner_spec.base, "fire_spirit")
        self.assertEqual(evo.spawner_spec.base, "fire_spirit")

    def test_it_still_produces_fire_spirits_on_that_cadence(self):
        eng = _make_engine()
        s = build_spec(eng.db, "furnace", LVL)
        u = Unit(spec=s, team=0, x=0.50, y=0.80, hp=s.hp)
        eng.units.append(u)
        seen, x0, y0 = set(), u.x, u.y
        for _ in range(160):                     # 16 s -> three 5 s periods
            u.x, u.y = x0, y0
            eng.advance(0.1)
            seen.update(id(z) for z in eng.units if z.spec.base == "fire_spirit")
        self.assertGreaterEqual(len(seen), 3, "16 s at a 5 s period is at least three spirits")

    def test_real_buildings_keep_their_lifetime(self):
        """The blast radius. Only the Furnace's row was touched, so every genuine building --
        including the other eleven the same 2023 dump supplies -- is unchanged."""
        eng = _make_engine()
        expected = {"tesla": 30.0, "goblin_hut": 30.0, "barbarian_hut": 30.0, "x_bow": 30.0,
                    "mortar": 30.0, "cannon": 30.0, "bomb_tower": 30.0, "inferno_tower": 30.0,
                    "tombstone": 30.0, "goblin_cage": 20.0, "goblin_drill": 10.0}
        for name, life in expected.items():
            with self.subTest(card=name):
                self.assertAlmostEqual(build_spec(eng.db, name, LVL).lifetime, life, delta=1e-6)


class RamRiderSnareTests(unittest.TestCase):
    """Ram Rider's snare lasts 2 s, off the card and not off a global default.

    Wiki (Ram_Rider.wikitext rev 437334, "Rider Attributes" table):
    Hit Speed 1.1 | First Hit 0.4 | Snare Duration 2 sec | Slowdown -70% | Range 5.5 |
    Projectile Speed 600 | Target "Air & Ground (Troops only)".
    Owner: R2 #8 item 3.

    MEASURED BEFORE: build_spec slow_dur 0.00 with slow_mult 0.30, so `_apply_status` fell through
    to `spec.slow_dur or self.slow_dur` and used the engine-wide `sim.slow_duration`. That global
    is 2.0 in both decks today, so the snare LOOKED right -- by coincidence. Ram Rider was the only
    card in either KB carrying slow_pct without a slow_duration_s.
    """

    def test_the_card_publishes_its_own_snare_duration(self):
        eng = _make_engine()
        s = build_spec(eng.db, "ram_rider", LVL)
        self.assertAlmostEqual(s.slow_dur, 2.0, delta=1e-6, msg="MEASURED BEFORE: 0.0")
        self.assertAlmostEqual(s.slow_mult, 0.30, delta=1e-6)     # -70%
        self.assertTrue(s.slows)

    def _snare(self, engine_default):
        eng = _make_engine()
        eng.slow_dur = engine_default              # retune the GLOBAL out from under the card
        s = build_spec(eng.db, "ram_rider", LVL)
        t = build_spec(eng.db, "knight", LVL)
        atk = Unit(spec=s, team=0, x=0.50, y=0.55, hp=s.hp)
        tgt = Unit(spec=t, team=1, x=0.50, y=0.55 - (0.5 + t.radius) / _TILES_Y, hp=t.hp * 50)
        eng.units += [atk, tgt]
        eng._attack(atk, "unit", tgt)
        return tgt

    def test_the_snare_is_applied_at_the_published_strength(self):
        tgt = self._snare(2.0)
        self.assertAlmostEqual(tgt.slow_left, 2.0, delta=1e-6)
        self.assertAlmostEqual(tgt.slow_mult, 0.30, delta=1e-6)

    def test_it_no_longer_moves_with_the_global_slow_duration(self):
        """The defect this closes. Retuning sim.slow_duration for, say, the Ice Wizard used to
        silently retune Ram Rider's snare with it."""
        self.assertAlmostEqual(self._snare(9.0).slow_left, 2.0, delta=1e-6)
        self.assertAlmostEqual(self._snare(0.5).slow_left, 2.0, delta=1e-6)

    def _walk(self, snare):
        """A lone Knight walking up an empty lane, clear of both towers. Returns the tiles it
        covers in the first 2 s and in the 2 s after that."""
        eng = _make_engine()
        t = build_spec(eng.db, "knight", LVL)
        k = Unit(spec=t, team=1, x=0.50, y=0.35, hp=t.hp)
        eng.units.append(k)
        for _ in range(20):                        # burn the 1 s deploy timer first
            eng.advance(0.1)
        if snare:
            eng._apply_status(0, build_spec(eng.db, "ram_rider", LVL), k)
        ys = [k.y]
        for _ in range(40):                        # 4 s
            eng.advance(0.1)
            ys.append(k.y)
        return (ys[20] - ys[0]) * 32.0, (ys[40] - ys[20]) * 32.0, k.slow_left

    def test_a_snared_unit_crawls_then_regains_full_speed_after_two_seconds(self):
        """The behaviour, measured on the board rather than on the counter.
        MEASURED: free 1.290 then 1.319 tiles per 2 s; snared 0.387 then 1.290 --
        0.387 / 1.290 = 0.30, exactly the published -70%, and it lasts exactly 2 s."""
        free_a, free_b, _ = self._walk(False)
        slow_a, slow_b, left = self._walk(True)
        self.assertAlmostEqual(slow_a / free_a, 0.30, delta=0.02, msg="snared window is -70%")
        self.assertAlmostEqual(slow_b / free_a, 1.00, delta=0.05,
                               msg="full speed is back once the 2 s snare expires")
        self.assertEqual(left, 0.0)


class RageTargetingImportBugTests(unittest.TestCase):
    """Rage is a FRIENDLY-target spell; the KB claimed it only ever hits buildings.

    Wiki (Rage.wikitext rev 437309). Attributes row:
    Cost 2 | Radius 3 | Deploy 0.5 s | Duration 4.5 s | Boost +30% |
    Target "Friendly [[Troops]] & [[Buildings]]" | Spell | Epic.
    Lead: "It is an area-damage, air-targeting spell with a medium radius and low damage. It
    increases the movement speed and attack speed of allied troops and buildings by 30%."
    The damage itself was added 12/12/2022 ("made the spell deal area damage").
    Owner: R2 #8 item 4.

    MEASURED BEFORE: attacks ['buildings'], which in the sim's schema means Hog/Rocket-style
    "this only ever hits buildings" -- the exact opposite of what the Target column says. It came
    from `"building" in target` matching the word inside "Friendly Troops & Buildings".

    ⚠ SCOPE: the friendly BUFF (+30% move/attack speed for 4.5 s) is deliberately still not
    modelled -- that is stage I9. This fixes only the false targeting claim.
    """

    def test_the_row_no_longer_claims_buildings_only(self):
        eng = _make_engine()
        row = eng.db.get("rage") or {}
        self.assertNotEqual(row.get("attacks"), ["buildings"], "MEASURED BEFORE: ['buildings']")
        self.assertEqual(row.get("attacks"), ["air", "ground"], "its DAMAGE is air-targeting")

    def test_no_engine_path_treats_rage_as_a_buildings_spell(self):
        eng = _make_engine()
        s = build_spec(eng.db, "rage", LVL)
        self.assertEqual(s.kind, "spell")
        self.assertFalse(s.building_only, "building_only comes from flags/targets, never attacks")
        self.assertFalse(s.ground_only)
        self.assertFalse(s.rolls)
        self.assertTrue(s.attacks_air, "the blast reaches air; MEASURED BEFORE: False")

    def _blast(self, target, do_cast):
        """Damage taken by a pinned enemy over 3 s, with and without a Rage on top of it.
        Pinned and placed 12+ tiles from either crown tower so nothing else can touch it --
        the control run proves that (0.0 damage)."""
        eng = _make_engine()
        t = build_spec(eng.db, target, LVL)
        u = Unit(spec=t, team=1, x=0.50, y=0.50, hp=t.hp * 20)
        eng.units.append(u)
        if do_cast:
            eng.elixir = [10.0, 10.0]
            self.assertTrue(eng.deploy(0, build_spec(eng.db, "rage", LVL), 0.50, 0.50))
        before, x0, y0 = u.hp, u.x, u.y
        for _ in range(30):
            u.x, u.y = x0, y0
            eng.advance(0.1)
        return before - u.hp

    def test_the_blast_reaches_ground_and_air_alike(self):
        for name in ("knight", "minions", "baby_dragon"):
            with self.subTest(card=name):
                self.assertEqual(self._blast(name, False), 0.0, "control: nothing else hits it")
                self.assertAlmostEqual(self._blast(name, True), 179.0, delta=1.0)

    def test_real_building_targeters_are_untouched(self):
        eng = _make_engine()
        for name in ("giant", "hog_rider", "ram_rider", "golem", "balloon"):
            with self.subTest(card=name):
                self.assertTrue(build_spec(eng.db, name, LVL).building_only)


class TargetCellParseTests(unittest.TestCase):
    """card_import must not turn a BUFF target into an attack target again.

    The nine distinct Target cells across every archived page in
    research/sim_parity/webcache: "Ground" (185), "Air & Ground" (152), "Buildings" (52),
    "Friendly Troops" (4), "Friendly Troops & Buildings" (3), "Air & Ground (Troops only)" (3),
    "Building" (3), "King's Tower" (1), "Melee" (1). The table below is therefore exhaustive,
    not a sample.
    """

    def test_every_published_target_cell_maps_correctly(self):
        from clashrl.card_import import _attacks_from_target
        cases = {
            "Ground": ["ground"],
            "Air & Ground": ["air", "ground"],
            "Buildings": ["buildings"],
            "Building": ["buildings"],
            "Air & Ground (Troops only)": ["air", "ground"],
            "Friendly Troops": None,
            "Friendly Troops & Buildings": None,     # MEASURED BEFORE: ['buildings']
            "King's Tower": None,
            "Melee": None,
        }
        for cell, want in cases.items():
            with self.subTest(cell=cell):
                self.assertEqual(_attacks_from_target(cell), want)

    def test_the_archived_rage_page_no_longer_parses_as_a_buildings_card(self):
        from clashrl.card_import import _parse_attr_tables
        wc = ROOT.parents[0] / "research" / "sim_parity" / "webcache"
        page = wc / "Rage.wikitext"
        if not page.exists():
            self.skipTest("archived wikitext not present in this checkout")
        self.assertIsNone(_parse_attr_tables(page.read_text(encoding="utf-8")).get("attacks"),
                          "MEASURED BEFORE: ['buildings']")

    def test_the_pages_that_should_still_parse_as_buildings_do(self):
        from clashrl.card_import import _parse_attr_tables
        wc = ROOT.parents[0] / "research" / "sim_parity" / "webcache"
        want = {"Giant": ["buildings"], "Hog_Rider": ["buildings"], "Ram_Rider": ["buildings"],
                "Musketeer": ["air", "ground"], "Arrows": ["air", "ground"],
                "Battle_Healer": ["ground"], "Lumberjack": ["ground"]}
        for page, attacks in want.items():
            f = wc / (page + ".wikitext")
            if not f.exists():
                continue
            with self.subTest(page=page):
                self.assertEqual(_parse_attr_tables(f.read_text(encoding="utf-8")).get("attacks"),
                                 attacks)


if __name__ == "__main__":
    unittest.main()
