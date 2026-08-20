"""The counter table's LOCAL validation gate (tools/counters_build.py).

The research fleet audits its own rows, but a self-audit is a claim, not a verification. Every
row is re-checked against THIS repo's card database before it can ship, and this file is the
gauntlet: rows carrying each known failure mode go in, and only the good ones may come out.

Two of the bad rows are the user's own bug reports (2026-08-20) -- knight on a balloon, rocket on
wall breakers -- so if a future regenerate reintroduces either, this fails rather than shipping it.
"""
from __future__ import annotations

import os
import sys
import unittest

_HERE = os.path.dirname(__file__)
sys.path.insert(0, os.path.join(_HERE, "..", "src"))
sys.path.insert(0, os.path.join(_HERE, "..", "tools"))

import counters_build as cb                    # noqa: E402
from clashrl.cards import CardDB               # noqa: E402
from clashrl.config import Config              # noqa: E402
from clashrl.counters import load              # noqa: E402


DECK = ["hog_rider", "firecracker", "mighty_miner", "tesla", "the_log", "earthquake",
        "skeletons", "ice_spirit"]


def row(threat, cards, responses):
    return {"threat": threat, "threat_cards": cards, "respond": responses}


class ValidationGauntletTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.db = CardDB(Config.load())

    def build(self, rows, deck=None):
        return cb.build(rows, deck or DECK, self.db, log=lambda *a: None)

    def test_the_reported_knight_on_balloon_row_cannot_ship(self):
        clean, dropped = self.build([row("balloon", ["balloon"], [
            {"card": "mighty_miner", "when": "at_bridge", "where": "in_front"},
            {"card": "tesla", "when": "at_bridge", "where": "center_kite"}])])
        self.assertEqual(1, len(clean))
        self.assertEqual(["tesla"], [e["card"] for e in clean[0]["respond"]],
                         "a ground-only card survived validation against a lone balloon")
        self.assertTrue(any("vetoed" in why for _t, why in dropped))

    def test_a_ground_only_spell_against_air_cannot_ship(self):
        """hogeq's twin of the reported rocket-on-wall-breakers row: earthquake SHAKES THE
        GROUND, so it can never answer a balloon however often a guide lists it as an answer."""
        clean, dropped = self.build([row("balloon", ["balloon"], [
            {"card": "earthquake", "when": "at_bridge", "where": "on_top"},
            {"card": "tesla", "when": "at_bridge", "where": "center_kite"}])])
        self.assertEqual(["tesla"], [e["card"] for e in clean[0]["respond"]],
                         "earthquake survived validation against a flying balloon")
        self.assertTrue(any("vetoed" in why for _t, why in dropped))

    def test_the_skeletons_at_tower_placement_survives(self):
        """User, 2026-08-20: skeletons answer wall breakers WITH the tower's help -- the row is
        only useful if the placement travels with it."""
        clean, _ = self.build([row("wall_breakers", ["wall_breakers"], [
            {"card": "skeletons", "when": "at_bridge", "where": "at_tower",
             "note": "tower assists the kill"}])])
        self.assertEqual("at_tower", clean[0]["respond"][0]["where"])

    def test_a_card_from_another_deck_is_dropped(self):
        clean, dropped = self.build([row("mega_knight", ["mega_knight"], [
            {"card": "fireball", "when": "in_our_half", "where": "on_top"}])])
        self.assertEqual([], clean)
        self.assertTrue(any("not in this deck" in why for _t, why in dropped))

    def test_an_unexecutable_placement_word_is_dropped(self):
        """A `where` the wheels cannot map would silently place nothing."""
        clean, dropped = self.build([row("golem", ["golem"], [
            {"card": "tesla", "when": "in_our_half", "where": "somewhere_nice"}])])
        self.assertEqual([], clean)
        self.assertTrue(any("bad when/where" in why for _t, why in dropped))

    def test_an_unknown_threat_card_is_dropped_not_guessed(self):
        clean, dropped = self.build([row("mystery", ["fake_card"], [
            {"card": "tesla", "when": "at_bridge", "where": "on_top"}])])
        self.assertEqual([], clean)
        self.assertTrue(any("unknown threat card" in why for _t, why in dropped))

    def test_duplicate_threat_keys_keep_the_first(self):
        clean, dropped = self.build([
            row("balloon A", ["balloon"], [{"card": "tesla", "when": "at_bridge",
                                            "where": "center_kite"}]),
            row("balloon B", ["balloon"], [{"card": "firecracker", "when": "at_bridge",
                                            "where": "center_kite"}]),
        ])
        self.assertEqual(1, len(clean))
        self.assertEqual("balloon A", clean[0]["threat"])
        self.assertTrue(any("duplicate" in why for _t, why in dropped))

    def test_a_good_row_survives_intact(self):
        clean, _ = self.build([row("hog_rider", ["hog_rider"], [
            {"card": "tesla", "when": "at_bridge", "where": "center_kite",
             "note": "pulls and survives"}])])
        self.assertEqual(1, len(clean))
        r = clean[0]["respond"][0]
        self.assertEqual(("tesla", "at_bridge", "center_kite"), (r["card"], r["when"], r["where"]))
        self.assertIn("note", r)

    def test_mitigation_rows_are_preserved(self):
        clean, _ = self.build([dict(row("golem", ["golem"], [
            {"card": "tesla", "when": "in_our_half", "where": "center_kite"}]),
            mitigation=True)])
        self.assertTrue(clean[0].get("mitigation"))


class RoundTripTests(unittest.TestCase):
    """What the builder writes, the loader must read back identically."""

    @classmethod
    def setUpClass(cls):
        cls.db = CardDB(Config.load())

    def test_yaml_round_trip(self):
        import tempfile
        rows = [
            row("balloon", ["balloon"], [{"card": "tesla", "when": "at_bridge",
                                          "where": "center_kite", "note": 'has a "quote" in it'}]),
            row("lava_hound+balloon", ["lava_hound", "balloon"],
                [{"card": "tesla", "when": "at_bridge", "where": "center_kite"}]),
        ]
        clean, _ = cb.build(rows, DECK, self.db, log=lambda *a: None)
        d = tempfile.mkdtemp()
        p = os.path.join(d, "counters.yaml")
        cb.dump_yaml(clean, p, "icebow", "unit test")
        t = load(path=p)
        self.assertEqual(2, len(t))
        self.assertEqual("tesla", t.best_card(["balloon"]))
        self.assertEqual("lava_hound+balloon", t.lookup(["lava_hound", "balloon"])["threat"])
        self.assertIn("quote", t.lookup(["balloon"])["respond"][0]["note"],
                      "a note with quotes did not survive the YAML round trip")


if __name__ == "__main__":
    unittest.main(verbosity=1)
