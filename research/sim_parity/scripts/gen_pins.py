"""Generate config/import_pins.json (both decks) from the adjudicated R2 ledger.

    python research/sim_parity/scripts/gen_pins.py            # write both decks' copies
    python research/sim_parity/scripts/gen_pins.py --check    # exit 1 if they disagree

`--check` writes nothing and FAILS when a committed pins file differs from what this
script produces. It exists because ruling 31a hand-edited config/import_pins.json and did
NOT touch this generator: the value looked set, and the next gen_pins.py run would have
silently reverted it. That failure class -- a value that looks set, behind a regeneration
step that quietly undoes it -- has cost this project repeatedly, so the disagreement is now
an exit code and a unit test (tests/test_card_import_guards.py,
PinTests.test_the_generator_reproduces_the_committed_pins) instead of a convention.

A PIN is a curated value the wiki is known to lag or contradict: the importer applies
pins as a post-pass over the scraped rows, and `--write` refuses if a pinned field
would regress (PLAN.md I4 "Curated values survive import"). Sources, in order:

  1. every ledger/stat_diffs.jsonl row with verdict "pin" (66 rows, R2 sweep) --
     value = the row's current_db (the curated value the sweep upheld);
  2. the owner rulings in decisions.md (2026-08-26 R2 ADJUDICATION) that assert a
     specific number, including the 5 balance-lag crown pins the sweep re-derived;
  3. I5 (2026-08-26): every row of `ledger/i5_plan.json` that i5_apply.py routed to the
     IMPORT layer. These are the adjudicated corrections the wiki would otherwise undo
     on the next scrape -- the whole CROWN family, the proven-lag reconstructions, the
     floor()-convention DPS values, and the parent/child stat swaps. Without them the
     import re-writes the stale number and I5 silently unwinds itself.

Where both name the same (key, field) the stat_diffs row wins the provenance slot and
the script asserts the values agree -- a disagreement would mean the ledger and the
rulings diverged, which is a stop-and-investigate, not a merge.

Pin schema: {key, field, value, source, date}. `value: null` means "this field must
NOT be imported" (e.g. the champion ability_cooldown_s entries -- dead numbers under
the 4/8/2026 single-use rework, decisions.md "Still open"). Fields the importer does
not emit (cards.yaml-curated values like spark_dps_small, composite fields like
`spawns.delay`) are ADVISORY here: recorded for I5's stat_sweep EXPECTED sync, no-ops
in the importer post-pass.

The file is a byte-identical pair; this script writes both decks' copies and verifies.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
LEDGER = ROOT / "research" / "sim_parity" / "ledger"
DECKS = ("icebow", "hogeq")

# decisions.md 2026-08-26 R2 ADJUDICATION -- owner-verified values that must survive
# any re-import. (key, field, value, which ruling).
# Shared source for the four Electro Dragon pins below. Long, because the whole case for holding
# a number against a live wiki value has to travel with the pin.
_ED15 = (
    "decisions.md ruling 15 (OWNER, in-game 2026-08-26): the Electro Dragon deals 192 @L11, not "
    "the 267 both wiki pages publish. Three independent supports: (a) the Evolution page's own "
    "`late_dmg_11 = 64` -- its level table's 'Damage after 5 chains' column -- reproduces exactly "
    "from 192 through its two dated chain nerfs (192 x 0.67 on 8/1/2025 'damage after the first "
    "3 chains -33%' x 0.50 on 2/3/2026 'chain damage -50%' = 64.3 -> 64) and NOT from 267 "
    "(-> 89); (b) webcache/Electro_Dragon.rev436720.wikitext publishes `dmg_11 | 192`, so 192 is "
    "this page's own older value rather than an unsourced reading; (c) the page's stat block has "
    "drifted far past what its History documents -- hp_11 949 -> 1383 -> 1451 (+53%) against "
    "History entries recording only two +5% buffs. The competing reading (267 live, late_dmg_11 "
    "stale) is recorded in conflicts.md, not discarded. dps is the quotient 192/2.3 because "
    "build_spec rebuilds per-hit damage as dps * hit_speed"
)


DECISION_PINS = [
    ("mighty_miner", "ability_bomb_damage", 332,
     "decisions.md #9: rarity-floor anchor, wiki integer base 332 @ L11 reproduces the "
     "owner's observed 440 @ L14; replaces the 366 reverse-derivation"),
    ("firecracker_evo", "spark_dps_small", 48,
     "decisions.md #5: wiki correct for ALL firecracker_evo entries; owner overturned "
     "the old verified 60 (closes the long-flagged spark_dps_small conflict)"),
    ("earthquake", "damage", 81,
     "decisions.md #5: earthquake damage = 81 @ L11, not 84 (overrides the 2026-08 "
     "HANDOFF card-data row)"),
    ("tesla_evo", "hitpoints", 1182,
     "decisions.md #5: tesla_evo hitpoints = base = 1182 @ L11 (evo hp same as base)"),
    ("cannon_evo", "volley_damage", 281,
     "decisions.md #9: cannon_evo volley damage 281 @ L11 (nerfed; wiki vardefine "
     "lags at 304)"),
    # I8 (2026-08-27): the SAME parent/child field swap I5 already pinned on the BASE barbarian
    # barrel, now on its hero row. On a spell row `damage:` is the ROLL's area damage, which the
    # page renders from spawn_11 (232 on Barbarian Barrel/Hero, revid 437523); dmg_11 192 is the
    # spawned Barbarian's own swing and lives on the curated `barrel_barbarian` row. Without this
    # pin the hero barrel would roll for LESS than the base card, and stat_sweep reported it as a
    # live MISMATCH (ours 232 vs wiki 192) rather than the known deviation it is.
    ("barbarian_barrel_hero", "damage", 232,
     "I8: parent/child swap, same as the base card's pin -- 'Barbarian Barrel Area Damage' "
     "renders from spawn_11 (232); dmg_11 192 is the spawned Barbarian's swing"),
    ("mortar", "hit_speed", 4.7, "decisions.md #10: mortar AND mortar_evo hit speed 4.7 s"),
    ("mortar_evo", "hit_speed", 4.7,
     "decisions.md #10: mortar AND mortar_evo hit speed 4.7 s"),
    # The 5 balance-lag crown pins (post-1/6/2026 percentages; wiki vardefines lag their
    # own balance history -- tools/crown_damage_audit.py is the detector).
    ("rocket", "crown_tower_damage", 341,
     "decisions.md balance-lag pin: 1/6/2026 set 23% of full; 1484 * 0.23 = 341.32 -> 341 "
     "(cards.yaml's 342 is off by one against this pin -- I5 applies 341)"),
    ("lightning", "crown_tower_damage", 264, "decisions.md balance-lag pin (post-1/6/2026)"),
    ("zap", "crown_tower_damage", 48, "decisions.md balance-lag pin (post-1/6/2026)"),
    ("the_log", "crown_tower_damage", 35, "decisions.md balance-lag pin (post-1/6/2026)"),
    ("poison", "crown_tower_damage", 21, "decisions.md balance-lag pin (post-1/6/2026)"),
    # I5: the third of I4's predicted --force-field refusals. Unlike the two mortar dps rows this
    # one is a cards_stats-layer HYGIENE fix, not a merged-DB change -- cards.yaml has curated
    # `rage: {attacks: [air, ground]}` since d8fc808, so the stale ['buildings'] was already
    # shadowed. Pinned null so the importer stops re-asserting it.
    ("rage", "attacks", None,
     "I5: the imported ['buildings'] was a FALSE buildings-only assertion -- the wiki's Target "
     "cell 'Friendly Troops & Buildings' names who Rage BUFFS, not who it attacks (root cause "
     "fixed in card_import by d8fc808). Released with --force-field rage.attacks on the I5 "
     "--write and pinned null here"),
    # I7 / decisions.md ruling 15 (owner, in-game 2026-08-26). The wiki publishes dmg_11 267 on
    # BOTH the base and the Evolution page and the R2 sweep re-fetched it live, so these four are
    # a deliberate deviation and the importer must never pull them back.
    ("electro_dragon", "damage", 192, _ED15),
    ("electro_dragon", "dps", 83.478, _ED15),
    ("electro_dragon_evo", "damage", 192, _ED15),
    ("electro_dragon_evo", "dps", 83.478, _ED15),
]
DECISION_DATE = "2026-08-26"

# decisions.md ruling 19 (OWNER, 2026-08-27) -- SPAWNED-BODY ELIXIR PRICES.
# ⚠ THE POINTER DOES NOT RESOLVE, and the values are fine: decisions.md heads this ruling
# "RULING 29" (and commit d9b20d6 calls it 29), while conflicts.md, this block and the `source`
# string of all three pins below call it 19. There is no "ruling 19" heading in decisions.md.
# Same ruling, two numbers; recorded in conflicts.md 2026-08-27 rather than renumbered, because
# renumbering rewrites three GENERATED source strings for a labelling error. Prefer 29 in new text.
# 25 KB keys carry no `elixir` and every one of them fell through to the engine's default of 4, so
# a Goblin Barrel decoy goblin and a Golemite each read as 4 elixir of enemy investment -- the same
# as a Knight -- through the ~30 `spec.elixir` reads in the reward and triage layers. The owner
# priced three of them; the other 22 are in conflicts.md's owner checklist.
# THE SKELETON KING'S IS A TOTAL, NOT A PER-BODY PRICE, and that is the whole trap in the ruling:
# 3 elixir buys the WHOLE full-charge activation. A full charge is `ability_spawn_count` 6 plus
# `_SOUL_CAP` 10 = 16 Skeletons, so the per-body share is 3 / 16 = 0.1875 and MEASURED the full
# summon totals exactly 3.0000. (Not 3 / max_souls = 0.3, which the ruling offered as a formula:
# 16 x 0.3 = 4.80, 60% over the intended number. The divisor is the spawn COUNT, not the bar.)
# These are pinned rather than merely curated because a re-import that emitted an elixir for a
# spawned body would otherwise silently take them back to null -> 4. Pins outrank `verified`, which
# is what lets magic_archer_decoy keep `verified: false` on a row whose damage and hit speed are
# still open questions while its elixir is owner-ruled.
RULING19_PINS = [
    ("magic_archer_decoy", "elixir", 2,
     "decisions.md ruling 19 (OWNER 2026-08-27): the Hero Magic Archer's Triple Threat decoy is "
     "worth 2 elixir. ONE decoy per activation, so the per-body price is the activation price"),
    ("guardienne", "elixir", 3,
     "decisions.md ruling 19 (OWNER 2026-08-27): the Little Prince's Royal Rescue guardian is "
     "worth 3 elixir. ONE body per activation, so the per-body price is the activation price"),
    ("soul_skeleton", "elixir", 0.1875,
     "decisions.md ruling 19 (OWNER 2026-08-27): the Skeleton King's Skeletons are worth 3 elixir "
     "AT FULL CHARGE -- for the WHOLE summon, not each body. Full charge = ability_spawn_count 6 "
     "+ _SOUL_CAP 10 = 16 Skeletons, so 3 / 16 = 0.1875 per body and the full summon MEASURES "
     "exactly 3.0000. NOT 3 / max_souls (0.3), which would total 4.80"),
]
RULING19_DATE = "2026-08-27"

# RULING 22 (owner, 2026-08-27) -- the Barbarian Barrel's ROLL SPEED is 200, the same as The Log's.
# Ruling 21 made `roll_speed` load-bearing: a rolling spell now SWEEPS its corridor over time at
# roll_speed / 60 tiles per second instead of resolving it in one frame, so a card that publishes
# no speed falls back to the old instantaneous behaviour. The Log publishes 200 (20/10/2016, "its
# projectile speed to 200 (from 170)") and the Evo Snowball 300; the Barbarian Barrel page
# publishes NOTHING -- no speed cell in either attributes table and no history entry that ever set
# one -- which is exactly why this has to be a pin rather than a curation. An import would emit the
# row without the field and silently return the barrel to an instant corridor.
RULING22_PINS = [
    ("barbarian_barrel", "roll_speed", 200,
     "decisions.md ruling 22 (OWNER 2026-08-27): the Barbarian Barrel rolls at 200, as The Log "
     "does. ABSENT UPSTREAM -- the card page publishes no roll/projectile speed at all -- so "
     "without this pin a re-import would drop it and ruling 21's swept corridor would degrade "
     "back to an instant one for this card only"),
]
RULING22_DATE = "2026-08-27"

# RULING 31a (owner, 2026-08-27) -- the Electro Giant's "Reflected Tower Damage" is the ZAP PACK's
# figure, not his swing's. I5 parked the page's crown_11 = 97 on the generic `crown_tower_damage`,
# where build_spec fed it to `tower_hit_dmg` and crown-reduced his NORMAL swing to 97 (measured,
# against hit_dmg 163.8 @ L11). It now lives on its own `reflect_crown_damage`, consumed only by
# SimEngine._zap_pack's tower branch.
#
# ⚠ RECORDED HERE 2026-08-27 BECAUSE b4be2b7 HAND-EDITED import_pins.json AND DID NOT TOUCH THIS
# GENERATOR. Running gen_pins.py silently reverted ruling 31a's pin to the I5 row; the pair only
# stays honest if every ruling lands in the generator, which is what the file's own meta claims
# ("never hand-edit one copy"). Found by regenerating for ruling 31b.
RULING31A_PINS = [
    ("electro_giant", "reflect_crown_damage", 97,
     "I5 apply (CROWN, curated) re-plumbed by ruling 31a 2026-08-27: crown_11 = 97 is the page's "
     "'Reflected Tower Damage' column -- the ZAP PACK's reduced figure, not his swing's. Parked "
     "on the generic crown_tower_damage it fed build_spec's tower_hit_dmg and crown-reduced his "
     "NORMAL swing to 97 (measured, vs hit_dmg 163.8 @ L11); it now lives on "
     "reflect_crown_damage, consumed only by SimEngine._zap_pack's tower branch"),
]
RULING31A_DATE = "2026-08-27"
# The I5 row ruling 31a RETIRES: the field itself is gone from cards.yaml, so the pin must not
# come back on the old name.
RULING31A_DROPS = {("electro_giant", "crown_tower_damage")}

# RULING 31b (owner, 2026-08-27) -- the Evo Firecracker's PRIMARY spark (the zone left at the MAIN
# projectile's impact point) is 2.5 tiles; the SECONDARY shrapnel sparks are 1.2. OWNER-SUPPLIED,
# and they agree exactly with the wiki's own Evolution Attributes table row (Firecracker/Evolution
# revid 437259: Big Spark Radius 2.5 / Small Spark Radius 1.2). The agreement is why both numbers
# ship; the OWNER is the recorded authority, per the project's order (owner in-game > wiki > API).
#
# WHY A PIN AND NOT ONLY A CURATION. Those radii live in a wikitext TABLE CELL, not in a
# `{{#vardefine:}}`, and the importer reads vardefines -- so a re-import emits the row with no
# radius at all and both fields silently vanish, returning every zone to the engine's hardcoded
# 0.75 fallback. ADVISORY because the importer cannot act on a field it never emits; recording
# them here is what lets tools/stat_sweep.py read ONE registry of deliberate values.
RULING31B_PINS = [
    ("firecracker_evo", "spark_radius_large_tiles", 2.5,
     "decisions.md ruling 31b (OWNER 2026-08-27): the PRIMARY spark, at the main projectile's "
     "impact point, has radius 2.5 tiles -- larger than the shrapnel sparks. Owner-supplied and "
     "matched by the page's Evolution Attributes table (Big Spark Radius 2.5). ABSENT FROM THE "
     "VARDEFINES -- table cell only -- so an import drops it and the engine falls back to 0.75"),
    ("firecracker_evo", "spark_radius_tiles", 1.2,
     "decisions.md ruling 31b (OWNER 2026-08-27): the SECONDARY shrapnel sparks are 1.2 tiles. "
     "Owner-supplied and matched by the page's Evolution Attributes table (Small Spark Radius "
     "1.2). SUPERSEDES the curated 0.75, a relic of the old zones-along-the-path model, which "
     "made every secondary zone 2.56x too small in area as well. Table cell only, so pinned"),
]
RULING31B_DATE = "2026-08-27"

# RULING 25 (owner, IN-GAME 2026-08-27) -- a Barbarian has 716 hitpoints at level 11, and the body
# the Barbarian Barrel drops is a NORMAL Barbarian.
#
# THIS IS NOT THE OWNER AGAINST THE WIKI. It is the owner breaking a tie the wiki has with itself,
# and I5 recorded that tie without being able to settle it: `barbarians_evo.hitpoints` is pinned
# 691 with the note "WIKI IS SELF-INCONSISTENT. The 4/8/2026 rule is 'Evo HP = base HP', yet the
# Evo page says 716 and the base page says 691; both cannot be right." Three pieces of published
# evidence line up behind 716:
#   * Barbarians history: "On 4/8/2026, a Balance Update, increased the Barbarians' hitpoints by
#     4%" -- a buff its own `hp_11` vardefine (691) never received;
#   * Barbarians/Evolution (revid 437363) `hp_11 716`, with "On 4/8/2026 ... REMOVED the Evolved
#     Barbarians' Extra Hitpoints", i.e. Evo HP == base HP from that date;
#   * Barbarian Barrel/Hero (revid 437523) `hp_11 716` for the body it drops.
# Setting BOTH to 716 is the only assignment that satisfies the 4/8/2026 rule.
#
# The barrel bodies also carry the 2/3/2026 attack-speed buff their own pages never applied
# ("increased their attack speed to 1.4 seconds (from 1.3 seconds)"), and take the `barbarians`
# card's damage 191 so the barrel drops a Barbarian and not a 0.5%-stronger one.
_R25 = ("decisions.md ruling 25 (OWNER IN-GAME 2026-08-27): a Barbarian has 716 hp at L11 and the "
        "barrel drops a NORMAL Barbarian. The base page's own history carries a 4/8/2026 +4% hp "
        "buff its hp_11 never received, while Barbarians/Evolution and Barbarian Barrel/Hero both "
        "print 716; 2/3/2026 moved the attack speed to 1.4 s and neither barrel page followed")
RULING25_PINS = [
    ("barbarians", "hitpoints", 716, _R25),
    ("barbarians_evo", "hitpoints", 716,
     _R25 + " -- this SUPERSEDES I5's 691, which was held only because the tie could not be "
            "broken; at 716 both pages agree and 4/8/2026's 'Evo HP = base HP' holds"),
    ("base_barrel_barbarian", "hitpoints", 716, _R25 + " (was 670, two balance updates behind)"),
    ("base_barrel_barbarian", "damage", 191, _R25),
    ("base_barrel_barbarian", "dps", 136, _R25 + " -- consequential: 191 / 1.4 = 136.4 -> 136"),
    ("base_barrel_barbarian", "hit_speed", 1.4, _R25),
    ("barrel_barbarian", "hitpoints", 716, _R25 + " (already 716; the owner's reading confirms it)"),
    ("barrel_barbarian", "damage", 191, _R25 + " (was 192, the hero page's own vardefine)"),
    ("barrel_barbarian", "dps", 136, _R25 + " -- consequential: 191 / 1.4 = 136.4 -> 136"),
    ("barrel_barbarian", "hit_speed", 1.4, _R25 + " (was 1.3 from the page's Barbarian Attributes "
                                                  "table, against its own atk_speed vardefine)"),
    ("barbarian_hut", "spawn_unit_stats", "716/191/1.4",
     _R25 + " -- the hut spawns `barbarians` x3, so its spawned-body anchor moves with them. "
            "SUPERSEDES the stat_diffs pin '670/192/1.3'"),
    # RULING 27 (owner, 2026-08-27), same commit because it is the same row.
    ("barbarian_barrel", "crown_tower_damage", 116,
     "decisions.md ruling 27 (OWNER 2026-08-27): the barrel row published NO crown value, so "
     "build_spec's `dmg if _td is None` fallback handed it its FULL 230 against a tower. The hero "
     "page's `rerolldmg_11` 116 is the Crown Tower Damage column -- 116/232 is the ordinary 50% "
     "reduction, and the variable name is misleading"),
]
RULING25_DATE = "2026-08-27"
# (key, field) pairs ruling 25 OVERRIDES. The I5 loop below asserts that an earlier pin agrees with
# the plan it is replaying, which is the right default -- silent disagreement between two pin
# sources is how a curated value gets quietly reverted. An owner ruling that supersedes a recorded
# I5 value has to say so EXPLICITLY, here, rather than by weakening that assertion for everyone.
RULING25_OVERRIDES = {(k, f) for k, f, _v, _w in RULING25_PINS}

I5_PLAN = LEDGER / "i5_plan.json"
_DROP = "__DROP__"

# The three columns tools/stat_sweep.py compares against the wiki. Any I5 value in one of these
# is a DELIBERATE DEVIATION and has to appear in this file, even when its home is cards.yaml --
# otherwise the sweep would have to keep a second, drifting list of "known" disagreements.
# Curated ones are marked `advisory: true`: recorded here, never pushed into cards_stats.json.
SWEPT_FIELDS = ("hitpoints", "damage", "dps", "hit_speed", "crown_tower_damage")

# ENGINE-MODELLING deviations. Not corrections and not import material -- the KB deliberately
# holds a number the wiki does not print, because the sim resolves the mechanic differently.
MODEL_PINS = [
    ("vines", "damage", 306,
     "MODELLING: we apply both hits at once (dmg_hits 2 x 153 = 306); the 1.25 s between them is "
     "below the sim's decision resolution"),
    ("vines", "crown_tower_damage", 70,
     "MODELLING: same doubling on the crown chip -- 2 x 35 after the 1/6/2026 cut to 23%"),
    ("goblinstein", "damage", 128,
     "MODELLING: a two-body champion held as ONE merged unit -- the wiki's dmg_11 92 is the "
     "Doctor alone and monster_dmg_11 is 128. Splitting them is the SIM_FIDELITY deferred item"),
]


def render():
    """Build the pins file's exact text from the ledger + the rulings. WRITES NOTHING.

    Split out of `main` so --check and the deck test suites can ask what the generator
    WOULD produce without touching the tree: a check that had to write first could not be
    used as a guard. Returns (text, counts).
    """
    rows = [json.loads(line) for line in
            (LEDGER / "stat_diffs.jsonl").read_text(encoding="utf-8").splitlines() if line]
    pin_rows = [r for r in rows if r.get("verdict") == "pin"]
    assert len(pin_rows) == 66, f"expected 66 verdict:pin rows, got {len(pin_rows)}"

    pins: dict = {}
    for r in pin_rows:
        key, field = r["key"], r["field"]
        src = r.get("sources") or []
        date = (src[0].get("fetched") if src else None) or "2026-08-26"
        prov = r.get("provenance") or {}
        pins[(key, field)] = {
            "key": key,
            "field": field,
            "value": r.get("current_db"),
            "source": f"stat_diffs.jsonl verdict:pin ({prov.get('file', '?')}:"
                      f"{prov.get('line', '?')}, family {r.get('family')})",
            "date": date,
        }

    dup = 0
    adv31b = 0
    for key, field, value, why in DECISION_PINS:
        if (key, field) in pins:
            got = pins[(key, field)]["value"]
            assert got == value, \
                f"pin disagreement for {key}.{field}: stat_diffs {got!r} vs decisions {value!r}"
            pins[(key, field)]["source"] += " + " + why
            dup += 1
        else:
            pins[(key, field)] = {"key": key, "field": field, "value": value,
                                  "source": why, "date": DECISION_DATE}

    for key, field, value, why in RULING19_PINS:
        if (key, field) in pins:
            got = pins[(key, field)]["value"]
            assert got == value, \
                f"pin disagreement for {key}.{field}: existing {got!r} vs ruling 19 {value!r}"
            pins[(key, field)]["source"] += " + " + why
            dup += 1
        else:
            pins[(key, field)] = {"key": key, "field": field, "value": value,
                                  "source": why, "date": RULING19_DATE}

    for key, field, value, why in RULING25_PINS:
        if (key, field) in pins:
            pins[(key, field)] = {"key": key, "field": field, "value": value,
                                  "source": why, "date": RULING25_DATE}
            dup += 1
        else:
            pins[(key, field)] = {"key": key, "field": field, "value": value,
                                  "source": why, "date": RULING25_DATE}

    for key, field, value, why in RULING22_PINS:
        if (key, field) in pins:
            got = pins[(key, field)]["value"]
            assert got == value, \
                f"pin disagreement for {key}.{field}: existing {got!r} vs ruling 22 {value!r}"
            pins[(key, field)]["source"] += " + " + why
            dup += 1
        else:
            pins[(key, field)] = {"key": key, "field": field, "value": value,
                                  "source": why, "date": RULING22_DATE}

    # ADVISORY: cards.yaml-curated. The importer emits NO spark radius at all (the
    # values are a table cell, not a vardefine), so these are recorded for stat_sweep
    # and never pushed into cards_stats.json.
    for key, field, value, why in RULING31A_PINS:
        pins[(key, field)] = {"key": key, "field": field, "value": value,
                              "advisory": True, "source": why,
                              "date": RULING31A_DATE}
        adv31b += 1

    for key, field, value, why in RULING31B_PINS:
        if (key, field) in pins:
            got = pins[(key, field)]["value"]
            assert got == value, \
                f"pin disagreement for {key}.{field}: existing {got!r} vs ruling 31b {value!r}"
            pins[(key, field)]["source"] += " + " + why
            dup += 1
        else:
            pins[(key, field)] = {"key": key, "field": field, "value": value,
                                  "advisory": True, "source": why,
                                  "date": RULING31B_DATE}
            adv31b += 1

    # 3. I5: everything routed to the import layer, PLUS every curated value that lands in a
    #    column tools/stat_sweep.py compares (those are advisory -- recorded, never imported).
    i5 = adv = 0
    if I5_PLAN.exists():
        for row in json.loads(I5_PLAN.read_text(encoding="utf-8"))["plan"]:
            key, field = row["key"], row["field"]
            advisory = row["route"] != "pin"
            if advisory and field not in SWEPT_FIELDS:
                continue
            value = None if row["after"] == _DROP else row["after"]
            why = "I5 apply (%s%s): %s" % (row["bucket"], ", curated" if advisory else "",
                                           row["ruling"])
            if (key, field) in RULING25_OVERRIDES or (key, field) in RULING31A_DROPS:
                continue                    # an owner ruling supersedes the recorded I5 value
            if (key, field) in pins:
                got = pins[(key, field)]["value"]
                assert got == value, ("pin disagreement for %s.%s: existing %r vs I5 plan %r"
                                      % (key, field, got, value))
                continue
            entry = {"key": key, "field": field, "value": value,
                     "source": why, "date": DECISION_DATE}
            if advisory:
                entry["advisory"] = True
                adv += 1
            else:
                i5 += 1
            pins[(key, field)] = entry

    for key, field, value, why in MODEL_PINS:
        if (key, field) in pins:
            continue
        pins[(key, field)] = {"key": key, "field": field, "value": value, "advisory": True,
                              "source": why, "date": DECISION_DATE}
        adv += 1

    ordered = [pins[k] for k in sorted(pins)]
    payload = {
        "meta": {
            "generator": "research/sim_parity/scripts/gen_pins.py",
            "sources": ["ledger/stat_diffs.jsonl (66 verdict:pin rows)",
                        "decisions.md 2026-08-26 R2 ADJUDICATION (owner rulings)",
                        "ledger/i5_plan.json (rows i5_apply.py routed to the import layer)",
                        "decisions.md ruling 19 (owner 2026-08-27, spawned-body elixir)",
                        "decisions.md ruling 22 (owner 2026-08-27, the barrel's roll speed)",
                        "decisions.md ruling 25 (owner IN-GAME 2026-08-27, the Barbarian's 716 hp)",
                        "decisions.md ruling 27 (owner 2026-08-27, the barrel's crown damage)",
                        "decisions.md ruling 31a (owner 2026-08-27, the Electro Giant's reflected crown damage)",
                        "decisions.md ruling 31b (OWNER 2026-08-27, the Evo Firecracker's two spark radii)"],
            "semantics": "the importer applies pins as a post-pass over the scraped rows and "
                         "--write refuses if a pinned field would regress; value null = the "
                         "field must not be imported; fields the importer does not emit are "
                         "advisory (curated layer / stat_sweep EXPECTED sync); an explicit "
                         "advisory:true pin is recorded for the sweep and never imported",
            "pair": "byte-identical across icebow/ and hogeq/ -- regenerate with the "
                    "generator and it writes both; never hand-edit one copy",
            "counts": {"total": len(ordered),
                       "from_stat_diffs": len(pin_rows),
                       "from_decisions": (len(DECISION_PINS) + len(RULING19_PINS)
                                          + len(RULING22_PINS) + len(RULING25_PINS)
                                          + len(RULING31B_PINS)),
                       "from_i5_plan": i5,
                       "advisory": adv + adv31b,
                       "overlapping": dup},
        },
        "pins": ordered,
    }
    text = json.dumps(payload, indent=1, sort_keys=False) + "\n"
    decisions = (len(DECISION_PINS) + len(RULING19_PINS) + len(RULING22_PINS)
                 + len(RULING25_PINS) + len(RULING31B_PINS))
    return text, {"total": len(ordered), "stat_diffs": len(pin_rows), "decisions": decisions,
                  "i5": i5, "advisory": adv + adv31b, "overlapping": dup}


OUTS = [ROOT / d / "config" / "import_pins.json" for d in DECKS]


def _norm(s: str) -> str:
    r"""Newline-normalised text.

    NOT COSMETIC. This repo runs `core.autocrlf=true` over an LF index, so a fresh checkout
    hands you a CRLF working copy of import_pins.json while this generator writes LF -- and
    a byte comparison would then FAIL on a file whose `git diff` is empty. That exact trap
    already cost the project a day on `tools/parity_check.py --strict` (HANDOFF SS8). The
    check compares CONTENT and leaves line endings to git.
    """
    return s.replace("\r\n", "\n").replace("\r", "\n")


def check() -> int:
    """Exit 1 when a committed pins file disagrees with what this generator produces.

    Reports the disagreement PER PIN -- (key, field), generator value vs the file's --
    because the failure being guarded against is ONE silently-lost owner value (ruling
    31a's electro_giant.reflect_crown_damage, ruling 31b's two Firecracker radii, ruling
    29's elixir prices), and "the files differ" would not name it.
    """
    text, counts = render()
    mine = {(p["key"], p["field"]): p for p in json.loads(text)["pins"]}
    bad = 0
    for out in OUTS:
        if not out.exists():
            print(f"MISSING  {out}")
            bad += 1
            continue
        raw = _norm(out.read_text(encoding="utf-8"))
        if raw == _norm(text):
            print(f"OK       {out}  ({counts['total']} pins reproduce)")
            continue
        bad += 1
        print(f"STALE    {out}")
        got = {(p["key"], p["field"]): p for p in json.loads(raw)["pins"]}
        named = 0
        for k in sorted(set(mine) | set(got)):
            a, c = mine.get(k), got.get(k)
            if a is None:
                print(f"  ONLY IN THE FILE   {k[0]}.{k[1]} = {c['value']!r}"
                      "   <- hand-edited; express it in gen_pins.py")
            elif c is None:
                print(f"  ONLY IN GENERATOR  {k[0]}.{k[1]} = {a['value']!r}"
                      "   <- re-run gen_pins.py")
            elif (a["value"] != c["value"]
                  or bool(a.get("advisory")) != bool(c.get("advisory"))):
                print(f"  DISAGREE           {k[0]}.{k[1]}: generator {a['value']!r}"
                      f" vs file {c['value']!r}")
            else:
                continue
            named += 1
        if not named:
            print("  the PIN VALUES all agree -- the difference is in meta/counts/source "
                  "text; re-run gen_pins.py")
    if bad:
        print()
        print("A PIN THAT ONLY EXISTS IN THE FILE IS A PIN THE NEXT GENERATOR RUN DELETES.")
        print("Fix it by expressing the value in gen_pins.py (a RULING*_PINS block), never")
        print("by editing config/import_pins.json -- that is the defect this check exists for.")
    return 1 if bad else 0


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if "--check" in argv:
        return check()
    text, counts = render()
    for o in OUTS:
        o.write_text(text, encoding="utf-8", newline="\n")
    same = OUTS[0].read_bytes() == OUTS[1].read_bytes()
    print(f"wrote {counts['total']} pins ({counts['stat_diffs']} stat_diffs + "
          f"{counts['decisions']} decisions + {counts['i5']} I5-plan + "
          f"{counts['advisory']} advisory, {counts['overlapping']} overlapping) to:")
    for o in OUTS:
        print(f"  {o}")
    print(f"pair byte-identical: {same}")
    return 0 if same else 1


if __name__ == "__main__":
    sys.exit(main())
