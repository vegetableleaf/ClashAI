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
from clashrl.sim.engine import (Unit, build_spec, replace,           # noqa: E402
                                _TILES_X, _TILES_Y)

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
        # Identity, and STRONG references: a spirit is a kamikaze that dies within a second or
        # two, and CPython reuses the freed address, so a set of id() values silently merged
        # distinct spirits and made this test flaky (it failed roughly one run in five).
        seen, x0, y0 = [], u.x, u.y
        for _ in range(160):                     # 16 s -> three 5 s periods
            u.x, u.y = x0, y0
            eng.advance(0.1)
            for z in eng.units:
                if z.spec.base == "fire_spirit" and not any(z is w for w in seen):
                    seen.append(z)
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


class LittlePrinceRampGraceTests(unittest.TestCase):
    """The Little Prince keeps his ramp through a SHORT move.

    Wiki (Little_Prince.wikitext rev 437347): "On 4/8/2026, a Balance Update, ... The Little Prince
    will now maintain his charged-up Hit Speed for up to 0.3 seconds while moving."
    That is a grace window on the base behaviour, not a removal of it: 14/12/2023 "fixed a bug
    where the Little Prince's hit speed would not reset after moving", and the page's strategy
    prose still lists The Log, Zap, Fireball and Giant Snowball as ramp resets.
    Owner: R2 #8 item 5.

    MEASURED BEFORE: `_move_toward` reset ramp_shots on the FIRST non-zero step, with no window.
    """

    def _saturated(self, grace=None):
        """Pin him on his firing spot until the ramp is at its top stage."""
        eng = _make_engine()
        s = build_spec(eng.db, "little_prince", LVL)
        if grace is not None:
            s = replace(s, ramp_move_grace=grace)
        t = build_spec(eng.db, "giant", LVL)
        lp = Unit(spec=s, team=0, x=0.50, y=0.55, hp=s.hp)
        tg = Unit(spec=t, team=1, x=0.50, y=0.55 - (s.reach * 0.6 + t.radius) / _TILES_Y,
                  hp=t.hp * 900)
        eng.units += [lp, tg]
        spot = (lp.x, lp.y, tg.x, tg.y)
        for _ in range(120):
            lp.x, lp.y, tg.x, tg.y = spot
            eng.advance(0.1)
        self.assertGreaterEqual(lp.ramp_shots, 6, "not saturated: the probe would prove nothing")
        return eng, lp, tg, spot

    def test_the_card_publishes_the_grace_window(self):
        eng = _make_engine()
        self.assertAlmostEqual(build_spec(eng.db, "little_prince", LVL).ramp_move_grace, 0.3,
                               delta=1e-9, msg="MEASURED BEFORE: no such field")

    def _after_moving(self, ticks, grace=None):
        eng, lp, _tg, _spot = self._saturated(grace)
        before = lp.ramp_shots
        for _ in range(ticks):
            eng._move_toward(lp, 0.50, 0.20, 0.1, 1.0)
        return before, lp.ramp_shots

    def test_a_brief_move_keeps_the_ramp(self):
        for ticks in (1, 2, 3):                        # 0.1 s .. 0.3 s
            with self.subTest(moved_s=ticks * 0.1):
                before, after = self._after_moving(ticks)
                self.assertEqual(after, before, "the ramp must survive up to 0.3 s of movement")

    def test_a_longer_move_still_resets_it(self):
        for ticks in (4, 6, 10):                       # 0.4 s and up
            with self.subTest(moved_s=ticks * 0.1):
                _before, after = self._after_moving(ticks)
                self.assertEqual(after, 0)

    def test_the_window_includes_exactly_three_tenths(self):
        """Three 0.1 s ticks sum to 0.30000000000000004, so a bare `>` expired the window a whole
        tick early. "Up to 0.3 seconds" includes 0.3."""
        self.assertNotEqual(self._after_moving(3)[1], 0)
        self.assertEqual(self._after_moving(4)[1], 0)

    def test_cards_with_no_grace_reset_on_the_first_step(self):
        """The control: the pre-4/8/2026 behaviour, which is still every other card's."""
        for ticks in (1, 2, 3):
            with self.subTest(moved_s=ticks * 0.1):
                self.assertEqual(self._after_moving(ticks, grace=0.0)[1], 0)

    def test_displacement_is_a_hard_reset_that_ignores_the_grace(self):
        """Log / Zap / Fireball / Giant Snowball. Named on the card's own page as the counterplay,
        so the grace must not protect him from a shove."""
        eng, lp, _tg, _spot = self._saturated()
        before = lp.ramp_shots
        eng._knock(lp, build_spec(eng.db, "the_log", LVL), lp.x, lp.y + 0.05)
        self.assertGreater(before, 0)
        self.assertEqual(lp.ramp_shots, 0)
        self.assertEqual(lp.ramp_move_t, 0.0)

    def test_the_grace_is_worth_real_damage(self):
        """The ramp is a HIT SPEED, so keeping it has to show up as output, not just as a counter.
        MEASURED over the 3 s after the move, back on his firing spot:
        no move 835, moved 0.3 s 835, moved 0.4 s 313, moved 1.0 s 313."""
        def dealt(ticks):
            eng, lp, tg, spot = self._saturated()
            for _ in range(ticks):
                eng._move_toward(lp, 0.50, 0.20, 0.1, 1.0)
            lp.x, lp.y = spot[0], spot[1]
            hp0 = tg.hp
            for _ in range(30):
                lp.x, lp.y, tg.x, tg.y = spot
                eng.advance(0.1)
            return hp0 - tg.hp
        kept, lost = dealt(3), dealt(4)
        self.assertAlmostEqual(kept, dealt(0), delta=1.0, msg="0.3 s of movement costs nothing")
        self.assertGreater(kept, lost * 2.0, "and losing the ramp has to hurt")


class DarkPrinceSplashShadowTests(unittest.TestCase):
    """Dark Prince splash 1.1, charge splash 1.1 -- and no field may shadow another again.

    Wiki (Dark_Prince.wikitext rev 437262), secondary attributes table
    Speed | Charge Range | Splash Radius | Target | Transport:
    "Very Fast (120) || 3 || 1.1 || Ground || Ground". Owner: R2 #8 item 6, splash 1.1 and
    charge splash 1.1 (r2_buckets: the curated 2.2 "is roughly double every published figure").

    MEASURED BEFORE: splash_r 1.250, charge_splash_r 2.200. The 1.25 came from a curated
    `splash_radius_tiles` SHADOWING the imported `splash_radius: 1.1` on the same merged row --
    build_spec prefers the *_tiles spelling, so the engine swung at 1.25 while every audit that
    read the row saw 1.1.
    """

    def test_the_published_radii(self):
        eng = _make_engine()
        s = build_spec(eng.db, "dark_prince", LVL)
        self.assertAlmostEqual(s.splash_r, 1.1, delta=1e-9, msg="MEASURED BEFORE: 1.250")
        self.assertAlmostEqual(s.charge_splash_r, 1.1, delta=1e-9, msg="MEASURED BEFORE: 2.200")

    def test_the_row_now_holds_exactly_one_splash_number(self):
        eng = _make_engine()
        row = eng.db.get("dark_prince") or {}
        self.assertIsNone(row.get("splash_radius_tiles"), "the stale shadowing field is gone")
        self.assertAlmostEqual(float(row.get("splash_radius")), 1.1, delta=1e-9)

    def _bystanders(self, radius_override=None, offsets=(1.05, 1.2, 2.5)):
        """Damage taken by bystanders sitting `offsets` tiles from the PRIMARY target, which is
        the ruler the splash loop uses (centre to centre from the unit that was struck)."""
        eng = _make_engine()
        s = build_spec(eng.db, "dark_prince", LVL)
        if radius_override is not None:
            s = replace(s, splash_r=radius_override)
        t = build_spec(eng.db, "knight", LVL)
        dp = Unit(spec=s, team=0, x=0.50, y=0.55, hp=s.hp)
        prime = Unit(spec=t, team=1, x=0.50, y=0.55 - (1.0 + t.radius) / _TILES_Y, hp=t.hp * 50)
        eng.units += [dp, prime]
        bys = []
        for off in offsets:
            b = Unit(spec=t, team=1, x=prime.x + off / _TILES_X, y=prime.y, hp=t.hp * 50)
            eng.units.append(b)
            bys.append(b)
        hp0 = [b.hp for b in bys]
        dp.charge_dist = 0.0
        eng._attack(dp, "unit", prime)
        return [round(h - b.hp, 1) for h, b in zip(hp0, bys)]

    def test_the_narrower_swing_actually_reaches_less_far(self):
        """MEASURED at 1.05 / 1.2 / 2.5 tiles from the struck body:
        splash 1.25 (old) -> 266.5, 266.5, 0.0
        splash 1.10 (new) -> 266.5,   0.0, 0.0"""
        old = self._bystanders(1.25)
        new = self._bystanders()
        self.assertGreater(old[1], 0.0, "the old radius caught the body at 1.2 tiles")
        self.assertEqual(new[1], 0.0, "1.1 does not reach 1.2 tiles")
        self.assertGreater(new[0], 0.0, "...but it still catches the body at 1.05")
        self.assertEqual(new[2], 0.0)

    def test_no_row_in_this_deck_shadows_anything(self):
        """The guard, run over the whole KB. mortar (2.0) and wall_breakers (1.5) carry BOTH
        spellings and agree, which is fine; a disagreement is not."""
        import warnings as _w
        from clashrl.sim.engine import _SHADOW_WARNED
        eng = _make_engine()
        with _w.catch_warnings(record=True) as caught:
            _w.simplefilter("always")
            _SHADOW_WARNED.clear()
            for name in sorted(eng.db.cards):
                try:
                    build_spec(eng.db, name, LVL)
                except Exception:                      # noqa: BLE001 - unbuildable rows are not our business
                    pass
        self.assertEqual([str(c.message) for c in caught], [])

    def test_the_guard_fires_on_a_genuine_shadow_and_only_once(self):
        import warnings as _w
        from clashrl.sim.engine import _tiles_or, _SHADOW_WARNED
        row = {"splash_radius_tiles": 1.25, "splash_radius": 1.1}
        with _w.catch_warnings(record=True) as caught:
            _w.simplefilter("always")
            _SHADOW_WARNED.clear()
            first = _tiles_or(row, "splash_radius", card="probe")
            _tiles_or(row, "splash_radius", card="probe")
        self.assertEqual(len(caught), 1, "deduped per (card, field): build_spec runs per fork")
        self.assertIn("SHADOWS", str(caught[0].message))
        self.assertAlmostEqual(first, 1.25, delta=1e-9, msg="precedence is unchanged on purpose")
        _SHADOW_WARNED.clear()

    def test_the_guard_is_silent_when_the_two_agree(self):
        import warnings as _w
        from clashrl.sim.engine import _tiles_or, _SHADOW_WARNED
        with _w.catch_warnings(record=True) as caught:
            _w.simplefilter("always")
            _SHADOW_WARNED.clear()
            v = _tiles_or({"splash_radius_tiles": 2.0, "splash_radius": 2.0}, "splash_radius",
                          card="mortar")
        self.assertEqual(len(caught), 0)
        self.assertAlmostEqual(v, 2.0, delta=1e-9)

    def test_other_splash_cards_are_untouched(self):
        eng = _make_engine()
        for name, r in (("mortar", 2.0), ("wall_breakers", 1.5), ("valkyrie", 2.0),
                        ("mega_knight", 1.3), ("bomber", 1.5), ("wizard", 1.5)):
            with self.subTest(card=name):
                self.assertAlmostEqual(build_spec(eng.db, name, LVL).splash_r, r, delta=1e-9)


class GiantSnowballBaseTargetingTests(unittest.TestCase):
    """The BASE Giant Snowball hits air and ground. Owner ruling R2 #5, item 7 of the #8 batch.

    Wiki: both the base and the Evolution pages print Target "Air & Ground".

    VERIFIED, no change was needed: the base row already reads attacks ['air', 'ground'] and the
    curated cards.yaml row does not override it. This class exists to LOCK that, because the
    Evolution row overrides it to ['ground'] on the very next line of the same file.

    ⚠ The EVO is still ground-only and that contradicts the same ruling -- see conflicts.md E4.
    It is deliberately not fixed here: `rolls` is derived as ("rolls" in flags AND ground_only),
    so flipping the Evo's attacks alone silently turns its ROLL off. That belongs with the rest
    of the #5 data batch, not in this engine/schema one.
    """

    def _cast(self, card, target):
        eng = _make_engine()
        t = build_spec(eng.db, target, LVL)
        u = Unit(spec=t, team=1, x=0.50, y=0.50, hp=t.hp * 20)
        eng.units.append(u)
        eng.elixir = [10.0, 10.0]
        self.assertTrue(eng.deploy(0, build_spec(eng.db, card, LVL), 0.50, 0.50))
        before, x0, y0 = u.hp, u.x, u.y
        for _ in range(30):
            u.x, u.y = x0, y0
            eng.advance(0.1)
        return before - u.hp, u.slow_left

    def test_the_base_row_targets_air_and_ground(self):
        eng = _make_engine()
        self.assertEqual((eng.db.get("giant_snowball") or {}).get("attacks"), ["air", "ground"])
        self.assertFalse(build_spec(eng.db, "giant_snowball", LVL).ground_only)

    def test_it_damages_and_slows_air_as_well_as_ground(self):
        """MEASURED: 179.0 damage and a slow applied to knight, minions and bats alike."""
        for name in ("knight", "minions", "bats"):
            with self.subTest(card=name):
                dealt, slow = self._cast("giant_snowball", name)
                self.assertAlmostEqual(dealt, 179.0, delta=1.0)
                self.assertGreater(slow, 0.0)


if __name__ == "__main__":
    unittest.main()
