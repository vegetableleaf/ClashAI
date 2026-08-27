"""I9 -- EVOLUTION CYCLING IN DRILLS. Deck-agnostic; BYTE-IDENTICAL in icebow and hogeq.

THE MEASURED GAP. `SimMatchEnv` presents a slot's Evolution once it has banked `slot_cycles` base
plays (env.py `_slot_card_id` / `_play_slot`), and `reset()` starts every slot at zero. `DrillEnv`
inherits all of that -- contrary to the brief, `evo_charge` and `slot_cycles` DO exist in drills --
but a restricted-hand drill deals one or two cards and `DrillEnv._play_slot` then removes the slot
from the cycle (deliberately: a drill dealt one card could otherwise replay it forever). So the
charge can reach 1 and never the 2 an Evolution needs.

MEASURED before `_apply_evo_charge` existed: an evolution was presented in **0 of 26 icebow drills
and 0 of 24 hogeq drills**, while a match first presents one after 9 plays. Evolutions were not
"always on" in drills -- they were permanently OFF, and a drill that named an `<base>_evo` key in
its `hand` was silently dealt the base card under the evolution's name.

The DEFAULT is deliberately unchanged: every existing reference line was written against the base
card. `Scenario.evo_charged` is the opt-in.
"""
from __future__ import annotations

import sys
import unittest
from dataclasses import replace as dreplace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for _p in (str(ROOT / "src"), str(ROOT / "tests")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from clashrl.config import Config                                  # noqa: E402
from clashrl.sim import scenarios as sc                            # noqa: E402
from clashrl.sim.drill_env import DrillEnv                         # noqa: E402
from clashrl.sim.env import SimMatchEnv                            # noqa: E402

sc.load_all()                       # whichever deck this is, register its own drills


def _hand_drills():
    return [s for s in sc.all_scenarios() if getattr(s, "hand", ())]


class DrillEvoCycleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cfg = Config.load()
        cls.pool = _hand_drills()
        if not cls.pool:
            raise unittest.SkipTest("this deck registers no restricted-hand drills")

    def _dealt(self, scenario):
        d = DrillEnv(self.cfg, scenario, seed=0)
        d.reset()
        return d, [str(d.deck_keys[i]) for i in d._hand_ids()]

    def test_the_match_machinery_is_present_in_a_drill(self):
        """The premise this stage was handed said `evo_charge`/`slot_cycles` "do not exist" in
        drills. They do -- DrillEnv extends SimMatchEnv -- and that matters, because the fix is a
        charge policy rather than a second copy of the cycle."""
        d, _ = self._dealt(self.pool[0])
        self.assertTrue(hasattr(d, "evo_charge"))
        self.assertTrue(hasattr(d, "slot_cycles"))
        self.assertEqual(len(d.evo_charge), d.n_slots)
        self.assertTrue(any(e >= 0 for e in d.slot_evo_id),
                        "both decks hold at least one evolution-capable slot")

    def test_the_default_is_match_behaviour_and_deals_the_base_card(self):
        """A match starts every slot UNCHARGED; so does a drill. Nothing that already exists
        changes identity, which is what keeps every recorded reference line valid."""
        for s in self.pool:
            with self.subTest(drill=s.name):
                d, ids = self._dealt(s)
                self.assertEqual(d.evo_charge, [0] * d.n_slots)
                self.assertFalse([k for k in ids if k.endswith("_evo")],
                                 "no drill presents an evolution by default")

    def test_an_evolution_is_unreachable_without_the_flag(self):
        """The gap itself: spend the whole restricted hand and the charge still cannot reach the
        slot's cycle count, because the slot leaves the cycle when it is played."""
        s = next((x for x in self.pool
                  if any(self._dealt(x)[0].slot_evo_id[sl] >= 0
                         for sl in self._dealt(x)[0].cycle)), None)
        self.assertIsNotNone(s, "at least one drill deals an evolution-capable card")
        d, _ = self._dealt(s)
        for cid in list(d._hand_ids()):
            d._play_slot(cid)
        reached = [sl for sl in range(d.n_slots)
                   if d.slot_evo_id[sl] >= 0 and d.evo_charge[sl] >= d.slot_cycles[sl]]
        self.assertEqual(reached, [],
                         "a restricted-hand drill can never bank the plays an evolution needs")

    def test_the_scenario_flag_charges_every_evolution_slot(self):
        n = 0
        for s in self.pool:
            d, ids = self._dealt(dreplace(s, evo_charged=True))
            evo_slots = [sl for sl in range(d.n_slots) if d.slot_evo_id[sl] >= 0]
            for sl in evo_slots:
                self.assertGreaterEqual(d.evo_charge[sl], d.slot_cycles[sl])
            if [k for k in ids if k.endswith("_evo")]:
                n += 1
        # MEASURED 2026-08-27: 10 of 26 icebow drills and 10 of 24 hogeq drills deal an
        # evolution-capable card, so those are the drills the flag can change.
        self.assertGreater(n, 0, "the flag must actually change what some drill is dealt")

    def test_the_flag_can_name_one_card(self):
        """`evo_charged=(key,)` charges only that slot -- named by base or by `<base>_evo`."""
        s = self.pool[0]
        d0, _ = self._dealt(s)
        evo_slots = [sl for sl in range(d0.n_slots) if d0.slot_evo_id[sl] >= 0]
        self.assertTrue(evo_slots)
        pick = evo_slots[0]
        key = str(d0.deck_keys[d0.slot_evo_id[pick]])
        d, _ = self._dealt(dreplace(s, evo_charged=(key,)))
        self.assertGreaterEqual(d.evo_charge[pick], d.slot_cycles[pick])
        for sl in evo_slots[1:]:
            self.assertEqual(d.evo_charge[sl], 0, "only the named slot is charged")
        d2, _ = self._dealt(dreplace(s, evo_charged=(key.replace("_evo", ""),)))
        self.assertGreaterEqual(d2.evo_charge[pick], d2.slot_cycles[pick],
                                "naming the BASE charges the same slot")

    def test_naming_an_evolution_in_the_hand_is_honoured(self):
        """Previously silent: `_restrict_hand` matches on the identity a slot CURRENTLY presents,
        which at charge 0 is the base -- so `hand: ('tesla_evo',)` dealt a plain Tesla under the
        evolution's name. A drill that fails for that reason is exactly what `_restrict_hand`
        exists to prevent."""
        found = False
        for s in self.pool:
            d0, _ = self._dealt(s)
            evo_of = {str(d0.deck_keys[e]).replace("_evo", ""): str(d0.deck_keys[e])
                      for e in d0.slot_evo_id if e >= 0}
            named = [b for b in s.hand if str(b) in evo_of]
            if not named:
                continue
            ek = evo_of[str(named[0])]
            s2 = dreplace(s, hand=tuple(ek if str(b) == str(named[0]) else b for b in s.hand))
            _d, ids = self._dealt(s2)
            self.assertIn(ek, ids, "%s: naming %s must deal %s" % (s.name, ek, ek))
            found = True
            break
        self.assertTrue(found, "at least one drill deals an evolution-capable card")

    def test_a_matchup_drill_cycles_exactly_like_a_match(self):
        """Drills with no declared hand keep the full 8-slot cycle, so they already charge the
        way a match does. Nothing here may change that."""
        matchups = [s for s in sc.all_scenarios() if not getattr(s, "hand", ())]
        if not matchups:
            self.skipTest("this deck registers no matchup drills")
        m = SimMatchEnv(self.cfg, seed=0)
        m.reset()
        d = DrillEnv(self.cfg, matchups[0], seed=0)
        d.reset()
        self.assertEqual(len(d.cycle), len(m.cycle))
        self.assertEqual(d.slot_cycles, m.slot_cycles)
        self.assertEqual(d.evo_charge, [0] * d.n_slots)

    def test_a_compound_declaration_does_not_outlive_its_episode(self):
        """`_compound_hand` was assigned in `_place_components` and never cleared, so one compound
        episode's hand leaked into every later single-scenario drill in the same env. Latent
        (`sim.drill_compound_frac` is 0.0 in both decks) and fixed with its evolution twin."""
        d = DrillEnv(self.cfg, self.pool[0], seed=0)
        d.reset()
        d._compound_hand = ("x_bow", "rocket", "tornado")
        d._compound_evo = True
        d.reset()
        self.assertIsNone(d._compound_hand)
        self.assertIsNone(d._compound_evo)
        self.assertEqual(d.evo_charge, [0] * d.n_slots)


if __name__ == "__main__":
    unittest.main()
