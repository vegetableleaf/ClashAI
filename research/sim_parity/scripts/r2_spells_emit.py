# -*- coding: utf-8 -*-
"""Emit research/sim_parity/ledger/r2_spells.jsonl for the 22-key "spells" group."""
import json

OUT = r'C:/Users/benpe/ClashBot/research/sim_parity/ledger/r2_spells.jsonl'
W = "https://clashroyale.fandom.com/wiki/"
F = "2026-08-26"
REV = {
    "arrows": ("Arrows", 437304), "barbarian_barrel": ("Barbarian_Barrel", 437163),
    "clone": ("Clone", 436842), "earthquake": ("Earthquake", 437302),
    "fireball": ("Fireball", 437299), "freeze": ("Freeze", 437301),
    "giant_snowball": ("Giant_Snowball", 437307), "goblin_barrel": ("Goblin_Barrel", 436494),
    "goblin_barrel_decoy": ("Goblin_Barrel/Evolution", 437372),
    "goblin_curse": ("Goblin_Curse", 437353), "graveyard": ("Graveyard", 437290),
    "lightning": ("Lightning", 437298), "mirror": ("Mirror", 436846),
    "poison": ("Poison", 437536), "rage": ("Rage", 437309), "rocket": ("Rocket", 437297),
    "royal_delivery": ("Royal_Delivery", 437384), "the_log": ("The_Log", 437310),
    "tornado": ("Tornado", 436504), "vines": ("Vines", 437543), "void": ("Void", 437352),
    "zap": ("Zap", 437305),
}
# fields compared per key, including the matching ones that get no JSONL line
CHECKED = {
    "arrows": 10, "barbarian_barrel": 17, "clone": 7, "earthquake": 12, "fireball": 9,
    "freeze": 8, "giant_snowball": 9, "goblin_barrel": 13, "goblin_barrel_decoy": 7,
    "goblin_curse": 18, "graveyard": 17, "lightning": 8, "mirror": 4, "poison": 10,
    "rage": 9, "rocket": 9, "royal_delivery": 16, "the_log": 10, "tornado": 8,
    "vines": 11, "void": 10, "zap": 8,
}

rows = []


def R(key, field, cur, p1, p2, p3, vote, verdict, notes, raws):
    t, rv = REV[key]
    rows.append({
        "key": key, "field": field, "current_db": cur, "p1_vardefine": p1,
        "p2_table": p2, "p3_history": p3,
        "sources": [{"url": W + t, "revid": rv, "fetched": F, "raw": r} for r in raws],
        "vote": vote, "cross_checks": {"edit_war": "pass"},
        "verdict": verdict, "notes": notes,
    })


# ------------------------------- ARROWS -------------------------------
R("arrows", "crown_tower_damage", 31, 31, None, 24, "split", "escalate",
  "1/6/2026 cut Arrows crown damage to 20% of full; 122*0.20=24.4 -> 24. Vardefine 31 is the "
  "pre-1/6/2026 25% value (122*0.25=30.5 -> 31) and is what the sim imported. The same lag was "
  "already resolved by owner pins for rocket/lightning/zap/the_log/poison -- arrows was MISSED "
  "because icebow/tools/crown_damage_audit.py's regex requires the literal 'of the full damage' "
  "and every one of the Arrows page's four crown entries says 'of their full damage', so the "
  "tool printed 'no % in history'. Field is not set in icebow/config/cards.yaml (row is "
  "verified:true but this field is imported).",
  ["{{#vardefine: dmg_11 | 122 }}", "{{#vardefine: crown_dmg_11| 31 }}",
   "* On 1/6/2026, a Balance Update decreased the Arrows' Crown Tower Damage to 20% of their "
   "full damage (from 25%)"])

# --------------------------- BARBARIAN BARREL ---------------------------
bb = ["{{#vardefine: spawn_11 | 230 }}", "{{#vardefine: dmg_11 | 191 }}",
      "unit-statistics-table headers: Level | Barbarian Barrel Area Damage | Hitpoints | Damage "
      "| Damage Per Second",
      "the 'Barbarian Barrel Area Damage' column renders {{#var:spawn_11}}; the 'Damage' column "
      "renders {{#var:dmg_11}}"]
R("barbarian_barrel", "damage", 191, 230, 230, None, "2of3", "escalate",
  "INVERTED SPAWN/PARENT MAPPING. The statistics table's 'Barbarian Barrel Area Damage' column "
  "is rendered from spawn_11 (230); the 'Damage' column (dmg_11=191) is the spawned BARBARIAN's "
  "swing. Corroborating tell: 191/1.3 = 147 = the DB row's own dps field, so 191 demonstrably "
  "belongs to the troop. The barrel's roll should deal 230, so the sim under-rolls by 17%. Row "
  "is curated verified:true.", bb)
R("barbarian_barrel", "spawn_damage", 230.0, 191, 191, None, "2of3", "escalate",
  "Mirror of the damage row: spawn_damage currently holds the barrel's own 230 area damage "
  "while the spawned Barbarian's 191 sits in `damage`. The two fields are swapped.", bb)
R("barbarian_barrel", "roll_tiles", 5.0, None, 4.5, 4.5, "2of3", "escalate",
  "STALE BY ONE BALANCE UPDATE. cards.yaml pins roll_tiles 5.0 quoting the 3/9/2018 entry "
  "('decreased its rolling distance to 5 tiles (from 7 tiles)'), but 7/6/2022 cut it again to "
  "4.5, and the attributes table's Range cell agrees at 4.5. Internal tell: the same DB row "
  "already carries range_tiles 4.5, so roll_tiles 5.0 contradicts its own sibling field. "
  "Curated verified:true.",
  ["|2||4.5||2.6||Ground||Spell||{{Rarity|Epic}}   (Cost|Range|Width|Target|Type|Rarity)",
   "*On 7/6/2022, a Balance Update, decreased the Barbarians' attack time interval to 1.3 "
   "seconds (from 1.4 seconds), but it also decreased the Barbarian Barrel's rolling distance "
   "to 4.5 tiles (from 5 tiles)."])
R("barbarian_barrel", "width_tiles", None, None, 2.6, 2.6, "2of3", "update",
  "MISSING FIELD. The barrel is a rectangular corridor, not a point: the attributes table "
  "publishes Width 2.6 and 1/7/2019 set it to 2.6 (from 3.9). The DB has no width, so the sim "
  "cannot know which lane-adjacent troops the roll actually clips.",
  ["|2||4.5||2.6||Ground||Spell||{{Rarity|Epic}}   (Cost|Range|Width|Target|Type|Rarity)",
   "*On 1/7/2019, the July 2019 Update, decreased the Barbarian Barrel's width to 2.6 tiles "
   "(from 3.9 tiles)."])
R("barbarian_barrel", "spawn_unit_stats.deploy_time", None, None, 0.5, 1.0, "split", "escalate",
  "MISSING FIELD AND THE PATHS DISAGREE. The spawned Barbarian's deploy time is 1.0s per the "
  "1/12/2025 balance entry, but the secondary attributes table still reads 0.5 sec (never "
  "updated). The DB carries no deploy time for the spawn at all -- this is the window a "
  "counter-spell is thrown into.",
  ["secondary table: |1.3 sec||0.4 sec||Medium (60)||0.5 sec||Melee: Short (0.5)||Ground||x1||"
   "Ground   (Hit Speed|First Hit Speed|Speed|Deploy Time|Range|Target|Count|Transport)",
   "*On 1/12/2025, a Balance Update decreased the Barbarian Barrel's Barbarian deploy time to 1 "
   "seconds (from 0.5 seconds) and decreased the Barrel damage by 4%."])

# -------------------------------- CLONE --------------------------------
cl = ["|3||1||1||3||Friendly Troops||Spell||{{Rarity|Epic}}   (Cost|Clone Hitpoints|Clone Shield "
      "Hitpoints|Radius|Target|Type|Rarity)"]
R("clone", "clone_hitpoints", None, None, 1, None, "2of3", "update",
  "MISSING FIELD on a verified:false row (clone has no icebow/config/cards.yaml entry at all). "
  "The card's entire identity is that clones have 1 HP; the DB row carries only "
  "elixir/radius/rarity/count, so a cloned push is indistinguishable from a real one to the sim.",
  cl)
R("clone", "clone_shield_hitpoints", None, None, 1, None, "2of3", "update",
  "MISSING FIELD. The attributes table publishes Clone Shield Hitpoints = 1 (a cloned Dark "
  "Prince / Royal Recruit keeps a 1 HP shield).", cl)
R("clone", "cloning_time_s", None, None, None, 0.5, "2of3", "escalate",
  "MISSING FIELD, history path only. 12/6/2017 decreased the cloning time to 0.5s (from 0.8s) "
  "and nothing later changes it; no table cell corroborates, so this is escalate rather than "
  "update.",
  ["*On 12/6/2017, the June 2017 Update decreased the cloning time to 0.5 seconds (from 0.8 "
   "seconds)."])
R("clone", "targets", None, None, "Friendly Troops", None, "2of3", "update",
  "MISSING FIELD. Table Target = 'Friendly Troops', and the card text says 'Doesn't affect "
  "buildings'. The DB row has no attacks/targets key at all, so nothing constrains what Clone "
  "may be cast on or which entities it duplicates.",
  cl + ["{{Quote|Duplicates all friendly troops in the target area. Cloned troops are fragile, "
        "but pack the same punch as the original! Doesn't affect buildings.}}"])

# ------------------------------ EARTHQUAKE ------------------------------
eq = ["{{#vardefine: dmg_11 | 84 }}", "{{#vardefine: build_dmg_11 | 287 }}",
      "{{#vardefine: crown_dmg_11 | 53 }}", "{{#vardefine: dmg_hits | 3 }}"]
R("earthquake", "damage", 81, 84, 84, None, "2of3", "escalate",
  "The curated row pins damage 81 but the live vardefine is 84. PROOF the curator already had "
  "84 in hand: the same row's crown_tower_damage 49 is only reproducible as round(84*0.58)=49 "
  "-- round(81*0.58)=47 -- so the crown field was re-derived from 84 while `damage` was left at "
  "the old 81. Curated verified:true, so this goes to owner batch review rather than an "
  "auto-update.", eq)
R("earthquake", "build_damage", 283, 287, 287, None, "2of3", "escalate",
  "Same stale-curation as `damage`: vardefine build_dmg_11 = 287 vs DB 283. Ratio sanity check "
  "against the lead's 'doing 3.5 times damage to buildings': 287/84 = 3.42, 283/81 = 3.49 -- "
  "both approximate, but 287 is the published integer. Curated verified:true.", eq)
R("earthquake", "crown_tower_damage", 49, 53, None, 49, "2of3", "pin",
  "CORRECT PIN, no action. 1/6/2026 set crown damage to 58% of full troop damage: 84*0.58 = "
  "48.72 -> 49, which is exactly what the DB holds; vardefine 53 is the stale ~65% value. Note "
  "the owner's audit tool reports Earthquake as 'no % in history' because its regex wants 'of "
  "the full damage' and this page says 'of the full troop damage'.",
  eq + ["* On 1/6/2026, a Balance Update, decreased the Earthquake's Crown Tower damage to 58% "
        "of the full troop damage (from 65%)"])

# ------------------------------- FIREBALL -------------------------------
R("fireball", "crown_tower_damage", 207, 207, None, 172, "split", "escalate",
  "HIGHEST-TRAFFIC MISS IN THE GROUP. TWO independent 2026 history entries agree the value is "
  "now 172 -- one states the arithmetic outright ('207-172', linked to Supercell's June 2026 "
  "release notes), the other states the rule (25% of full: 688*0.25 = 172). Vardefine 207 is "
  "the 30% era. The owner's audit tool printed Fireball 'ok' because its regex skipped both "
  "2026 entries ('of its full damage') and matched the 4/8/2020 line instead, making pcts[-1] "
  "= 30% -- a FALSE PASS, which is worse than the silent misses. Field not set in cards.yaml "
  "(row verified:true, field imported).",
  ["{{#vardefine: dmg_11 | 688 }}", "{{#vardefine: crown_dmg_11 | 207 }}",
   "*1/7/26 Decreased the fireballs crown tower damage by 17% 207-172 [https://supercell.com/en/"
   "games/clashroyale/blog/release-notes/june-balance-changes-2026/ june update]",
   "* On 1/6/2026, a Balance Update, decreased the Fireball's Crown Tower Damage to 25% of its "
   "full damage (from 30%)"])

# -------------------------------- FREEZE --------------------------------
R("freeze", "crown_tower_damage", 35, 35, None, 29, "split", "escalate",
  "1/6/2026 cut Freeze crown damage to 25% of full: 115*0.25 = 28.75 -> 29. Vardefine 35 is the "
  "30% value. Freeze was never audited at all -- it is absent from crown_damage_audit.py's "
  "CARDS list, and it is one of only two spells in this group with NO icebow/config/cards.yaml "
  "entry (verified:false). Its regex WOULD have matched had the card been listed.",
  ["{{#vardefine: dmg_11 | 115 }}", "{{#vardefine: crown_dmg_11 | 35 }}",
   "* On 1/6/2026, a Balance Update, decreased the Freeze's Crown Tower damage to 25% of the "
   "full damage (from 30%)"])

# ----------------------------- GIANT SNOWBALL -----------------------------
R("giant_snowball", "crown_tower_damage", 54, 54, None, 45, "split", "escalate",
  "1/6/2026 cut it to 25% of full: 179*0.25 = 44.75 -> 45; vardefine 54 is the 30% value. "
  "Missed by the audit tool for a THIRD distinct reason: this page wraps the phrase in a "
  "category link ('[[:Category:Crown Towers|Crown Tower]] damage to 25% of the full damage'), "
  "so the tool's contiguous 'Crown Tower damage' regex never matches and it reported 'no % in "
  "history'. Row is verified:true but this field is not curated.",
  ["{{#vardefine: dmg_11 | 179 }}", "{{#vardefine: crown_dmg_11 | 54 }}",
   "decreased the Giant Snowball's [[:Category:Crown Towers|Crown Tower]] damage to 25% of the "
   "full damage (from 30%)"])

# ----------------------------- GOBLIN BARREL -----------------------------
R("goblin_barrel", "spawn_unit_stats.deploy_time", None, None, 1.1, 1.1, "2of3", "update",
  "MISSING FIELD, both paths agree on 1.1s. cards.yaml's own comment already argues this "
  "matters ('The Goblins then take their own deploy time ... which is the window a log is "
  "thrown into') but no field carries it. Every other field on this key is a clean match "
  "(damage 0 after the 4/7/2016 impact-damage removal, radius 1.5, count 3, goblin 202 hp / "
  "1.1s / melee 0.5 / Very Fast 120 -> 2.0 tiles-per-sec).",
  ["secondary table: |1.1 sec||0.4 sec||Very Fast (120)||1.1 sec||Melee: Short (0.5)||Ground||"
   "x3||Ground   (Hit Speed|First Hit Speed|Speed|Deploy Time|Range|Target|Count|Transport)",
   "*On 6/5/2019, a Balance Update, decreased the Goblins' spawn time to 1.1 seconds (from 1.2 "
   "seconds)."])

# -------------------------- GOBLIN BARREL DECOY --------------------------
R("goblin_barrel_decoy", "spawns_troop.decoy_goblin.damage", 89, 89, 89, 66, "split", "escalate",
  "Sourced from Goblin Barrel/Evolution -- the 'Decoy Goblin Damage' column of "
  "unit-statistics-table plus the de_* vardefine block; this key has no page of its own. The "
  "4/8/2026 entry would put the Decoy Goblin at 89*0.74 = 65.9 -> 66, but I do NOT recommend "
  "acting on it: (a) a revision time-machine shows the only 2026 edit to this page touched the "
  "History section -- de_dmg_11 has been 89 since before 4/8/2026; (b) the 4/8/2026 line is a "
  "verbatim duplicate of the 8/7/2024 line, same -26%, which reads like an editor copy-paste; "
  "(c) cards.yaml records the owner USER-VERIFYING 89 damage in-game on 2026-08-14, ten days "
  "AFTER the claimed change. Evidence favours 89 standing. Flagged so it is not silently "
  "'fixed' later. NB the row this would touch is decoy_goblin, which belongs to another group.",
  ["{{#vardefine: de_dmg_11 | 89 }}", "{{#vardefine: de_hp_11 | 81 }}",
   "*On 8/7/2024, a Balance Update, decreased the Decoy Goblins' damage by 26%.",
   "* On 4/8/2026, a balance Update, decreased the Decoy Goblins' damage by 26%.",
   "time-machine: pre-4/8/2026 revid 436495 (2026-06-27) de_dmg_11=89; live revid 437372 "
   "de_dmg_11=89 (unchanged)"])

# ------------------------------ GOBLIN CURSE ------------------------------
gc = ["{{#vardefine: curse_dmg_11 | 35 }}", "{{#vardefine: dmg_hits | 6 }}",
      "{{#vardefine: crown_dmg_11 | 10 }}", "{{#vardefine: hp_11 | 202 }}",
      "{{#vardefine: dmg_11 | 120 }}",
      "unit-statistics-table headers: Level | Area Damage | Crown Tower Damage | Goblin "
      "Hitpoints | Goblin Damage | Goblin Damage per second",
      "the 'Area Damage' column renders {{#var:curse_dmg_11}} x{{#var:dmg_hits}}; the 'Goblin "
      "Damage' column renders {{#var:dmg_11}}"]
R("goblin_curse", "damage", 120, 35, 35, None, "2of3", "update",
  "SPAWNED-UNIT STATS SUBSTITUTED FOR THE SPELL -- the largest numeric error in this group. The "
  "statistics table's 'Area Damage' column is rendered from curse_dmg_11 (35 per tick, x6 = 210 "
  "total); dmg_11 = 120 feeds the column headed 'Goblin Damage', i.e. the Goblin the curse "
  "converts victims into. The DB put 120 in the spell's `damage` alongside hits_per_attack 6, "
  "so a 2-elixir spell resolves 720 damage instead of 210 -- 3.4x. Corroborating tell: the "
  "row's dps 109 = 120/1.1, the Goblin's DPS, which is not a property a spell has. Row is "
  "verified:false (no cards.yaml entry), so no curated value is being overturned.", gc)
R("goblin_curse", "zone_s", None, None, 6, 6, "2of3", "update",
  "MISSING FIELD. Goblin Curse is a 6-second damage-over-time zone (table Duration 6 sec; lead "
  "'dealt every second for 6 seconds'), but unlike poison/void/earthquake the DB row has no "
  "zone_s/zone_tick_s -- it resolves as an instant 6x multi-hit, so nothing can walk out of it.",
  ["|2||3||6 sec||Air & Ground||Spell||{{Rarity|Epic}}   (Cost|Radius|Duration|Target|Type|"
   "Rarity)",
   "lead: 'an area-damage, air-targeting spell with a medium radius and very low damage that is "
   "dealt every second for 6 seconds'"])
R("goblin_curse", "zone_tick_s", None, None, 1.0, 1.0, "2of3", "update",
  "MISSING FIELD, pairs with zone_s: 6 hits over 6 seconds = a 1.0s tick (vardefine dmg_hits = "
  "6).",
  ["{{#vardefine: dmg_hits | 6 }}", "lead: 'dealt every second for 6 seconds'"])
R("goblin_curse", "spawns_troop", None, None, "Goblin: hp 202 / dmg 120 / hit speed 1.1s", None,
  "2of3", "update",
  "MISSING MECHANIC. The card's defining effect -- cursed enemies that die become Goblins for "
  "the caster -- is not represented at all: the row has spawn_unit_stats but no "
  "spawns_troop/on-death conversion, so the sim prices Goblin Curse as pure chip damage. "
  "Per-Goblin stats come from the hp_11/dmg_11/atk_speed block (202 / 120 / 1.1). The number of "
  "Goblins per conversion is NOT published anywhere on the page.", gc)
R("goblin_curse", "slow_pct", None, None, None, None, "split", "escalate",
  "NULL ON ALL PATHS. A 4/8/2026 balance update 'added a slowdown mechanic to the Goblin Curse' "
  "with no magnitude and no duration published anywhere on the page, and the time-machine "
  "confirms no vardefine was added for it (the only 2026 edit touched the History section). "
  "Recording null: the mechanic is real and current but unquantified. Separately, 1/9/2025 "
  "REMOVED the old damage-amplification boost, so the DB is correct to carry no amplification "
  "field -- do not re-add one.",
  ["* On 4/8/2026, a Balance Update, added a slowdown mechanic to the Goblin Curse",
   "*On 1/9/2025, the September 2025 Update, increased the Goblin Curse's damage by 17%, its "
   "Crown Tower damage to 27% of its full damage (from 20%), but removed its damage boost",
   "time-machine: pre-4/8/2026 revid 436501 vardefines identical to live revid 437353"])

# ------------------------------- GRAVEYARD -------------------------------
R("graveyard", "zone_spawn_edge", True, None, 3.3, 3.3, "2of3", "escalate",
  "SPAWN RING IS 3.3 TILES, NOT THE 4-TILE EDGE. The DB models Skeletons appearing on the edge "
  "of the 4-tile radius (zone_spawn_edge true + radius_tiles 4.0); the live spawn radius is 3.3 "
  "tiles after the 2/2/2026 update (from 2.9), and 14/1/2026 only moved them 'closer to' the "
  "edge, not onto it. The sim therefore drops every Skeleton about 0.7 tiles further from the "
  "tower than the real card does, which shifts exactly the tower-connect timing this archetype "
  "lives on. Curated verified:true. Everything else on Graveyard is a clean multi-path match: "
  "count 12 (table x12 AND the 1/6/2026 entry), duration 9s, spawn gap 0.5s, first spawn 2.2s, "
  "radius 4, skeleton hp 81, hit speed 1.1 (6/10/2025), Fast(90) -> 1.5 tiles/s.",
  ["|5||4||9 sec||0.5 sec||Spell||{{Rarity|Legendary}}   (Cost|Radius|Duration|Spawn Speed|Type|"
   "Rarity)",
   "secondary table: |1.1 sec||0.5 sec||Fast (90)||2.2 sec||Melee: Short (0.5)||Ground||x12||"
   "Ground",
   "* On 2/2/2026, a Balance Update, increased the spawn radius to 3.3 tiles (from 2.9 tiles)",
   "* On 14/1/2026, a Maintenance Break, decreased the amount of skeletons to 13 (from 14), and "
   "made it to where the skeletons spawn closer to the edge of the graveyard",
   "*On 9/10/2017 ... made the spawn mechanics of the Skeletons less random by making the "
   "Skeletons spawn on the edge."])

# ------------------------------- LIGHTNING -------------------------------
R("lightning", "crown_tower_damage", 264, 286, None, 264, "2of3", "pin",
  "CORRECT PIN, no action. 1/6/2026 -> 25% of full: 1057*0.25 = 264.25 -> 264 = DB. Vardefine "
  "286 is the 27% value from 3/6/2025. Independently reproduced by re-running the owner's own "
  "audit tool today. NB Lightning has no unit-attributes-table at all, so radius 3.5 rests "
  "solely on the 25/4/2018 history entry -- which does confirm it.",
  ["{{#vardefine: dmg_11 | 1057 }}", "{{#vardefine: crown_dmg_11| 286 }}",
   "* On 1/6/2026, a Balance Update, decreased the Lightning's Crown Tower damage to 25% of the "
   "full damage (from 27%)",
   "*On 25/4/2018, the Clan Wars Update, increased the Lightning's area radius to 3.5 tiles "
   "(from 3 tiles)."])

# --------------------------------- MIRROR ---------------------------------
R("mirror", "elixir", None, None, "Cost of previous card played +1", None, "2of3", "escalate",
  "NULL BY DESIGN, BUT UNMODELLED. Mirror has no fixed cost (infobox Cost=? '(Cost of previous "
  "card played +1)'). The DB row is {count, display, kind, rarity} only -- no cost rule -- so "
  "the sim cannot price the card at all. verified:false (no cards.yaml entry). Not a wrong "
  "number; flagged as a modelling gap for the owner to rule on.",
  ["{{Card Infobox|Cost=? ''(Cost of previous card played +1)''|Rarity=Epic|Type=Spell|"
   "Arena=Miner's Mine|ReleaseDate=4 January 2016}}",
   "|Cost of previous card played +1||Spell||{{Rarity|Epic}}"])
R("mirror", "mirrored_level_delta", None, None, 1, 1, "2of3", "update",
  "MISSING FIELD. The statistics table maps every Mirror level N to mirrored level N+1 across "
  "all five rarities (rows 6->7, 7->8, 8->9, 9->10) -- the mirrored copy is one level higher, "
  "which is the card's second mechanic after the +1 elixir. 29/9/2025 additionally allowed "
  "Mirror to copy Champion cards.",
  ["|6||7||7||7||7||7   (Level | Mirrored Common | Rare | Epic | Legendary | Champion)",
   "*On 19/9/2016, the September 2016 Update, increased all Mirrored cards Level by 1.",
   "*On 29/9/2025, the 2025 Quarter 3 Update, made the Mirror able to copy a {{Rarity|Champion}}"
   " card."])

# --------------------------------- POISON ---------------------------------
R("poison", "crown_tower_damage", 21, 22, None, 21, "2of3", "pin",
  "CORRECT PIN, no action. 1/6/2026 -> 23% of full: 92*0.23 = 21.16 -> 21 = DB.",
  ["{{#vardefine: dmg_11 | 92 }}", "{{#vardefine: crown_dmg_11 | 22 }}",
   "* On 1/6/2026, a Balance Update, decreased the Poison's Crown Tower damage to 23% of the "
   "full damage (from 25%)"])
R("poison", "radius_tiles", 3.5, None, None, None, "split", "escalate",
  "NULL ON ALL PATHS. The Poison page has NO unit-attributes-table (verified: zero occurrences "
  "of that id in the wikitext), no radius vardefine, and no radius entry anywhere in its "
  "balance history -- the only prose is 'a medium radius'. The DB's 3.5 is therefore "
  "unsourceable from this page today, even though the row is curated verified:true with a "
  "'2026-08-15 wiki' comment. Contrast Lightning, which also lacks an attributes table but IS "
  "confirmed at 3.5 by its 25/4/2018 history entry. Needs a non-wiki source or an owner ruling.",
  ["lead: 'It is an area-damage, air-targeting spell with a medium radius and low damage that "
   "is dealt every second for 8 seconds.'",
   "grep -c 'unit-attributes-table' Poison.wikitext -> 0"])

# ---------------------------------- RAGE ----------------------------------
rg = ["|2||3||0.5 sec||4.5 sec||+30%||Friendly Troops & Buildings||Spell||{{Rarity|Epic}}   "
      "(Cost|Radius|Deploy Time|Duration|Boost|Target|Type|Rarity)"]
R("rage", "duration_s", None, None, 4.5, 4.5, "2of3", "update",
  "MISSING FIELD -- the card's whole point. Table Duration 4.5 sec, and 4/8/2025 set it to 4.5 "
  "(from 5.5). The DB row has no duration, so a Rage in the sim is an instant with no window. "
  "Damning internal check: cards.yaml ALREADY models the Lumberjack's dropped rage correctly as "
  "drops_rage: {radius_tiles 3.0, duration_s 4.5, boost 0.30, delay_s 0.5} -- the derived "
  "effect is fully specified while the card it is derived from is not.",
  rg + ["*On 4/8/2025, the August 2025 Update increased the Rage's damage by 21%, but decreased "
        "its duration to 4.5 seconds (from 5.5 seconds)."])
R("rage", "boost", None, None, 0.30, 0.30, "2of3", "update",
  "MISSING FIELD. Table Boost +30%; 6/10/2025 cut the speed boost to 30% (from 35%); lead: "
  "'It increases the movement speed and attack speed of allied troops and buildings by 30%.' "
  "Same 0.30 the Lumberjack drops_rage entry already uses.",
  rg + ["* On 6/10/2025, a Balance Update decreased the Rage's speed boost to 30% (from 35%)."])
R("rage", "attacks", ["buildings"], None, "Friendly Troops & Buildings", "air, ground",
  "split", "escalate",
  "IMPORT BUG. attacks:['buildings'] looks like the Target cell 'Friendly Troops & Buildings' "
  "mis-parsed into the sim's attacks schema, where it means 'this spell only hits buildings' "
  "(rocket-style building targeting). Rage attacks nothing; its Target column names who it "
  "BUFFS. Its damage component is air+ground per the lead ('an area-damage, air-targeting "
  "spell'). As written, any targeting or counter logic that reads attacks will mis-handle Rage. "
  "verified:false row.",
  rg + ["lead: 'It is an area-damage, air-targeting spell with a medium radius and low damage. "
        "It increases the movement speed and attack speed of allied troops and buildings by "
        "30%.'"])
R("rage", "crown_tower_damage", 54, 54, None, 45, "split", "escalate",
  "1/6/2026 -> 25% of full: 179*0.25 = 44.75 -> 45; vardefine 54 is the 30% value. Like Freeze, "
  "Rage is absent from crown_damage_audit.py's CARDS list, so it was never checked. NB Rage and "
  "Giant Snowball genuinely share dmg_11 179 and crown_dmg_11 54 on the wiki -- I checked both "
  "pages, it is a real coincidence and not a duplicated import row.",
  ["{{#vardefine: dmg_11 | 179 }}", "{{#vardefine: crown_dmg_11 | 54 }}",
   "* On 1/6/2026, a Balance Update, decreased the Rage's Crown Tower damage to 25% of the full "
   "damage (from 30%)"])

# --------------------------------- ROCKET ---------------------------------
R("rocket", "crown_tower_damage", 342, 371, None, 341, "2of3", "escalate",
  "OFF BY ONE AGAINST ITS OWN PIN. The pin registry says 341 and the owner's own tool says 341; "
  "cards.yaml has 342 with the comment '# post-1/6/2026 (see crown_damage_audit.py)'. "
  "Derivation: 1484*0.23 = 341.32 -> 341 (342 would require a ceil, while the rest of the "
  "family rounds: 192*0.25 = 48 exactly, 266*0.13 = 34.58 -> 35, 1057*0.25 = 264.25 -> 264). "
  "Re-running icebow/tools/crown_damage_audit.py today prints 'Rocket vardefine 371 -> should "
  "be 341', so the curated file disagrees with the very tool cited to justify it. Tiny "
  "magnitude, but this is the reference pin for the whole crown-damage family. Curated "
  "verified:true.",
  ["{{#vardefine: dmg_11 | 1484 }}", "{{#vardefine: crown_dmg_11 | 371 }}",
   "* On 1/6/2026, a Balance Update, decreased the Rocket's Crown Tower damage to 23% of the "
   "full damage (from 25%)",
   "crown_damage_audit.py stdout 2026-08-26: 'Rocket  1484  371  23%  341  ** STALE vardefine "
   "**'"])
R("rocket", "knockback_tiles", None, None, None, None, "split", "escalate",
  "NULL ON ALL PATHS, already documented as deliberate. The lead says Rocket 'inflicts "
  "knockback' but no pushback range is published on the page and no balance entry ever set one; "
  "cards.yaml explicitly leaves it null and lets the engine fall back to Fireball's 1 tile. "
  "Recorded so the gap stays visible, not to re-litigate the fallback.",
  ["lead: 'It is an area-damage, air-targeting spell with a small radius and very high damage "
   "that also inflicts knockback.'",
   "no pushback figure anywhere in Rocket's History; only Fireball (2/8/2022, 1 tile), The Log "
   "(7/2/2023, 0.7) and Giant Snowball (6/9/2021, 1.8) publish one"])

# ----------------------------- ROYAL DELIVERY -----------------------------
rd = ["{{#vardefine: spawn_11 | 437 }}", "{{#vardefine: dmg_11 | 133 }}",
      "unit-statistics-table headers: Level | Royal Delivery Area Damage | Hitpoints | Shield "
      "Hitpoints | Damage | Damage Per Second",
      "the 'Royal Delivery Area Damage' column renders {{#var:spawn_11}}; the 'Damage' column "
      "renders {{#var:dmg_11}}"]
R("royal_delivery", "damage", 133, 437, 437, 385, "2of3", "escalate",
  "SAME INVERTED MAPPING AS BARBARIAN BARREL, and here it propagated into a curated comment. "
  "The landing/area damage is spawn_11 = 437; dmg_11 = 133 is the spawned Royal Recruit's melee "
  "(133/1.3 = 102 = the row's own dps). cards.yaml's crown_tower_damage comment reads 'the "
  "spell's 133 impact damage ... The spawned Recruit still hits towers at full melee' -- "
  "exactly backwards. FURTHER: 4/8/2026 cut the landing damage by 12%, and a revision "
  "time-machine shows the vardefines were NOT touched (only the History section was edited in "
  "2026), so even 437 is stale -- the current landing damage derives to 437*0.88 = 384.6 -> "
  "385, which is the p3 value recorded here.",
  rd + ["* On 4/8/2026, a Balance Update, decreased the Royal Delivery's landing damage by 12%",
        "time-machine: pre-4/8/2026 revid 436490 (2026-06-27) spawn_11=437; live revid 437384 "
        "spawn_11=437 (unchanged)"])
R("royal_delivery", "spawn_damage", 437.0, 133, 133, None, "2of3", "escalate",
  "Mirror of the damage row -- the two fields are swapped. Whatever the owner decides about the "
  "12% cut, `spawn_damage` should hold the Recruit-side number and `damage` the landing number, "
  "or the field names need redefining; as written they contradict the page's own column "
  "headers.", rd)
R("royal_delivery", "crown_tower_damage", 40, None, None, None, "split", "escalate",
  "NULL ON ALL PATHS -- the value is invented. Royal Delivery has NO crown_dmg_11 vardefine, no "
  "Crown Tower Damage column in its statistics table, no 'Reduced damage to Crown Towers' line "
  "in its card text, and no crown entry anywhere in its history. cards.yaml's own comment "
  "concedes this ('~30%; USER VERIFY exact'). Compare Barbarian Barrel, whose crown damage was "
  "explicitly REMOVED on 3/9/2018 and which correctly carries no such field. Needs an owner "
  "ruling on whether RD's landing damage touches towers at all.",
  ["Royal Delivery vardefine block is spawn_11, hp_11, Shield_11, dmg_11, atk_speed -- there is "
   "no crown_dmg_11",
   "{{Quote|No need to sign for this package! Dropped from the sky, it deals Area Damage to "
   "enemy Troops before delivering a Royal Recruit. The empty box is also handy for espionage.}}"
   " -- no 'Reduced damage to Crown Towers' clause"])
R("royal_delivery", "radius_tiles", None, None, 3, None, "2of3", "update",
  "MISSING FIELD. The attributes table publishes Radius 3; the DB row has no radius at all, so "
  "the landing blast has no area. (Deploy Time 3 sec IS present in the DB and matches the same "
  "table row.)",
  ["|3||3||3 sec||Air & Ground||Spell||{{Rarity|Common}}   (Cost|Radius|Deploy Time|Target|Type|"
   "Rarity)"])

# -------------------------------- THE LOG --------------------------------
R("the_log", "crown_tower_damage", 35, 40, None, 35, "2of3", "pin",
  "CORRECT PIN, no action. 1/6/2026 -> 13% of full: 266*0.13 = 34.58 -> 35 = DB; vardefine 40 "
  "is the 15% value. NB the cards.yaml trailing comment on this key still reads "
  "'crown_tower_damage 40 (poor tower chip)', contradicting the 35 set a few lines above it -- "
  "a stale comment with no code effect, but worth cleaning so the next reader is not misled.",
  ["{{#vardefine: dmg_11 | 266 }}", "{{#vardefine: crown_dmg_11 | 40 }}",
   "* On 1/6/2026, a Balance Update, decreased The Log's Crown Tower damage to 13% of the full "
   "damage (from 15%)"])
R("the_log", "width_tiles", None, None, 3.9, None, "2of3", "update",
  "MISSING FIELD. The Log is explicitly a rectangle -- the attributes table publishes Range "
  "10.1 AND Width 3.9, and the lead calls it 'a very long rectangular area'. The DB carries "
  "range_tiles 10.1 but no width, so the roll has no lane footprint. (Barbarian Barrel has the "
  "identical gap at 2.6.)",
  ["|2||10.1||3.9||Ground||Spell||{{Rarity|Legendary}}   (Cost|Range|Width|Target|Type|Rarity)",
   "lead: 'It is an area-damage, ground-targeting spell with a very long rectangular area and "
   "moderate damage that also inflicts knockback to any troop it hits.'"])
R("the_log", "roll_speed", None, None, None, 200, "2of3", "escalate",
  "MISSING FIELD, history path only. 20/10/2016 set The Log's projectile speed to 200 (from "
  "170) and its casting speed to 360 (from 300), and neither has changed since. The DB has no "
  "travel speed, so the roll is effectively instantaneous and the defender's reaction window "
  "does not exist. No table cell corroborates, hence escalate rather than update.",
  ["*On 20/10/2016, a Balance Update, increased The Log's casting speed to 360 (from 300), its "
   "projectile speed to 200 (from 170), its rolling distance to 11.6 tiles (from 9.6 tiles), "
   "and its damage by 8.5%."])

# -------------------------------- TORNADO --------------------------------
R("tornado", "zone_tick_s", None, None, 0.55, 0.55, "2of3", "update",
  "MISSING FIELD. Tornado is a damage-over-time zone -- the lead says damage 'is dealt every "
  "0.55 seconds', and 9/4/2025 set the attack interval to 0.55 (from 0.5). The DB has neither "
  "zone_tick_s nor zone_s, so its 84 resolves as a single blast while poison/void/earthquake "
  "all get proper zones. Directly relevant here: this deck's tornado synergies are being priced "
  "off a one-tick approximation.",
  ["lead: 'a very large radius and low damage that is dealt every 0.55 seconds for 1.05 "
   "seconds'",
   "*On 9/4/2025, a Balance Update, increased the Tornado's attack time interval to 0.55 "
   "seconds (from 0.5 seconds)."])
R("tornado", "zone_s", None, None, 1.05, 2.05, "split", "escalate",
  "MISSING FIELD AND THE PATHS DISAGREE. The attributes table gives Duration = 1.05 sec and the "
  "lead agrees ('for 1.05 seconds'), but the last duration entry in the balance history is "
  "25/4/2018 'decreased the duration to 2.05 seconds (from 2.55 seconds)' with no later change "
  "logged -- an unlogged 2.05 -> 1.05 cut is implied. Both recorded. This field also governs "
  "the PULL window (how long troops are dragged), which the DB models only as a flag with no "
  "duration. NB Tornado publishes no dmg_hits vardefine, so the per-cast hit count is NOT "
  "published; at 1.05s/0.55s it derives to 2 ticks, but I am not asserting that as sourced.",
  ["|3||5.5||1.05 sec||Air & Ground||Spell||{{Rarity|Epic}}   (Cost|Radius|Duration|Target|Type|"
   "Rarity)",
   "*On 25/4/2018, the Clan Wars Update, increased the Tornado's damage per second by 21%, but "
   "also decreased the duration to 2.05 seconds (from 2.55 seconds).",
   "unit-statistics-table row 11: '| 11 || {{#var:dmg_11}} || {{#var:crown_dmg_11}}' -- a "
   "single value, no x{{#var:dmg_hits}} multiplier unlike Poison/Void/Vines/Earthquake"])

# --------------------------------- VINES ---------------------------------
R("vines", "stun_duration_s", 2.5, None, 2, 2, "2of3", "escalate",
  "PROSE LAGS HISTORY, AND THE CURATOR QUOTED THE PROSE. The attributes table gives Duration = "
  "2 sec AND 8/10/2025 'decreased duration to 2 seconds (from 2.5 seconds)' -- two independent "
  "paths at 2.0. The 2.5 in cards.yaml is quoted verbatim from the page's LEAD sentence, which "
  "still says 'for 2.5 seconds' and was never updated after the balance change. The sim "
  "therefore holds enemies 25% longer than the real card. Curated verified:true.",
  ["|3||2.5||2 sec / 0.9s||3||Air & Ground||Spell||{{Rarity|Epic}}   (Cost|Radius|Duration|"
   "Deploy Time|Count|Target|Type|Rarity)",
   "* On 8/10/2025, a Balance Update decreased duration to 2 seconds (from 2.5 seconds) and "
   "decreased total damage 9%.",
   "lead (STALE): 'it will freeze the troop in place and render it unable to move or attack, "
   "and allow ground units to hit the trapped unit for 2.5 seconds'"])
R("vines", "crown_tower_damage", 78, 78, None, 70, "split", "escalate",
  "1/6/2026 -> 23% of full. Per hit: 153*0.23 = 35.19 -> 35, x2 hits = 70. The DB's 78 is the "
  "vardefine's 39/hit x2, i.e. the 25% era. Missed by the audit tool for two compounding "
  "reasons: Vines is not in its CARDS list, and its entry says 'of its full damage' which the "
  "regex would not have matched anyway. Curated verified:true.",
  ["{{#vardefine: dmg_11 | 153 }}", "{{#vardefine: dmg_hits | 2 }}",
   "{{#vardefine: crown_dmg_11 | 39 }}",
   "* On 1/6/2026, a Balance Update, decreased the Vines' Crown Tower damage to 23% of its full "
   "damage (from 25%)"])

# ---------------------------------- VOID ----------------------------------
vd = ["{{#vardefine: 1_dmg_11 | 696 }}", "{{#vardefine: 3_dmg_11 | 294 }}",
      "{{#vardefine: 5_dmg_11 | 153 }}",
      "unit-statistics-table headers: Level | Single Target Damage | Single Target Crown Tower "
      "Damage | 2-4 Targets Damage | 2-4 Targets Crown Tower Damage | 5 Or More Targets Damage "
      "| 5 Or More Targets Crown Tower Damage",
      "the '2-4 Targets Damage' column renders {{#var:3_dmg_11}}; the '5 Or More Targets "
      "Damage' column renders {{#var:5_dmg_11}}"]
R("void", "zone_tiers", [[1, 696, 97], [3, 294, 51], [99, 153, 35]],
  [[1, 696, 97], [4, 294, 51], [99, 153, 35]], [[1, 696, 97], [4, 294, 51], [99, 153, 35]],
  None, "2of3", "escalate",
  "TIER BOUNDARY OFF BY ONE -- read from the vardefine NAME instead of the column LABEL. The "
  "vardefines are named 1_/3_/5_, but the table headers they feed are 'Single Target', '2-4 "
  "Targets' and '5 Or More Targets', and the 4/8/2026 balance entry uses exactly the same "
  "brackets ('single target', '2-4 unit target', '5 or more target'). So the middle tier covers "
  "2-4, not 2-3: with exactly 4 targets in the radius the sim deals 153 where the real card "
  "deals 294 -- a 2x error in a common defensive case. The damage NUMBERS are all correct (see "
  "the zone_tick_s note for the time-machine confirming they are post-4/8/2026). Curated "
  "verified:true.",
  vd + ["* On 4/8/2026, a Balance Update, increased the Void's elixir cost to 5 elixir (from "
        "3), increased its hit speed to 1.2 seconds (from 1 second), increased the single "
        "target damage by 105%, increased the 2-4 unit target damage by 83%, and increased the "
        "5 or more target damage by 101%"])
R("void", "zone_tick_s", 1.333, None, None, 1.2, "2of3", "escalate",
  "STALE BY TWO BALANCE UPDATES. The strike interval went 1.3 -> 1.0 (4/3/2025) -> 1.2 "
  "(4/8/2026). The DB's 1.333 is not any published value: it is 4s duration / 3 hits, a "
  "reconstruction that happens to fit the duration and so looked right. The published answer is "
  "1.2. Time-machine cross-check on this page: the 4/8/2026 rework DID land in the vardefines "
  "(pre-revid 436503 held 340/160/76 with crowns 48/25/17; live holds 696/294/153 and 97/51/35, "
  "matching the entry's +105%/+83%/+101% almost exactly), which is why the tier damages are "
  "trustworthy while the interval -- which has no vardefine to update -- is not. Curated "
  "verified:true.",
  ["*On 4/3/2025, a Balance Update, decreased the Void's strike interval to 1 second (from 1.3 "
   "seconds).",
   "* On 4/8/2026, ... increased its hit speed to 1.2 seconds (from 1 second) ...",
   "time-machine: pre-4/8/2026 revid 436503 1_dmg_11=340 -> live 696 (+105%); 3_dmg_11=160 -> "
   "294 (+83%); 5_dmg_11=76 -> 153 (+101%)"])
R("void", "first_strike_delay_s", None, None, None, 1.0, "2of3", "escalate",
  "MISSING FIELD, history path only. 17/6/2024 'increased the Void's first strike interval to 1 "
  "second (from 0.5 seconds)'. With a 1.0s first strike and 1.2s intervals the three hits land "
  "at 1.0 / 2.2 / 3.4s inside the 4s duration -- internally consistent, and a useful "
  "cross-check on the 1.2 above. The DB has no first-strike delay, so Void's opening tick is "
  "instant and it kills things it should not reach.",
  ["*On 17/6/2024, the Goblin World Update, decreased the Void's strike interval to 1.3 seconds "
   "(from 1.5 seconds), but increased the Void's first strike interval to 1 second (from 0.5 "
   "seconds)."])

# ----------------------------------- ZAP -----------------------------------
R("zap", "crown_tower_damage", 48, 58, None, 48, "2of3", "pin",
  "CORRECT PIN, no action. 1/6/2026 -> 25% of full: 192*0.25 = 48 exactly = DB; vardefine 58 is "
  "the 30% value. Independently reproduced by re-running the owner's own audit tool today.",
  ["{{#vardefine: dmg_11 | 192 }}", "{{#vardefine: crown_dmg_11 | 58 }}",
   "* On 1/6/2026, a Balance Update, decreased the Zap's Crown Tower damage to 25% of the full "
   "damage (from 30%)"])


with open(OUT, "w", encoding="utf-8") as f:
    for r in rows:
        f.write(json.dumps(r, ensure_ascii=False) + "\n")

from collections import Counter
v = Counter(r["verdict"] for r in rows)
fields_checked = sum(CHECKED.values())
lines = len(rows)
# a "pin" line agrees with current_db, so it counts as a match as well as a flagged line
matches = fields_checked - lines + v["pin"]
print("lines:", lines)
print("verdicts:", dict(v))
print("keys with >=1 flagged line:", len(set(r["key"] for r in rows)))
print("keys_done:", len(CHECKED))
print("fields_checked:", fields_checked)
print("matches:", matches)
