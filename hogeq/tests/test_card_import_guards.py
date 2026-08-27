"""I4 importer hardening -- the guards, proven offline against archived pages.

Three failure modes this file pins, each measured before the fix (PLAN.md I4,
ledger/stat_diffs.jsonl):

* INVENTED CONTENT: wiki editors create "Coming soon" stubs for announced cards
  (Mega Knight/Battle Healer heroes, release 2026-09-07) and the channel is
  unmoderated. The allowlist must exclude announced keys loudly and hard-stop on
  unknown ones -- an announced stub page must NOT produce a row.
* CURATED-VALUE ROLLBACK: the wiki's vardefines lag its own balance history, so a
  re-import regressed rocket crown 341 -> 371 on 2026-08-14. The pins post-pass must
  force the curated value back over the scrape, and --write must refuse a pinned
  field that would still regress.
* HERO PARSE: /Hero pages put the ABILITY in a second Cost-bearing attributes table;
  Balloon/Hero's Skeletrooper row read as a second body (count 2, MEASURED BEFORE).

Archived pages come from research/sim_parity/webcache/ with skipTest-on-missing,
same idiom as test_r2_engine_schema.py. The allowlist/pins configs are the deck's
own (config/import_allowlist.json, config/import_pins.json) -- generated files,
committed, always present.
"""
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from clashrl.card_import import (_allowlist_gate, _apply_pins, _assert_emittable,  # noqa: E402
                                 _diff_stats, _parse_card, _variant_key, _write_guard)

WC = ROOT.parents[0] / "research" / "sim_parity" / "webcache"


def _allow():
    return json.loads((ROOT / "config" / "import_allowlist.json")
                      .read_text(encoding="utf-8"))["allow"]


def _pins():
    return json.loads((ROOT / "config" / "import_pins.json")
                      .read_text(encoding="utf-8"))["pins"]


def _page(name: str) -> str:
    f = WC / (name + ".wikitext")
    if not f.exists():
        raise unittest.SkipTest("archived wikitext not present in this checkout")
    return f.read_text(encoding="utf-8")


class HeroPageParseTests(unittest.TestCase):
    """Body stats off archived /Hero pages -- the numbers are read straight off the pages."""

    def test_knight_hero_body_stats(self):
        e = _parse_card("Knight/Hero", _page("Knight_Hero"))
        self.assertEqual(e.get("elixir"), 3)
        self.assertEqual(e.get("rarity"), "common")
        self.assertEqual(e.get("kind"), "troop")
        self.assertEqual(e.get("hitpoints"), 1766)
        self.assertEqual(e.get("damage"), 202)
        self.assertEqual(e.get("hit_speed"), 1.2)
        self.assertEqual(e.get("count"), 1)
        # ability numerics live in the SECOND table / prose; they must stay absent for I8
        self.assertNotIn("ability_cost", e)

    def test_balloon_hero_ability_table_is_not_a_second_body(self):
        e = _parse_card("Balloon/Hero", _page("Balloon_Hero"))
        self.assertEqual(e.get("count"), 1, "MEASURED BEFORE: 2 (the Skeletrooper ability "
                                            "table carries Cost+Count+Transport)")
        self.assertEqual(e.get("movement"), "air")
        self.assertEqual(e.get("hitpoints"), 1679)

    def test_tombstone_hero_is_a_building_with_spawner_stats(self):
        e = _parse_card("Tombstone/Hero", _page("Tombstone_Hero"))
        self.assertEqual(e.get("kind"), "building")
        self.assertEqual(e.get("lifetime_s"), 30.0)
        self.assertEqual(e.get("spawn_interval_s"), 4.0)


class AllowlistTests(unittest.TestCase):
    """The importer does not invent content."""

    def test_variant_keys(self):
        self.assertEqual(_variant_key("Zap/Evolution"), "zap_evo")
        self.assertEqual(_variant_key("Mini P.E.K.K.A./Hero"), "mini_pekka_hero")
        self.assertIsNone(_variant_key("Knight"))

    def test_announced_hero_stub_does_not_produce_a_row(self):
        # The real stub page parses to an empty shell...
        try:
            wt = _page("Mega_Knight_Hero")
        except unittest.SkipTest:
            wt = "Coming soon... Release Date: 7th September 2026"   # the stub, verbatim shape
        entry = _parse_card("Mega Knight/Hero", wt)
        self.assertNotIn("hitpoints", entry)
        # ...and the allowlist gate keeps it out of the import entirely, naming WHY.
        keep, excluded = _allowlist_gate(["Knight", "Knight/Hero", "Mega Knight/Hero"], _allow())
        self.assertEqual(keep, ["Knight", "Knight/Hero"])
        self.assertEqual(len(excluded), 1)
        page, key, status, date = excluded[0]
        self.assertEqual((page, key, status), ("Mega Knight/Hero", "mega_knight_hero",
                                               "announced"))
        self.assertEqual(date, "2026-09-07")

    def test_unknown_variant_is_a_hard_stop(self):
        # Werewolf/Evolution is a known upcoming-content stub (4/10/2026) NOT in the registry.
        with self.assertRaises(SystemExit) as cm:
            _allowlist_gate(["Werewolf/Evolution"], _allow())
        self.assertIn("werewolf_evo", str(cm.exception))
        self.assertIn("does not invent content", str(cm.exception))

    def test_emission_guard_names_the_status(self):
        allow = _allow()
        with self.assertRaises(SystemExit) as cm:
            _assert_emittable("mega_knight_hero", allow)
        msg = str(cm.exception)
        self.assertIn("announced", msg)
        self.assertIn("2026-09-07", msg)
        with self.assertRaises(SystemExit) as cm2:
            _assert_emittable("werewolf_evo", allow)
        self.assertIn("unknown", str(cm2.exception))
        # live keys and base cards pass silently
        _assert_emittable("knight_hero", allow)
        _assert_emittable("elite_barbarians_evo", allow)
        _assert_emittable("knight", allow)

    def test_api_forward_declared_ghosts_are_excluded_not_fatal(self):
        # berserker_evo/giant_evo: the official API forward-declares them, the wiki has no
        # page. If a page ever appears, the gate must EXCLUDE it (status named), not import.
        keep, excluded = _allowlist_gate(["Berserker/Evolution"], _allow())
        self.assertEqual(keep, [])
        self.assertEqual(excluded[0][1:3], ("berserker_evo", "api_forward_declared_no_wiki_page"))


class PinTests(unittest.TestCase):
    """Curated values survive import; --write refuses a regression."""

    def test_round_trip_stale_rocket_comes_out_pinned(self):
        out = {"rocket": {"damage": 1484, "crown_tower_damage": 371}}     # the 2026-08-14 rollback
        applied = _apply_pins(out, _pins())
        self.assertEqual(out["rocket"]["crown_tower_damage"], 341)
        self.assertIn(("rocket", "crown_tower_damage", 371, 341), applied)

    def test_pinned_regression_refuses_write(self):
        pins = _pins()
        bad = {"rocket": {"damage": 1484, "crown_tower_damage": 371}}     # post-pass bypassed
        viol = _write_guard(bad, {"rocket": {"crown_tower_damage": 341}}, pins, set())
        self.assertTrue(any("rocket.crown_tower_damage" in v and "371" in v for v in viol), viol)
        # --force-field releases exactly that field
        self.assertEqual(_write_guard(bad, {}, pins, set(),
                                      frozenset({"rocket.crown_tower_damage"})), [])

    def test_dropped_pinned_field_refuses_write(self):
        pins = _pins()
        viol = _write_guard({"rocket": {"damage": 1484}},                 # scrape lost the field
                            {"rocket": {"crown_tower_damage": 341}}, pins, set())
        self.assertTrue(any("DROPS" in v for v in viol), viol)

    def test_null_pin_removes_the_field(self):
        # ability_cooldown_s: dead numbers under the 4/8/2026 single-use rework -- pinned ABSENT
        out = {"archer_queen": {"hitpoints": 1000, "ability_cooldown_s": 17.0}}
        _apply_pins(out, _pins())
        self.assertNotIn("ability_cooldown_s", out["archer_queen"])

    def test_advisory_pins_do_not_touch_structured_fields(self):
        # barbarian_hut's pin value is the '670/192/1.3' shorthand; the imported field is a dict
        out = {"barbarian_hut": {"spawn_unit_stats": {"range_tiles": 0.8}}}
        _apply_pins(out, _pins())
        self.assertEqual(out["barbarian_hut"]["spawn_unit_stats"], {"range_tiles": 0.8})

    def test_verified_row_guard_and_pin_precedence(self):
        pins = _pins()
        # a verified: true row changing refuses...
        viol = _write_guard({"knight": {"damage": 220}}, {"knight": {"damage": 202}},
                            pins, {"knight"})
        self.assertTrue(any("VERIFIED knight.damage" in v for v in viol), viol)
        # ...but a change the pin post-pass itself made is allowed (pins outrank verified)
        self.assertEqual(_write_guard({"earthquake": {"damage": 81}},
                                      {"earthquake": {"damage": 84}}, pins, {"earthquake"}), [])

    def test_dps_recomputed_when_a_pin_moves_hit_speed(self):
        """A hit_speed pin drags the derived dps with it -- for a key with no dps pin of its own.

        `giant_skeleton` is that case in the live pins file: hit_speed is pinned, dps is not.
        """
        out = {"giant_skeleton": {"damage": 276, "hit_speed": 1.4, "dps": 197}}
        _apply_pins(out, _pins())
        self.assertEqual(out["giant_skeleton"]["hit_speed"], 1.3)
        self.assertEqual(out["giant_skeleton"]["dps"], round(276 / 1.3))

    def test_an_explicit_dps_pin_beats_the_derived_recompute(self):
        """I5: pins apply in (key, field) order, so "hit_speed" lands AFTER "dps".

        Before this rule a hit_speed pin silently overwrote the key's OWN dps pin with
        round(damage/hit_speed) -- an alphabetical accident deciding an adjudicated value. Mortar
        pins both (hit_speed 4.7 from decisions.md #10, dps 57 from the LAG bucket), so it is the
        live case: the explicit pin must survive.
        """
        out = {"mortar": {"damage": 230, "hit_speed": 5.0, "dps": 46}}
        _apply_pins(out, _pins())
        self.assertEqual(out["mortar"]["hit_speed"], 4.7)
        self.assertEqual(out["mortar"]["dps"], 57)          # the pin, not round(230/4.7) = 49

    def test_force_field_releases_the_dps_pin_back_to_the_recompute(self):
        out = {"mortar": {"damage": 230, "hit_speed": 5.0, "dps": 46}}
        _apply_pins(out, _pins(), force=frozenset({"mortar.dps"}))
        self.assertEqual(out["mortar"]["dps"], round(230 / 4.7))


class DiffTests(unittest.TestCase):
    def test_src_metadata_is_not_a_stat_diff(self):
        old = {"knight": {"damage": 202, "_src": {"revid": 1, "fetched": "2026-08-14"}}}
        new = {"knight": {"damage": 202, "_src": {"revid": 2, "fetched": "2026-08-26"}}}
        d = _diff_stats(old, new)
        self.assertEqual(d["changed"], {})

    def test_field_level_diff(self):
        d = _diff_stats({"a": {"x": 1}, "b": {"y": 2}}, {"a": {"x": 3}, "c": {"z": 4}})
        self.assertEqual(d["added"], ["c"])
        self.assertEqual(d["removed"], ["b"])
        self.assertEqual(d["changed"], {"a": {"x": (1, 3)}})


if __name__ == "__main__":
    unittest.main()
