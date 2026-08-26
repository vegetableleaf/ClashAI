"""No PHANTOM evolutions: `build_spec` must refuse an `_evo` key the KB does not define, and the
scripted opponents must field only evolutions that really exist.

The defect these pin (I2/I3, 2026-08-26): `build_spec` fabricated a spec for ANY `<x>_evo` key --
with no evo row the overlay merged nothing and it returned the BASE card wearing the evo's name.
`ScriptedBot` then picked its evolution as "the first deck card whose `<key>_evo` builds", and since
nothing ever failed to build, that was ALWAYS deck index 0. MEASURED before the fix: 689 of the 1000
meta decks fielded a phantom (arrows x188, berserker x128, barbarian_barrel x124, ...). After:
0 phantoms, 233 decks fielding their DECLARED slot, 767 fielding none.

`berserker` and `giant` are the interesting cases: they ARE evolved on live top ladder (937 and 277
sightings in research/sim_parity/ledger/meta_evo_slots.json) but the KB has no row for either, so
the honest answer is "cannot build", not "here is the base card". They light up by themselves once
the importer grows those rows -- meta_decks.yaml already declares them.
"""
import random
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for _p in (str(ROOT / "src"), str(ROOT / "tests")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from test_sim_status_effects import DummyCfg  # noqa: E402

from clashrl.cards import CardDB  # noqa: E402
from clashrl.sim.engine import build_spec  # noqa: E402
from clashrl.sim.meta_decks import load_meta_decks  # noqa: E402
from clashrl.sim.opponents import ScriptedBot  # noqa: E402

# Evolutions the live meta fields that the KB has no row for. Not a wish list: every key here was
# seen evolved in the R4 battlelog sweep, so any of them gaining a row is a legitimate change --
# the test then simply has fewer keys to guard.
NO_KB_ROW = ("berserker_evo", "giant_evo")
# ...and one that is a phantom in the strict sense: `arrows` was never once seen evolved in 7173
# top-ladder deck sightings, yet it was the single most-fielded fake (188 decks).
NEVER_EVOLVED = "arrows_evo"


class _Cfg(DummyCfg):
    """DummyCfg plus the two lookups the meta-deck pool needs."""

    def path(self, p):
        return ROOT / p

    def get(self, section, key, default=None):
        if (section, key) == ("sim", "meta_decks_file"):
            return "config/meta_decks.yaml"
        return super().get(section, key, default)


def _db():
    return CardDB(path=ROOT / "config" / "cards.yaml")


def _has_real_evo(db, base: str) -> bool:
    return bool(db.get(base + "_evo")) or isinstance((db.get(base) or {}).get("evolution"), dict)


class BuildSpecRefusesPhantomsTests(unittest.TestCase):
    def test_an_evo_key_with_no_kb_row_raises(self):
        db = _db()
        for key in NO_KB_ROW + (NEVER_EVOLVED,):
            with self.subTest(key=key):
                self.assertIsNone(db.get(key), f"{key} gained a KB row -- update this test")
                with self.assertRaises(KeyError):
                    build_spec(db, key, 11)

    def test_the_error_names_the_key_rather_than_failing_obscurely(self):
        db = _db()
        with self.assertRaises(KeyError) as ctx:
            build_spec(db, NEVER_EVOLVED, 11)
        self.assertIn("arrows", str(ctx.exception))

    def test_a_real_live_evolution_still_builds(self):
        """Evo Elite Barbarians is a live evolution with an imported row -- it must NOT be refused."""
        db = _db()
        spec = build_spec(db, "elite_barbarians_evo", 11)
        self.assertEqual(spec.key, "elite_barbarians_evo")
        self.assertEqual(spec.base, "elite_barbarians")
        self.assertGreater(spec.hp, 0.0)

    def test_a_curated_evolution_block_is_enough_on_its_own(self):
        """The Knight's evolution is curated as a mechanics dict, not only an imported row."""
        db = _db()
        self.assertIsInstance((db.get("knight") or {}).get("evolution"), dict)
        self.assertGreater(build_spec(db, "knight_evo", 11).hp, 0.0)

    def test_the_evo_row_actually_overlays_the_base(self):
        """Guards the other half: refusing fakes is worthless if real evos still field base stats."""
        db = _db()
        row = db.get("bomber_evo") or {}
        self.assertTrue(row.get("hitpoints"), "bomber_evo lost its imported hitpoints")
        base = build_spec(db, "bomber", 11)
        evo = build_spec(db, "bomber_evo", 11)
        self.assertNotAlmostEqual(base.hp, evo.hp, places=1,
                                  msg="the evo row is not reaching the spec")


class ScriptedBotFieldsOnlyRealEvosTests(unittest.TestCase):
    def test_every_meta_deck_evo_pick_resolves_to_a_real_kb_row(self):
        """The gate: 0 phantoms across the whole pool (was 689/1000). Mirrors tools/evo_audit.py."""
        cfg, db = _Cfg(), _db()
        pool = load_meta_decks(cfg, db)
        self.assertGreater(len(pool), 100, "the meta pool did not load")
        phantoms, real = [], 0
        for deck in pool:
            bot = ScriptedBot(cfg, db, random.Random(0), deck["cards"], deck["style"],
                              [11] * len(deck["cards"]), evo=deck.get("evo"))
            if bot.evo_idx < 0 or bot.evo_spec is None:
                continue
            real += 1
            base = deck["cards"][bot.evo_idx]
            if not _has_real_evo(db, base):
                phantoms.append((deck["name"], base))
        self.assertEqual(phantoms, [], f"{len(phantoms)} decks field a phantom evolution")
        self.assertGreater(real, 0, "no deck fields any evolution -- the slots stopped loading")

    def test_the_fielded_evo_is_the_declared_one(self):
        cfg, db = _Cfg(), _db()
        deck = next(d for d in load_meta_decks(cfg, db)
                    if any(_has_real_evo(db, k) for k in (d.get("evo") or [])))
        bot = ScriptedBot(cfg, db, random.Random(0), deck["cards"], deck["style"],
                          [11] * 8, evo=deck["evo"])
        self.assertIn(deck["cards"][bot.evo_idx], deck["evo"])

    def test_no_declared_slot_means_no_evolution(self):
        """Guessing a slot is exactly what fabricated the phantoms, so absence must field NOTHING."""
        cfg, db = _Cfg(), _db()
        cards = ["knight", "archers", "skeletons", "musketeer", "fireball", "the_log",
                 "ice_spirit", "cannon"]
        self.assertTrue(any(_has_real_evo(db, c) for c in cards), "picked a deck with no evos")
        bot = ScriptedBot(cfg, db, random.Random(0), cards, "cycle", [11] * 8, evo=None)
        self.assertEqual(bot.evo_idx, -1)
        self.assertIsNone(bot.evo_spec)

    def test_a_declared_evo_the_deck_does_not_hold_is_ignored(self):
        cfg, db = _Cfg(), _db()
        cards = ["knight", "archers", "skeletons", "musketeer", "fireball", "the_log",
                 "ice_spirit", "cannon"]
        bot = ScriptedBot(cfg, db, random.Random(0), cards, "cycle", [11] * 8,
                          evo=["mega_knight"])       # not in the deck
        self.assertEqual(bot.evo_idx, -1)

    def test_a_declared_evo_with_no_kb_row_fields_nothing_rather_than_a_fake(self):
        cfg, db = _Cfg(), _db()
        cards = ["berserker", "archers", "skeletons", "musketeer", "fireball", "the_log",
                 "ice_spirit", "cannon"]
        bot = ScriptedBot(cfg, db, random.Random(0), cards, "cycle", [11] * 8, evo=["berserker"])
        self.assertEqual(bot.evo_idx, -1, "a KB-less evolution must not fall back to the base card")

    def test_evo_cycles_come_from_the_evolution_row_not_a_flat_default(self):
        """Evo Elite Barbarians cycles ONCE; the old code hard-defaulted every import-only evo to 2."""
        cfg, db = _Cfg(), _db()
        self.assertEqual(int((db.get("elite_barbarians_evo") or {}).get("evo_cycles")), 1)
        cards = ["elite_barbarians", "archers", "skeletons", "musketeer", "fireball", "the_log",
                 "ice_spirit", "cannon"]
        bot = ScriptedBot(cfg, db, random.Random(0), cards, "control", [11] * 8,
                          evo=["elite_barbarians"])
        self.assertEqual(bot.evo_idx, 0)
        self.assertEqual(bot.evo_cycles, 1)


if __name__ == "__main__":
    unittest.main()
