"""Evolution cycling, and where Evo Firecracker's damage-over-time actually lands.

Two user-reported bugs, both of which produced plausible-looking play:

EVOLUTIONS DID NOT CYCLE. `CardDB.evo_cycles` returns 0 to mean "this card has no evolution", but
the sim's slot asks `evo_charge >= cycles` -- and 0 satisfies that from the first tick, so a slot
marked evolved whose cycle count was missing presented the EVOLUTION every single lap and the base
card could never be played. Firecracker hit this because its base row comes from the importer and
carries no `evolution` block, which the old lookup required before it would read the evo row's
`evo_cycles`. Evo Firecracker every cycle, on a 2-cycle evolution.

SPARKS COVERED A LANE. The lingering spark zones were dropped every 1.25 tiles along the flight
path -- for the carrier AND all five shrapnel bolts, which fly up to 11 tiles. The card's DoT is
supposed to sit in exactly two places: one large circle where the primary projectile lands, and one
small circle at the very end of each bolt's run.

SHARED, byte-identical in both decks (I1, 2026-08-26). Every assertion here is about the ENGINE or
the KB, not about a deck: the Firecracker rows are card facts both knowledge bases carry, and the
cycling tests read whichever slot the loaded deck marks evolved (Evo Firecracker in hogeq, Evo
Tesla / Evo Knight in icebow) rather than naming one. An opponent can field any of them, so an
engine that cycled evolutions differently per deck would be exactly the drift this pass removes.
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


class EvoCycleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cfg = Config.load()
        cls.env = SimMatchEnv(cls.cfg)

    def test_the_deck_has_no_zero_cycle_evolutions(self):
        for s in CardDB(self.cfg).deck_slots():
            if s["evo"]:
                self.assertGreater(s["cycles"], 0,
                                   "%s would be permanently evolved" % s["base"])

    def test_firecracker_is_a_two_cycle_evolution(self):
        self.assertEqual(2, CardDB(self.cfg).evo_cycles("firecracker"))

    def test_evo_cycles_reads_the_evo_row_without_a_base_evolution_block(self):
        """Firecracker's base row is imported and has no `evolution` key; the cycle count lives on
        the `_evo` row. Requiring the base block is what silently produced 0."""
        db = CardDB(self.cfg)
        self.assertNotIn("evolution", db.get("firecracker") or {})
        self.assertEqual(2, db.evo_cycles("firecracker"))

    def test_a_card_with_no_evolution_still_reports_zero(self):
        """Reading the `_evo` row directly cannot invent an evolution: a card that has none has no
        such row. (Ice Spirit and Skeletons are NOT examples -- both really do have Evolutions, and
        report 2 here; they are simply not slotted as evolved in this deck.)"""
        db = CardDB(self.cfg)
        for k in ("hog_rider", "the_log", "earthquake", "mighty_miner"):
            self.assertIsNone(db.get(k + "_evo"), "%s unexpectedly has an evo row" % k)
            self.assertEqual(0, db.evo_cycles(k), k)

    def test_an_evolved_slot_with_no_cycle_count_is_refused(self):
        """A missing number must not quietly become an infinitely-charged Evolution."""
        db = CardDB(self.cfg)
        db._deck = {"cards": [{"card": "hog_rider", "evolved": True, "level": 13}]}   # has no evo
        with self.assertRaises(ValueError):
            db.deck_slots()

    def _evolved_slot(self, env):
        """A slot this deck marks evolved, and its cycle count. Read from the deck rather than
        named, so the same test covers Evo Firecracker (hogeq) and Evo Tesla / Evo Knight
        (icebow) -- the mechanic under test is the slot's, not any one card's."""
        slot = next((s for s in range(env.n_slots) if env.slot_evo_id[s] >= 0), None)
        if slot is None:
            self.skipTest("this deck slots no evolution")
        return slot, int(env.slot_cycles[slot])

    def test_the_base_card_is_played_n_times_before_the_evolution(self):
        env = self.env
        env.reset()
        slot, cycles = self._evolved_slot(env)
        base = env.deck_keys[env.slot_base_id[slot]]
        evo = env.deck_keys[env.slot_evo_id[slot]]
        seen = []
        for _ in range(cycles + 1):
            seen.append(env.deck_keys[env._slot_card_id(slot)])
            env._play_slot(env._slot_card_id(slot))
        self.assertEqual([base] * cycles + [evo], seen)

    def test_playing_the_evolution_discharges_it(self):
        env = self.env
        env.reset()
        slot, cycles = self._evolved_slot(env)
        for _ in range(cycles + 1):                         # base x cycles, then the evo
            env._play_slot(env._slot_card_id(slot))
        self.assertEqual(env.deck_keys[env.slot_base_id[slot]],
                         env.deck_keys[env._slot_card_id(slot)])

    def test_a_played_card_leaves_the_hand_and_must_cycle_back(self):
        """Cards have an ORDER: the same slot cannot be played twice in a row."""
        env = self.env
        env.reset()
        played = []
        for _ in range(200):
            hand = env._hand_ids()
            _ab = getattr(env, "ability_id", -1)      # icebow has no champion -> no such slot
            pick = next((c for c in hand
                         if c != _ab and env.eng.elixir[0] >= env.specs[c].elixir), None)
            if pick is None:
                env.step((0, -1, 0))
                continue
            before = list(env.cycle)
            env.step((1, pick, 200))
            if list(env.cycle) != before:
                played.append(env.slot_of[pick])
            if env.eng.done:
                break
        self.assertGreater(len(played), 10, "the drive loop played almost nothing")
        dups = [i for i in range(1, len(played)) if played[i] == played[i - 1]]
        self.assertEqual([], dups, "the same slot was played twice in a row")

    def test_a_slot_needs_the_full_lap_to_return(self):
        """Eight slots, four in hand -- a played card cannot reappear until the others have gone."""
        env = self.env
        env.reset()
        first = env.cycle[0]
        env._play_slot(env._slot_card_id(first))
        self.assertEqual(env.n_slots - 1, env.cycle.index(first))
        self.assertNotIn(first, env.cycle[:4])


class SparkGeometryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.env = SimMatchEnv(Config.load())

    def _one_volley(self):
        env = self.env
        env.reset()
        eng = env.eng
        eng.units.clear(); eng.spells.clear()
        eng.projectiles.clear(); eng.spark_zones.clear()
        fc = build_spec(env.db, "firecracker_evo", 13)
        kn = build_spec(env.db, "knight", 11)
        eng.units.append(Unit(spec=fc, team=0, x=0.50, y=0.62, hp=fc.hp))
        eng.units.append(Unit(spec=kn, team=1, x=0.50, y=0.47, hp=kn.hp))
        peak, snap = 0, []
        for _ in range(120):
            eng.advance(0.1)
            if len(eng.spark_zones) > peak:
                peak = len(eng.spark_zones)
                snap = [list(z) for z in eng.spark_zones]
        return peak, snap

    def test_one_volley_leaves_exactly_six_zones(self):
        """One large circle on the impact point, plus one small circle per shrapnel bolt."""
        peak, _ = self._one_volley()
        self.assertEqual(6, peak)

    def test_exactly_one_of_them_is_the_large_zone(self):
        _, snap = self._one_volley()
        ticks = sorted({round(z[5], 1) for z in snap})
        self.assertEqual(2, len(ticks), "expected exactly two zone strengths, got %s" % ticks)
        big = [z for z in snap if round(z[5], 1) == ticks[-1]]
        self.assertEqual(1, len(big))
        self.assertEqual(5, len(snap) - len(big))

    def test_the_large_zone_sits_on_the_impact_point(self):
        _, snap = self._one_volley()
        big = max(snap, key=lambda z: z[5])
        self.assertAlmostEqual(big[0], 0.50, places=2)
        self.assertAlmostEqual(big[1], 0.47, places=2, msg="not on the target it hit")

    def test_the_small_zones_are_beyond_the_impact_not_behind_it(self):
        """They mark the END of each bolt's flight, so they sit past the target, away from us."""
        _, snap = self._one_volley()
        big = max(snap, key=lambda z: z[5])
        small = [z for z in snap if z is not big]
        for z in small:
            self.assertLess(z[1], big[1], "a spark zone landed behind the impact point")

    def test_no_zones_are_dropped_along_the_flight_path(self):
        """The old model trailed one every 1.25 tiles, carpeting the lane between us and them."""
        _, snap = self._one_volley()
        for z in snap:
            self.assertLess(z[1], 0.55,
                            "a zone was dropped mid-flight between the Firecracker and her target")


class RecoilTests(unittest.TestCase):
    """"After attacking, she will recoil backwards 1 tile" (wiki).

    The widely-quoted 1.5 is stale -- the 7/7/2020 balance update "decreased her recoil range to 1
    tile (from 1.5)". It matters in both directions: the recoil walks her away from the melee troop
    she is shooting, and it is also why "her repeated recoil may cause her to switch to the other
    lane", which is the reason she is placed behind the engagement rather than beside it.
    """

    @classmethod
    def setUpClass(cls):
        cls.env = SimMatchEnv(Config.load())
        cls.env.reset()

    def _pair(self, fx=0.50, fy=0.62, tx=0.50, ty=0.47):
        env = self.env
        fc = build_spec(env.db, "firecracker_evo", 13)
        kn = build_spec(env.db, "knight", 11)
        return (Unit(spec=fc, team=0, x=fx, y=fy, hp=fc.hp),
                Unit(spec=kn, team=1, x=tx, y=ty, hp=kn.hp))

    def _tiles(self, ax, ay, bx, by):
        from clashrl.sim.engine import _TILES_X, _TILES_Y
        import math
        return math.hypot((ax - bx) * _TILES_X, (ay - by) * _TILES_Y)

    def test_the_published_distance_is_one_tile(self):
        self.assertEqual(1.0, build_spec(self.env.db, "firecracker", 13).recoil)

    def test_the_evolution_recoils_the_same(self):
        self.assertEqual(1.0, build_spec(self.env.db, "firecracker_evo", 13).recoil)

    def test_she_moves_exactly_one_tile(self):
        f, t = self._pair()
        x0, y0 = f.x, f.y
        self.env.eng._recoil(f, t)
        self.assertAlmostEqual(self._tiles(x0, y0, f.x, f.y), 1.0, places=3)

    def test_she_moves_AWAY_from_what_she_shot(self):
        f, t = self._pair()
        before = self._tiles(f.x, f.y, t.x, t.y)
        self.env.eng._recoil(f, t)
        self.assertAlmostEqual(self._tiles(f.x, f.y, t.x, t.y), before + 1.0, places=3)

    def test_the_recoil_is_along_the_firing_line_not_just_backwards(self):
        """Shooting diagonally must push her diagonally, or she would drift out of her own lane."""
        import math
        from clashrl.sim.engine import _TILES_X, _TILES_Y
        f, t = self._pair(fx=0.40, fy=0.62, tx=0.55, ty=0.50)
        x0, y0 = f.x, f.y
        self.env.eng._recoil(f, t)
        a0 = math.atan2((y0 - t.y) * _TILES_Y, (x0 - t.x) * _TILES_X)
        a1 = math.atan2((f.y - t.y) * _TILES_Y, (f.x - t.x) * _TILES_X)
        self.assertAlmostEqual(a0, a1, places=6)
        self.assertNotAlmostEqual(f.x, x0, places=4, msg="a diagonal shot moved her straight back")

    def test_cards_that_do_not_recoil_do_not_move(self):
        env = self.env
        _, t = self._pair()
        for k in ("archers", "musketeer"):
            sp = build_spec(env.db, k, 11)
            u = Unit(spec=sp, team=0, x=0.50, y=0.62, hp=sp.hp)
            env.eng._recoil(u, t)
            self.assertEqual((0.50, 0.62), (u.x, u.y), k)

    def test_recoil_does_not_disarm_a_charge_the_way_a_real_shove_does(self):
        """It is self-inflicted, so it must not route through the knockback path -- nothing hit her."""
        f, t = self._pair()
        f.charge_dist, f.ramp_shots = 3.0, 2
        self.env.eng._recoil(f, t)
        self.assertEqual(3.0, f.charge_dist)
        self.assertEqual(2, f.ramp_shots)

    def test_she_recoils_when_she_actually_fires(self):
        env = self.env
        env.reset()
        eng = env.eng
        eng.units.clear(); eng.projectiles.clear(); eng.spark_zones.clear()
        f, t = self._pair()
        eng.units += [f, t]
        y0 = f.y
        moved_back = False
        prev = f.y
        for _ in range(60):
            eng.advance(0.1)
            if f.y - prev > 1e-6:
                moved_back = True
                break
            prev = f.y
        self.assertTrue(moved_back, "she never recoiled across a full attack cycle")
        self.assertGreater(f.y, y0, "team 0 recoils toward its own side (+y)")


if __name__ == "__main__":
    unittest.main()
