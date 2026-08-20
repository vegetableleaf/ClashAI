"""The COUNTER TABLE lookup (clashrl.counters).

The table answers what the three tiers above it could not: threat_value triages (is this worth a
card), threat_value.pick_invalid vetoes (can this card even touch it), card_threat.counters
matches by role -- and none of them can say "Wall Breakers want Skeletons placed so the tower
helps" or "a Lavaloon is not a Lava Hound plus a Balloon: ignore the hound and kill the balloon".

The rows in these tests are FIXTURES, not the shipped table: they exist to pin the lookup rules
(combo beats single, subset matching, hand filtering, priority order) so a regenerated table
cannot silently change how a push is read.
"""
from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from clashrl.counters import WHEN_VALUES, WHERE_VALUES, CounterTable, load   # noqa: E402


ROWS = [
    {"threat": "balloon", "threat_cards": ["balloon"],
     "respond": [{"card": "tesla", "when": "at_bridge", "where": "center_kite"},
                 {"card": "ice_spirit", "when": "in_our_half", "where": "on_top"}]},
    {"threat": "lava_hound+balloon", "threat_cards": ["lava_hound", "balloon"],
     "respond": [{"card": "tesla", "when": "at_bridge", "where": "center_kite",
                  "note": "ignore the hound, kill the balloon"}]},
    {"threat": "wall_breakers", "threat_cards": ["wall_breakers"],
     "respond": [{"card": "skeletons", "when": "at_bridge", "where": "at_tower",
                  "note": "tower assists the kill"},
                 {"card": "the_log", "when": "at_bridge", "where": "in_front"}]},
]


class LookupTests(unittest.TestCase):
    def setUp(self):
        self.t = CounterTable(ROWS)

    def test_a_combo_beats_its_parts(self):
        """The whole point of researching combos: Lavaloon has its own answer, and it is NOT the
        union of the two single-card answers."""
        self.assertEqual("lava_hound+balloon",
                         self.t.lookup(["lava_hound", "balloon"])["threat"])

    def test_a_superset_push_still_finds_the_combo_row(self):
        """A Lavaloon with minions tagging along is still a Lavaloon."""
        self.assertEqual("lava_hound+balloon",
                         self.t.lookup(["lava_hound", "balloon", "minions"])["threat"])

    def test_a_single_card_finds_its_own_row(self):
        self.assertEqual("tesla", self.t.best_card(["balloon"]))

    def test_responses_are_filtered_to_the_hand(self):
        """A doctrine answer we cannot play is not an answer: the second-priority card takes over
        rather than the caller being told to play a card it does not hold."""
        self.assertEqual("ice_spirit", self.t.best_card(["balloon"],
                                                        hand_bases=["ice_spirit", "the_log"]))

    def test_priority_order_is_preserved(self):
        got = [r["card"] for r in self.t.responses(["wall_breakers"])]
        self.assertEqual(["skeletons", "the_log"], got,
                         "the table's priority order was not preserved")

    def test_the_user_note_about_skeletons_and_the_tower_survives(self):
        """User, 2026-08-20: skeletons counter wall breakers WITH the princess tower's help, if
        placed correctly -- so the placement detail has to reach the caller, not just the card."""
        first = self.t.responses(["wall_breakers"])[0]
        self.assertEqual("at_tower", first["where"])

    def test_an_unknown_threat_returns_nothing(self):
        """No opinion is not the same as 'hold': callers fall back to their previous behaviour."""
        self.assertIsNone(self.t.lookup(["golem"]))
        self.assertEqual([], self.t.responses(["golem"]))
        self.assertIsNone(self.t.best_card(["golem"]))

    def test_an_empty_board_returns_nothing(self):
        self.assertIsNone(self.t.lookup([]))

    def test_no_hand_overlap_returns_nothing(self):
        self.assertIsNone(self.t.best_card(["balloon"], hand_bases=["mighty_miner", "skeletons"]))


class HygieneTests(unittest.TestCase):
    def test_rows_without_a_response_are_dropped(self):
        t = CounterTable([{"threat": "x", "threat_cards": ["golem"], "respond": []}])
        self.assertEqual(0, len(t))

    def test_rows_without_threat_cards_are_dropped(self):
        t = CounterTable([{"threat": "x", "threat_cards": [],
                           "respond": [{"card": "tesla", "when": "at_bridge", "where": "on_top"}]}])
        self.assertEqual(0, len(t))

    def test_the_first_row_for_a_key_wins(self):
        """So a hand-written override placed above the generated rows survives a regenerate."""
        t = CounterTable([
            {"threat": "override", "threat_cards": ["balloon"],
             "respond": [{"card": "firecracker", "when": "at_bridge", "where": "center_kite"}]},
            ROWS[0],
        ])
        self.assertEqual("firecracker", t.best_card(["balloon"]))

    def test_a_missing_file_is_not_an_error(self):
        """A deck with no researched table keeps its previous behaviour instead of crashing."""
        t = load(path=os.path.join(os.path.dirname(__file__), "no_such_counters.yaml"))
        self.assertEqual(0, len(t))

    def test_the_shipped_table_uses_only_known_vocabulary(self):
        """If config/counters.yaml exists, every when/where must be one the wheels can execute --
        an unknown placement word would silently do nothing."""
        p = os.path.join(os.path.dirname(__file__), "..", "config", "counters.yaml")
        if not os.path.exists(p):
            self.skipTest("no counter table shipped for this deck yet")
        t = load(path=p)
        self.assertGreater(len(t), 0, "config/counters.yaml exists but parsed to zero rows")
        for row in t.rows:
            for r in row["respond"]:
                self.assertIn(r["when"], WHEN_VALUES, "bad when in row %r" % row["threat"])
                self.assertIn(r["where"], WHERE_VALUES, "bad where in row %r" % row["threat"])


if __name__ == "__main__":
    unittest.main(verbosity=1)
