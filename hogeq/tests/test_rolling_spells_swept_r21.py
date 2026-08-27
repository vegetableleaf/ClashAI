"""RULINGS 21-28 -- a rolling spell SWEEPS its corridor over time instead of resolving it at t=0.

BYTE-IDENTICAL in icebow and hogeq (parity_check enforces it), bare-engine and deck-agnostic.

RULING 21 (owner, 2026-08-27): "the log doesn't damage everything in the corridor at once, it takes
time to roll the entire 9.6 tiles, damaging a smaller area as it sweeps across the corridor."

WHAT WAS ACTUALLY WRONG, measured before the change. `_resolve_roll` was called once from the
spell-resolution path and iterated every unit, damaging the whole 9.6-tile corridor in one frame --
and `roll_speed` was DEAD DATA: the KB published it for `the_log` (200) and `giant_snowball_evo`
(300) and `build_spec` never read it, so the number that governs the whole mechanic reached nothing.

THE SPEED CONVERSION, verified rather than assumed. CR publishes speeds as a rating in "units" --
"Very Fast (120)", "Medium (60)" -- and `card_import._SPEED_UNITS_PER_TILE = 60.0` is the divisor
every troop's `speed_tiles` already goes through. The engine now carries the same constant (it must
not import the scraper) and `SpeedConversionTests` asserts the two agree, so the roll and a walking
Barbarian can never end up on different scales.

    card                     tiles   raw   tiles/s   sweep
    the_log                    9.6   200    3.3333   2.88 s
    barbarian_barrel           4.5   200    3.3333   1.35 s   (ruling 22: owner, same as The Log)
    barbarian_barrel_hero      4.5   200    3.3333   1.35 s   (inherited from the base row)
    giant_snowball_evo         4.0   300    5.0000   0.80 s   (fastest: shorter AND quicker)

MEASURED BEFORE -> AFTER, one Log, bodies pinned in place:

    whole corridor damaged at t=0   ->   swept over 2.88 s
    body 0.5 tiles ahead   t=0.00 -> t=0.15 s
    body 4.0 tiles ahead   t=0.00 -> t=1.20 s
    body 8.0 tiles ahead   t=0.00 -> t=2.40 s
    a body 8 tiles ahead that steps clear at 1.5 s: 266 damage -> 0
    a body outside the lane that steps in at 1.5 s:   0 damage -> 266

RULING 23 -- the barrel's Barbarian appears at the corridor END when the sweep COMPLETES.
⚠ THE BRIEF'S PREMISE WAS WRONG ABOUT THE POSITION: it was already the corridor end before this
change (`_resolve_roll` used `ey = s.y + fdir * roll_len`), and it was not at t=0 either. MEASURED,
a team-1 barrel cast at (0.500, 0.450):

    BEFORE:  body at (0.528, 0.594) = 4.60 tiles forward, at t=0.45 s (the spell's cast delay)
    AFTER:   body at (0.528, 0.594) = 4.60 tiles forward, at t=1.80 s (0.45 + the 1.35 s sweep)

so ONLY the timing moved, by exactly the sweep. The wiki says the same three times: "Once the spell
reaches its DESTINATION, it spawns a single Barbarian"; "AFTER IT FINISHES ROLLING, the Barbarian
will help take out and tank some of the Skeletons"; and "If the Barbarian Barrel is placed at most
2 tiles from the river, the Barbarian will spawn at the OPPOSING SIDE of the Arena".

RULINGS 24 / 26 / 27 / 28 -- the Hero Barbarian Barrel's Rowdy Reroll is a LITERAL second roll:
same `_Roll` path, same speed, a SHORTER 3.0-tile corridor (History 4/5/2026, "decreased the reroll
range to 3 tiles (from 4 tiles)"), launched from the LIVING Barbarian's current position, which
ABSORBS him and redeploys him at the endpoint healed by half the damage he had taken. There is
never a second Barbarian. Sources: `Barbarian_Barrel_Hero.live.wikitext` (revid 437523) and
`Barbarian_Barrel.wikitext`, both archived under `research/sim_parity/webcache/`.
"""
from __future__ import annotations

import sys
import unittest
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for _p in (str(ROOT / "src"), str(ROOT / "tests")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from test_sim_status_effects import _make_engine                          # noqa: E402
from clashrl.sim.engine import (Unit, _Roll, _Spell, build_spec,          # noqa: E402
                                _LOG_BACK_SLOP, _SPEED_UNITS_PER_TILE,
                                _TILES_X, _TILES_Y)

LVL = 11
DT = 0.05
ROLLERS = ("the_log", "barbarian_barrel", "barbarian_barrel_hero", "giant_snowball_evo")


def _quiet(eng):
    """Disarm the crown towers WITHOUT killing them (`alive = False` ends the match and freezes
    every timer under test)."""
    for side in (eng.towers[0], eng.towers[1]):
        for tw in side:
            tw.hit_dmg = 0.0
            tw.max_hp = tw.hp = 1e9
    return eng


def _still(eng, team, x, y, hp=1e6, base="knight"):
    """A pinned, harmless target. Every timing measurement here needs the body to STAY where it was
    put: a walking Knight closes on the corridor and is hit early, and one that reaches the river
    walks sideways to a bridge and out of the lane entirely (MEASURED -- a body placed 9.5 tiles
    ahead was never hit at all, because it had left the corridor before the edge arrived)."""
    s = replace(build_spec(eng.db, base, LVL), speed=0.0, hit_dmg=0.0, tower_hit_dmg=0.0,
                dmg_stages=())
    u = Unit(s, team, x, y, hp)
    u.deploy_left = 0.0
    eng.units.append(u)
    return u


def _cast_roll(eng, key, x, y, team=0):
    """Land a rolling spell AT ONCE at (x, y) and hand back the live `_Roll` it launches."""
    sp = build_spec(eng.db, key, LVL)
    eng._resolve_spell(_Spell(team, x, y, sp, 0.0))
    return sp, eng.rolls[-1]


def _sweep(eng, cap=400):
    """Advance until every roll has finished; returns the elapsed seconds."""
    t0 = eng.t
    for _ in range(cap):
        if not eng.rolls:
            break
        eng.advance(DT)
    return eng.t - t0


class SpeedConversionTests(unittest.TestCase):
    """`roll_speed` was in the KB and read by nothing. This is the wiring, and the units."""

    def test_the_engine_uses_the_SAME_divisor_as_the_importer(self):
        """60 speed units = 1 tile/second. If these two ever diverge, a rolling corridor and a
        walking troop are on different scales and every interaction timing is wrong."""
        from clashrl.card_import import _SPEED_UNITS_PER_TILE as importer
        self.assertEqual(60.0, _SPEED_UNITS_PER_TILE)
        self.assertEqual(importer, _SPEED_UNITS_PER_TILE)

    def test_every_rolling_card_publishes_a_speed_and_it_reaches_the_spec(self):
        eng = _make_engine()
        rows = []
        for k in ROLLERS:
            with self.subTest(card=k):
                s = build_spec(eng.db, k, LVL)
                self.assertTrue(s.rolls)
                self.assertGreater(s.roll_speed, 0.0,
                                   "%s has no roll speed, so its corridor would still resolve "
                                   "in one frame -- ruling 21 undone for that card alone" % k)
                rows.append((k, s.roll_len, s.roll_speed, s.roll_len / s.roll_speed))
        print("\n[R21] %-24s %6s %9s %8s" % ("card", "tiles", "tiles/s", "sweep s"))
        for k, ln, sp, dur in rows:
            print("[R21] %-24s %6.2f %9.4f %8.4f" % (k, ln, sp, dur))

    def test_the_published_numbers_are_the_ones_the_engine_ends_up_with(self):
        eng = _make_engine()
        for key, raw, tiles in (("the_log", 200.0, 9.6),
                                ("barbarian_barrel", 200.0, 4.5),
                                ("barbarian_barrel_hero", 200.0, 4.5),
                                ("giant_snowball_evo", 300.0, 4.0)):
            with self.subTest(card=key):
                s = build_spec(eng.db, key, LVL)
                self.assertAlmostEqual(raw / 60.0, s.roll_speed, places=6)
                self.assertAlmostEqual(tiles, s.roll_len, places=3)

    def test_the_HERO_barrel_inherits_the_speed_from_the_base_row(self):
        """RULING 23a. The hero row is a minimal overlay ({damage, spawns_troop, ability_*}); a
        zero here would make its sweep instantaneous and silently exempt the hero form from ruling
        21 -- the one place the change is hardest to notice."""
        eng = _make_engine()
        base = build_spec(eng.db, "barbarian_barrel", LVL)
        hero = build_spec(eng.db, "barbarian_barrel_hero", LVL)
        self.assertAlmostEqual(base.roll_speed, hero.roll_speed, places=6)
        self.assertAlmostEqual(base.roll_len / base.roll_speed,
                               hero.roll_len / hero.roll_speed, places=6)

    def test_a_card_with_no_published_speed_still_resolves_its_corridor(self):
        """THE DEGRADATION IS THE OLD BEHAVIOUR, never a division by zero and never a corridor that
        does nothing. No shipped card takes this path -- it guards a future one."""
        eng = _quiet(_make_engine())
        sp = replace(build_spec(eng.db, "the_log", LVL), roll_speed=0.0)
        foe = _still(eng, 1, 0.5, 0.75 - 8.0 / _TILES_Y)
        eng._resolve_spell(_Spell(0, 0.5, 0.75, sp, 0.0))
        self.assertEqual([], eng.rolls, "a speedless roll is consumed at once")
        self.assertAlmostEqual(sp.spell_dmg, 1e6 - foe.hp, places=1)

    def test_a_NON_rolling_spell_never_acquires_a_sweep(self):
        eng = _make_engine()
        for k in ("rocket", "fireball", "arrows", "zap", "giant_snowball"):
            with self.subTest(card=k):
                s = build_spec(eng.db, k, LVL)
                self.assertFalse(s.rolls)
                self.assertEqual(0.0, s.roll_speed)


class TheCorridorSweepsTests(unittest.TestCase):
    """Ruling 21 itself: WHEN each tile of the corridor is damaged."""

    def _timeline(self, key, dists):
        eng = _quiet(_make_engine())
        cx, cy = 0.5, 0.75
        vics = [(d, _still(eng, 1, cx, cy - d / _TILES_Y)) for d in dists]
        sp, _r = _cast_roll(eng, key, cx, cy)
        t0, seen = eng.t, {}
        for _ in range(400):
            eng.advance(DT)
            for d, u in vics:
                if d not in seen and u.hp < 1e6:
                    seen[d] = round(eng.t - t0, 4)
            if not eng.rolls:
                break
        return sp, seen, round(eng.t - t0, 4)

    def test_the_log_does_NOT_damage_its_whole_corridor_at_t0(self):
        """THE MEASUREMENT THE RULING IS ABOUT. One frame after the cast the far end is untouched;
        before this change both bodies took their damage in that same frame."""
        eng = _quiet(_make_engine())
        cx, cy = 0.5, 0.75
        near = _still(eng, 1, cx, cy - 0.5 / _TILES_Y)
        far = _still(eng, 1, cx, cy - 8.0 / _TILES_Y)
        sp, _r = _cast_roll(eng, "the_log", cx, cy)
        eng.advance(DT)
        self.assertAlmostEqual(0.0, 1e6 - far.hp, places=3,
                               msg="8 tiles ahead cannot be hit 0.05 s in")
        dur = _sweep(eng)
        self.assertAlmostEqual(sp.spell_dmg, 1e6 - near.hp, places=1)
        self.assertAlmostEqual(sp.spell_dmg, 1e6 - far.hp, places=1)
        print("\n[R21] the_log: whole corridor at t=0  ->  swept over %.2f s "
              "(9.6 tiles / 3.333 tiles per second = 2.88 s)" % dur)
        self.assertGreater(dur, 2.8)
        self.assertLess(dur, 3.0)

    def test_each_tile_is_reached_at_its_own_time(self):
        sp, seen, dur = self._timeline("the_log", (0.5, 2.0, 4.0, 8.0, 9.5))
        print("[R21] the_log leading edge (3.333 tiles/s), body at D tiles hit at t:")
        for d in sorted(seen):
            print("[R21]     %4.1f tiles -> %.2f s (D / 3.333 = %.2f)" % (d, seen[d], d / sp.roll_speed))
            self.assertAlmostEqual(d / sp.roll_speed, seen[d], delta=DT + 1e-6)
        self.assertEqual(5, len(seen), "everything in the corridor is still hit eventually")

    def test_the_three_rolling_cards_take_their_own_measured_time(self):
        for key, want in (("the_log", 2.88), ("barbarian_barrel", 1.35),
                          ("giant_snowball_evo", 0.80)):
            with self.subTest(card=key):
                eng = _quiet(_make_engine())
                _cast_roll(eng, key, 0.5, 0.75)
                dur = _sweep(eng)
                print("[R21] %-20s sweep %.2f s (published %.2f)" % (key, dur, want))
                self.assertAlmostEqual(want, dur, delta=DT + 1e-6)

    def test_a_body_is_damaged_AT_MOST_ONCE_by_one_cast(self):
        """`r.hit` is keyed on `deploy_seq`, and this is what it buys: the corridor test is
        re-evaluated every one of ~58 frames, so without it a stationary body would take the
        Log's 266 damage 58 times."""
        eng = _quiet(_make_engine())
        cx, cy = 0.5, 0.75
        foe = _still(eng, 1, cx, cy - 4.0 / _TILES_Y)
        sp, _r = _cast_roll(eng, "the_log", cx, cy)
        _sweep(eng)
        self.assertAlmostEqual(sp.spell_dmg, 1e6 - foe.hp, places=1)

    def test_the_back_slop_still_catches_a_body_BEHIND_the_cast_point(self):
        """`_LOG_BACK_SLOP` is 1.0 tile of backward tolerance at the ORIGIN, and it has to survive
        the rewrite -- a roll that only ever looks forward would quietly delete it."""
        eng = _quiet(_make_engine())
        cx, cy = 0.5, 0.75
        behind = _still(eng, 1, cx, cy + 0.6 * _LOG_BACK_SLOP / _TILES_Y)
        beyond = _still(eng, 1, cx, cy + 2.0 * _LOG_BACK_SLOP / _TILES_Y)
        sp, _r = _cast_roll(eng, "the_log", cx, cy)
        _sweep(eng)
        self.assertAlmostEqual(sp.spell_dmg, 1e6 - behind.hp, places=1)
        self.assertAlmostEqual(0.0, 1e6 - beyond.hp, places=3, msg="2 slops back is out")

    def test_the_knockback_arrives_WITH_the_edge_and_not_at_t0(self):
        """The Log is the one spell that pushes back ALL ground troops, so the shove is half of
        what the card does -- and it now happens as the roll reaches each body."""
        eng = _quiet(_make_engine())
        cx, cy = 0.5, 0.75
        far = _still(eng, 1, cx, cy - 8.0 / _TILES_Y)
        y0 = far.y
        sp, _r = _cast_roll(eng, "the_log", cx, cy)
        self.assertGreater(sp.knockback, 0.0)
        for _ in range(20):                                   # 1.0 s: the edge is ~3.3 tiles along
            eng.advance(DT)
        self.assertAlmostEqual(y0, far.y, places=6, msg="not shoved before the roll arrives")
        _sweep(eng)
        self.assertLess(far.y, y0, "shoved AWAY from the caster once the edge reaches it")
        self.assertAlmostEqual(sp.knockback, (y0 - far.y) * _TILES_Y, delta=0.05)


class WalkInAndWalkOutTests(unittest.TestCase):
    """The behavioural difference the ruling exists to create. Under the instant model BOTH of
    these bodies took the same damage, because the whole corridor resolved before either moved."""

    def _run(self, start_x_tiles, step_to_x_tiles, at_seconds):
        eng = _quiet(_make_engine())
        cx, cy = 0.5, 0.75
        u = _still(eng, 1, cx + start_x_tiles / _TILES_X, cy - 8.0 / _TILES_Y)
        sp, _r = _cast_roll(eng, "the_log", cx, cy)
        t0, moved = eng.t, False
        for _ in range(400):
            if not moved and eng.t - t0 >= at_seconds:
                u.x = cx + step_to_x_tiles / _TILES_X
                moved = True
            eng.advance(DT)
            if not eng.rolls:
                break
        return sp, 1e6 - u.hp

    def test_a_body_that_STEPS_CLEAR_before_the_edge_arrives_survives(self):
        sp, dealt = self._run(start_x_tiles=0.0, step_to_x_tiles=4.0, at_seconds=1.5)
        print("\n[R21] a body 8 tiles ahead that steps 4 tiles sideways at 1.5 s "
              "(edge is 5.0 of 9.6 tiles along): %.0f damage, was %.0f" % (dealt, sp.spell_dmg))
        self.assertAlmostEqual(0.0, dealt, places=3)

    def test_a_body_that_STEPS_IN_ahead_of_the_roll_is_caught(self):
        sp, dealt = self._run(start_x_tiles=4.0, step_to_x_tiles=0.0, at_seconds=1.5)
        print("[R21] a body outside the lane that steps IN at 1.5 s: %.0f damage, was 0" % dealt)
        self.assertAlmostEqual(sp.spell_dmg, dealt, places=1)

    def test_stepping_clear_AFTER_the_edge_has_passed_is_too_late(self):
        sp, dealt = self._run(start_x_tiles=0.0, step_to_x_tiles=4.0, at_seconds=2.9)
        self.assertAlmostEqual(sp.spell_dmg, dealt, places=1)

    def test_a_body_that_appears_BEHIND_the_leading_edge_is_not_hit(self):
        """The rule is "the edge sweeps PAST you", not "you are somewhere it has been". MEASURED
        with the naive swept-region test: a Goblin Barrel's goblins landing 3 tiles behind a Log's
        edge took the Log's damage from a roll that had gone by a second earlier."""
        eng = _quiet(_make_engine())
        cx, cy = 0.5, 0.75
        sp, _r = _cast_roll(eng, "the_log", cx, cy)
        for _ in range(20):                                   # 1.0 s -> the edge is ~3.3 tiles up
            eng.advance(DT)
        late = _still(eng, 1, cx, cy - 1.5 / _TILES_Y)         # well behind the edge
        _sweep(eng)
        self.assertAlmostEqual(0.0, 1e6 - late.hp, places=3)

    def test_a_body_that_appears_AHEAD_of_the_leading_edge_is_hit(self):
        eng = _quiet(_make_engine())
        cx, cy = 0.5, 0.75
        sp, _r = _cast_roll(eng, "the_log", cx, cy)
        for _ in range(20):
            eng.advance(DT)
        late = _still(eng, 1, cx, cy - 7.0 / _TILES_Y)          # still in front of the edge
        _sweep(eng)
        self.assertAlmostEqual(sp.spell_dmg, 1e6 - late.hp, places=1)


class TowerChipTests(unittest.TestCase):

    def test_a_tower_is_chipped_ONCE_and_only_when_the_edge_reaches_it(self):
        eng = _make_engine()
        tw = eng.towers[1][0]
        tw.hit_dmg = 0.0
        cy = tw.y + 6.0 / _TILES_Y                             # 6 tiles behind it, same lane
        sp, _r = _cast_roll(eng, "the_log", tw.x, cy)
        hp0 = tw.hp
        eng.advance(DT)
        self.assertAlmostEqual(hp0, tw.hp, places=3, msg="not chipped in the first frame")
        _sweep(eng)
        self.assertAlmostEqual(sp.spell_tower_dmg, hp0 - tw.hp, places=1,
                               msg="exactly one chip, not one per frame")


class SnowBowlingTests(unittest.TestCase):
    """Evo Giant Snowball: "the affected troops get pulled into it and [it] rolls for 4.5 tiles ...
    when it finishes its roll, the troops are freed". The instant model had to apologise for
    folding the carry into a teleport; now it is a real journey."""

    def test_a_carried_body_TRAVELS_with_the_roll_instead_of_teleporting(self):
        eng = _quiet(_make_engine())
        cx, cy = 0.5, 0.75
        u = _still(eng, 1, cx, cy - 0.5 / _TILES_Y)
        sp, r = _cast_roll(eng, "giant_snowball_evo", cx, cy)
        self.assertTrue(sp.carry_roll)
        seen = []
        for _ in range(400):
            eng.advance(DT)
            seen.append((cy - u.y) * _TILES_Y)
            if not eng.rolls:
                break
        self.assertGreater(len(set(round(v, 2) for v in seen)), 3,
                           "the carried body occupies several distinct positions, not two")
        self.assertAlmostEqual(sp.roll_len, seen[-1], delta=0.6,
                               msg="and is released at the corridor's end")
        self.assertGreater(u.slow_left, 0.0)


class EndOfCorridorSpawnTests(unittest.TestCase):
    """RULING 23 / 23a -- the barrel's Barbarian appears at the corridor END, when the sweep ends."""

    def _drop(self, key, body_key, cx=0.5, cy=0.45, team=1):
        eng = _quiet(_make_engine())
        sp = build_spec(eng.db, key, LVL)
        eng.elixir[team] = 10.0
        self.assertTrue(eng.deploy(team, sp, cx, cy))
        t0 = eng.t
        for _ in range(200):
            eng.advance(DT)
            got = [u for u in eng.units if u.team == team and u.spec.key == body_key]
            if got:
                return eng, sp, got[0], eng.t - t0
        self.fail("%s never left a %s" % (key, body_key))

    def test_the_base_barrel_drops_its_barbarian_4_5_tiles_up_when_the_sweep_ENDS(self):
        eng, sp, u, t = self._drop("barbarian_barrel", "base_barrel_barbarian")
        fwd = (u.y - 0.45) * _TILES_Y
        print("\n[R23] barbarian_barrel cast (0.500, 0.450) -> Barbarian at (%.3f, %.3f) "
              "= %.2f tiles forward, at t=%.2f s" % (u.x, u.y, fwd, t))
        print("[R23]   BEFORE: the same (0.528, 0.594) / 4.60 tiles, but at t=0.45 s -- only the "
              "TIMING moved, by exactly the 1.35 s sweep")
        self.assertAlmostEqual(sp.roll_len, fwd, delta=0.2)
        self.assertAlmostEqual(0.45 + sp.roll_len / sp.roll_speed, t, delta=DT + 1e-6)

    def test_the_HERO_barrel_drops_ITS_OWN_body_on_the_same_schedule(self):
        """RULING 23a: base drops `base_barrel_barbarian`, hero drops `barrel_barbarian`. Both at
        the corridor end, both when the sweep completes."""
        eng_b, sp_b, ub, tb = self._drop("barbarian_barrel", "base_barrel_barbarian")
        eng_h, sp_h, uh, th = self._drop("barbarian_barrel_hero", "barrel_barbarian")
        self.assertAlmostEqual(tb, th, delta=1e-6, msg="the hero sweeps for exactly as long")
        self.assertAlmostEqual(ub.y, uh.y, places=6)
        self.assertNotEqual(ub.spec.key, uh.spec.key)
        print("[R23a] hero barrel -> %s at (%.3f, %.3f) t=%.2f s (base: %s, same schedule)"
              % (uh.spec.key, uh.x, uh.y, th, ub.spec.key))

    def test_the_barbarian_lands_PAST_the_group_the_barrel_just_rolled_over(self):
        """THE TACTICAL POINT of ruling 23: the corridor damages the group and the body arrives on
        the FAR side of it, not behind it -- "The roll can also ... get behind troops"."""
        eng = _quiet(_make_engine())
        sp = build_spec(eng.db, "barbarian_barrel", LVL)
        cx, cy = 0.5, 0.45
        mid = [_still(eng, 0, cx, cy + d / _TILES_Y) for d in (1.5, 2.0, 2.5)]
        eng.elixir[1] = 10.0
        self.assertTrue(eng.deploy(1, sp, cx, cy))
        for _ in range(200):
            eng.advance(DT)
            got = [u for u in eng.units if u.team == 1 and u.spec.key == "base_barrel_barbarian"]
            if got:
                break
        self.assertTrue(got)
        for m in mid:
            self.assertLess(1e6 - m.hp, sp.spell_dmg + 1.0)
            self.assertGreater(1e6 - m.hp, 0.0, "the corridor rolled over the group")
            self.assertGreater(got[0].y, m.y,
                               "the Barbarian is BEYOND the group (%.3f vs %.3f)"
                               % (got[0].y, m.y))

    def test_the_spawn_point_is_CLAMPED_and_never_leaves_the_board(self):
        """A barrel cast near the far edge would put the corridor's end off-board; `_clamp_xy` is
        what stops it, and a body outside [0, 1] is a body the whole engine mis-handles."""
        eng = _quiet(_make_engine())
        sp = build_spec(eng.db, "barbarian_barrel", LVL)
        eng.elixir[1] = 10.0
        self.assertTrue(eng.deploy(1, sp, 0.5, 0.97))          # 4.5 tiles further is off the end
        for _ in range(200):
            eng.advance(DT)
            got = [u for u in eng.units if u.team == 1 and u.spec.key == "base_barrel_barbarian"]
            if got:
                break
        self.assertTrue(got, "it still spawns -- clamped, not cancelled")
        self.assertLessEqual(got[0].y, 1.0)
        self.assertGreaterEqual(got[0].y, 0.0)


class RowdyRerollTests(unittest.TestCase):
    """RULINGS 24 / 26 / 27 / 28 -- the hero's ability is another roll of the same barrel."""

    def _hero_body(self, eng, x=0.5, y=0.45):
        sp = build_spec(eng.db, "barbarian_barrel_hero", LVL)
        eng.elixir[1] = 10.0
        assert eng.deploy(1, sp, x, y)
        for _ in range(200):
            eng.advance(DT)
            got = [u for u in eng.units if u.team == 1 and u.spec.key == "barrel_barbarian"]
            if got:
                b = got[0]
                b.spec = replace(b.spec, hit_dmg=0.0, tower_hit_dmg=0.0)
                b.deploy_left = 0.0
                return sp, b
        raise AssertionError("no Barbarian")

    def test_the_second_roll_is_SHORTER_than_the_first(self):
        """History 4/5/2026: "decreased the reroll range to 3 tiles (from 4 tiles)". The barrel's
        own Range is 4.5, so reusing `roll_len` would silently restore a nerfed 4.5-tile corridor."""
        eng = _make_engine()
        s = build_spec(eng.db, "barbarian_barrel_hero", LVL)
        self.assertAlmostEqual(4.5, s.roll_len, places=3)
        self.assertAlmostEqual(3.0, s.spawn_spec.ability_range_tiles, places=3)
        self.assertLess(s.spawn_spec.ability_range_tiles, s.roll_len)

    def test_the_second_roll_sweeps_at_the_SAME_speed_as_the_first(self):
        """RULING 24: "all the roll mechanics carry over". The Barbarian is a TROOP, so his own
        `rolls` is False -- without the explicit carry the reroll would land in the no-speed branch
        and resolve instantly, i.e. ruling 21 undone on the one card that rolls twice."""
        eng = _quiet(_make_engine())
        sp, b = self._hero_body(eng)
        self.assertAlmostEqual(sp.roll_speed, b.spec.roll_speed, places=6)
        b.spec = replace(b.spec, speed=0.0)
        eng.elixir[1] = 10.0
        self.assertTrue(eng.champion_ability(1))
        for _ in range(40):                                   # past the 1.0 s activation delay
            eng.advance(DT)
            if eng.rolls:
                break
        self.assertTrue(eng.rolls, "the ability launched a real _Roll")
        r = eng.rolls[-1]
        self.assertAlmostEqual(sp.roll_speed, r.spec.roll_speed, places=6)
        self.assertAlmostEqual(3.0, r.spec.roll_len, places=3)
        dur = _sweep(eng)
        print("\n[R24] Rowdy Reroll: 3.0 tiles at %.4f tiles/s swept in %.2f s"
              % (r.spec.roll_speed, dur))
        self.assertAlmostEqual(3.0 / sp.roll_speed, dur, delta=DT + 1e-6)

    def test_the_roll_starts_at_the_BARBARIANS_CURRENT_POSITION_not_the_first_rolls_end(self):
        """RULING 26, and the reason it matters: the Barbarian lands at the first corridor's end
        and then WALKS, so a stored end-of-first-roll coordinate falls further behind the longer
        the player waits. The assertion message carries the tile gap so a regression is readable."""
        eng = _quiet(_make_engine())
        sp, b = self._hero_body(eng)
        end_of_first = b.y
        for _ in range(60):                                   # let him march for 3 s
            eng.advance(DT)
        walked = (b.y - end_of_first) * _TILES_Y
        self.assertGreater(walked, 1.0, "he has to have moved for this test to mean anything")
        b.spec = replace(b.spec, speed=0.0)     # pin him, so "where he is" has one answer across
        here = b.y                              # the 1.0 s activation delay
        eng.elixir[1] = 10.0
        self.assertTrue(eng.champion_ability(1))
        for _ in range(40):
            eng.advance(DT)
            if eng.rolls:
                break
        r = eng.rolls[-1]
        print("[R26] second roll origin ny=%.4f; the Barbarian is at ny=%.4f, the first roll ended "
              "at ny=%.4f -- %.2f tiles apart" % (r.y, here, end_of_first, walked))
        self.assertAlmostEqual(here, r.y, places=4,
                               msg="the reroll must start where the BARBARIAN is, not where the "
                                   "first roll ended (%.2f tiles behind him)" % walked)

    def test_the_barbarian_is_ABSORBED_and_redeployed_at_the_corridors_end(self):
        """RULING 28: "The first barbarian disappears into the second roll when the ability casts,
        and redeploys at the endpoint of the second roll." Never two, never zero at the end -- and
        the SAME Unit, so `deploy_seq` and the accumulated damage ride along."""
        eng = _quiet(_make_engine())
        sp, b = self._hero_body(eng)
        b.spec = replace(b.spec, speed=0.0)
        b.hp = b.spec.hp * 0.5
        hp_before, seq, y0 = b.hp, b.deploy_seq, b.y
        eng.elixir[1] = 10.0
        self.assertTrue(eng.champion_ability(1))
        for _ in range(40):
            eng.advance(DT)
            if eng.rolls:
                break
        self.assertEqual([], [u for u in eng.units if u.spec.key == "barrel_barbarian"],
                         "absorbed: NO Barbarian on the board while the barrel rolls")
        self.assertGreater(b.hp, 0.0, "absorbed, not killed -- no death effect may fire")
        _sweep(eng)
        back = [u for u in eng.units if u.spec.key == "barrel_barbarian"]
        self.assertEqual(1, len(back), "exactly one, never two (there is no second Barbarian)")
        self.assertIs(b, back[0], "the SAME body")
        self.assertEqual(seq, back[0].deploy_seq, "identity preserved across the absorb")
        moved = (back[0].y - y0) * _TILES_Y
        print("[R28] absorbed at ny=%.4f, redeployed at ny=%.4f (%.2f tiles up), hp %.0f -> %.0f"
              % (y0, back[0].y, moved, hp_before, back[0].hp))
        self.assertAlmostEqual(3.0, moved, delta=0.3)

    def test_it_emerges_healed_by_half_the_damage_it_had_TAKEN(self):
        """RULING 27, and the reading is stated because the prose is loose. "healling the barbarian
        for 50% of the damage" + Strategy "while healing some hp" + the table's "Damage Healed 50%"
        are read as half the damage he HAS TAKEN -- half his missing hitpoints. The competing
        lifesteal reading (50% of what the reroll deals) pays NOTHING when the corridor is empty,
        which is precisely when a player presses this to save a dying Barbarian; it is recorded in
        conflicts.md as an owner in-game check."""
        eng = _quiet(_make_engine())
        sp, b = self._hero_body(eng)
        b.spec = replace(b.spec, speed=0.0)
        full = b.spec.hp
        b.hp = full * 0.25                                    # 75% of his hp is missing
        hp0 = b.hp
        eng.elixir[1] = 10.0
        self.assertTrue(eng.champion_ability(1))
        for _ in range(40):
            eng.advance(DT)
            if eng.rolls:
                break
        _sweep(eng)
        print("[R27] a Barbarian at %.0f / %.0f hp rerolls and comes back at %.0f "
              "(half the %.0f it was missing)" % (hp0, full, b.hp, full - hp0))
        self.assertAlmostEqual(hp0 + (full - hp0) * 0.5, b.hp, places=1)

    def test_a_full_health_barbarian_gains_nothing_and_never_overheals(self):
        eng = _quiet(_make_engine())
        sp, b = self._hero_body(eng)
        b.spec = replace(b.spec, speed=0.0)
        b.hp = b.spec.hp
        eng.elixir[1] = 10.0
        self.assertTrue(eng.champion_ability(1))
        for _ in range(40):
            eng.advance(DT)
            if eng.rolls:
                break
        _sweep(eng)
        self.assertAlmostEqual(b.spec.hp, b.hp, places=3)

    def test_the_second_roll_damages_what_it_rolls_over_and_stops_at_3_tiles(self):
        eng = _quiet(_make_engine())
        sp, b = self._hero_body(eng)
        b.spec = replace(b.spec, speed=0.0)
        near = _still(eng, 0, b.x, b.y + 2.0 / _TILES_Y)
        past = _still(eng, 0, b.x, b.y + 5.0 / _TILES_Y)
        eng.elixir[1] = 10.0
        self.assertTrue(eng.champion_ability(1))
        for _ in range(60):
            eng.advance(DT)
            if eng.rolls:
                break
        _sweep(eng)
        self.assertAlmostEqual(232.0, 1e6 - near.hp, places=1, msg="spawn_11, both rolls")
        self.assertAlmostEqual(0.0, 1e6 - past.hp, places=3, msg="5 tiles is past a 3-tile roll")

    def test_the_ability_is_REFUSED_and_the_elixir_kept_when_no_barbarian_is_alive(self):
        """RULING 26 q1 / ruling 27: if he dies before the ability goes off the elixir comes back.
        Two halves, and both are the EXISTING machinery rather than a second path -- there is no
        body to select, so `champion_ability` refuses and never charges; and a body that dies
        DURING the 1.0 s activation delay hits ruling 7's refund in `_tick_ability_pending`."""
        eng = _quiet(_make_engine())
        sp, b = self._hero_body(eng)
        b.hp = 0.0
        eng.advance(DT)                         # ...and elixir regenerates on every tick, so the
        eng.elixir[1] = 5.0                     # snapshot has to be taken AFTER the advance
        self.assertFalse(eng.champion_ability(1), "no body, no activation")
        self.assertAlmostEqual(5.0, eng.elixir[1], places=6, msg="and nothing was charged")

    def test_a_barbarian_killed_DURING_the_activation_delay_refunds_the_elixir(self):
        eng = _quiet(_make_engine())
        sp, b = self._hero_body(eng)
        cost = b.spec.ability_cost
        self.assertGreater(cost, 0.0)
        eng.elixir[1] = 5.0
        self.assertTrue(eng.champion_ability(1))
        self.assertAlmostEqual(5.0 - cost, eng.elixir[1], places=6, msg="charged up front")
        spent = float(eng.elixir[1])
        b.hp = 0.0                                            # killed mid-cast
        eng.advance(DT)
        # ...plus ONE tick of ordinary elixir regeneration, which is why this is a delta.
        self.assertAlmostEqual(spent + cost, eng.elixir[1], delta=0.05,
                               msg="ruling 7's refund pays it back")
        self.assertEqual([], eng.rolls, "and no roll was launched")

    def test_the_second_roll_is_NOT_re_clamped_to_our_own_half(self):
        """RULING 24: the own-half rule is about a CAST, and this is not one. The Barbarian is very
        often standing in the ENEMY half by the time the button is pressed, and the roll has to
        launch from where he is -- the same way a legally cast Log's corridor crosses the river."""
        eng = _quiet(_make_engine())
        sp, b = self._hero_body(eng)
        b.spec = replace(b.spec, speed=0.0)
        b.y = 0.20                                            # deep in the ENEMY half (team 1 owns
        b.x = 0.5                                             # the low-y side, so this is ours)
        eng.elixir[1] = 10.0
        self.assertTrue(eng.champion_ability(1))
        for _ in range(40):
            eng.advance(DT)
            if eng.rolls:
                break
        self.assertTrue(eng.rolls, "the roll launched from an enemy-half origin")
        self.assertAlmostEqual(0.20, eng.rolls[-1].y, places=4)


class SpellVerdictTimingTests(unittest.TestCase):
    """The sim bills `spell_waste` for a cast that damaged nothing, at a fixed delay after landing.
    A 2.88 s roll outlives the old 0.35 s settle, so a good Log would have been billed for damage
    it had not dealt YET -- the same bug §5 records for LIVE spells."""

    def test_the_pending_check_is_scheduled_AFTER_the_roll_finishes(self):
        from clashrl.config import Config
        from clashrl.sim.env import SimMatchEnv
        env = SimMatchEnv(Config.load(), seed=7)
        env.reset()
        spec = build_spec(env.eng.db, "the_log", LVL)
        env._pending_spell_checks = []
        t0 = float(env.eng.t)
        env._arm_spell_check(0.5, 0.75, spec)
        self.assertEqual(1, len(env._pending_spell_checks))
        due = float(env._pending_spell_checks[0]["t"]) - t0
        sweep = spec.roll_len / spec.roll_speed
        print("\n[R21] spell verdict for a Log: due %.2f s after the cast; the roll takes %.2f s "
              "(was due at %.2f s, i.e. with the edge %.2f of 9.6 tiles along)"
              % (due, sweep, spec.spell_delay + 0.35,
                 max(0.0, (spec.spell_delay + 0.35 - spec.spell_delay)) * spec.roll_speed))
        self.assertGreater(due, sweep, "the verdict must not be taken mid-roll")
        self.assertAlmostEqual(spec.spell_delay + sweep + 0.35, due, places=3)

    def test_a_blast_spells_verdict_timing_is_UNCHANGED(self):
        from clashrl.config import Config
        from clashrl.sim.env import SimMatchEnv
        env = SimMatchEnv(Config.load(), seed=7)
        env.reset()
        env._pending_spell_checks = []
        spec = build_spec(env.eng.db, "fireball", LVL)
        t0 = float(env.eng.t)
        env._arm_spell_check(0.5, 0.4, spec)
        due = float(env._pending_spell_checks[0]["t"]) - t0
        self.assertAlmostEqual(spec.spell_delay + 0.35, due, places=3)


class SimViewTests(unittest.TestCase):
    """A PIXEL test, in the I9 idiom: a mechanic the debugger cannot show is a mechanic whose
    evidence is missing. A roll used to exist only as a pending `_Spell`, so for the 2.88 s it is
    actually working the frame showed nothing at all."""

    def test_a_roll_in_motion_is_DRAWN(self):
        try:
            import numpy as np
            from clashrl.sim_view import render_frame
        except Exception as exc:                               # noqa: BLE001
            self.skipTest("sim_view unavailable: %s" % exc)
        eng = _quiet(_make_engine())
        eng.spells.clear()
        blank = render_frame(eng, width=460).astype(np.int32)
        _cast_roll(eng, "the_log", 0.5, 0.75)
        for _ in range(10):                                    # 0.5 s in: mid-sweep
            eng.advance(DT)
        self.assertTrue(eng.rolls, "still rolling")
        drawn = render_frame(eng, width=460).astype(np.int32)
        self.assertGreater(int(np.abs(drawn - blank).sum()), 0,
                           "the roll's current position must appear in the frame")

    def test_the_drawn_edge_MOVES_as_the_roll_advances(self):
        try:
            import numpy as np
            from clashrl.sim_view import render_frame
        except Exception as exc:                               # noqa: BLE001
            self.skipTest("sim_view unavailable: %s" % exc)
        eng = _quiet(_make_engine())
        eng.spells.clear()
        _cast_roll(eng, "the_log", 0.5, 0.75)
        for _ in range(6):
            eng.advance(DT)
        early = render_frame(eng, width=460).astype(np.int32)
        d0 = eng.rolls[0].dist
        for _ in range(24):
            eng.advance(DT)
        self.assertTrue(eng.rolls)
        self.assertGreater(eng.rolls[0].dist, d0 + 1.0)
        late = render_frame(eng, width=460).astype(np.int32)
        self.assertGreater(int(np.abs(late - early).sum()), 0)


if __name__ == "__main__":                                   # pragma: no cover
    unittest.main()
