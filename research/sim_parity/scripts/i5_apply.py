# -*- coding: utf-8 -*-
"""I5 -- apply the adjudicated R2 ledger to the card KB, and prove every row landed.

    python research/sim_parity/scripts/i5_apply.py plan [-v]   # route + target for every row
    python research/sim_parity/scripts/i5_apply.py verify       # re-read the DB, write the ledger

WHY THIS IS NOT A YAML ROUND-TRIP
---------------------------------
`config/cards.yaml` is a hand-maintained file whose COMMENTS are half its value -- every curated
number carries a dated citation naming the superseded value and the source. `yaml.safe_load` +
`yaml.dump` would delete all of it. So this script does not write cards.yaml. It does two things
instead:

  * `plan`   decides, for every adjudicated row, WHAT the value must become and WHICH layer owns
             it (the importer's `cards_stats.json` via a pin, or a curated `cards.yaml` edit),
             and records the BEFORE value so the edit is measurable;
  * `verify` re-reads the merged CardDB after the edits and fails loudly on any planned change
             that did not land, then writes `ledger/i5_applied.jsonl` (one row per applied
             change: key, field, before, after, route, source, ruling).

WHERE THE TARGET VALUES COME FROM
---------------------------------
Three inputs, in increasing authority:

  1. `ledger/stat_diffs.jsonl` -- 556 canonical claim rows. The 101 `verdict: update` rows carry
     a usable `proposed`. The 316 `escalate` rows do NOT (`proposed` is null by construction),
     which is why the buckets have to be re-joined and read through their probe fields.
  2. `ledger/r2_buckets.json` -- the 316 escalations in 14 cause buckets, REDUCED schema
     (`current`, `p1`, `p2`, `p3`, `vote`, `notes`). The owner approved seven buckets wholesale
     (decisions.md "R2 ADJUDICATION"): KBGAP, LAG, CROWN, PARENT, ROUNDING, DUP, NAMING. Each
     bucket has a DERIVATION RULE below saying which probe wins, because the buckets differ in
     which path is trustworthy -- a LAG row is one where the vardefine is stale and the dated
     History is right; a KBGAP row is one where only the vardefine publishes anything at all.
  3. `decisions.md` -- owner rulings. These are FINAL and outrank both of the above; they live in
     `OVERRIDE` with the ruling text quoted, so `i5_applied.jsonl` can cite it per row.

`SKIP` is the fourth category and the one that matters most for honesty: rows the sweep itself
said not to act on ("I am NOT updating on a mis-worded entry", "Report only", "null on all three
paths"). Applying a bucket wholesale does not mean overwriting a field the evidence refuses to
settle. Every skip carries its reason and is printed by `plan -v`.

`DEFERRED` is the fifth: rows whose only probes are PROSE, plus the update rows whose ledger
`proposed` is a composite string or a demonstrably corrupt scalar (measured: 5 of them -- see
conflicts.md). Those are recorded, not guessed.
"""
from __future__ import annotations

import collections
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
LEDGER = ROOT / "research" / "sim_parity" / "ledger"
sys.path.insert(0, str(ROOT / "icebow" / "src"))

BULK = ("KBGAP", "LAG", "CROWN", "PARENT", "ROUNDING", "DUP", "NAMING")

# Which probe wins, per bucket. See the module docstring: the buckets are cause-clustered, and
# the cause IS the evidence rule.
PREFER = {
    "KBGAP":  ("p1", "p2", "p3"),   # nothing in the KB -- take whatever the wiki publishes
    "LAG":    ("p3", "p2", "p1"),   # the vardefine lags its own History; History is current
    "CROWN":  ("p3", "p1", "p2"),   # same, for the post-1/6/2026 crown-damage family
    "PARENT": ("p1", "p3", "p2"),   # the child's OWN vardefine, never the parent's
    "DUP":    ("p1", "p2", "p3"),   # merge's pick; every disagreement is in OVERRIDE
    "NAMING": ("p2", "p1", "p3"),
    # ROUNDING is computed, not picked -- see _rounding_target.
}

_DEC = "decisions.md 2026-08-26 R2 ADJUDICATION"
_DROP = "__DROP__"          # the field must go away entirely


_CATEGORICAL = {"speed", "range", "rarity", "targets", "kind", "movement"}


def _n(v, field=""):
    """A probe value the KB can hold, or None when the probe is prose.

    The sweeps wrote a few probes as "<literal> (<explanation>)" -- "1 (single use since
    4/8/2026)", "true (untargetable during the cloak)", "[air, ground]". The literal half is a
    real value and the parenthetical is a note, so it is extracted rather than thrown away.
    Anything that is not a leading literal stays prose and is DEFERRED, never guessed.
    """
    if isinstance(v, bool) or isinstance(v, (int, float, list, dict)):
        return v
    if not isinstance(v, str):
        return None
    s = v.strip()
    head = s.split("(")[0].strip().rstrip(",;").strip()
    if head.lower() in ("true", "false"):
        return head.lower() == "true"
    if head.startswith("[") and head.endswith("]"):
        parts = [p.strip().strip("'\"") for p in head[1:-1].split(",")]
        return [p for p in parts if p]
    try:
        f = float(head)
        return int(f) if f.is_integer() and "." not in head else f
    except ValueError:
        pass
    if field in _CATEGORICAL and head and " " not in head:
        return head
    return None


def _norm_field(field: str) -> str:
    """Ledger field names carry human annotations; the KB path does not.

    'damage (MISSING)' -> 'damage', 'components[0].damage (Doctor)' -> 'components.0.damage',
    'attack_ramp.mults[1]' -> 'attack_ramp.mults.1'. Without this the same field arrives twice
    under two spellings and the OVERRIDE table silently misses one of them.
    """
    f = field.split(" (")[0].strip()
    return f.replace("[", ".").replace("]", "")


# --------------------------------------------------------------------------------------------
# OWNER RULINGS + hand adjudications. (key, field) -> (value, ruling, route_hint)
# route_hint: "y" forces the curated cards.yaml layer, "p" forces an import pin, "" = auto.
# --------------------------------------------------------------------------------------------
OVERRIDE = {
    # --- decisions.md #5, verified:true row rulings ------------------------------------------
    ("tesla", "rarity"): ("common", _DEC + " #5: tesla is COMMON rarity", ""),
    ("bomber", "rarity"): ("common", _DEC + " #5: bomber rarity = common", ""),
    ("tesla", "hitpoints"): (
        1182, _DEC + " #5: tesla_evo hitpoints = base = 1182 @ L11 (evo hp same as base). OWNER "
        "OVERRIDE: the live wiki publishes 1152 on BOTH the base and the Evolution page, and the "
        "1/6/2026 '+3%' reconstruction gives 1187; the RULE (evo hp == base hp) is "
        "wiki-confirmed, the VALUE 1182 is the owner's", "p"),
    ("tesla", "evolution.hitpoints"): (
        1182, _DEC + " #5: tesla_evo hitpoints = base = 1182 @ L11", "y"),
    ("tesla_evo", "hitpoints"): (
        1182, _DEC + " #5: tesla_evo hitpoints = base = 1182 @ L11 (wiki says 1152 on both "
        "pages -- pinned so a re-import cannot pull it back)", "p"),
    ("earthquake", "damage"): (
        81, _DEC + " #5: earthquake damage = 81 @ L11, not 84", "y"),
    ("earthquake", "crown_tower_damage"): (
        49, _DEC + " #5 + owner batch: KNOWINGLY inconsistent. 49 is 58% of the SUPERSEDED "
        "damage 84 (84*0.58 = 48.7 -> 49); against the ruled 81 the same 58% gives 47, and 49/81 "
        "= 60.5%; the wiki's own crown_dmg_11 is 53. All three were put to the owner and 49 was "
        "chosen", "y"),
    ("bats_evo", "hit_heal"): (76, _DEC + " #5: bats_evo heal per hit = 76 (wiki)", "y"),
    ("firecracker_evo", "spark_dps_small"): (
        48, _DEC + " #5: firecracker_evo wiki correct for ALL entries -- the owner OVERTURNED "
        "their own verified 60, closing the long-flagged SIM_FIDELITY 6.7 conflict", "y"),
    ("firecracker_evo", "spark_duration_s"): (
        2.5, _DEC + " #5: split spark durations -- small 2.5 s", "y"),
    ("firecracker_evo", "spark_duration_large_s"): (
        3.0, _DEC + " #5: split spark durations -- big 3.0 s", "y"),
    ("firecracker_evo", "spark_radius_tiles"): (
        0.75, _DEC + " #5: firecracker_evo wiki correct for ALL its entries", "y"),
    ("firecracker_evo", "spark_dps_large"): (
        192, _DEC + " #14: firecracker_evo spark_dps_large 192 -- wiki correct", "y"),
    ("giant_snowball_evo", "roll_tiles"): (
        4.0, _DEC + " #5: giant_snowball_evo roll range 4.0 tiles", "y"),
    ("giant_snowball_evo", "attacks"): (
        ["air", "ground"], _DEC + " #5: giant_snowball_evo hits air AND ground. conflicts.md E4: "
        "flipping this alone would turn the ROLL OFF, because build_spec derived rolls from "
        "ground_only -- applied together with that decoupling", "y"),
    ("giant_snowball_evo", "slow_duration_s"): (
        3.0, _DEC + " #5 family: 4/5/2026 removed the Evo's bonus slow duration, so it equals "
        "the base spell's 3 s", "y"),
    ("giant_snowball_evo", "crown_tower_damage"): (
        45, _DEC + " #3 CROWN: 1/6/2026 cut it to 25% of full; 179*0.25 = 44.75 -> 45", "y"),
    ("decoy_goblin", "deploy_time"): (
        1.1, _DEC + " #5: decoy goblins deploy time = normal goblin-barrel goblins (1.1 s)", "y"),
    ("ghost_souldier", "deploy_time"): (
        0.2, _DEC + " #5 pairs with decoy_goblin: the two keys held each other's published "
        "values (one transposition at curation time); the Souldier's own table says 0.2", "y"),
    ("lava_pups", "speed"): ("fast", _DEC + " #5: lava_pups speed per the wiki", "y"),
    ("spirit_empress", "damage"): (309, _DEC + " #5: spirit_empress 309 is correct", "y"),
    ("spirit_empress_air", "damage"): (309, _DEC + " #5: spirit_empress 309 is correct", "y"),
    ("suspicious_bush", "pop_distance_tiles"): (
        1.6, _DEC + " #5: the 1.6 tiles is the POP distance -- the bush releases its goblins "
        "1.6 tiles from its target when it arrives (an engine semantic, not a plain stat)", "y"),
    ("furnace", "spawns.interval"): (5.0, _DEC + " #5: furnace spawn speed 5 s", "y"),
    ("boss_bandit", "leap_towers"): (
        True, _DEC + " #5: boss_bandit's passive dash triggers on every ground unit INCLUDING "
        "crown towers (contrast Golden Knight, whose chain merely ENDS at one)", "y"),
    ("boss_bandit", "leap_invulnerable"): (
        True, _DEC + " #5 + KBGAP: revid 437146 describes her dash invulnerability in the "
        "official card quote and twice in strategy prose, contradicting the curated 'she is NOT "
        "described as immune' comment", "y"),
    ("baby_dragon_evo", "aura_radius_tiles"): (
        4.0, _DEC + " #5: baby_dragon_evo wiki correct", "y"),

    # --- decisions.md #9, page self-contradictions --------------------------------------------
    ("royal_delivery", "damage"): (
        385, _DEC + " #9: the 12% cut applies to the SPAWN damage. The landing damage is "
        "spawn_11 437 (dmg_11 133 is the spawned Recruit's melee); 437*0.88 = 384.6 -> 385", "y"),
    ("royal_delivery", "spawn_damage"): (
        385, _DEC + " #9: the 4/8/2026 -12% lands on the SPAWN damage: 437*0.88 -> 385", "y"),
    ("royal_delivery", "crown_tower_damage"): (
        0, _DEC + " #11: royal_delivery CANNOT hit crown towers. Written as an explicit 0, NOT "
        "deleted: MEASURED, removing the field took spell_tower_dmg 40 -> 385, because "
        "build_spec fell back to the card's full damage when the KB carried none. build_spec's "
        "falsy `or dmg` was fixed in the same commit so a published 0 survives", "y"),
    ("fisherman", "slow_pct"): (_DROP, _DEC + " #9: fisherman has NO slow anymore", "y"),
    ("fisherman", "slow_duration_s"): (_DROP, _DEC + " #9: fisherman has NO slow anymore", "y"),
    ("phoenix", "spawn_interval_s"): (3.8, _DEC + " #9: phoenix spawn interval 3.8 s", "y"),
    ("royal_ghost", "invisibility_time_s"): (
        1.8, _DEC + " #9: royal_ghost 1.8 s to re-cloak", "y"),
    ("ghost_souldier", "invisibility_time_s"): (
        1.8, _DEC + " #10: ghost_souldier invisibility time = royal_ghost's", "y"),
    ("royal_ghost_evo", "invisibility_time_s"): (
        1.8, _DEC + " #9: royal_ghost 1.8 s to re-cloak -- the self-contradictory 2/3/2026 "
        "2.0 s entry is what the ruling settles", "y"),
    ("cannon_evo", "volley_damage"): (
        281, _DEC + " #9: cannon_evo volley damage 281 @ L11 (nerfed; the vardefine lags at "
        "304)", "y"),

    # --- decisions.md #10, split votes --------------------------------------------------------
    ("mortar", "hit_speed"): (4.7, _DEC + " #10: mortar AND mortar_evo hit speed 4.7 s", "p"),
    ("mortar_evo", "hit_speed"): (4.7, _DEC + " #10: mortar AND mortar_evo hit speed 4.7 s", "p"),
    ("mighty_miner", "ability_bomb_damage"): (
        332, "decisions.md ruling 9 (2026-08-26): rarity floors put champions at level 11, so "
        "the wiki's integer base 332 @ L11 reproduces the owner's observed 440 @ L14 "
        "(332->365->402->440). The old 366 was reverse-derived from a champion level 1 that does "
        "not exist. conflicts.md C1 RESOLVED, and the 'not published in the KB' comment with "
        "it -- it IS published, as escape_11", "y"),
    ("giant_skeleton", "collision"): (
        1.0, _DEC + " #10: giant_skeleton collision -- sweep recommendation accepted", "y"),
    ("ram_rider", "hit_speed"): (
        1.8, _DEC + " #10: ram_rider hit speed -- the most up-to-date entry", "y"),
    ("phoenix", "egg.hatch_s"): (3.8, _DEC + " #10: phoenix_egg -> revival 3.8 s", "y"),

    # --- decisions.md #11, unpublished values -------------------------------------------------
    ("goblin_cage", "sight"): (
        _DROP, _DEC + " #11: goblin_cage has NO sight stat (it cannot attack while the cage "
        "stands); the '20' is the LIFETIME, which the row already carries as lifetime_s", "y"),
    ("lumberjack_ghost", "untargetable"): (
        True, _DEC + " #11: no troop, building or tower can target the ghost", "y"),
    ("lumberjack_ghost", "damage_immune"): (
        True, _DEC + " #11: no source damages it -- but spells CAN still knock it back", "y"),
    ("lumberjack_ghost", "spell_knockback_ok"): (
        True, _DEC + " #11: spells can still knock the ghost back", "y"),
    ("lumberjack_ghost", "ghost_life_s"): (
        4.5, _DEC + " #14: lumberjack_ghost lifetime 4.5 s = the rage duration, conditional on "
        "staying inside the pool (leaves early -> dies early)", "y"),
    ("furnace_evo", "lifetime_s"): (
        _DROP, _DEC + " #11: FURNACE IS A TROOP NOW -- no lifetime stat", "y"),
    ("goblin_curse", "damage"): (
        35, _DEC + " #12: goblin_curse 35 = damage PER SECOND; the spell lasts 6 s -> 210 total. "
        "The KB's 120 was the GOBLIN the curse converts victims into", "y"),

    # --- decisions.md #13/#14 -----------------------------------------------------------------
    ("little_prince", "royal_rescue_damage"): (
        256, _DEC + " #13/#14 + NAMING: royal_rescue_damage is real and stays. charge_11 = 256 "
        "is the ABILITY dash damage (column 'Royal Rescue Damage'), NOT a Prince-style charge -- "
        "charge_damage: 0 is correct curation and must never be fed from charge_*", "y"),

    # --- CROWN bucket, hand adjudications -----------------------------------------------------
    ("wall_breakers_evo", "death_damage"): (
        233, "CROWN bucket: the +50%/+11%/-10% chain closes exactly on 291, so 291 is the "
        "3/11/2025 value and the 4/8/2026 -20% is missing from it: 291*0.80 = 232.8 -> 233", "y"),
    ("wall_breakers_evo", "death_crown_damage"): (
        154, "CROWN bucket: 8/1/2025 fixed death damage at 66% of full against Crown Towers; the "
        "published crown_11 193 is 66% of the SUPERSEDED 291. Against the applied 233: "
        "233*0.66 = 153.8 -> 154", "y"),
    ("valkyrie_evo", "attack_nado_crown_damage"): (
        37, "CROWN bucket: tor_crown_11 = 37 is what the wiki publishes. UNRESOLVED and recorded "
        "in conflicts.md: if the 4/8/2026 -50% also halved the crown chip it would be ~18, but "
        "no entry says so and the vardefine is undated", "y"),
    ("goblinstein", "lightning_link_crown_tower_damage"): (
        23, "CROWN bucket: crown_11 = 23 published. Pre-4/8/2026 like every other vardefine on "
        "this page; a post-nerf value depends on resolving the link damage first", "y"),
    ("dart_goblin_evo", "poison_stages"): (
        [64, 128, 307], "CROWN bucket: the time machine shows 51/115/307 predate the 1/6/2026 "
        "buff and never moved. Reconstructed 51*1.25 -> 64, 115*1.11 -> 128, stage 3 "
        "unchanged", "y"),

    # --- PARENT bucket ------------------------------------------------------------------------
    ("goblin_cage", "hit_speed"): (
        _DROP, "PARENT bucket: 1.1 s is the Goblin BRAWLER's period from the secondary table; "
        "the cage never attacks and publishes no hit-speed column. Already carried where it "
        "belongs, in spawn_unit_stats.hit_speed", "p"),
    ("skeleton_barrel_evo", "death_damage"): (
        190, "PARENT bucket: 238 is the 4/8/2025 snapshot (P1 and P2 are one witness, not two). "
        "Two dated 2026 nerfs postdate it: 238*0.92*0.87 = 190.5 -> 190. Reading (a), "
        "evo-specific -- the entries appear ONLY on the Evolution page", "y"),
    ("barbarian_barrel", "damage"): (
        230, "PARENT bucket: the two fields are SWAPPED. 'Barbarian Barrel Area Damage' renders "
        "from spawn_11 (230); dmg_11 191 is the spawned Barbarian's swing", "p"),
    ("barbarian_barrel", "spawn_damage"): (
        191, "PARENT bucket: mirror of the damage row -- the spawned Barbarian swings 191", "p"),

    # --- DUP bucket, merge's pick -------------------------------------------------------------
    ("phoenix_egg", "hitpoints"): (
        240, "DUP bucket (merge's pick): the wiki moved to 240 and the KB kept 239. The 317 in "
        "P3 is the sweep's own reconstruction of a 2/3/2026 +32% the wiki never applied -- not a "
        "published number, so not applied", "y"),
    ("elixir_collector", "lifetime"): (
        _DROP, "DUP bucket (merge's pick): the curated `lifetime: 70` is the PRE-4/4/2022 value "
        "and the SAME row already carries the correct lifetime_s 93. Delete the stale key rather "
        "than keep two disagreeing lifetimes on one row", "y"),
    ("rocket", "crown_tower_damage"): (
        341, "DUP bucket (merge's pick) + the crown-damage pin family: 1484*0.23 = 341.32 -> "
        "341. cards.yaml carried 342, which needs a ceil where the rest of the family rounds, "
        "and disagrees with the crown_damage_audit output it cites", "y"),
    ("zap_evo", "crown_tower_damage"): (
        48, "DUP bucket: THE OWNER PIN LANDED ON THE PARENT AND MISSED THE EVOLUTION. "
        "zap.crown_tower_damage is 48 = round(192*0.25), correct post-1/6/2026; zap_evo held 58, "
        "the stale 30% vardefine, off IDENTICAL damage 192. Caught by stat_sweep --all: the "
        "bucket's own probe order puts p1 (the stale vardefine) first, so the derivation alone "
        "would have kept 58", "p"),
    ("goblin_cage_evo", "damage"): (
        337, "DUP bucket (merge's pick): the kept claim proposes NO auto-update -- 367 assumes "
        "the 4/8/2026 +9% trapped DPS landed on damage, and it cannot be ruled out that the trap "
        "period moved instead. With hit_speed at the published 1.0 s the page's own 'Goblin Cage "
        "Damage per second' column is 337/1 = 337, which is self-consistent", "y"),

    # --- LAG bucket, hand adjudications -------------------------------------------------------
    ("barbarian_hut", "spawns.interval"): (
        15.0, "LAG bucket: the curated 13.5 is the pre-4/2/2020 trivia line and is refuted by "
        "every path. Two LIVE surfaces (attribute table + intro prose) say 15 against a history "
        "RECONSTRUCTION of 14; the same row already carries spawn_interval_s 15.0, so 15 also "
        "stops the row holding two disagreeing values. The 14 reading is in conflicts.md", "y"),
    ("goblin_demolisher", "hit_speed"): (
        1.1, "LAG bucket: the two paths saying 1.2 are two renderings of ONE page whose stat "
        "block provably did not move across 1/12/2025; the two saying 1.1 are the change record "
        "(this page's History and the independent Version History)", "p"),
    ("furnace", "hit_speed"): (
        1.7, "LAG bucket: the same page's table is demonstrably stale in BOTH of its other 2026 "
        "entries (range and spawn interval, both applied as updates), so table agreement is not "
        "evidence of currency for this field either", "p"),
    ("goblin_gang", "load_time_s"): (
        0.5, _DEC + " #10: ALL wiki load_time entries correct. First Hit Speed 0.6 against hit "
        "speed 1.1 gives 0.5; the 2023 dump's 0.7 predates the 9/4/2025 goblin first-hit "
        "move", "y"),
    ("musketeer", "load_time_s"): (
        0.3, _DEC + " #10: ALL wiki load_time entries correct -- this settles the three-way "
        "conflict (KB/dump 0.2, wiki 0.3, engine comment 1.0) in the wiki's favour", "y"),

    # --- ROUNDING follow-on the floor rule cannot see on its own -------------------------------
    ("goblin_machine", "dps"): (
        192, _DEC + " #7: adopt the wiki's floor() for derived DPS -- floor(231/1.2) = 192 on "
        "the LAG-corrected damage 231. (On today's 212 the floor is 176; the stored 177 is a "
        "round().)", "p"),

    # --- CONSEQUENTIAL dps, declared rather than forced ---------------------------------------
    # Every row here is a `verified: true` cards.yaml row whose `dps` moves ONLY because an
    # adjudicated damage or hit_speed landed above. The importer recomputes dps with its own
    # round(damage/hit_speed); pinning the same number is what tells the write guard the change
    # is a declared consequence instead of an undeclared regression -- so the forced-field set
    # stays exactly the three I4 predicted. NB these use the importer's round(), NOT the
    # decisions.md #7 floor(): that ruling was approved for the ten ROUNDING rows, and a global
    # flip would move 47 rows and contradict two approved update rows (see conflicts.md).
    ("barbarian_barrel", "dps"): (
        177, "consequential on the PARENT swap: 230/1.3 = 176.9 -> 177", "p"),
    ("barbarians_evo", "dps"): (
        136, "consequential on the LAG damage 191: 191/1.4 = 136.4 -> 136", "p"),
    ("bats_evo", "dps"): (
        68, "consequential on the LAG hit_speed 1.2: 81/1.2 = 67.5 -> 68", "p"),
    ("cannon_evo", "dps"): (
        201, "consequential on the LAG damage 201: 201/1.0 = 201", "p"),
    ("dart_goblin_evo", "dps"): (
        180, "consequential on the LAG damage 144: 144/0.8 = 180", "p"),
    ("executioner_evo", "dps"): (
        75, "consequential on the LAG damage 180: 180/2.4 = 75", "p"),
    ("furnace", "dps"): (
        105, "consequential on the LAG hit_speed 1.7: 179/1.7 = 105.3 -> 105", "p"),
    ("furnace_evo", "dps"): (
        105, "consequential on the LAG hit_speed 1.7: 179/1.7 = 105.3 -> 105", "p"),
    ("goblin_barrel_evo", "dps"): (
        114, "consequential on the LAG damage 125: 125/1.1 = 113.6 -> 114", "p"),
    ("rune_giant", "dps"): (
        103, "consequential on the LAG damage 154: 154/1.5 = 102.7 -> 103", "p"),
    ("mortar_evo", "dps"): (
        57, _DEC + " #10 consequence: 266/4.7 = 56.6 -> 57. One of the three refusals I4's "
        "dry-run predicted -- released with --force-field mortar_evo.dps on the I5 --write and "
        "pinned here so the next import does not refuse again (cli.py's own instruction)", "p"),

    # --- update rows whose ledger `proposed` is corrupt (see conflicts.md) ---------------------
    ("witch_evo", "damage"): (
        135, "stat_diffs verdict:update: dmg_11 = 135, 3-of-3 (evo vardefine, evo attributes "
        "table, base Witch under the 'identical stats' clause)", "y"),
    ("witch_evo", "hit_speed"): (
        1.1, "stat_diffs verdict:update: her own atk_speed is 1.1 on both pages; the 6/10/2025 "
        "'attack time interval to 1.1s' entry is the SKELETON's", "y"),
    ("witch_evo", "dps"): (
        123, "stat_diffs verdict:update: 135/1.1 = 122.7 -> 123. The ledger row's `proposed` "
        "field reads 11.0, which is a scalar-extraction bug in the emitter, not the value", "y"),
    ("witch_evo", "speed_tiles"): (
        1.0, "stat_diffs verdict:update: Medium (60) = 1.0 tiles/s", "y"),
    ("goblinstein", "components.0.damage"): (
        135, "stat_diffs verdict:update + conflicts.md C4 RESOLVED: dmg_11 92 is byte-identical "
        "at revid 436759 (2026-07-16) and live, so it predates the 4/8/2026 '+47% Doctor "
        "damage': 92*1.47 = 135.2 -> 135. The ledger `proposed` reads 11.0 (emitter bug)", "y"),
    ("mighty_miner", "damage_stages.0"): (
        43, "stat_diffs verdict:update: 1_dmg_11 = 40 is byte-identical across three revisions "
        "and predates the 4/8/2026 '+8% base damage': 40*1.08 = 43.2 -> 43. The ledger "
        "`proposed` reads 1.0 (emitter bug)", "y"),
    ("mighty_miner", "damage"): (
        43, "stat_diffs verdict:update: stage 1 = the base damage; the KB duplicates it in "
        "damage, damage_stages[0] and damage_ramp", "y"),

    # --- KBGAP / LAG rows whose probes are prose but whose VALUE is unambiguous ---------------
    ("zap_evo", "zap_pulses"): (
        2, "LAG bucket, 3-of-3: 8/10/2024 'increased the second pulse's damage by 100%, but "
        "REMOVED THE THIRD PULSE'; dmg_hits = 2 and the infobox says 'TWO Zaps'. The curated 3 "
        "quotes the retired pre-8/10/2024 card text", "y"),
    ("princess_evo", "volley_slow_every"): (
        2, "LAG bucket: the 4/8/2026 nerfset moved the cadence to every 2nd hit; the stub's "
        "Ability section was never rewritten", "y"),
    ("princess_evo", "volley_slow_s"): (
        5.5, "LAG bucket: same 4/8/2026 entry cut the slowdown duration to 5.5 s", "y"),
    ("princess_evo", "volley_slow_radius_tiles"): (
        3.0, "KBGAP: the ability prose publishes a 3-tile slow radius (single path, stub "
        "page)", "y"),
    ("princess_evo", "volley_slow_pct"): (
        30, "KBGAP: slow magnitude 30% (single-path prose on a stub page)", "y"),
    ("mega_knight_evo", "uppercut_every_hits"): (
        2, "KBGAP/P3: the 2026-08-14 curation modelled the uppercut on EVERY attack; since "
        "4/8/2026 it fires every 2nd hit (uppercut_tiles 4.0 is current-correct)", "y"),
    ("witch_evo", "overheal_frac"): (
        1.73, "LAG bucket: 4/8/2026 'increased her overheal ratio to x1.73 (from x1.24)'. P1 and "
        "P2 are one stale snapshot -- maks_hp_11/hp_11 is still exactly the old x1.24", "y"),
    ("witch_evo", "spawn_death_heal"): (
        220, "LAG bucket: heal chain -12%/-12%/+36%/-21%/-11% then 4/8/2026 '+189%'; "
        "76*2.89 = 219.6 -> 220. Must land WITH heal_source_cap 4, which partly offsets it", "y"),
    ("witch_evo", "max_hitpoints"): (
        1452, "KBGAP: two independent derivations agree -- 1039*1.40 = 1455 (the 4/8/2026 '+40% "
        "max hitpoints') and 839*1.73 = 1452 (base x the new ratio). Cross-check that base "
        "hitpoints 839 did NOT move on 4/8/2026", "y"),
    ("witch_evo", "heal_source_cap"): (
        4, "KBGAP: 4/8/2026 'made it to where she can only be healed by the first 4 skeletons "
        "that she spawns' -- without it the sim heals her off every skeleton she ever "
        "spawns", "y"),
    ("witch_evo", "spawn_count_per_wave"): (
        4, "KBGAP: base Witch lead -- 'Every 7 seconds ... a group of four Skeletons'", "y"),
    ("witch_evo", "spawn_first_wave_s"): (
        1.0, "KBGAP: 'her first wave of Skeletons will spawn 1 second after she is deployed', "
        "not after the generic 7 s interval", "y"),
    ("tesla_evo", "pulse_damage"): (
        174, "KBGAP, 3-of-3: pulse_dmg_11 = 174, and the balance chain (227 -> -22.9% -> +17% -> "
        "-15%) lands on it. The death pulse was REMOVED 8/10/2024 -- do not model one", "y"),
    ("tesla_evo", "pulse_radius_tiles"): (6.0, "KBGAP: Evolution Attributes give 6 tiles", "y"),
    ("tesla_evo", "pulse_stun_s"): (
        0.5, "KBGAP: 0.5 s stun; the Lumberjack Ghost has been immune to it since "
        "4/2/2025", "y"),
    ("royal_hogs_evo", "air_drop_damage"): (
        59, "LAG bucket: the 2026-08-14 curation note itself reads '115 (post 2/3/2026 -27% "
        "nerf)' and missed the 4/5/2026 -49%: 115*0.51 = 58.65 -> 59", "y"),
    ("valkyrie_evo", "attack_nado_damage"): (
        42, "LAG bucket: the curated 76 is the LAUNCH value (pre-14/5/2024). Chain fit "
        "76 -> x1.11 = 84 (the vardefine) -> 4/8/2026 x0.5 = 42", "y"),
    ("goblinstein", "lightning_link_damage"): (
        107, "KBGAP: link_11 = 107 published, with the same proven vardefine lag as the Doctor "
        "row. The 4/8/2026 note nerfs 'Ability DPS' -12%, which could land on damage (-> 94) or "
        "on hit speed (-> 0.568 s); recorded in conflicts.md, published value applied", "y"),
    ("goblinstein", "ability_radius_tiles"): (
        2.0, "KBGAP: Radius 2 is published; conflicts.md C8 geometry (measured from the Doctor, "
        "the Monster, or the line between them) is still unresolved on revid 437348", "y"),
    ("goblinstein", "range_tiles"): (
        1.2, "NAMING bucket, snapshot hygiene: the card-level row's hitpoints/damage/hit_speed "
        "are the MONSTER's, so its range must be the Monster's melee 1.2 -- 5.5 is the DOCTOR's "
        "and contradicts the row's own range: melee. Both component rows are already "
        "correct", "y"),
    ("lumberjack_evo", "death_crown_damage"): (
        54, "CROWN bucket: rage_crown_11 = 54 -- the sim models the rage-drop blast via "
        "death_damage 179 but carried no crown figure, so it chipped towers at full", "y"),
    ("little_prince", "attack_ramp.mults.1"): (
        2.0, "LAG bucket, REAL SIM ERROR quantified: engine.py applies the ramp mults as a "
        "CADENCE divisor, so 1.5 gives stage 2 = 1.2/1.5 = 0.800 s where the wiki publishes "
        "0.600 s on two paths. Stages 1 and 3 are already exact; mults[1] must be 2.0", "y"),
    ("monk", "combo_damage"): (
        422, "KBGAP, 3-of-3, conflicts.md C3 CONFIRMED: combo_11 = 422 IS published. The "
        "cards.yaml comment 'the 3rd hit's EXTRA DAMAGE is not published' is factually wrong -- "
        "the same error class as C1. The sim gives 140 on the 3rd hit instead of ~422", "y"),
    ("skeleton_barrel_evo", "spawn_count"): (
        7, "KBGAP: '2 barrels, each with 7 Skeletons' (14 total); the base card's per-barrel "
        "count has been 7 since 25/4/2018 and the evo page never changed it", "y"),
    ("skeleton_army_evo", "shadow_skeleton_speed_tiles"): (
        1.0, "KBGAP: the Shadow Skeletons move at 1.0 tiles/s since 12/01/2026; inheriting the "
        "skeleton 1.5 makes them 50% too fast", "y"),
    ("mortar_evo", "first_hit_speed_s"): (
        1.0, "KBGAP: 8/10/2024 'added a 1 second delay in the Evolved Mortar's first attack', "
        "matching the attributes table; the base Mortar has no such delay", "y"),
    ("mortar_evo", "spawn_goblin_deploy_time_s"): (
        0.5, "KBGAP: the spawned Goblins take 0.5 s to deploy since 1/6/2026 (the tertiary "
        "table still says 0.2)", "y"),
    ("bomb_tower", "death_damage_targets"): (
        ["air", "ground"], "KBGAP: attacks:[ground] describes only the turret; the wiki gives "
        "the DEATH blast Air & Ground, so today a Bomb Tower death cannot kill the Bats it "
        "should", "y"),
    ("wall_breakers_evo", "runner_spawn"): (
        {"unit": "wall_breaker_runner", "count": 2, "hitpoints": 164, "damage": 196,
         "speed_tiles": 2.0, "range_tiles": 0.5, "splash_radius": 1.5, "deploy_time": 1.0,
         "attacks": ["buildings"], "movement": "ground"},
        "KBGAP, 3-of-3: run_hp_11 = 164 / run_dmg_11 = 196 plus the 'Runner Attributes' "
        "tertiary table. Each evo Wall Breaker spawns a Runner on death -- the row had "
        "spawn_unit_stats geometry but no spawn declaration, so nothing spawned", "y"),
    ("archer_queen", "ability_attack_speed_boost"): (
        1.8, "KBGAP: history ('to 180% from 200%') and prose ('80% increase') BOTH describe a "
        "x1.8 multiplier -> hit speed 1.2/1.8 = 0.667 s. The table's leading '+' is the outlier "
        "(it would mean x2.8)", "y"),
    ("golden_knight", "ability_dash_delay_s"): (
        0.05, "KBGAP: sourced and dated (0.2 -> 0.05 on 3/11/2025), but its SEMANTICS are "
        "defined nowhere on revid 437147 -- best reading is an intra-chain wind-up "
        "(decisions.md ruling 10 amendment). Distinct from the 0.766 s cast time", "y"),
    ("little_prince", "spawn_unit_stats.hitpoints"): (
        1600, "KBGAP: guard_hp_11 = 1600, unaffected by the 4/8/2026 note (damage only). The "
        "Guardienne had NO hitpoints in the KB -- the sim's summoned tank was statless", "y"),
    ("little_prince", "spawn_unit_stats.damage"): (
        232, "KBGAP: guard_dmg_11 = 217 is byte-identical at revid 436758 (the edit that "
        "installed the vardefine block) and at live revid 437347, so it predates the 4/8/2026 "
        "'Guardian Melee Damage +7%': 217*1.07 = 232.2 -> 232. NB PLAN.md's I7 line still "
        "quotes the published 217 -- 232 is the post-4/8/2026 value, do not 'fix' it back", "y"),
    ("little_prince", "spawn_unit_stats.deploy_time"): (
        0.3, "KBGAP: Guardienne Attributes Deploy Time 0.3 sec", "y"),
    ("little_prince", "royal_rescue_dash_range_tiles"): (
        4.0, "KBGAP: the attributes table and the strategy prose both say 4 against a 13/11/2023 "
        "entry of 4.5. Here the history is the OLDER reading, so an undocumented 4.5 -> 4 "
        "happened; 2 of 3 favour 4", "y"),
    ("little_prince", "ability_cost"): (
        3, "KBGAP: Royal Rescue Attributes Cost 3 -- the most expensive champion ability in the "
        "group (3 elixir on a 3-elixir card)", "y"),
    ("little_prince", "ability_uses"): (
        1, "KBGAP + decisions.md ruling 6: single use PER BODY since 4/8/2026", "y"),
    ("little_prince", "first_hit_speed_s"): (
        0.4, "KBGAP: the wiki's First Hit Speed is 0.4 s. NB this is a DIFFERENT metric from "
        "the frozen dump's load_time_s -- Archer Queen's first-attack interval moved on "
        "7/2/2023, before the 2023-10-18 freeze, and the dump still disagrees", "y"),
    ("clone", "targets"): (
        "friendly_troops", "stat_diffs verdict:update: table Target = 'Friendly Troops' and the "
        "card text says 'Doesn't affect buildings'. The row had no attacks/targets key at all, "
        "so nothing constrained what Clone may be cast on", "y"),
    # --- KBGAP rows the probe-preference rule reads WRONG (unit or shape mismatch) ------------
    ("ice_spirit_evo", "blast_repeat_delay_s"): (
        3.0, "KBGAP: the Evo Ice Spirit hits TWICE -- the initial 110 + 1.1 s freeze, then a "
        "SECOND identical hit three seconds later. p1 (110) is the BLAST DAMAGE, not the "
        "delay", "y"),
    ("ice_spirit_evo", "blast_damage"): (
        110, "KBGAP companion: dedicated vardefine Blast_11 = 110 for the second hit", "y"),
    ("executioner_evo", "smash_damage"): (
        241, "KBGAP: close_11 = 294 is provably stale by two nerfs -- 294*0.91*0.90 = 240.9 -> "
        "241. The axe hits for close_11 instead of dmg_11 inside the smash band, on both the "
        "outward and the return pass", "y"),
    ("graveyard", "zone_spawn_edge"): (
        False, "LAG bucket: the spawn RING is 3.3 tiles, not the 4-tile edge. 2/2/2026 moved it "
        "to 3.3 (from 2.9) and 14/1/2026 only moved them 'closer to' the edge, never onto it", "y"),
    ("graveyard", "zone_spawn_radius_tiles"): (
        3.3, "LAG bucket companion: the live spawn radius, against the KB's edge-of-4.0 "
        "model", "y"),
    ("lumberjack", "evolution"): (
        {"available": True, "cycles": 2},
        "KBGAP: the Lumberjack has an Evolution (3/2/2025) and a lumberjack_evo row exists, but "
        "the base row had no `evolution` dict -- so cards.py evo_cycles() short-circuits on the "
        "PARENT and reports 'never evolves'. Published cycles 2", "y"),
    ("lumberjack", "drops_rage.damage"): (
        179, "KBGAP: rage_dmg_11 = 179 -- the dropped Rage DEALS damage in the current game and "
        "the KB's drops_rage dict had no damage key, so the sim's Lumberjack death was "
        "damage-free", "y"),
    ("lumberjack", "drops_rage.crown_damage"): (
        54, "KBGAP companion: rage_crown_11 = 54", "y"),
    ("goblin_machine", "rocket_ability"): (
        {"damage": 304, "crown_tower_damage": 152, "radius_tiles": 1.5, "min_range_tiles": 2.5,
         "range_tiles": 5.0, "hit_speed": 3.5, "projectile_speed": 250, "first_hit_s": 1.5,
         "attacks": ["air", "ground"]},
        "KBGAP: the Goblin Machine's locking AOE missile is unmodelled -- the row carries no "
        "rocket at all. Hit speed and projectile speed are contested by the same 4/8/2026 lag "
        "(page 3.5 s / 250 vs history 5 s and +40% = 350); the page values are taken and the "
        "conflict recorded", "y"),
    ("heal_spirit", "heal_ability"): (
        {"heal_per_pulse": 100.25, "pulses": 4, "pulse_interval_s": 0.25, "radius_tiles": 2.5,
         "targets": ["air", "ground"]},
        "KBGAP: a Heal Spirit that does not heal. Published 100.25 per pulse at L11, 4 pulses "
        "every 1 second (0.25 s interval), radius 2.5, friendly air and ground", "y"),
    ("ice_wizard", "spawn_slow"): (
        {"radius_tiles": 3.0, "duration_s": 1.0, "slow_pct": -30, "targets": ["air", "ground"]},
        "KBGAP: the row carried spawn_damage 84 but none of the spawn's area or slow, so the "
        "deploy blast damaged nothing around it and slowed nobody. Distinct from the ATTACK slow "
        "already on the row (slow_duration_s 2.5)", "y"),
    ("ram_rider", "rider_attack"): (
        {"damage": 104, "hit_speed": 1.1, "range_tiles": 5.5, "projectile_speed": 600,
         "attacks": ["air", "ground"], "targets": "troops"},
        "KBGAP/PRIORITY: the KB modelled only the Ram and the snare. The RIDER's own attack -- "
        "104 every 1.1 s at 5.5 tiles, projectile 600, hitting AIR as well as ground, troops "
        "only -- was absent, so in the sim a Ram Rider did no ranged chip and could not touch "
        "air at all", "y"),
    ("rune_giant", "enchant"): (
        {"bonus_damage": 220, "range_tiles": 6.0, "limit": 2, "every_nth": 3,
         "duration_after_death_s": 3.0},
        "KBGAP/PRIORITY: the card's entire identity was unmodelled -- a Rune Giant was just a "
        "weak 4-elixir building-targeting body granting nothing. Published: +220 bonus damage "
        "at L11 on every 3rd attack, to the 2 nearest troops", "y"),
    ("goblin_giant_evo", "backpack_spear_goblins"): (
        {"count": 2, "hitpoints": 133, "damage": 81, "hit_speed": 1.6, "range_tiles": 5.0,
         "projectile_speed": 500, "attacks": ["air", "ground"]},
        "KBGAP: the Evo row's spawn_unit_stats describes the low-hp Goblin trickle; there was "
        "nowhere for the TWO backpack Spear Goblins the card always carries. p3 1.6 s is their "
        "hit speed, not the whole sub-unit", "y"),
    ("archer_queen", "ability_move_speed_tiles"): (
        0.75, "stat_diffs verdict:update, UNIT CORRECTED: the ledger's `proposed` 45 is in WIKI "
        "SPEED UNITS ('Slow (45)') on a field named _tiles. 45/60 = 0.75 tiles/s, confirmed on "
        "the same page (her body Medium (60) == the KB's speed_tiles 1.0)", "y"),
    ("golden_knight", "ability_move_speed_tiles"): (
        2.0, "stat_diffs verdict:update, UNIT CORRECTED: 'Very Fast (120)' is 120 speed units = "
        "2.0 tiles/s, not 120 tiles. This is the movement boost that applies while NO target is "
        "within 5.5 tiles -- a DIFFERENT quantity from the unpublished dash travel speed", "y"),
    ("mortar_evo", "range_tiles"): (
        11.5, "stat_diffs verdict:update: THE SAME PARSE BUG THE BASE CARD WAS FIXED FOR, left "
        "unfixed on the evo row -- the importer takes the leading number of the '3.5-11.5' band, "
        "the DEAD-ZONE MINIMUM, as the reach. Curated here exactly as the base mortar is", "y"),
    ("goblin_curse", "spawns_troop"): (
        {"unit": "goblins", "hitpoints": 202, "damage": 120, "hit_speed": 1.1},
        "stat_diffs verdict:update: the card's defining effect -- cursed enemies that die become "
        "Goblins for the caster -- was not represented at all, so the sim priced Goblin Curse as "
        "pure chip. Per-Goblin stats are the hp_11/dmg_11/atk_speed the KB had mistakenly put "
        "in the SPELL's own damage field", "y"),
}

# Rows left OUT on purpose, with the reason recorded rather than a value guessed.
DEFER = {
    # the ledger names these under a prose spelling; they land as spawn_unit_stats.* above
    ("little_prince", "guardienne damage"):
        "applied as little_prince.spawn_unit_stats.damage = 232 (same fact, KB spelling)",
    ("little_prince", "guardienne hitpoints"):
        "applied as little_prince.spawn_unit_stats.hitpoints = 1600 (same fact, KB spelling)",
    ("little_prince", "guardienne deploy_time_s"):
        "applied as little_prince.spawn_unit_stats.deploy_time = 0.3 (same fact, KB spelling)",
    ("three_musketeers", "dps"):
        "already satisfied in substance by the 3/11/2025 rework commit (50a15de): the KB "
        "carries damage 204 (ranged) and melee_damage 314 at hit_speed 1.3, which derive to "
        "exactly the ledger's 157 / 242",
    ("three_musketeers", "range_tiles"):
        "already satisfied: range_tiles 6.0 + melee_range_tiles 1.6 landed with the rework",
    ("pekka_evo", "kill_heal"):
        "the sweep's own conclusion: 'sim needs a MODEL change, not a number swap' -- the "
        "launch-era flat 470 becomes a 3-tier heal by victim max-hp (160/305/577, thresholds "
        "990/1991), pulsed. Belongs with the I7/I9 engine work",
    ("wall_breakers_evo", "damage_vs_troops"):
        "attack damage is now SPLIT by target class; the single `damage` 391 stays correct "
        "against buildings, which is what they target. A schema change, not a value",
    ("minion_horde_evo", "evo_cycles"):
        "already correct: the curated row carries evo_cycles 1, which is exactly the stub's "
        "infobox value -- nothing to write",
    ("minion_horde_evo", "invisible_hit_speed_mult"):
        "the DIRECTION of the multiplier (attack period vs attack rate) is not decidable from "
        "the stub page -- 0.67 could mean either",
    ("princess_evo", "death_slow_zone"):
        "the zone's damage value is unpublished; an unmodelled mechanic, not a number",
    ("monk", "ability_tornado_immune"):
        "pull immunity is stated ONLY as ability-scoped while knockback immunity became "
        "permanent (12/12/2025); whether the pull followed is unstated anywhere",
    ("goblinstein", "first_hit_speed_s"):
        "published per BODY (Doctor 0.5 / Monster ...), and the card-level row cannot hold two",
    ("mighty_miner", "damage / damage_stages.0 / damage_ramp.damages.0"):
        "applied as mighty_miner.damage = 43 and mighty_miner.damage_stages.0 = 43 (the ledger "
        "spells one fact as a three-way composite field name)",
    ("skeleton_king", "ability_spawn_count"):
        "published as a RANGE (6-16, floor 6 plus one per soul) -- a soul-bank model, which is "
        "decisions.md ruling 8 / I7 scope, not a scalar",
    ("skeleton_king", "first_hit_speed_s"):
        "published per body (king 0.3 / summoned skeleton 0.2); the card-level row cannot hold "
        "both and spawn_unit_stats has no first-hit field yet",
    ("little_prince", "spawn_unit_stats.first_hit_speed_s"):
        "spawn_unit_stats carries no first-hit field anywhere in the KB; add the field with the "
        "I7 guardian handler rather than inventing a schema for one card",
}
for _c in ("archer_queen", "goblinstein", "golden_knight", "little_prince", "mighty_miner",
           "monk", "skeleton_king"):
    DEFER[(_c, "ability_cast_time_s")] = (
        "conflicts.md C7, reconfirmed live on all 8 champion pages: prose says a 1 s delay, the "
        "tables say Cast Time 0.933 / 0.944 / 0.766. The engine needs ONE convention and "
        "mighty_miner's ability_delay_s 1.0 is the standing precedent -- I7 rules on it")
DEFER[("boss_bandit", "ability_delay_s")] = (
    "conflicts.md C7 again, and load-bearing for decisions.md ruling 7 (the refund fires if the "
    "body dies DURING the delay). I7 sets the convention and wires the refund together")

# Rows the sweep itself refuses to settle. Recorded, never written.
SKIP = {
    ("bats", "hit_speed"):
        "sweep: 'I am NOT updating on a mis-worded entry' -- the 2/3/2026 line says 'hitpoints' "
        "while quoting seconds and naming the 1.3 the vardefine already holds",
    ("firecracker", "projectile_speed"):
        "sweep: 'No majority. Escalating with both raw strings rather than picking' -- the paths "
        "disagree about the whole series, and decisions.md #5 rules the firecracker_evo twin "
        "'wiki correct' at the same 550",
    ("three_musketeers", "hit_speed"):
        "sweep: 'WEAKEST of the P3 conflicts -- treat this History entry with suspicion'; the "
        "3/11/2025 rework already landed separately (commit 50a15de)",
    ("goblin_barrel_decoy", "spawns_troop.decoy_goblin.damage"):
        "sweep: 'I do NOT recommend acting on it' -- the 4/8/2026 line duplicates the 8/7/2024 "
        "line verbatim, the vardefine never moved, and cards.yaml records the owner "
        "USER-VERIFYING 89 in game on 2026-08-14, ten days after the claimed change",
    ("giant_skeleton", "death_crown_mult"):
        "sweep: 'Report only' -- unsourced on the page and pointing the wrong way (the only "
        "crown-family value in the DB above 1.0). conflicts.md item, not an I5 write",
    ("tombstone", "spawns.interval"):
        "DUP bucket: CURATION CONFIRMED CORRECT against the live page -- keep, do not re-open",
    ("fire_spirit", "hitpoints"):
        "PARENT bucket: the KB already uses the card page (215), which is the right default; the "
        "Furnace page's 230 is the stale surface",
    ("x_bow", "projectile_speed"):
        "null on all three paths -- no published baseline exists for the 4/8/2026 '+14%'",
    ("goblin_curse", "slow_pct"):
        "null on all three paths -- the 4/8/2026 slowdown mechanic is real but unquantified "
        "anywhere on the page",
    ("rocket", "knockback_tiles"):
        "null on all three paths, already deliberate: cards.yaml leaves it null and the engine "
        "falls back to Fireball's 1 tile",
    ("mirror", "elixir"):
        "null BY DESIGN -- Mirror costs 'previous card + 1'. A modelling gap, not a number",
    ("golden_knight", "ability_dash_travel_speed"):
        "null on all three paths; decisions.md ruling 10 amendment records the analog 500 "
        "(Bandit / Boss Bandit) as an UNTESTED placeholder, not a value to write",
    ("elite_barbarians_evo", "javelin_rage_trail"):
        "no source publishes magnitude, radius or duration -- record null and leave open",
    ("battle_ram_evo", "hit_speed"):
        "resolved as GENUINELY UNPUBLISHED: neither page publishes a hit speed for the ram",
    ("furnace", "lifetime_s"):
        "already applied on this branch (commit 1409b36): the Furnace is a TROOP since 4/8/2025 "
        "and carries no lifetime",
    ("dark_prince", "splash_radius_tiles"):
        "ALREADY RESOLVED, and re-adding it would REGRESS commit ba71b8f. That commit deleted the "
        "stale curated `splash_radius_tiles: 1.25` precisely because `_tiles_or` reads the "
        "*_tiles spelling in PREFERENCE to `splash_radius`, so two numbers on one row let the "
        "engine and every audit read different values in silence. The row's imported "
        "splash_radius is already the LAG bucket's 1.1; writing the *_tiles twin back would "
        "restore the shadow (tests/test_r2_engine_schema.DarkPrinceSplashShadowTests pins it)",
    ("tesla", "lifetime_s"):
        "conflicts.md E2: the mechanics layer (live, 30.0) and cards_stats (25.0) disagree and "
        "the field is imported-but-undeclared. The 3-of-3 wiki answer is 25; applied through the "
        "mechanics declaration in I4, not re-litigated here",
}
# princess_evo / minion_horde_evo: 'keep null + open per protocol' -- both Evolution pages are
# stubs that publish no stats, and build_spec already resolves these through the base card.
for _k in ("hitpoints", "damage", "hit_speed", "dps", "count", "range_tiles", "speed_tiles"):
    SKIP[("princess_evo", _k)] = ("wiki stub publishes no stats on any path; build_spec resolves "
                                  "it through the base princess row (protocol: keep null + open)")
    SKIP[("minion_horde_evo", _k)] = ("wiki stub publishes no stats on any path; build_spec "
                                      "resolves it through the base minion_horde row")

# decisions.md #11 tail: "Everything else in #11: keep sim values, tag `unsourced: true`".
# These are the 21 UNPUB bucket rows -- fields (and, for 13 of them, whole rows) that NO path
# publishes. The sim's number is kept because replacing it would be a guess; the row is MARKED so
# the next sweep can tell "nobody publishes this" apart from "nobody checked".
UNSOURCED_ROWS = ("balloon", "berserker", "elite_barbarians", "flying_machine", "barbarians",
                  "bowler", "cannon_cart", "electro_spirit", "battle_healer", "dart_goblin",
                  "fire_spirit", "electro_giant", "bats", "lumberjack_ghost", "goblin_cage",
                  "inferno_tower", "poison", "royal_delivery", "elite_barbarians_evo",
                  "minion_horde_evo", "furnace_evo")
for _k in UNSOURCED_ROWS:
    OVERRIDE[(_k, "unsourced")] = (
        True, _DEC + " #11: no path publishes the flagged value on this row -- the sim's own "
        "number is KEPT and the row marked, rather than replaced by a reconstruction", "y")

# Fields the importer emits (card_import._parse_card). Anything else is curated by hand.
IMPORT_FIELDS = {
    "attacks", "base", "champion", "charge_damage", "charge_range", "charge_speed_tiles",
    "components", "count", "crown_tower_damage", "damage", "damage_stages", "dash_damage",
    "dash_time_s", "death_damage", "death_radius_tiles", "deploy_time", "display", "dps",
    "elixir", "evo_cycles", "evolution", "freeze_duration_s", "hit_speed", "hitpoints",
    "hits_per_attack", "jump_damage", "jump_time_s", "kamikaze", "kind", "lifetime_s",
    "movement", "projectile_radius", "projectile_range", "projectile_speed",
    "projectile_width_tiles", "radius_tiles", "range_tiles", "rarity", "river_jump",
    "shield_hp", "slow_duration_s", "slow_pct", "spawn_crown_damage", "spawn_damage",
    "spawn_delay_s", "spawn_interval_s", "spawn_range_tiles", "spawn_unit_stats",
    "speed_tiles", "splash_radius", "stun_duration_s",
}


# --------------------------------------------------------------------------------------------
def _why(notes: str) -> str:
    """The first two sentences of a sweep note -- enough to say WHY in a cards.yaml comment.

    One sentence was too little: several notes open with a bare label ("HIGH IMPACT",
    "SYSTEMIC GATE BUG -- 10 of my 32 keys") and the evidence is in the sentence after it.
    """
    flat = " ".join((notes or "").split())
    parts = [p for p in flat.split(". ") if p.strip()]
    out = ". ".join(parts[:2]).strip()
    return (out[:260].rstrip(" ,;") if out else "r2 sweep, see stat_diffs.jsonl")


def _load():
    rows = [json.loads(l) for l in
            (LEDGER / "stat_diffs.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    buckets = json.loads((LEDGER / "r2_buckets.json").read_text(encoding="utf-8"))
    return rows, buckets


def _db(path=None):
    from clashrl.cards import CardDB
    return CardDB(path=path or (ROOT / "icebow" / "config" / "cards.yaml"))


_BASE_REF = "0905104"       # I4 gate -- the last commit before any I5 data change


def _baseline_db():
    """The merged CardDB as it stood BEFORE I5 touched anything.

    `before` is the measurement, so it has to be reproducible after the edits have landed --
    otherwise re-running `plan` silently re-baselines every row it already applied and the
    ledger's before/after collapses to a no-op. Materialising the three config files from the
    pre-I5 commit makes the plan a pure function of (ledger, rulings, baseline).
    """
    import subprocess
    import tempfile
    d = Path(tempfile.mkdtemp(prefix="i5_base_"))
    for name in ("cards.yaml", "cards_stats.json", "card_mechanics.json"):
        blob = subprocess.run(["git", "show", f"{_BASE_REF}:icebow/config/{name}"],
                              cwd=str(ROOT), capture_output=True, check=True).stdout
        (d / name).write_bytes(blob)
    return _db(d / "cards.yaml")


def _cur(db, key, field):
    c = db.get(key)
    if c is None:
        return "<NOKEY>"
    node = c
    for part in field.split("."):
        if isinstance(node, list) and part.isdigit() and int(part) < len(node):
            node = node[int(part)]
            continue
        if isinstance(node, dict) and part in node:
            node = node[part]
            continue
        return "<ABSENT>"
    return node


def _eq(a, b):
    if isinstance(a, str) or isinstance(b, str) or a is None or b is None:
        return a == b
    if isinstance(a, (list, dict)) or isinstance(b, (list, dict)):
        return a == b
    try:
        return abs(float(a) - float(b)) < 1e-6
    except (TypeError, ValueError):
        return a == b


def _rounding_target(db, key, resolved):
    """decisions.md #7: adopt the wiki's floor() convention for a DERIVED dps.

    Computed from OUR POST-I5 damage and hit_speed rather than copied from a probe. Six of the
    ten rows sit downstream of a damage or hit_speed ruling in another bucket, and the ledger's
    own note says so out loud for magic_archer: "If the damage ruling above is taken, dps becomes
    floor(125/1.1) = 113. Do not resolve this field before damage." `resolved` carries the values
    already planned this run (BULK puts LAG before ROUNDING for exactly this reason).
    """
    c = db.get(key) or {}
    dmg = resolved.get((key, "damage"), c.get("damage"))
    spd = resolved.get((key, "hit_speed"), c.get("hit_speed"))
    if dmg == _DROP or spd == _DROP or not dmg or not spd:
        return None
    return int(math.floor(float(dmg) / float(spd)))


def build_plan():
    import subprocess
    import yaml
    rows, buckets = _load()

    db = _baseline_db()
    cy = yaml.safe_load(subprocess.run(["git", "show", f"{_BASE_REF}:icebow/config/cards.yaml"],
                                       cwd=str(ROOT), capture_output=True,
                                       check=True).stdout.decode("utf-8"))
    curated = cy.get("cards") or {}
    stats = json.loads(subprocess.run(
        ["git", "show", f"{_BASE_REF}:icebow/config/cards_stats.json"], cwd=str(ROOT),
        capture_output=True, check=True).stdout.decode("utf-8"))["cards"]
    plan, skipped, deferred = [], [], []
    seen, resolved = set(), {}

    def emit(key, field, value, source, ruling, bucket, hint=""):
        if (key, field) in seen:
            return
        seen.add((key, field))
        before = _cur(db, key, field)
        if value != _DROP and _eq(before, value):
            skipped.append({"key": key, "field": field, "bucket": bucket, "after": value,
                            "reason": "already correct in the merged DB"})
            return
        if value == _DROP and before == "<ABSENT>":
            skipped.append({"key": key, "field": field, "bucket": bucket, "after": None,
                            "reason": "already absent from the merged DB"})
            return
        base = field.split(".")[0]
        # A pin can CORRECT or REMOVE an imported field; it cannot CREATE one -- `_apply_pins`
        # only acts when the field is present in the scraped row. Measured on 8 rows during I5
        # (electro_giant.crown_tower_damage, royal_delivery.radius_tiles, ...): the wiki simply
        # does not emit them for that key, so the value has to be curated or it lands nowhere.
        importable = base in (stats.get(key) or {})
        if hint == "p" and importable:
            route = "pin"
        elif hint == "y" or not importable:
            route = "curated"
        elif base in (curated.get(key) or {}) or "." in field or field not in IMPORT_FIELDS:
            route = "curated"
        else:
            route = "pin"
        resolved[(key, field)] = value
        plan.append({"key": key, "field": field, "before": before, "after": value,
                     "route": route, "source": source, "ruling": ruling, "bucket": bucket})

    # 1. owner rulings first -- they outrank every derivation
    for (key, field), (value, ruling, hint) in OVERRIDE.items():
        emit(key, field, value, "decisions.md", ruling, "RULING", hint)

    def gate(key, raw_field, bucket):
        """SKIP / DEFER / already-emitted, on the NORMALISED field name."""
        field = _norm_field(raw_field)
        for table, sink, why in ((SKIP, skipped, None), (DEFER, deferred, None)):
            if (key, field) in table or (key, raw_field) in table:
                reason = table.get((key, field)) or table[(key, raw_field)]
                sink.append({"key": key, "field": field, "bucket": bucket, "after": None,
                             "reason": reason})
                seen.add((key, field))
                return None
        return None if (key, field) in seen else field

    # 2. the seven owner-approved buckets
    for bucket in BULK:
        for r in buckets[bucket]:
            key = r["key"]
            field = gate(key, r["field"], bucket)
            if field is None:
                continue
            if bucket == "ROUNDING":
                emit(key, field, _rounding_target(db, key, resolved),
                     "r2_buckets.json ROUNDING + " + _DEC + " #7",
                     "adopt the wiki's floor() for derived DPS: floor(damage/hit_speed)", bucket)
                continue
            val = None
            for p in PREFER[bucket]:
                val = _n(r.get(p), field.split(".")[-1])
                if val is not None:
                    break
            if val is None:
                deferred.append({"key": key, "field": field, "bucket": bucket,
                                 "reason": "every probe is prose, not a value the KB can hold",
                                 "p1": r.get("p1"), "p2": r.get("p2"), "p3": r.get("p3")})
                continue
            emit(key, field, val, "r2_buckets.json %s" % bucket, _why(r.get("notes")), bucket)

    # 3. the 101 verdict:update rows
    for r in rows:
        if r.get("verdict") != "update":
            continue
        key, prop = r["key"], r.get("proposed")
        field = gate(key, r["field"], "UPDATE")
        if field is None:
            continue
        val = _n(prop, field.split(".")[-1])
        if val is None:
            deferred.append({"key": key, "field": field, "bucket": "UPDATE",
                             "reason": "the ledger's `proposed` is prose, not a value the KB can "
                                       "hold", "proposed": prop})
            continue
        emit(key, field, val, "stat_diffs.jsonl verdict:update", _why(r.get("notes")), "UPDATE")

    return {"plan": plan, "skipped": skipped, "deferred": deferred}


def cmd_plan(argv):
    out = build_plan()
    (LEDGER / "i5_plan.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    byb = collections.Counter(p["bucket"] for p in out["plan"])
    byr = collections.Counter(p["route"] for p in out["plan"])
    sks = collections.Counter(
        "already correct/absent" if s["reason"].startswith("already") else "sweep declined"
        for s in out["skipped"])
    print("PLAN %d changes | skipped %d | deferred %d"
          % (len(out["plan"]), len(out["skipped"]), len(out["deferred"])))
    print("  by bucket: " + ", ".join("%s %d" % kv for kv in sorted(byb.items())))
    print("  by route : " + ", ".join("%s %d" % kv for kv in sorted(byr.items())))
    print("  skipped  : " + ", ".join("%s %d" % kv for kv in sorted(sks.items())))
    if "-v" in argv:
        for p in out["plan"]:
            print("  %-8s %-8s %-22s %-36s %s -> %s"
                  % (p["bucket"], p["route"], p["key"], p["field"],
                     repr(p["before"])[:22], repr(p["after"])[:34]))
        print("\nSKIPPED:")
        for s in out["skipped"]:
            print("  %-22s %-36s %s" % (s["key"], s["field"], s["reason"][:100]))
        print("\nDEFERRED:")
        for d in out["deferred"]:
            print("  %-22s %-36s %s" % (d["key"], d["field"], d["reason"][:80]))
    return 0


def cmd_verify(argv):
    out = json.loads((LEDGER / "i5_plan.json").read_text(encoding="utf-8"))
    db = _db()
    applied, missing = [], []
    for p in out["plan"]:
        now = _cur(db, p["key"], p["field"])
        want = p["after"]
        ok = (now == "<ABSENT>") if want in (None, _DROP) else _eq(now, want)
        if ok:
            applied.append({"key": p["key"], "field": p["field"], "before": p["before"],
                            "after": (None if want == _DROP else want), "route": p["route"],
                            "source": p["source"], "ruling": p["ruling"], "bucket": p["bucket"]})
        else:
            missing.append((p["key"], p["field"], want, now, p["route"]))
    with (LEDGER / "i5_applied.jsonl").open("w", encoding="utf-8") as fh:
        for a in applied:
            fh.write(json.dumps(a, ensure_ascii=False) + "\n")
    byr = collections.Counter(a["route"] for a in applied)
    byb = collections.Counter(a["bucket"] for a in applied)
    print("APPLIED %d/%d rows -> ledger/i5_applied.jsonl" % (len(applied), len(out["plan"])))
    print("  by bucket: " + ", ".join("%s %d" % kv for kv in sorted(byb.items())))
    print("  by route : " + ", ".join("%s %d" % kv for kv in sorted(byr.items())))
    if missing:
        print("NOT LANDED (%d):" % len(missing))
        for k, f, w, n, r in missing:
            print("  %-22s %-36s want %-18s got %-18s [%s]"
                  % (k, f, repr(w)[:18], repr(n)[:18], r))
        return 1
    print("every planned change is present in the merged CardDB.")
    return 0


# --------------------------------------------------------------------------------------------
# The curated half: a SURGICAL cards.yaml editor.
#
# Not a YAML round-trip. Every curated number in that file carries a dated citation naming the
# superseded value and the source, and safe_load/dump would delete all of it. This walks the
# file as TEXT: it rewrites only the lines it must, keeps every other byte, and prefixes each
# touched entry with a dated house-style comment block naming the superseded value and the
# ruling. The safety net is in cmd_edit: the parsed `cards` mapping before and after must differ
# by EXACTLY the planned set -- so however clumsy the text handling, a stray edit is caught.
# --------------------------------------------------------------------------------------------
_KEYLINE = __import__("re").compile(r"^  ([A-Za-z0-9_]+):")
_DATE = "2026-08-26"


def _yv(v):
    """A value as YAML would write it inline.

    safe_dump closes a bare-scalar document with a "..." marker line, which is not part of the
    value -- emitting it wrote `gen_every_s: 13.0` followed by a stray `...` and broke the parse.
    """
    import yaml
    t = yaml.safe_dump(v, default_flow_style=True, width=10 ** 6,
                       allow_unicode=True, sort_keys=False)
    return "\n".join(l for l in t.split("\n") if l.strip() != "...").strip()


def _entries(lines):
    """{key: (start, end)} spans of the top-level card entries."""
    start = next(i for i, l in enumerate(lines) if l.rstrip() == "cards:")
    hits = [(i, m.group(1)) for i, l in enumerate(lines[start + 1:], start + 1)
            if (m := _KEYLINE.match(l))]
    out = {}
    for n, (i, key) in enumerate(hits):
        out[key] = (i, hits[n + 1][0] if n + 1 < len(hits) else len(lines))
    return out


def _own_end(lines, start, end):
    """Where the entry REALLY ends.

    A key's span runs to the next key line, which drags along the blank line and the indent-2
    comment block that introduce the NEXT entry. Appending a field there puts it after a comment
    that belongs to somebody else -- and, measured on elixir_collector, after a section header,
    which is how `verified: true` ended up outside the mapping entirely.
    """
    j = end
    while j > start + 1 and (not lines[j - 1].strip()
                             or (lines[j - 1].startswith("  #")
                                 and not lines[j - 1].startswith("    "))):
        j -= 1
    return j


def _flow_span(lines, i):
    """(last_line_index, inner_text, trailing_comment) for a `key: {...}` entry, or None."""
    head = lines[i]
    if "{" not in head.split(":", 1)[1][:2].strip() and not head.split(":", 1)[1].lstrip().startswith("{"):
        return None
    j, depth, buf = i, 0, []
    while j < len(lines):
        seg = lines[j] if j > i else lines[i].split(":", 1)[1]
        buf.append(seg)
        depth += seg.count("{") - seg.count("}")
        if depth == 0:
            break
        j += 1
    text = "\n".join(buf)
    close = text.rindex("}")
    return j, text[text.index("{") + 1:close], text[close + 1:].strip()


def _edit_entry(lines, span, changes, merged, key):
    """Rewrite one entry's lines for `changes` = [(field, value), ...]. Returns new lines."""
    import yaml
    i, end = span
    own = _own_end(lines, i, end)
    body = lines[i:own]
    tail_lines = lines[own:end]
    flow = _flow_span(lines, i)

    # Fields whose parent is a dict/list: cards.yaml curation REPLACES the whole value (CardDB
    # merges per top-level field, not deeply), so the parent has to be written out in full from
    # the merged row or the imported siblings are silently dropped.
    # Several dotted changes can share one parent (little_prince writes three
    # spawn_unit_stats.* fields). Each has to fold into the SAME copy -- rebuilding the parent
    # per change made the last write win and silently dropped the earlier two.
    flat, parents = [], {}
    for field, value in changes:
        if "." not in field:
            flat.append((field, value))
            continue
        head, rest = field.split(".", 1)
        if head not in parents:
            parents[head] = json.loads(json.dumps(merged.get(head) or {}))   # deep copy
        node, parts = parents[head], rest.split(".")
        for p in parts[:-1]:
            if isinstance(node, list):
                node = node[int(p)]
            else:
                node = node.setdefault(p, {})
        leaf = parts[-1]
        if value == _DROP:
            (node.pop(int(leaf)) if isinstance(node, list) else node.pop(leaf, None))
        elif isinstance(node, list):
            node[int(leaf)] = value
        else:
            node[leaf] = value
    flat += list(parents.items())

    if flow:
        last, inner, tail = flow
        row = yaml.safe_load("{" + inner + "}") or {}
        for field, value in flat:
            if value == _DROP:
                row.pop(field, None)
            else:
                row[field] = value
        row.setdefault("verified", True)
        ver = row.pop("verified")
        row["verified"] = ver                                  # keep `verified` last, house style
        new = ["  %s: {%s}%s" % (key, ", ".join("%s: %s" % (k, _yv(v)) for k, v in row.items()),
                                 ("   " + tail) if tail else "")]
        return new + lines[last + 1:end]

    # block entry: touch only the affected lines
    out = list(body)
    for field, value in flat:
        pat = __import__("re").compile(r"^    %s\s*:" % __import__("re").escape(field))
        at = next((n for n, l in enumerate(out) if pat.match(l)), None)
        # A block field can own CHILD lines (tesla's `evolution:` is a nested mapping at indent
        # 6). Replacing only the header line leaves the children orphaned and the file stops
        # parsing, so the whole sub-block goes with it.
        stop = at + 1 if at is not None else None
        while stop is not None and stop < len(out) and out[stop].startswith("      "):
            stop += 1
        if value == _DROP:
            if at is not None:
                del out[at:stop]
            continue
        old_c = ""
        if at is not None:
            rest = out[at].split(":", 1)[1]
            if "#" in rest:
                old_c = rest.split("#", 1)[1].strip()
        line = "    %s: %s" % (field, _yv(value))
        if old_c:
            line += "   # " + old_c
        if at is None:
            out.append(line)
        else:
            out[at:stop] = [line]
    if not any(__import__("re").match(r"^    verified\s*:", l) for l in out):
        out.append("    verified: true")
    return out + tail_lines


def _comment_block(key, changes, unsourced=False):
    import textwrap
    head = ("  # I5 %s -- adjudicated R2 ledger applied (research/sim_parity/decisions.md; "
            "row-by-row provenance in research/sim_parity/ledger/i5_applied.jsonl)." % _DATE)
    out = textwrap.wrap(head, 98, initial_indent="", subsequent_indent="  # ")
    for c in changes:
        was = "ABSENT" if c["before"] == "<ABSENT>" else repr(c["before"])
        now = "REMOVED" if c["after"] == _DROP else repr(c["after"])
        out += textwrap.wrap("%s: SUPERSEDED %s -> %s. %s" % (c["field"], was, now, c["ruling"]),
                             98, initial_indent="  #   ", subsequent_indent="  #     ")
    if unsourced:
        out += textwrap.wrap("unsourced: true -- decisions.md #11: no path publishes these; the "
                             "sim's own values are kept and MARKED rather than replaced by a "
                             "guess.", 98, initial_indent="  #   ", subsequent_indent="  #     ")
    return out


_META_OLD = """meta:
  level: 11
  mode: "1v1"
  updated: "2026-07-24"
  stats_source: null        # e.g. "RoyaleAPI" once combat stats are imported
  notes: >
    Elixir + categorical fields populated. Combat stats (hitpoints/damage/
    hit_speed) pending import from a stats source (see README refresh note)."""

_META_NEW = """meta:
  level: 11
  mode: "1v1"
  updated: "2026-08-26"     # I5: the adjudicated R2 ledger applied (both stale since 2026-07-24)
  stats_source: "clashroyale.fandom.com (MediaWiki level-11 vardefines) via `cards-import`,
    corrected by the R2 sweep + owner adjudications in research/sim_parity/decisions.md.
    Deliberate deviations from the wiki live in config/import_pins.json and NOWHERE else --
    tools/stat_sweep.py reads that file as its EXPECTED set, so a value that disagrees with
    the wiki and is not pinned is a finding, not a preference."
  notes: >
    Combat stats are imported (config/cards_stats.json, level 11) and overlaid by the curated
    rows below; the game-file structural constants sit between them (config/card_mechanics.json).
    Every curated number that contradicts the wiki carries a dated comment naming the superseded
    value and the ruling; row-by-row provenance for the I5 application is in
    research/sim_parity/ledger/i5_applied.jsonl."""


def _bump_meta(text: str) -> str:
    """PLAN.md I5: `updated` and `stats_source` have both been stale since 2026-07-24.

    Folded into `edit` rather than done by hand so the whole application is one repeatable
    command; a second run is a no-op because the old block is gone.
    """
    return text.replace(_META_OLD, _META_NEW, 1)


def cmd_edit(argv):
    import copy
    import yaml
    plan = json.loads((LEDGER / "i5_plan.json").read_text(encoding="utf-8"))["plan"]
    rows = [p for p in plan if p["route"] == "curated"]
    by_key = collections.OrderedDict()
    for p in rows:
        by_key.setdefault(p["key"], []).append(p)
    merged_db = _db()

    for deck in ("icebow", "hogeq"):
        path = ROOT / deck / "config" / "cards.yaml"
        text = path.read_text(encoding="utf-8")
        before = yaml.safe_load(text)["cards"]
        lines = text.split("\n")
        spans = _entries(lines)
        missing = [k for k in by_key if k not in spans]

        for key in sorted(by_key, key=lambda k: spans.get(k, (10 ** 9,))[0], reverse=True):
            if key not in spans:
                continue
            ch = by_key[key]
            merged = merged_db.get(key) or {}
            new = _edit_entry(lines, spans[key], [(c["field"], c["after"]) for c in ch],
                              merged, key)
            i, end = spans[key]
            lines[i:end] = _comment_block(key, ch, unsourced=key in UNSOURCED_ROWS) + new

        if missing:
            lines += ["", "  # " + "=" * 68,
                      "  # I5 %s -- cards with NO curated row until now. Every field below is a"
                      % _DATE,
                      "  # value the importer does not emit for this key, so it can only live"
                      " here.",
                      "  # " + "=" * 68]
            for key in missing:
                ch = by_key[key]
                row = {}
                for c in ch:
                    if c["after"] != _DROP:
                        row[c["field"]] = c["after"]
                row["verified"] = True
                lines += _comment_block(key, ch)
                lines.append("  %s: {%s}" % (key, ", ".join("%s: %s" % (k, _yv(v))
                                                            for k, v in row.items())))

        # UNSOURCED marker for rows decisions.md #11 leaves at their sim values
        out = "\n".join(lines)
        after = yaml.safe_load(out)["cards"]

        # SAFETY NET: the parsed mapping must differ by EXACTLY the planned set.
        want = {}
        for p in rows:
            want.setdefault(p["key"], []).append(p)
        stray = []
        for k in set(before) | set(after):
            b, a = before.get(k), after.get(k)
            if b == a:
                continue
            fields = {f for f in set(b or {}) | set(a or {})
                      if (b or {}).get(f) != (a or {}).get(f)}
            planned = {p["field"].split(".")[0] for p in want.get(k, [])} | {"verified"}
            extra = fields - planned
            if extra:
                stray.append("%s: %s" % (k, sorted(extra)))
        if stray:
            print("REFUSING to write %s -- %d stray field change(s):" % (path, len(stray)))
            for s in stray:
                print("   " + s)
            return 1
        out = _bump_meta(out)
        path.write_text(out.rstrip("\n") + "\n", encoding="utf-8", newline="")
        print("edited %s: %d entries, %d fields (%d new rows)"
              % (path, len(by_key), len(rows), len(missing)))
    return 0


def main(argv) -> int:
    cmd = argv[1] if len(argv) > 1 else "plan"
    if cmd == "plan":
        return cmd_plan(argv)
    if cmd == "edit":
        return cmd_edit(argv)
    if cmd == "verify":
        return cmd_verify(argv)
    print(__doc__)
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
