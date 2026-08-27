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

    The EVO half landed in I5 -- see EvoSnowballAirAndRollTests below.
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


class EvoSnowballAirAndRollTests(unittest.TestCase):
    """conflicts.md E4, CLOSED in I5: the Evo Giant Snowball hits AIR and still ROLLS.

    decisions.md #5 rules the Evo "roll range 4.0 tiles, hits air AND ground". The data half of
    that is one word in cards.yaml -- and on its own it would have DELETED the card's mechanic.

    MEASURED BEFORE, by flipping the row in memory on the pre-I5 tree:
        attacks ['ground']        -> ground_only True,  rolls True,  roll_len 4.5
        attacks ['air','ground']  -> ground_only False, rolls False, roll_len 0.0
    because build_spec derived `rolls` as ("rolls" in flags AND ground_only). The engine half of
    I5 decouples them: whether a corridor EXISTS is not the same question as what it may damage.

    MEASURED AFTER (this file): rolls True, roll_len 4.0 (the ruled range), ground_only False,
    and the roll damages minions and bats where before it dealt them 0.0.
    """

    def _cast(self, target):
        eng = _make_engine()
        t = build_spec(eng.db, target, LVL)
        u = Unit(spec=t, team=1, x=0.50, y=0.50, hp=t.hp * 20)
        eng.units.append(u)
        eng.elixir = [10.0, 10.0]
        self.assertTrue(eng.deploy(0, build_spec(eng.db, "giant_snowball_evo", LVL), 0.50, 0.50))
        before, x0, y0 = u.hp, u.x, u.y
        for _ in range(30):
            u.x, u.y = x0, y0
            eng.advance(0.1)
        return before - u.hp

    def test_the_roll_survives_the_air_and_ground_flip(self):
        eng = _make_engine()
        s = build_spec(eng.db, "giant_snowball_evo", LVL)
        self.assertEqual((eng.db.get("giant_snowball_evo") or {}).get("attacks"),
                         ["air", "ground"])
        self.assertFalse(s.ground_only)
        self.assertTrue(s.rolls, "MEASURED BEFORE: False -- the flip turned the roll off")
        self.assertTrue(s.carry_roll)
        self.assertAlmostEqual(s.roll_len, 4.0, delta=1e-9,
                               msg="MEASURED BEFORE: 0.0 (was 4.5 while ground-only)")

    def test_rolls_no_longer_depends_on_ground_only_in_either_direction(self):
        """The decoupling has to hold BOTH ways, or it is just a differently-placed coupling."""
        eng = _make_engine()
        row = dict(eng.db.get("giant_snowball_evo") or {})
        row["attacks"] = ["ground"]
        eng.db.cards["giant_snowball_evo"] = row
        try:
            s = build_spec(eng.db, "giant_snowball_evo", LVL)
            self.assertTrue(s.ground_only)
            self.assertTrue(s.rolls)
            self.assertAlmostEqual(s.roll_len, 4.0, delta=1e-9)
        finally:
            eng.db.cards["giant_snowball_evo"] = dict(row, attacks=["air", "ground"])

    def test_it_now_damages_air_and_still_damages_ground(self):
        """MEASURED BEFORE: knight 179.0, minions 0.0, bats 0.0 -- it could not answer air."""
        for name in ("knight", "minions", "bats"):
            with self.subTest(card=name):
                self.assertAlmostEqual(self._cast(name), 179.0, delta=1.0)

    def test_the_base_spell_does_not_roll(self):
        """The base Snowball is a point blast; only the Evolution carries the `rolls` flag, and
        the decoupling must not hand a corridor to every air-and-ground spell."""
        eng = _make_engine()
        self.assertFalse(build_spec(eng.db, "giant_snowball", LVL).rolls)
        self.assertFalse(build_spec(eng.db, "fireball", LVL).rolls)


class ChainArcIsPerCardTests(unittest.TestCase):
    """decisions.md #6: the chain arc is a PER-CARD KB field, and the Electro Dragon's is 4 tiles.

    This is the owner's original "the chain doesn't work" report, finally measured. engine.py had
    one global `_CHAIN_TILES = 3.0` carrying the comment "not published by the wiki". The R2 sweep
    disproved that premise on FOUR independent pages -- Electro Dragon, Electro Dragon/Evolution
    and Card Evolution all say 4 tiles for the ED family, and the Electro Spirit page says 4 for
    itself. The target COUNT was never wrong (1 + 2 others = hits_per_attack 3); only the reach.

    MEASURED, Electro Dragon swinging at body A with body B 3.5 tiles from A:
        arc 3.0 (the old global)  A 533.6   B   0.0   <- the bolt never leaves the first body
        arc 4.0 (the ruled value) A 266.8   B 266.8   <- it arcs, and each takes one hit
    533.6 is two swings' worth on A precisely BECAUSE the hop failed: nothing else was in range.
    """

    def _probe(self, arc):
        eng = _make_engine()
        s = replace(build_spec(eng.db, "electro_dragon", LVL), chain_tiles=arc)
        t = build_spec(eng.db, "knight", LVL)
        ax, ay = 0.50, 0.60 - 3.0 / _TILES_Y
        bx, by = 0.50 + 3.5 / _TILES_X, ay                   # 3.5 tiles from A: inside 4, not 3
        ed = Unit(spec=s, team=0, x=0.50, y=0.60, hp=s.hp)
        a = Unit(spec=t, team=1, x=ax, y=ay, hp=t.hp * 50)
        b = Unit(spec=t, team=1, x=bx, y=by, hp=t.hp * 50)
        eng.units += [ed, a, b]
        ha, hb = a.hp, b.hp
        for _ in range(60):
            a.x, a.y, b.x, b.y = ax, ay, bx, by              # pin them: this is a reach test
            eng.advance(0.05)
            if ha - a.hp > 0 and hb - b.hp > 0:
                break
        return ha - a.hp, hb - b.hp

    def test_a_chain_that_dies_at_three_tiles_connects_at_four(self):
        _, b3 = self._probe(3.0)
        a4, b4 = self._probe(4.0)
        self.assertEqual(b3, 0.0, "MEASURED BEFORE: the second body took nothing at 3.0 tiles")
        self.assertGreater(b4, 0.0, "at the published 4.0 the bolt arcs to it")
        self.assertAlmostEqual(b4, a4, delta=1.0, msg="each body takes one full hit")

    def test_the_ed_family_carries_the_published_arc(self):
        eng = _make_engine()
        for key in ("electro_dragon", "electro_dragon_evo"):
            with self.subTest(card=key):
                self.assertAlmostEqual(build_spec(eng.db, key, LVL).chain_tiles, 4.0, delta=1e-9)

    def test_the_global_is_only_a_FALLBACK_now(self):
        """A card that publishes no arc still lands on the module constant -- moving one card must
        not move every chain card with it, which is exactly why this became a KB field."""
        import clashrl.sim.engine as E
        eng = _make_engine()
        s = build_spec(eng.db, "electro_spirit", LVL)
        self.assertEqual(s.chain_tiles, 0.0, "electro_spirit is NOT in the #6 ruling")
        self.assertEqual(s.chain_tiles or E._CHAIN_TILES, E._CHAIN_TILES)
        self.assertEqual(E._CHAIN_TILES, 3.0)


class TestE1WalkingSpawnerPricing(unittest.TestCase):
    """E1 (owner-approved, MEASURED 2026-08-26): a spawner that WALKS is priced by how long it
    SURVIVES, not by an unmeasured flat constant.

    Owner ruling #11 made the Furnace a troop, which removed its `lifetime`. `threat_value`
    computes waves as lifetime/interval, so it fell through to the flat `_SPAWNER_WAVES = 2.0`
    and repriced the card by a third (ignore_cost_frac 0.2620 -> 0.0936) on a number nobody
    measured. Measured instead: an enemy Furnace deployed across 4 enemy levels x 15 placements
    (n=60) survives a median 19.4 s against our towers = 3.87 waves at its 5 s cadence; the Evo
    survives 19.1 s = 7.96 waves at 2.4 s. Those go in the KB as `effective_life_s`.
    """

    @classmethod
    def setUpClass(cls):
        from clashrl.cards import CardDB
        from clashrl.config import Config
        cls.db = CardDB(Config.load())

    def test_walking_spawner_carries_a_measured_effective_life(self):
        for key in ("furnace", "furnace_evo"):
            row = self.db.get(key) or {}
            self.assertIsNone(row.get("lifetime"), "%s is a troop now: no lifetime" % key)
            self.assertGreater(float(row.get("effective_life_s") or 0.0), 0.0,
                               "%s must carry the measured survival" % key)

    def test_the_flat_fallback_no_longer_prices_the_furnace(self):
        """2.0 waves was the unmeasured fallback; the measurement puts it near 3.87."""
        from clashrl.threat_value import ignore_cost_frac
        self.assertGreater(ignore_cost_frac(self.db, "furnace"), 0.15)

    def test_the_evo_outranks_the_base(self):
        """The Evo spawns at 2.4 s against the base's 5.0 s. Under the flat fallback BOTH got
        exactly 2 waves, so the faster spawner priced identically to the slower one -- the same
        class of bug the 2026-08 spawn-interval fix removed. Surviving time restores the order."""
        from clashrl.threat_value import ignore_cost_frac
        self.assertGreater(ignore_cost_frac(self.db, "furnace_evo"),
                           ignore_cost_frac(self.db, "furnace"))

    def test_a_real_lifetime_still_wins_over_the_measurement(self):
        """`effective_life_s` is the LAST fallback: a stationary hut keeps using its own lifetime."""
        from clashrl.threat_value import ignore_cost_frac
        row = self.db.get("goblin_hut") or {}
        self.assertTrue(row.get("lifetime") or row.get("lifetime_s"))
        self.assertGreater(ignore_cost_frac(self.db, "goblin_hut"), 0.0)


class ChainFalloffAndNoRepeatTests(unittest.TestCase):
    """decisions.md rulings 11, 12 and 15 -- the Electro Dragon chain, finally the right shape.

    A chain is NOT uniform. Electro_Dragon_Evolution.wikitext (live revid 437294) publishes three
    separate level-table columns for it:
        #vardefine: dmg_11       | 267   <- superseded by ruling 15, see below
        #vardefine: dmg_hits     | 3     <- bodies that take the FULL hit
        #vardefine: late_dmg_11  | 64    <- column "Damage after 5 chains"
    and the History that produced the third: 8/1/2025 "decreased the Evolved Electro Dragon's
    damage after the first 3 chains by 33%", 2/3/2026 "decreased it's chain damage by 50%".

    RULING 12 (owner): implement the RULE, not the constant. `chain_falloff_frac` = 0.3333 with
    `chain_full_hits` = 3, so the reduced number follows the card's damage instead of being frozen
    at a figure that has already gone stale once -- `late_dmg_11` sat at 64 across three archived
    revisions while `dmg_11` above it moved 192 -> 268 -> 267.

    RULING 15 (owner, in-game 2026-08-26): the damage is 192 @L11, not the 267 both wiki pages
    publish. 64 / 192 = 0.3333 exactly, so the published constant and the ruled fraction agree;
    against 267 the same fraction would give 89 and the wiki would contradict its own column.
    Pinned in config/import_pins.json; the competing reading is recorded in conflicts.md.

    MEASURED, one swing into a line of 13 knights 3 tiles apart (inside the published 4-tile arc),
    towers disarmed so nothing else enters the ledger:
        before   3204.0 total, 12 bodies at 267.0, EVERY one stunned
        after    1151.9 total, 3 at 192.0 stunned + 9 at 63.99 NOT stunned
    3204 was the single largest overstatement of enemy strength the R2 sweep found: the engine
    read `hits_per_attack: 12` as twelve FULL hits.
    """

    def _swing(self, key, n_bodies=13, spacing=3.0):
        """One attack cycle into a pinned line of bodies. Returns (per-body damage, stun flags)."""
        eng = _make_engine()
        for side in (eng.towers[0], eng.towers[1]):
            for tw in side:
                tw.hit_dmg = 0.0                      # tower fire would read as chain damage
        s = build_spec(eng.db, key, LVL)
        t = build_spec(eng.db, "knight", LVL)
        ax, ay = 0.50, 0.60 - 3.0 / _TILES_Y
        ed = Unit(spec=s, team=0, x=0.50, y=0.60, hp=s.hp)
        bodies = [Unit(spec=t, team=1, x=ax + (i * spacing) / _TILES_X, y=ay, hp=t.hp * 800)
                  for i in range(n_bodies)]
        eng.units.append(ed)
        eng.units.extend(bodies)
        pos = [(b.x, b.y) for b in bodies]
        start = [b.hp for b in bodies]
        for _ in range(400):
            for b, (px, py) in zip(bodies, pos):
                b.x, b.y = px, py                     # pinned: this is a chain-SHAPE test
            ed.x, ed.y = 0.50, 0.60
            eng.advance(0.05)
            if sum(start) - sum(b.hp for b in bodies) > 0:
                for _ in range(3):                    # let the arcs finish, stop before swing 2
                    for b, (px, py) in zip(bodies, pos):
                        b.x, b.y = px, py
                    eng.advance(0.05)
                break
        return ([h0 - b.hp for h0, b in zip(start, bodies)],
                [b.stun_left > 0.0 for b in bodies])

    def test_the_first_three_bodies_take_the_full_hit_WITH_the_stun(self):
        dmg, stun = self._swing("electro_dragon_evo")
        for i in range(3):
            with self.subTest(body=i):
                self.assertAlmostEqual(192.0, dmg[i], delta=0.5)
                self.assertTrue(stun[i], "the stun rides the full hits")

    def test_every_bounce_after_the_third_takes_a_THIRD_and_no_stun(self):
        """64 at level 11 -- the wiki's own `late_dmg_11`, and 192/3 under ruling 15."""
        dmg, stun = self._swing("electro_dragon_evo")
        for i in range(3, 12):
            with self.subTest(body=i):
                self.assertAlmostEqual(64.0, dmg[i], delta=0.5)
                self.assertFalse(stun[i], "a late bounce carries no stun")
        self.assertEqual(0.0, dmg[12], "hits_per_attack 12 is the total bounce budget")

    def test_the_swing_total_is_a_third_of_what_it_was(self):
        dmg, _ = self._swing("electro_dragon_evo")
        self.assertAlmostEqual(1152.0, sum(dmg), delta=2.0,
                               msg="MEASURED BEFORE: 3204.0 = 12 x 267")

    def test_the_base_card_chains_three_bodies_at_full_damage(self):
        """`chain_falloff` 0 means the uniform chain every OTHER chain card has: the base Electro
        Dragon's three hops are all full, all stunning. Only the Evolution declares a falloff."""
        eng = _make_engine()
        self.assertEqual(0.0, build_spec(eng.db, "electro_dragon", LVL).chain_falloff)
        dmg, stun = self._swing("electro_dragon")
        self.assertEqual([True, True, True], stun[:3])
        for i in range(3):
            self.assertAlmostEqual(192.0, dmg[i], delta=0.5)
        self.assertEqual(0.0, dmg[3], "the base card stops at its published dmg_hits of 3")

    def test_the_full_hit_count_is_the_base_cards_own_published_number(self):
        """`dmg_hits | 3` is published on BOTH pages. Pinning the identity stops the two drifting:
        ruling 12's "the first `multi_hits` targets (3, matching the base card)" is only true
        while they agree."""
        eng = _make_engine()
        base = build_spec(eng.db, "electro_dragon", LVL)
        evo = build_spec(eng.db, "electro_dragon_evo", LVL)
        self.assertEqual(3, base.multi_hits)
        self.assertEqual(3, evo.chain_full_hits)
        self.assertEqual(base.multi_hits, evo.chain_full_hits)
        self.assertAlmostEqual(0.3333, evo.chain_falloff, places=4)

    def test_ONE_chain_attack_can_never_hit_the_same_body_twice(self):
        """RULING 11 (owner, 2026-08-26), NARROWED BY RULING 16 (owner, 2026-08-27) to the PRIMARY
        chain, and pinned here so that half cannot regress. The engine was already correct --
        `_multi_hit` keeps `seen = {id(ref)}` -- and the 533.6 in the original arc measurement was
        TWO SEPARATE ATTACK CYCLES, not one chain double-hitting.

        Two bodies and a twelve-bounce budget. `chain_full_hits` is 3, so hops 1 and 2 are both
        PRIMARY: hop 1 takes the second body and hop 2 has no unhit body left, so the chain dies
        before the falloff bounces ever begin. Each body takes exactly one full hit. This is the
        case ruling 16 deliberately does NOT touch -- the secondary chain's revisit permission
        cannot rescue a chain that never reaches its secondary half.

        ED-3 RESOLVED (conflicts.md): the Evolution page's card quote -- "Evolved Electro Dragon's
        attack will chain between targets infinitely and can hit the same target more than once"
        -- is now implemented, for the SECONDARY bounces only. See
        `EvoChainSecondaryRepeatRuling16Tests` below.
        """
        dmg, _ = self._swing("electro_dragon_evo", n_bodies=2)
        self.assertAlmostEqual(192.0, dmg[0], delta=0.5)
        self.assertAlmostEqual(192.0, dmg[1], delta=0.5)
        self.assertAlmostEqual(384.0, sum(dmg), delta=1.0,
                               msg="a repeat-hitting PRIMARY chain would have dealt far more")


class EvoChainSecondaryRepeatRuling16Tests(unittest.TestCase):
    """decisions.md ruling 16 -- the Evo Electro Dragon's SECONDARY chain may revisit a target.

    Resolves conflict ED-3. The Evolution page contradicted ruling 11 in two places -- the card
    quote ("will chain between targets infinitely **and can hit the same target more than once**")
    and the Strategy note about the bolt bouncing off a Crown Tower back onto a troop it already
    hit. The owner split the difference rather than picking a side:

      * PRIMARY chain (the first `chain_full_hits` = 3 full-damage-with-stun hops): ruling 11
        stands unchanged -- it can NEVER hit the same body twice.
      * SECONDARY chain (the 9 falloff bounces, damage x `chain_falloff_frac`, no stun): MAY
        return to a body it already hit, but only after bouncing to a DIFFERENT body first. No
        immediate self-repeat; it must alternate.

    IMPLEMENTATION NOTE, and it is a deliberate reading of the ruling rather than a literal one.
    "Exclude only the immediately previous node" taken literally makes the nearest-target rule
    OSCILLATE: from the third body the two nearest are the first and the fourth, `min` breaks the
    tie toward the first, and the bolt then ping-pongs between two adjacent bodies for its whole
    remaining budget. MEASURED on the 13-knight line under that literal reading: total unchanged
    at 1151.9 but only THREE bodies took anything, against twelve before the ruling -- a large
    unmeasured nerf to the card's spread and the exact opposite of the page line that motivated
    the ruling. So `_multi_hit` prefers a body nothing has hit yet and revisits only when it has
    run out, which makes the revisit fire precisely where the chain used to DIE. Recorded in
    conflicts.md for the owner to overrule in one line if the oscillation was intended.

    MEASURED, one swing into a line of knights 3 tiles apart (arc 4.0), towers disarmed:

        bodies in arc |  before (ruling 11 only) |  after (ruling 16) |  change
              1       |        192.0             |       192.0        |    --
              2       |        384.0             |       384.0        |    --   (primary only)
              3       |        576.0             |      1151.9        |  +99.98%
              4       |        640.0             |      1151.9        |  +80.0%
              6       |        768.0             |      1151.9        |  +50.0%
             13       |       1151.9             |      1151.9        |    --   (never ran dry)

    The card now always spends its full 12-hit budget once it has three bodies to alternate
    between, instead of stopping when it runs out of fresh ones. The base Electro Dragon is
    untouched at every count (it declares no falloff, so it has no secondary chain at all).
    """

    ARC_SPACING = 3.0        # tiles, inside the ED family's published 4.0-tile arc

    def _swing_nodes(self, key, n_bodies, spacing=ARC_SPACING):
        """One attack cycle. Returns (per-body damage, hop sequence as body indices).

        The hop sequence is reconstructed from `eng.arc_events`, which records every chain hop as
        (from_x, from_y, to_x, to_y, team, t, label) -- so it is the engine's own account of where
        the bolt went, not an inference from the damage.
        """
        eng = _make_engine()
        for side in (eng.towers[0], eng.towers[1]):
            for tw in side:
                tw.hit_dmg = 0.0
        s = build_spec(eng.db, key, LVL)
        t = build_spec(eng.db, "knight", LVL)
        ax, ay = 0.50, 0.60 - 3.0 / _TILES_Y
        ed = Unit(spec=s, team=0, x=0.50, y=0.60, hp=s.hp)
        bodies = [Unit(spec=t, team=1, x=ax + (i * spacing) / _TILES_X, y=ay, hp=t.hp * 800)
                  for i in range(n_bodies)]
        eng.units.append(ed)
        eng.units.extend(bodies)
        pos = [(b.x, b.y) for b in bodies]
        start = [b.hp for b in bodies]
        eng.arc_events.clear()
        for _ in range(400):
            for b, (px, py) in zip(bodies, pos):
                b.x, b.y = px, py
            ed.x, ed.y = 0.50, 0.60
            eng.advance(0.05)
            if sum(start) - sum(b.hp for b in bodies) > 0:
                for _ in range(3):
                    for b, (px, py) in zip(bodies, pos):
                        b.x, b.y = px, py
                    eng.advance(0.05)
                break

        def _idx(x, y):
            """Map an arc endpoint back to the body standing on it (-1 = the dragon itself)."""
            for i, (px, py) in enumerate(pos):
                if abs(x - px) < 1e-6 and abs(y - py) < 1e-6:
                    return i
            return -1

        hops = [(_idx(a[0], a[1]), _idx(a[2], a[3]), a[6]) for a in eng.arc_events]
        hops = [h for h in hops if h[1] >= 0]
        return [h0 - b.hp for h0, b in zip(start, bodies)], hops

    def test_a_secondary_bounce_CAN_revisit_a_body_the_chain_already_hit(self):
        """THE RULING'S POINT. Three bodies, twelve-hit budget: the primary chain uses all three
        and the nine falloff bounces have no fresh target left, so under ruling 11 the chain died
        at 576.0. Ruling 16 lets them alternate back over bodies already hit."""
        dmg, hops = self._swing_nodes("electro_dragon_evo", 3)
        late = [h for h in hops if h[2] == "chain_late"]
        self.assertTrue(late, "the falloff bounces must run at all")
        visited = [h[1] for h in hops]
        self.assertGreater(len(visited), len(set(visited)),
                           "at least one body was hit more than once in ONE attack")
        self.assertAlmostEqual(1151.9, sum(dmg), delta=2.0,
                               msg="MEASURED BEFORE ruling 16: 576.0, the chain ran out of targets")

    def test_a_secondary_bounce_never_hits_the_SAME_body_twice_in_a_row(self):
        """The other half of the ruling: it must ALTERNATE. Every hop's destination differs from
        its origin, so no bounce can sit on one body and farm it."""
        for n in (3, 4, 6, 13):
            with self.subTest(bodies=n):
                _, hops = self._swing_nodes("electro_dragon_evo", n)
                for src, dst, label in hops:
                    self.assertNotEqual(src, dst,
                                        "a %s hop returned to its own origin immediately" % label)

    def test_the_PRIMARY_hops_still_never_repeat(self):
        """Ruling 11 survives ruling 16 for the full-damage half. The first `chain_full_hits`
        bodies are distinct, every one at full damage."""
        dmg, hops = self._swing_nodes("electro_dragon_evo", 13)
        primary = [h[1] for h in hops if h[2] == "chain"]
        self.assertEqual(len(primary), len(set(primary)), "a PRIMARY hop repeated a body")
        evo = build_spec(_make_engine().db, "electro_dragon_evo", LVL)
        self.assertEqual(2, len(primary),
                         "chain_full_hits 3 = the initial target plus two primary hops")
        for i in range(evo.chain_full_hits):
            self.assertAlmostEqual(192.0, dmg[i], delta=0.5)

    def test_ONE_enemy_in_range_stops_the_secondary_chain(self):
        """It cannot bounce to a DIFFERENT body, so it cannot come back -- the alternation rule is
        what bounds an otherwise 'infinite' chain on a one-body board. A literal 'may repeat'
        reading would have farmed a lone body for all twelve hits (192 + 11 x 64 = 896)."""
        dmg, hops = self._swing_nodes("electro_dragon_evo", 1)
        self.assertAlmostEqual(192.0, sum(dmg), delta=0.5,
                               msg="a lone body takes the initial hit and nothing else")
        self.assertEqual([], hops, "no hop can leave the only body on the board")

    def test_the_spread_is_not_sacrificed_to_the_revisit(self):
        """The fresh-body preference, pinned. On a full line the chain must still march across
        twelve distinct bodies exactly as it did before ruling 16 -- the revisit is a fallback for
        a chain that has run dry, not a new default. Under the literal 'exclude only the previous
        node' reading this MEASURED 3 bodies hit instead of 12."""
        dmg, _ = self._swing_nodes("electro_dragon_evo", 13)
        hit = [i for i, d in enumerate(dmg) if d > 0]
        self.assertEqual(list(range(12)), hit,
                         "12 distinct bodies, the same spread as before the ruling")
        self.assertAlmostEqual(1151.9, sum(dmg), delta=2.0)

    def test_the_BASE_electro_dragon_is_untouched_by_ruling_16(self):
        """It declares no `chain_falloff_frac`, so `full_n == n` and every hop is PRIMARY: there
        is no secondary chain for the revisit rule to apply to. Pinned at every body count that
        moved for the Evolution."""
        for n, expect in ((1, 192.0), (2, 384.0), (3, 576.0), (4, 576.0), (6, 576.0), (13, 576.0)):
            with self.subTest(bodies=n):
                dmg, _ = self._swing_nodes("electro_dragon", n)
                self.assertAlmostEqual(expect, sum(dmg), delta=1.0)

    def test_the_electro_SPIRIT_is_untouched_by_ruling_16(self):
        """`hits_per_attack` 9 with no `chain_full_hits`, so `full_n` falls back to n and all nine
        hops are primary. The ruling can only reach a card that declares a falloff, and the Evo
        Electro Dragon is the only one in the KB that does."""
        eng = _make_engine()
        sp = build_spec(eng.db, "electro_spirit", LVL)
        self.assertEqual(0, sp.chain_full_hits)
        self.assertEqual(0.0, sp.chain_falloff)
        _, hops = self._swing_nodes("electro_spirit", 13)
        self.assertTrue(all(h[2] == "chain" for h in hops), "no falloff bounces exist for it")
        dst = [h[1] for h in hops]
        self.assertEqual(len(dst), len(set(dst)), "every hop unique, ruling 11 unmodified")


class TestRollCorridorWidthIsPerCard(unittest.TestCase):
    """RS-1: a rolling spell's corridor half-width comes from ITS OWN card, not The Log's.

    `build_spec` hard-coded `spell_radius = _LOG_ROLL_HALFW` (1.95) for every `rolls` card, so the
    Barbarian Barrel swept a 3.9-tile corridor when its own KB row and both wiki pages publish
    width_tiles 2.6 -- 50% wider than the card. The Log is unaffected (3.9 / 2 == 1.95 exactly),
    which is what makes this safe to change: it is a no-op for the card the constant was named for.
    """

    @classmethod
    def setUpClass(cls):
        from clashrl.cards import CardDB
        from clashrl.config import Config
        cls.db = CardDB(Config.load())

    def _hw(self, key):
        from clashrl.sim.engine import build_spec
        return build_spec(self.db, key, 11).spell_radius

    def test_the_log_is_unchanged_by_the_switch_to_per_card_width(self):
        self.assertAlmostEqual(self._hw("the_log"), 1.95, places=4)

    def test_the_barrel_uses_its_own_narrower_width(self):
        row = self.db.get("barbarian_barrel") or {}
        self.assertAlmostEqual(float(row["width_tiles"]), 2.6, places=4)
        self.assertAlmostEqual(self._hw("barbarian_barrel"), 1.30, places=4)

    def test_the_hero_barrel_inherits_the_narrower_corridor(self):
        """The hero row publishes no width of its own -- it must overlay the base, not the Log."""
        self.assertAlmostEqual(self._hw("barbarian_barrel_hero"), 1.30, places=4)

    def test_an_unsourced_rolling_card_falls_back_to_the_log_value(self):
        """giant_snowball_evo has no width_tiles yet; the fallback must be documented, not silent."""
        self.assertAlmostEqual(self._hw("giant_snowball_evo"), 1.95, places=4)


if __name__ == "__main__":
    unittest.main()
