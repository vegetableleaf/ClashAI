"""RULING 19 -- what a SPAWNED BODY is worth, and the default-4 hole underneath it.

I10 MEASURED the hole: 25 KB keys carry no `elixir`, and every one of them fell through
`build_spec`'s `or 4` to read as FOUR elixir of enemy investment -- a Goblin Barrel decoy goblin, a
Golemite and a Skeleton King's Skeleton each priced like a Knight. That number is read ~30 times in
icebow and ~27 in hogeq (`sim/env.py`, `sim/doctrine.py`, `sim/engine.py`, `sim/opponents.py`,
`sim/drill_env.py`), by `_trade_reward` (elixir_trade), `_side_value` (counterfactual),
`_hog_wincon`, `_ability_value`, icebow's rocket / nado / bow-overcommit terms, and by
`threat_value`, which prices a fully-ignored card at 0.120 tower per elixir -- so an overpriced
body inflates what it costs to IGNORE it.

The owner priced three (2026-08-27). The other 22 are listed in conflicts.md's owner checklist.

⚠ THE SKELETON KING'S IS A TOTAL, NOT A PER-BODY PRICE, and that is the whole trap. "3 elixir at
full charge" buys the WHOLE activation. A full charge is `ability_spawn_count` 6 plus `_SOUL_CAP`
10 = 16 Skeletons -- the page: "With no souls, the Skeleton King will spawn 6 Skeletons, but with a
maximum of 10 souls, he can summon 16" -- so the per-body share is 3 / 16 = 0.1875 and a full
summon totals exactly 3.0000.

⚠ NOT `3 / max_souls`. The ruling offered that formula; it gives 0.3, and 16 x 0.3 = 4.80, which is
60% over the number the ruling set. The divisor is the SPAWN COUNT, not the soul bar. Pinned below
so the wrong formula cannot be reintroduced by someone reading only the ruling text.

WHY PER-BODY RATHER THAN "price the activation, leave the bodies at 0": the reward layer has no
concept of an activation's value. `ability_cost` is what the PLAYER PAYS (Skeleton King's is 2, a
published number the engine deducts), which is a different quantity from what the summoned bodies
are WORTH to the opponent's ledger -- and every one of those ~57 call sites reads `spec.elixir` on
a BODY. Pricing per body reaches all of them at once and cannot be forgotten by a 58th. It also
degrades correctly: a 6-body uncharged summon is worth 1.125, because an uncharged King has
invested less.

That required widening `CardSpec.elixir` from int to float, which is inert for the ~178 cards whose
cost is a published integer (4 == 4.0 everywhere it is read) and is pinned by
`IntegerCostsAreUnaffectedTests`.
"""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for _p in (str(ROOT / "src"), str(ROOT / "tests")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from clashrl.cards import CardDB                                       # noqa: E402
from clashrl.config import Config                                      # noqa: E402
from clashrl.sim.engine import build_spec                              # noqa: E402

LVL = 11
_SOUL_CAP = 10          # engine constant; re-imported below so a change to it breaks this loudly


def _db():
    return CardDB(Config.load(str(ROOT / "config" / "config.yaml")))


class OwnerPricedThreeTests(unittest.TestCase):

    def test_magic_archer_decoy_is_two(self):
        self.assertAlmostEqual(2.0, build_spec(_db(), "magic_archer_decoy", LVL).elixir, places=6)

    def test_guardienne_is_three(self):
        self.assertAlmostEqual(3.0, build_spec(_db(), "guardienne", LVL).elixir, places=6)

    def test_a_FULL_CHARGE_soul_summon_totals_exactly_three(self):
        """THE RULING'S ACTUAL NUMBER. Not the per-body price -- the per-body price is what makes
        this come out right."""
        from clashrl.sim.engine import _SOUL_CAP as cap
        db = _db()
        king = build_spec(db, "skeleton_king", LVL)
        body = build_spec(db, "soul_skeleton", LVL)
        n = int(king.ability_spawn_count or 6) + int(cap)
        self.assertEqual(16, n, "full charge is 6 base + 10 souls = 16 Skeletons")
        self.assertAlmostEqual(3.0, n * body.elixir, places=6,
                               msg="a full-charge Soul Summoning must be worth 3 elixir in TOTAL")

    def test_the_per_body_share_is_three_sixteenths_not_three_tenths(self):
        """The ruling suggested `3 / max_souls`. That is 0.3, and 16 x 0.3 = 4.80 -- 60% over the
        number the ruling set. Pinned so the wrong divisor cannot come back."""
        body = build_spec(_db(), "soul_skeleton", LVL)
        self.assertAlmostEqual(3.0 / 16.0, body.elixir, places=6)
        self.assertNotAlmostEqual(3.0 / _SOUL_CAP, body.elixir, places=4)

    def test_an_UNCHARGED_summon_is_worth_proportionally_less(self):
        """Six bodies, not sixteen: an uncharged King has invested less, and the per-body model
        gets that for free where a flat activation price would not."""
        db = _db()
        king = build_spec(db, "skeleton_king", LVL)
        body = build_spec(db, "soul_skeleton", LVL)
        self.assertAlmostEqual(1.125, int(king.ability_spawn_count or 6) * body.elixir, places=6)

    def test_the_bodies_are_no_longer_priced_like_a_knight(self):
        """The measured bug, stated as a test: all three used to read 4.0, the Knight's cost."""
        db = _db()
        knight = build_spec(db, "knight", LVL).elixir
        for k in ("magic_archer_decoy", "guardienne", "soul_skeleton"):
            with self.subTest(card=k):
                self.assertNotAlmostEqual(4.0, build_spec(db, k, LVL).elixir, places=4)
        self.assertAlmostEqual(3.0, knight, places=6, msg="the Knight itself is unmoved")


class IntegerCostsAreUnaffectedTests(unittest.TestCase):
    """The float widening must be invisible to every real card."""

    def test_every_published_cost_is_unchanged_and_integral(self):
        db = _db()
        checked = 0
        for key, row in db.cards.items():
            want = row.get("elixir")
            if want is None or key in ("soul_skeleton",):
                continue
            try:
                got = build_spec(db, key, LVL).elixir
            except Exception:                                          # noqa: BLE001
                continue
            checked += 1
            self.assertAlmostEqual(float(want), got, places=6, msg=key)
            if key not in ("magic_archer_decoy", "guardienne"):
                self.assertEqual(int(got), got, "%s: a card cost must stay integral" % key)
        self.assertGreater(checked, 150, "the sweep must actually cover the KB")

    def test_can_afford_still_works_at_the_boundary(self):
        """`can_afford` is `elixir[team] >= spec.elixir`, and a float on the right-hand side of an
        integer comparison is the one place a widening could bite."""
        import random
        from clashrl.sim.engine import SimEngine
        db = _db()
        cfg = Config.load(str(ROOT / "config" / "config.yaml"))
        eng = SimEngine(cfg, db, random.Random(0))
        s = build_spec(db, "knight", LVL)
        eng.elixir[0] = 3.0
        self.assertTrue(eng.can_afford(0, s))
        eng.elixir[0] = 2.999
        self.assertFalse(eng.can_afford(0, s))


class TheRemainingHoleTests(unittest.TestCase):
    """22 keys still default to 4. Pinned as a COUNT so the owner checklist cannot go stale
    silently -- pricing another one, or a re-import adding a key, makes this fail and forces the
    list in conflicts.md to be updated with it."""

    EXPECT = {
        "barrel_barbarian", "base_barrel_barbarian", "brigade_goblin", "bush_goblin",
        "decoy_goblin", "elixir_blob", "elixir_golemite", "ghost_souldier",
        "goblin_barrel_decoy", "goblin_brawler", "golemite", "lava_pups", "lumberjack_ghost",
        "mirror", "mother_witch_hog", "phoenix_egg", "rhino", "royal_recruit",
        "skarmy_general", "skeletrooper", "tomb_queen", "trusty_turret",
    }

    def test_exactly_the_twenty_two_listed_in_conflicts_md_still_default(self):
        db = _db()
        got = {k for k, v in db.cards.items() if v.get("elixir") is None}
        self.assertEqual(self.EXPECT, got,
                         "the conflicts.md owner checklist must be updated with this diff")

    def test_they_all_still_read_as_four(self):
        db = _db()
        for k in sorted(self.EXPECT):
            with self.subTest(card=k):
                try:
                    s = build_spec(db, k, LVL)
                except Exception:                                      # noqa: BLE001
                    continue
                self.assertAlmostEqual(4.0, s.elixir, places=6,
                                       msg="%s: still the engine default" % k)

    def test_a_zero_elixir_row_would_no_longer_fall_through_to_four(self):
        """The latent bug the widening closed. `int(c.get("elixir") or ... or 4)` treated a
        declared 0 as MISSING, so the one value that could not be expressed was the one I9's Clone
        needs -- which is why the clone sets `elixir = 0` on the built SPEC instead. No shipped row
        carries 0, so this is checked on a synthetic row."""
        db = _db()
        db.cards["__zero_probe__"] = {"display": "Zero Probe", "kind": "troop", "elixir": 0,
                                      "hitpoints": 100, "damage": 10, "hit_speed": 1.0,
                                      "count": 1, "attacks": ["ground"], "movement": "ground"}
        try:
            self.assertAlmostEqual(0.0, build_spec(db, "__zero_probe__", LVL).elixir, places=6)
        finally:
            db.cards.pop("__zero_probe__", None)


class PinsTests(unittest.TestCase):
    """A curated value with no pin is one re-import away from being gone -- the failure mode I5
    had to undo by hand. Pins outrank `verified`, which is what lets magic_archer_decoy keep
    `verified: false` on a row whose damage and hit speed are still open questions."""

    def test_all_three_are_pinned_and_the_pair_is_byte_identical(self):
        a = (ROOT / "config" / "import_pins.json").read_bytes()
        b = (ROOT.parent / ("hogeq" if ROOT.name == "icebow" else "icebow")
             / "config" / "import_pins.json").read_bytes()
        self.assertEqual(a, b, "import_pins.json is a byte-identical pair")
        pins = {(p["key"], p["field"]): p for p in json.loads(a.decode("utf-8"))["pins"]}
        for key, value in (("magic_archer_decoy", 2), ("guardienne", 3),
                           ("soul_skeleton", 0.1875)):
            with self.subTest(card=key):
                p = pins.get((key, "elixir"))
                self.assertIsNotNone(p, "%s.elixir is not pinned" % key)
                self.assertAlmostEqual(float(value), float(p["value"]), places=6)
                self.assertEqual("2026-08-27", p["date"])
                self.assertNotIn("advisory", p, "a hard pin, so --write refuses a regression")

    def test_the_pinned_value_matches_the_KB(self):
        db = _db()
        pins = {(p["key"], p["field"]): p
                for p in json.loads((ROOT / "config" / "import_pins.json")
                                    .read_text(encoding="utf-8"))["pins"]}
        for key in ("magic_archer_decoy", "guardienne", "soul_skeleton"):
            with self.subTest(card=key):
                self.assertAlmostEqual(float(pins[(key, "elixir")]["value"]),
                                       build_spec(db, key, LVL).elixir, places=6)


if __name__ == "__main__":                                   # pragma: no cover
    unittest.main()
