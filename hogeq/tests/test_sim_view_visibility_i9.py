"""I9 -- the debugger has to SHOW what the engine does. BYTE-IDENTICAL in icebow and hogeq.

WHY. The owner's "the electro dragon chain doesn't work" report was partly a DRAWING bug. MEASURED:
an Electro Dragon chaining into six Barbarians for 12 s produced **zero frames** in which a
`<base>_chain` projectile was alive -- a hop is created and consumed inside one `advance(dt)` call
and never survives a frame boundary -- while the damage ledger showed 192 / 960 / 1152 / 576 / 576
across the row. The mechanic worked and the picture showed nothing, so the picture was the evidence
and the evidence was wrong.

The engine now records `arc_events` and `ability_events` in the same idiom as `splash_events`
(which already carries "-- sim_view" in its own comment), and `sim_view.render_frame` draws them,
along with the lingering zones and the ability state that had no marker at all.

Every test here is a PIXEL test: render, then assert the frame changed. A drawing test that only
checks a list is not a drawing test.
"""
from __future__ import annotations

import random
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for _p in (str(ROOT / "src"), str(ROOT / "tests")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import numpy as np                                                   # noqa: E402

from test_sim_status_effects import _make_engine                     # noqa: E402
from clashrl.sim.engine import Unit, _Spell, _Zone, build_spec       # noqa: E402
from clashrl.sim_view import render_frame                            # noqa: E402

LVL = 11


def _pixels(eng):
    return render_frame(eng, width=460).astype(np.int32)


def _changed(a, b):
    """How many pixels differ between two rendered frames."""
    return int((np.abs(a - b).sum(axis=2) > 0).sum())


class ChainArcTests(unittest.TestCase):
    def _chaining_engine(self):
        """A real Electro Dragon over a row of Barbarians -- the exact board from the report."""
        eng = _make_engine()
        for side in (eng.towers[0], eng.towers[1]):
            for tw in side:
                tw.hit_dmg = 0.0
                tw.max_hp = tw.hp = 1e9
        ed = Unit(spec=build_spec(eng.db, "electro_dragon", LVL), team=0, x=0.5, y=0.60, hp=5000.0)
        ed.deploy_left = 0.0
        eng.units.append(ed)
        for i in range(6):
            u = Unit(spec=build_spec(eng.db, "barbarians", LVL), team=1,
                     x=0.46 + i * 0.012, y=0.50, hp=5000.0)
            u.deploy_left = 0.0
            eng.units.append(u)
        return eng, ed

    def test_a_chain_hop_never_survives_a_physics_frame(self):
        """The measurement this whole item rests on. If this ever stops being true the arc record
        is redundant -- but it has been true for the entire life of the debugger."""
        eng, _ed = self._chaining_engine()
        alive = 0
        for _ in range(120):
            eng.advance(0.1)
            if [p for p in eng.projectiles if "_chain" in p.label]:
                alive += 1
        self.assertEqual(alive, 0,
                         "a chain projectile is created and consumed inside one advance()")
        self.assertGreater(len(eng.arc_events), 0,
                           "...so the ARC RECORD is the only thing a frame can draw")

    def test_the_chain_is_visible_in_a_rendered_frame(self):
        eng, _ed = self._chaining_engine()
        for _ in range(120):
            eng.advance(0.1)
            if eng.arc_events and eng.t - eng.arc_events[-1][5] < 0.05:
                break
        self.assertTrue(eng.arc_events, "the dragon must have chained")
        with_arcs = _pixels(eng)
        kept, eng.arc_events = eng.arc_events, []
        without = _pixels(eng)
        eng.arc_events = kept
        self.assertGreater(_changed(with_arcs, without), 20,
                           "the chain arcs must actually put pixels on the frame")

    def test_a_late_bounce_is_drawn_apart_from_a_full_hop(self):
        """Ruling 12: the first `chain_full_hits` bodies take the full hit AND the stun; later
        bounces take a reduced hit with no stun. Two damage classes, two colours."""
        eng, _ed = self._chaining_engine()
        eng.arc_events = [(0.40, 0.55, 0.60, 0.55, 0, eng.t, "chain")]
        full = _pixels(eng)
        eng.arc_events = [(0.40, 0.55, 0.60, 0.55, 0, eng.t, "chain_late")]
        late = _pixels(eng)
        self.assertGreater(_changed(full, late), 0,
                           "a full hop and a late bounce must not render identically")

    def test_an_arc_fades(self):
        eng, _ed = self._chaining_engine()
        eng.arc_events = [(0.40, 0.55, 0.60, 0.55, 0, eng.t, "chain")]
        now = _pixels(eng)
        eng.t += 5.0
        later = _pixels(eng)
        blank = None
        eng.arc_events = []
        blank = _pixels(eng)
        self.assertGreater(_changed(now, blank), 20)
        self.assertEqual(_changed(later, blank), 0, "a stale arc must not linger on screen")


class AbilityVisibilityTests(unittest.TestCase):
    def _engine(self):
        eng = _make_engine()
        for side in (eng.towers[0], eng.towers[1]):
            for tw in side:
                tw.hit_dmg = 0.0
                tw.max_hp = tw.hp = 1e9
        return eng

    def test_an_activation_flashes_at_the_press_point(self):
        eng = self._engine()
        base = _pixels(eng)
        eng.ability_events = [(0.5, 0.4, 1, eng.t, "bomb", "mighty_miner")]
        self.assertGreater(_changed(_pixels(eng), base), 20)

    def test_a_cast_still_in_its_activation_delay_is_drawn(self):
        """Ruling 7's refund window. Drawing it is what makes "he died mid-cast" legible."""
        eng = self._engine()
        u = Unit(spec=build_spec(eng.db, "knight", LVL), team=1, x=0.5, y=0.4, hp=1400.0)
        eng.units.append(u)
        base = _pixels(eng)
        eng._ability_pending = [[1, u, 1.0, 0.6, "taunt_shield"]]
        self.assertGreater(_changed(_pixels(eng), base), 20)

    def test_a_running_ability_marks_its_body(self):
        eng = self._engine()
        u = Unit(spec=build_spec(eng.db, "knight", LVL), team=1, x=0.5, y=0.4, hp=1400.0)
        eng.units.append(u)
        base = _pixels(eng)
        u.ability_active_s = 3.2
        self.assertGreater(_changed(_pixels(eng), base), 20,
                           "an ability that is RUNNING must be visible on the body")

    def test_stealth_flight_souls_and_dash_each_show(self):
        for field, value in (("invis_left", 2.0), ("flying_left", 2.0),
                             ("souls", 7), ("dash_left", 4)):
            with self.subTest(state=field):
                eng = self._engine()
                u = Unit(spec=build_spec(eng.db, "knight", LVL), team=1, x=0.5, y=0.4, hp=1400.0)
                eng.units.append(u)
                base = _pixels(eng)
                setattr(u, field, value)
                self.assertGreater(_changed(_pixels(eng), base), 5)

    def test_the_bodiless_state_is_drawn_too(self):
        """The Hero Goblins' banner and Goblinstein's antenna are engine state with no body to
        hang a marker on -- so without an explicit draw they are invisible by construction."""
        eng = self._engine()
        base = _pixels(eng)
        eng._banner = {1: [eng.t + 5.0, 0.5, 0.35, build_spec(eng.db, "goblins", LVL)]}
        self.assertGreater(_changed(_pixels(eng), base), 10, "the banner must show")
        eng._banner = {}
        eng._antenna = {1: (0.42, 0.33)}
        self.assertGreater(_changed(_pixels(eng), base), 5, "the antenna must show")

    def test_a_clone_is_marked_apart_from_its_original(self):
        eng = self._engine()
        u = Unit(spec=build_spec(eng.db, "knight", LVL), team=1, x=0.5, y=0.4, hp=1400.0)
        eng.units.append(u)
        base = _pixels(eng)
        u.cloned = True
        self.assertGreater(_changed(_pixels(eng), base), 0,
                           "a 1-hp clone worth no elixir must not read as the real body")


class ZoneVisibilityTests(unittest.TestCase):
    """Lingering zones were not drawn AT ALL -- a Poison was an 8-second area doing damage that
    nothing on screen accounted for, and after I9 a Heal Spirit's field is the same in reverse."""

    def _engine(self):
        eng = _make_engine()
        for side in (eng.towers[0], eng.towers[1]):
            for tw in side:
                tw.hit_dmg = 0.0
                tw.max_hp = tw.hp = 1e9
        return eng

    def test_a_damage_zone_is_drawn(self):
        eng = self._engine()
        base = _pixels(eng)
        sp = build_spec(eng.db, "poison", LVL)
        self.assertGreater(sp.zone_s, 0.0, "poison is a lingering zone")
        eng._resolve_spell(_Spell(0, 0.5, 0.4, sp, 0.0))
        self.assertTrue(eng.zones)
        self.assertGreater(_changed(_pixels(eng), base), 20)

    def test_a_heal_field_is_drawn_in_its_own_colour(self):
        eng = self._engine()
        sp = build_spec(eng.db, "poison", LVL)
        eng.zones = [_Zone(0, 0.5, 0.4, sp, 4.0)]
        dmg = _pixels(eng)
        hs = build_spec(eng.db, "heal_spirit", LVL)
        from clashrl.sim.engine import replace
        fs = replace(hs, spell_radius=sp.spell_radius, zone_tick_s=hs.heal_tick_s,
                     zone_first_tick_now=True, spell_dmg=0.0, spell_tower_dmg=0.0)
        eng.zones = [_Zone(0, 0.5, 0.4, fs, 4.0)]
        heal = _pixels(eng)
        self.assertGreater(_changed(dmg, heal), 0,
                           "a field that HEALS must not look like one that hurts")


class RageZoneVisibilityTests(unittest.TestCase):
    """The Rage SPELL (I9) feeds the same `rage_zones` list the Lumberjack's bottle does, and it
    publishes a 0.5 s deploy timer of its own. A debugger that shows nothing for that half-second
    is the same "it did not work" trap the chain arcs closed."""

    def _engine(self):
        eng = _make_engine()
        for side in (eng.towers[0], eng.towers[1]):
            for tw in side:
                tw.hit_dmg = 0.0
                tw.max_hp = tw.hp = 1e9
        return eng

    def test_the_zone_shows_while_it_is_still_arming(self):
        eng = self._engine()
        base = _pixels(eng)
        eng._resolve_spell(_Spell(0, 0.5, 0.7, build_spec(eng.db, "rage", LVL), 0.0))
        self.assertTrue(eng.rage_zones)
        self.assertGreater(eng.rage_zones[0][4], eng.t, "the 0.5 s deploy timer has not run yet")
        arming = _pixels(eng)
        self.assertGreater(_changed(arming, base), 20, "an arming rage zone must be visible")

    def test_an_armed_zone_looks_different_from_an_arming_one(self):
        eng = self._engine()
        eng._resolve_spell(_Spell(0, 0.5, 0.7, build_spec(eng.db, "rage", LVL), 0.0))
        arming = _pixels(eng)
        eng.t += 1.0                                   # past the deploy timer, inside the 4.5 s
        armed = _pixels(eng)
        self.assertGreater(_changed(arming, armed), 0)

    def test_an_expired_zone_is_gone(self):
        eng = self._engine()
        eng._resolve_spell(_Spell(0, 0.5, 0.7, build_spec(eng.db, "rage", LVL), 0.0))
        eng.t += 99.0
        expired = _pixels(eng)
        # The baseline has to be rendered at the SAME engine time: the HUD prints the clock and
        # the elixir phase, so a frame taken 99 s earlier differs for reasons that are not the
        # zone. (Measured the hard way -- the first version of this test read 1267 changed pixels
        # from the clock alone.)
        kept, eng.rage_zones = eng.rage_zones, []
        blank = _pixels(eng)
        eng.rage_zones = kept
        self.assertEqual(_changed(expired, blank), 0, "an expired zone must not linger")


if __name__ == "__main__":
    unittest.main()
