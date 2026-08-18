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
        db._deck = {"cards": [{"card": "hog_rider", "evolved": True, "level": 13}]}
        with self.assertRaises(ValueError):
            db.deck_slots()

    def test_the_base_card_is_played_twice_before_the_evolution(self):
        env = self.env
        env.reset()
        slot = next(s for s in range(env.n_slots)
                    if env.deck_keys[env.slot_base_id[s]] == "firecracker")
        seen = []
        for _ in range(3):
            seen.append(env.deck_keys[env._slot_card_id(slot)])
            env._play_slot(env._slot_card_id(slot))
        self.assertEqual(["firecracker", "firecracker", "firecracker_evo"], seen)

    def test_playing_the_evolution_discharges_it(self):
        env = self.env
        env.reset()
        slot = next(s for s in range(env.n_slots)
                    if env.deck_keys[env.slot_base_id[s]] == "firecracker")
        for _ in range(3):                                  # base, base, evo
            env._play_slot(env._slot_card_id(slot))
        self.assertEqual("firecracker", env.deck_keys[env._slot_card_id(slot)])

    def test_a_played_card_leaves_the_hand_and_must_cycle_back(self):
        """Cards have an ORDER: the same slot cannot be played twice in a row."""
        env = self.env
        env.reset()
        played = []
        for _ in range(200):
            hand = env._hand_ids()
            pick = next((c for c in hand
                         if c != env.ability_id and env.eng.elixir[0] >= env.specs[c].elixir), None)
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


if __name__ == "__main__":
    unittest.main()
