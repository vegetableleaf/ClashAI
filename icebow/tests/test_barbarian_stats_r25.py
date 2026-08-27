"""RULING 25 / 27 -- one Barbarian, 716 hitpoints, and the barrel's crown damage.

BYTE-IDENTICAL in icebow and hogeq (parity_check enforces it).

RULING 25 (owner, IN-GAME 2026-08-27): "a Barbarian has 716 hp at level 11", and "the barbarian
spawned by the barrel should have the same stats as normal barbarians."

⚠ THIS IS NOT THE OWNER AGAINST THE WIKI, and the brief's framing of it ("the wiki agrees with the
stale number, so stat_sweep reported these rows as MATCHING and could never have flagged them") is
not what the data says. `stat_sweep` HAD been flagging `barbarians_evo hp ours 691 / wiki 716` all
along, and I5 pinned it with the note "WIKI IS SELF-INCONSISTENT. The 4/8/2026 rule is 'Evo HP =
base HP', yet the Evo page says 716 and the base page says 691; both cannot be right." The number
was flagged; what was missing was the tie-break. Three published facts line up behind 716:

    Barbarians (revid 437362)            hp_11 691   history: "On 4/8/2026 ... increased the
                                                     Barbarians' hitpoints by 4%"  <- never applied
    Barbarians/Evolution (revid 437363)  hp_11 716   history: "On 4/8/2026 ... REMOVED the Evolved
                                                     Barbarians' Extra Hitpoints" -> Evo == base
    Barbarian Barrel/Hero (revid 437523) hp_11 716

716 for BOTH is the only assignment that satisfies the 4/8/2026 rule, and once it is applied the
evo row stops being a deviation at all.

MEASURED BEFORE -> AFTER:

    key                      hp          damage        hit_speed
    barbarians               691 -> 716  191 (kept)    1.4 (kept)
    barbarians_evo           691 -> 716  191 (kept)    1.4 (kept)
    base_barrel_barbarian    670 -> 716  191 (kept)    1.3 -> 1.4
    barrel_barbarian         716 (kept)  192 -> 191    1.3 -> 1.4
    barbarian_hut's spawned body: 691 -> 716 each, x3 (inherited, no direct edit)

The 1.3 -> 1.4 is the 2/3/2026 balance entry on the Barbarians page ("increased their attack speed
to 1.4 seconds (from 1.3 seconds)") that neither barrel page ever applied -- the base barrel row's
old comment said its own vardefine "says 1.3 too, so ... there is nothing to reconcile here", which
was true and stale together.

RULING 27: the base `barbarian_barrel` row published NO crown value, so `build_spec`'s
`dmg if _td is None` fallback handed it its FULL 230 damage against a Crown Tower. The published
figure is 116 (`rerolldmg_11` -- the Crown Tower Damage column, not a reroll penalty: 116/232 is the
ordinary 50% reduction).
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for _p in (str(ROOT / "src"), str(ROOT / "tests")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from test_sim_status_effects import _make_engine                        # noqa: E402
from clashrl.sim.engine import build_spec                               # noqa: E402

LVL = 11
HP = 716.0
HIT_DMG = 190.4          # dps 136 x hit_speed 1.4; the engine rebuilds hit_dmg from those two
HIT_SPEED = 1.4
BODIES = ("barbarians", "base_barrel_barbarian", "barrel_barbarian")


class OneBarbarianTests(unittest.TestCase):

    def setUp(self):
        self.db = _make_engine().db

    def test_every_barbarian_body_has_the_same_716_hitpoints(self):
        for k in BODIES + ("barbarians_evo",):
            with self.subTest(card=k):
                self.assertAlmostEqual(HP, build_spec(self.db, k, LVL).hp, places=1)

    def test_the_barrel_bodies_are_numerically_a_NORMAL_barbarian(self):
        """The ruling in one assertion: both barrel bodies and the card build to the same numbers.
        Before: 670/191.1/1.3 (base) and 716/192.4/1.3 (hero) against the card's 691/190.4/1.4 --
        three different Barbarians."""
        card = build_spec(self.db, "barbarians", LVL)
        for k in ("base_barrel_barbarian", "barrel_barbarian"):
            with self.subTest(card=k):
                b = build_spec(self.db, k, LVL)
                self.assertAlmostEqual(card.hp, b.hp, places=1)
                self.assertAlmostEqual(card.hit_dmg, b.hit_dmg, places=1)
                self.assertAlmostEqual(card.hit_speed, b.hit_speed, places=3)
                self.assertEqual(1, b.count, "the barrel drops ONE; the card fields five")
        self.assertEqual(5, card.count)

    def test_the_2_3_2026_attack_speed_buff_reached_both_barrel_rows(self):
        for k in BODIES:
            with self.subTest(card=k):
                self.assertAlmostEqual(HIT_SPEED, build_spec(self.db, k, LVL).hit_speed, places=3)
                self.assertAlmostEqual(HIT_DMG, build_spec(self.db, k, LVL).hit_dmg, delta=0.3)

    def test_the_SECOND_copy_of_hit_speed_moved_too(self):
        """`spawn_unit_stats` on the barrel rows carries its own `hit_speed`, and a stale 1.3 left
        there would silently override the body row -- the whole reason it is checked separately."""
        for k in ("barbarian_barrel", "barbarian_barrel_hero"):
            with self.subTest(card=k):
                row = self.db.get(k) or {}
                sus = row.get("spawn_unit_stats")
                if sus is None:                          # the hero row inherits the base's block
                    sus = (self.db.get("barbarian_barrel") or {}).get("spawn_unit_stats") or {}
                self.assertAlmostEqual(HIT_SPEED, float(sus.get("hit_speed")), places=3)

    def test_the_barbarian_HUT_inherits_the_fix_without_being_edited(self):
        """It spawns `barbarians` x3, so the hut needs no direct change -- but "it inherits" is a
        claim about the resolution order, and the resolution order is worth a test."""
        hut = build_spec(self.db, "barbarian_hut", LVL)
        self.assertIsNotNone(hut.spawner_spec)
        self.assertEqual("barbarians", hut.spawner_spec.key)
        self.assertAlmostEqual(HP, hut.spawner_spec.hp, places=1,
                               msg="the hut's spawned body was 691, now 716, x%d" % hut.spawner_count)
        self.assertEqual(3, hut.spawner_count)

    def test_the_evolution_and_the_base_now_AGREE_which_is_what_4_8_2026_requires(self):
        """"On 4/8/2026, a Balance Update, REMOVED the Evolved Barbarians' Extra Hitpoints" -- from
        that date Evo HP == base HP. I5 could not satisfy it (691 vs 716, "both cannot be right");
        at 716 it holds, and the sweep's `barbarians_evo hp` deviation disappears entirely."""
        self.assertAlmostEqual(build_spec(self.db, "barbarians", LVL).hp,
                               build_spec(self.db, "barbarians_evo", LVL).hp, places=1)

    def test_the_two_barrel_body_rows_stay_SEPARATE(self):
        """They are numerically identical now and deliberately still two rows: two wiki pages, two
        revids, two `_src` provenances, and the hero page has diverged before -- it carried 716
        while the base carried 670, and it was the RIGHT one. One row would make the next
        divergence invisible instead of loud."""
        self.assertIsNot(self.db.get("base_barrel_barbarian"), self.db.get("barrel_barbarian"))
        self.assertEqual("base_barrel_barbarian",
                         build_spec(self.db, "barbarian_barrel", LVL).spawn_spec.key)
        self.assertEqual("barrel_barbarian",
                         build_spec(self.db, "barbarian_barrel_hero", LVL).spawn_spec.key)


class BarrelCrownDamageTests(unittest.TestCase):
    """RULING 27. A missing crown value is not zero here -- it falls back to the FULL damage."""

    def test_the_barrel_chips_a_tower_for_116_and_not_for_its_full_230(self):
        db = _make_engine().db
        base = build_spec(db, "barbarian_barrel", LVL)
        self.assertAlmostEqual(230.0, base.spell_dmg, places=1)
        self.assertAlmostEqual(116.0, base.spell_tower_dmg, places=1,
                               msg="MEASURED BEFORE: 230.0, the `dmg if _td is None` fallback")
        hero = build_spec(db, "barbarian_barrel_hero", LVL)
        self.assertAlmostEqual(232.0, hero.spell_dmg, places=1)
        self.assertAlmostEqual(116.0, hero.spell_tower_dmg, places=1)

    def test_it_really_only_takes_116_off_a_tower(self):
        eng = _make_engine()
        tw = eng.towers[1][0]
        tw.hit_dmg = 0.0
        hp0 = tw.hp
        from clashrl.sim.engine import _Spell
        sp = build_spec(eng.db, "barbarian_barrel", LVL)
        eng._resolve_spell(_Spell(0, tw.x, tw.y + 2.0 / 32.0, sp, 0.0))
        for _ in range(80):
            eng.advance(0.05)
            if not eng.rolls:
                break
        self.assertAlmostEqual(116.0, hp0 - tw.hp, places=1)


class PinsAreRegisteredTests(unittest.TestCase):
    """A curated value that is not pinned is a value the next import silently reverts, and the
    sweep derives its whole "deliberate deviation" list from the same file."""

    def test_every_changed_field_is_pinned_in_both_decks(self):
        import json
        want = {("barbarians", "hitpoints"): 716,
                ("barbarians_evo", "hitpoints"): 716,
                ("base_barrel_barbarian", "hitpoints"): 716,
                ("base_barrel_barbarian", "damage"): 191,
                ("base_barrel_barbarian", "hit_speed"): 1.4,
                ("barrel_barbarian", "hitpoints"): 716,
                ("barrel_barbarian", "damage"): 191,
                ("barrel_barbarian", "hit_speed"): 1.4,
                ("barbarian_barrel", "crown_tower_damage"): 116,
                ("barbarian_barrel", "roll_speed"): 200}
        pins = json.loads((ROOT / "config" / "import_pins.json").read_text(encoding="utf-8"))
        got = {(p["key"], p["field"]): p["value"] for p in pins["pins"]}
        for k, v in want.items():
            with self.subTest(pin=k):
                self.assertIn(k, got, "%s.%s is curated but not pinned" % k)
                self.assertAlmostEqual(float(v), float(got[k]), places=3)

    def test_the_superseded_691_is_GONE_from_the_pin_registry(self):
        """I5 pinned `barbarians_evo.hitpoints` to 691. Ruling 25 supersedes it, and a pin registry
        holding both values would be a registry that reverts the ruling on the next import."""
        import json
        pins = json.loads((ROOT / "config" / "import_pins.json").read_text(encoding="utf-8"))
        for p in pins["pins"]:
            if p["key"] == "barbarians_evo" and p["field"] == "hitpoints":
                self.assertEqual(716, p["value"])


if __name__ == "__main__":                                   # pragma: no cover
    unittest.main()
