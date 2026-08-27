"""No PHANTOM evolutions: `build_spec` must refuse an `_evo` key the KB does not define, and the
scripted opponents must field only evolutions that really exist.

The defect these pin (I2/I3, 2026-08-26): `build_spec` fabricated a spec for ANY `<x>_evo` key --
with no evo row the overlay merged nothing and it returned the BASE card wearing the evo's name.
`ScriptedBot` then picked its evolution as "the first deck card whose `<key>_evo` builds", and since
nothing ever failed to build, that was ALWAYS deck index 0. MEASURED before the fix: 689 of the 1000
meta decks fielded a phantom (arrows x188, berserker x128, barbarian_barrel x124, ...).

The restock (I3): each deck carries `evo_candidates` -- its own cards that really HAVE an evolution,
derived from the KB's 42 `_evo` rows, which match the 42 wiki-verified evolutions in
research/sim_parity/ledger/r1a_evolutions.json EXACTLY (zero additions, zero removals). The bot
draws ONE uniformly per match. MEASURED after: 1000/1000 decks field a REAL evolution, 0 phantoms,
0 candidates that fail to build, all 42 evolutions reachable.

Why a draw and not a named slot: nothing published says which card a player put in the slot. The
battlelog's `evolutionLevel` reports the player's OWNED level -- it yields THREE evolutions for
153/233 decks against a game that allows at most two, and reports a level for `berserker`, which has
no evolution at all -- so its 233 declarations were stripped. Naming one would be false precision;
drawing from the LEGAL set is honest and trains against realistic variety.
"""
import json
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
from clashrl.sim.meta_decks import evo_candidates, has_evolution, load_meta_decks  # noqa: E402
from clashrl.sim.opponents import ScriptedBot  # noqa: E402

# Cards the OFFICIAL API forward-declares an `evolutionLevel` for that have NO evolution in the
# game: the `Card Evolution` master page mentions "Berserker" zero times, and R1's probes found no
# `/Evolution` subpage for either. If one ever ships, it gains a KB row and this list shrinks.
NO_KB_ROW = ("berserker_evo", "giant_evo")
# ...and one that is a phantom in the strict sense: `arrows` was never once seen evolved in 7173
# top-ladder deck sightings, yet it was the single most-fielded fake (188 decks).
NEVER_EVOLVED = "arrows_evo"

# The wiki-verified evolution list (R1a). Lives above the deck root, so it is absent from a plain
# deck checkout -- the cross-check skips rather than fails there.
LEDGER = ROOT.parent / "research" / "sim_parity" / "ledger" / "r1a_evolutions.json"

# Eight real cards, none of which has an evolution -- the "fields nothing" fixture.
NO_EVO_DECK = ["fireball", "the_log", "hog_rider", "miner",
               "poison", "rocket", "arrows", "graveyard"]


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


def _bot(cfg, db, cards, seed=0, **kw):
    return ScriptedBot(cfg, db, random.Random(seed), cards, "control", [11] * len(cards), **kw)


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
        """Guards the other half: refusing fakes is worthless if real evos still field base stats.

        The card moved from bomber_evo to bats_evo in I5. bomber_evo is no longer a valid probe
        for this property: the R2 LAG bucket ruled its 332 stale (both the Evo page's own intro
        and the Card Evolution table say the Evo Bomber has IDENTICAL stats to the base, and the
        Evo page simply never took the 6/10/2025 -7%), so base and evo now agree at 304 BY
        RULING. A test that reads "different" as "the overlay works" would have made that
        correction look like a regression. bats_evo (81 -> 122) is a genuine stat divergence.
        """
        db = _db()
        row = db.get("bats_evo") or {}
        self.assertTrue(row.get("hitpoints"), "bats_evo lost its imported hitpoints")
        base = build_spec(db, "bats", 11)
        evo = build_spec(db, "bats_evo", 11)
        self.assertAlmostEqual(evo.hp, float(row["hitpoints"]), places=1,
                               msg="the evo row is not reaching the spec")
        self.assertNotAlmostEqual(base.hp, evo.hp, places=1,
                                  msg="the evo row is not reaching the spec")


class EvoCandidatesAreDerivedNotGuessedTests(unittest.TestCase):
    """`evo_candidates` is DERIVED DATA. These pin that it can only ever name real evolutions."""

    def test_every_candidate_in_the_pool_is_a_real_evolution_the_deck_holds(self):
        cfg, db = _Cfg(), _db()
        pool = load_meta_decks(cfg, db)
        self.assertGreater(len(pool), 100, "the meta pool did not load")
        bad = []
        for deck in pool:
            for k in deck["evo_candidates"]:
                if k not in deck["cards"]:
                    bad.append((deck["name"], k, "not in the deck"))
                elif not has_evolution(db, k):
                    bad.append((deck["name"], k, "no KB evolution"))
        self.assertEqual(bad, [], f"{len(bad)} candidates are not real, held evolutions")

    def test_every_candidate_resolves_through_build_spec(self):
        """The gate: a candidate that cannot build would field NOTHING on the run that drew it."""
        cfg, db = _Cfg(), _db()
        pool = load_meta_decks(cfg, db)
        seen, failed = set(), []
        for deck in pool:
            for k in deck["evo_candidates"]:
                if k in seen:
                    continue
                seen.add(k)
                try:
                    spec = build_spec(db, k + "_evo", 11)
                except Exception as exc:                                  # noqa: BLE001
                    failed.append((k, repr(exc)))
                    continue
                if spec.hp <= 0.0 and spec.kind != "spell":
                    failed.append((k, f"non-spell with hp {spec.hp}"))
        self.assertEqual(failed, [], f"{len(failed)} candidate evolutions do not resolve")
        self.assertGreater(len(seen), 20, "suspiciously few distinct candidates in the pool")

    def test_the_kb_evolution_set_matches_the_wiki_verified_ledger(self):
        """R1a: 42 wiki-verified evolutions, matching the KB's 42 `_evo` rows exactly.

        This is what makes the derived candidate list CHECKABLE rather than a guess. If the KB
        grows a row the wiki does not carry (or loses one it does), the candidates stop being
        verifiable and this goes red.
        """
        if not LEDGER.exists():
            self.skipTest(f"{LEDGER} not present (research/ lives above the deck root)")
        db = _db()
        kb = {k for k in db.cards if k.endswith("_evo")}
        wiki = {e["key"] for e in json.loads(LEDGER.read_text(encoding="utf-8"))["evolutions"]}
        self.assertEqual(len(wiki), 42)
        self.assertEqual(sorted(kb), sorted(wiki),
                         f"KB-only {sorted(kb - wiki)}, wiki-only {sorted(wiki - kb)}")

    def test_every_evolution_carries_the_ledgers_cycle_count(self):
        """A MISSING cycle count is not neutral: the slot asks `charge >= cycles`, so 0 is
        satisfied from the first tick and the Evolution is presented on every lap. MEASURED before
        the I1 backport: 6 of 42 reported a cycle count at all (the lookup was gated on a curated
        `evolution.available` only 6 base cards carry); after it, 40, with `minion_horde_evo` (1)
        and `princess_evo` (2) simply absent from the imported rows. Both were taken from the
        wiki's Cycles column and curated in, so this is now 42/42."""
        if not LEDGER.exists():
            self.skipTest(f"{LEDGER} not present (research/ lives above the deck root)")
        db = _db()
        wiki = {e["key"]: e.get("evo_cycles")
                for e in json.loads(LEDGER.read_text(encoding="utf-8"))["evolutions"]}
        bad = []
        for key, want in wiki.items():
            got = db.evo_cycles(key[:-4])
            if want and got != int(want):
                bad.append((key, got, want))
        self.assertEqual(bad, [], f"{len(bad)} evolutions disagree with the wiki (key, kb, wiki)")

    def test_a_deck_with_no_evolvable_card_has_no_candidates(self):
        db = _db()
        self.assertEqual(evo_candidates(db, NO_EVO_DECK), [])

    def test_candidates_are_derived_when_the_entry_does_not_carry_them(self):
        """A regenerated pool or a built-in fallback must not silently field no evolutions."""
        db = _db()
        cards = ["knight", "musketeer", "fireball", "skeletons",
                 "ice_spirit", "hog_rider", "cannon", "the_log"]
        self.assertEqual(evo_candidates(db, cards),
                         ["knight", "musketeer", "skeletons", "ice_spirit", "cannon"])


class ScriptedBotFieldsOnlyRealEvosTests(unittest.TestCase):
    def test_every_meta_deck_evo_pick_resolves_to_a_real_kb_row(self):
        """The gate: 0 phantoms across the whole pool (was 689/1000). Mirrors tools/evo_audit.py."""
        cfg, db = _Cfg(), _db()
        pool = load_meta_decks(cfg, db)
        self.assertGreater(len(pool), 100, "the meta pool did not load")
        phantoms, real, none = [], 0, 0
        for deck in pool:
            bot = _bot(cfg, db, deck["cards"], evo=deck["evo"],
                       evo_candidates=deck["evo_candidates"])
            if bot.evo_idx < 0 or bot.evo_spec is None:
                none += 1
                # Fielding nothing is only correct when there was nothing legal to field.
                self.assertEqual(deck["evo_candidates"], [],
                                 f"{deck['name']} had candidates but fielded no evolution")
                continue
            real += 1
            base = deck["cards"][bot.evo_idx]
            if not has_evolution(db, base):
                phantoms.append((deck["name"], base))
        self.assertEqual(phantoms, [], f"{len(phantoms)} decks field a phantom evolution")
        self.assertGreater(real, 0.9 * len(pool),
                           f"only {real}/{len(pool)} decks field an evolution (was 1000/1000)")

    def test_the_draw_is_reproducible_under_a_seeded_rng(self):
        cfg, db = _Cfg(), _db()
        cards = ["knight", "musketeer", "fireball", "skeletons",
                 "ice_spirit", "hog_rider", "cannon", "the_log"]
        cands = evo_candidates(db, cards)
        for seed in (0, 1, 7, 12345):
            a = _bot(cfg, db, cards, seed=seed, evo_candidates=cands)
            b = _bot(cfg, db, cards, seed=seed, evo_candidates=cands)
            with self.subTest(seed=seed):
                self.assertEqual(a.evo_idx, b.evo_idx)
                self.assertEqual(a.evo_spec.key, b.evo_spec.key)

    def test_the_draw_actually_varies_and_reaches_every_candidate(self):
        """A "uniform draw" that always returns index 0 is the ORIGINAL bug wearing a new name."""
        cfg, db = _Cfg(), _db()
        cards = ["knight", "musketeer", "fireball", "skeletons",
                 "ice_spirit", "hog_rider", "cannon", "the_log"]
        cands = evo_candidates(db, cards)
        self.assertGreater(len(cands), 1, "fixture must offer a real choice")
        got = {_bot(cfg, db, cards, seed=s, evo_candidates=cands).evo_spec.base
               for s in range(400)}
        self.assertEqual(sorted(got), sorted(cands),
                         "the draw does not reach every legal candidate")

    def test_only_one_evolution_slot_is_ever_fielded(self):
        """The 16/3/2026 loadout is one Evolution + one Hero + one Wild. The engine models the
        Evolution slot only: exactly one, never two, even when all eight cards could evolve."""
        cfg, db = _Cfg(), _db()
        cards = ["knight", "musketeer", "skeletons", "ice_spirit",
                 "cannon", "valkyrie", "tesla", "archers"]
        cands = evo_candidates(db, cards)
        self.assertEqual(len(cands), 8, "fixture must be all-evolvable")
        for seed in range(30):
            bot = _bot(cfg, db, cards, seed=seed, evo_candidates=cands)
            with self.subTest(seed=seed):
                self.assertGreaterEqual(bot.evo_idx, 0)
                self.assertIsNotNone(bot.evo_spec)
                # ONE index, ONE spec: the machinery holds a scalar slot, not a list of them.
                self.assertNotIsInstance(bot.evo_idx, (list, tuple))
                self.assertEqual(sum(1 for s in bot.specs if s is bot.evo_spec), 0,
                                 "the evo spec must replace the base at play time, not sit in the deck")

    def test_a_deck_with_no_evolvable_card_fields_nothing(self):
        cfg, db = _Cfg(), _db()
        cands = evo_candidates(db, NO_EVO_DECK)
        self.assertEqual(cands, [])
        bot = _bot(cfg, db, NO_EVO_DECK, evo_candidates=cands)
        self.assertEqual(bot.evo_idx, -1)
        self.assertIsNone(bot.evo_spec)

    def test_a_candidate_the_deck_does_not_hold_is_ignored(self):
        cfg, db = _Cfg(), _db()
        bot = _bot(cfg, db, NO_EVO_DECK, evo_candidates=["mega_knight", "wizard"])
        self.assertEqual(bot.evo_idx, -1, "a candidate outside the deck must not be fielded")

    def test_a_declared_slot_still_wins_over_the_draw(self):
        """`evo:` is authoritative if a real source ever names a slot. No shipped deck declares
        one today, but the hook must keep working -- and must not be silently overridden."""
        cfg, db = _Cfg(), _db()
        cards = ["knight", "musketeer", "fireball", "skeletons",
                 "ice_spirit", "hog_rider", "cannon", "the_log"]
        cands = evo_candidates(db, cards)
        for seed in range(20):
            bot = _bot(cfg, db, cards, seed=seed, evo=["cannon"], evo_candidates=cands)
            with self.subTest(seed=seed):
                self.assertEqual(cards[bot.evo_idx], "cannon")

    def test_no_declared_slot_and_no_candidates_means_no_evolution(self):
        """Guessing a slot is exactly what fabricated the phantoms, so absence must field NOTHING."""
        cfg, db = _Cfg(), _db()
        cards = ["knight", "archers", "skeletons", "musketeer", "fireball", "the_log",
                 "ice_spirit", "cannon"]
        self.assertTrue(any(has_evolution(db, c) for c in cards), "picked a deck with no evos")
        bot = _bot(cfg, db, cards, evo=None, evo_candidates=None)
        self.assertEqual(bot.evo_idx, -1)
        self.assertIsNone(bot.evo_spec)

    def test_a_declared_evo_the_deck_does_not_hold_is_ignored(self):
        cfg, db = _Cfg(), _db()
        cards = ["knight", "archers", "skeletons", "musketeer", "fireball", "the_log",
                 "ice_spirit", "cannon"]
        bot = _bot(cfg, db, cards, evo=["mega_knight"])       # not in the deck
        self.assertEqual(bot.evo_idx, -1)

    def test_a_declared_evo_with_no_kb_row_fields_nothing_rather_than_a_fake(self):
        cfg, db = _Cfg(), _db()
        cards = ["berserker", "archers", "skeletons", "musketeer", "fireball", "the_log",
                 "ice_spirit", "cannon"]
        bot = _bot(cfg, db, cards, evo=["berserker"])
        self.assertEqual(bot.evo_idx, -1, "a KB-less evolution must not fall back to the base card")

    def test_evo_cycles_come_from_the_evolution_row_not_a_flat_default(self):
        """Evo Elite Barbarians cycles ONCE; the old code hard-defaulted every import-only evo to 2."""
        cfg, db = _Cfg(), _db()
        self.assertEqual(int((db.get("elite_barbarians_evo") or {}).get("evo_cycles")), 1)
        cards = ["elite_barbarians", "archers", "skeletons", "musketeer", "fireball", "the_log",
                 "ice_spirit", "cannon"]
        bot = _bot(cfg, db, cards, evo=["elite_barbarians"])
        self.assertEqual(bot.evo_idx, 0)
        self.assertEqual(bot.evo_cycles, 1)

    def test_a_drawn_evo_also_takes_its_cycles_from_its_own_row(self):
        """The same rule must hold on the DRAW path, not just the declared one."""
        cfg, db = _Cfg(), _db()
        cards = ["elite_barbarians", "fireball", "the_log", "hog_rider",
                 "miner", "poison", "rocket", "graveyard"]
        cands = evo_candidates(db, cards)
        self.assertEqual(cands, ["elite_barbarians"], "fixture must force the draw")
        bot = _bot(cfg, db, cards, evo_candidates=cands)
        self.assertEqual(bot.evo_idx, 0)
        self.assertEqual(bot.evo_cycles, 1)


if __name__ == "__main__":
    unittest.main()
