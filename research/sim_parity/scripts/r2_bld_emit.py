# -*- coding: utf-8 -*-
"""R2 buildings: emit r2_buildings.jsonl (one line per (key,field) with a discrepancy/priority flag)."""
import json, io

REV = {"barbarian_hut": (436519, "Barbarian Hut"), "bomb_tower": (436520, "Bomb Tower"),
       "cannon": (437251, "Cannon"), "elixir_collector": (436522, "Elixir Collector"),
       "goblin_cage": (436552, "Goblin Cage"), "goblin_drill": (437382, "Goblin Drill"),
       "goblin_hut": (437256, "Goblin Hut"), "inferno_tower": (437542, "Inferno Tower"),
       "mortar": (437360, "Mortar"), "tesla": (437288, "Tesla"),
       "tombstone": (436518, "Tombstone"), "x_bow": (437356, "X-Bow")}
F = "2026-08-26"


def U(t):
    return ("https://clashroyale.fandom.com/api.php?action=parse&page=%s"
            "&prop=wikitext%%7Crevid&format=json" % t.replace(" ", "+"))


def S(key, raws, extra=None):
    rev, t = REV[key]
    out = [{"url": U(t), "revid": rev, "fetched": F, "raw": r} for r in raws]
    if extra:
        out += extra
    return out


R = []


def add(key, field, cur, p1, p2, p3, raws, vote, verdict, notes, extra=None):
    R.append({"key": key, "field": field, "current_db": cur, "p1_vardefine": p1,
              "p2_table": p2, "p3_history": p3, "sources": S(key, raws, extra),
              "vote": vote, "cross_checks": {"edit_war": "pass"},
              "verdict": verdict, "notes": notes})


# ---------------- barbarian_hut ----------------
add("barbarian_hut", "spawns.interval", 13.5, None, 15.0, 14.0,
    ["attributes table row: |6||15 sec||1 sec||30 sec||Building||Rare",
     "intro prose: 'Every 15 seconds, the Barbarian Hut will passively summon a group of three Barbarians'",
     "trivia L200: 'Among all buildings that can spawn troops, the Barbarian Hut has the lowest spawn"
     " speed of all buildings, with an spawn speed of 13.5 seconds.'",
     "history 4/2/2020: 'decreased its spawn time interval to 12.5 seconds (from 13.5 seconds)'",
     "history 7/12/2021: 'decreased ... its spawn time interval to 10 seconds (from 12.5 seconds)'",
     "history 4/10/2022: 'increased its spawn time interval to 14 seconds (from 10 seconds)'",
     "Common modifier: '+100% spawn rate ... Barbarians spawn twice as frequently' (15/2 = 7.5)"],
    "split", "escalate",
    "CURATED verified:true, so never auto-overwritten. The curated 13.5 is refuted by every path: the "
    "attribute table AND the intro prose both say 15, and the history shows 13.5 was superseded on "
    "4/2/2020 (13.5 -> 12.5 -> 10 -> 14). The curation comment cites the trivia line as its wiki source, "
    "but that trivia line is itself the stale pre-Feb-2020 value. Residual conflict between the two live "
    "surfaces (table/prose 15) and the last dated history entry (14) - no dated entry documents 14 -> 15. "
    "Owner must pick 15 (two live surfaces) or 14 (history reconstruction); 13.5 is wrong either way. "
    "NOTE the same row also carries spawn_interval_s = 15.0, so the sim holds two disagreeing values for "
    "one concept.")
add("barbarian_hut", "spawn_delay_s", None, None, 0.5, None,
    ["intro prose: 'a group of three Barbarians, with a 0.5 seconds delay from each other'"],
    "split", "escalate",
    "PRIORITY/gap: field absent from the KB row. The intra-wave stagger is published in prose only (this "
    "page's attribute table has no Spawn Delay column, unlike Goblin Hut). goblin_hut carries "
    "spawn_delay_s 0.5 from its table; barbarian_hut carries nothing, so its three-Barbarian wave lands "
    "instantaneously in the sim.")

# ---------------- bomb_tower ----------------
add("bomb_tower", "load_time_s", 1.1, None, 0.5, None,
    ["attributes table row: |4||1.8 sec||0.5 sec||1 sec||30 sec||6||1.5||500||Ground||Building||Rare"
     " (columns: Cost, Hit Speed, First Hit Speed, Deploy Time, Lifetime, Range, Splash Radius,"
     " Projectile Speed, Target, Type, Rarity)",
     "history: no entry anywhere on the page touches Bomb Tower's first-attack interval"],
    "split", "escalate",
    "current_db 1.1 has no wiki support; the attribute table's First Hit Speed column publishes 0.5. The "
    "value originates in icebow/config/card_mechanics.json (load_time_s 1.1), not from any wiki path, and "
    "history never mentions a first-hit change - so the two cannot be reconciled from the page.")
add("bomb_tower", "death_damage_targets", None, None, "Air & Ground", None,
    ["secondary attributes table: '|3||3 sec||Air & Ground' (columns: Death Damage Splash Radius,"
     " Deploy Time, Target)",
     "history 4/3/2019: 'allowed the Bomb Tower to deal Death Damage'",
     "history 30/3/2021: 'decreased the Bomb Tower's death damage by 50%'"],
    "split", "escalate",
    "PRIORITY/gap: the KB row carries death_damage 222 / death_radius_tiles 3.0 / death_delay_s 3.0 but no "
    "target spec, while attacks:[ground] describes only the turret. The wiki gives the DEATH blast "
    "Air & Ground targeting, so in the sim a Bomb Tower death cannot kill the Bats/Minions it should kill.")

# ---------------- cannon ----------------
_cn = ["current vardefines: hp_11=824, dmg_11=212, life=30, atk_speed=1",
       "history 6/4/2026: '* On 6/4/2026, a Balance Update, decreased the Cannon's damage by 5%'",
       "rev 433597 (2025-12-22, pre-change) manual level table: '|11||824||27.4||212||{{Dps|212|1}}'",
       "rev 436508 (2026-06-27) introduced the vardefines carrying dmg_11=212 verbatim",
       "rev 437251 (2026-08-14, edit comment '/* History */') added the 6/4/2026 line; dmg_11 untouched"]
_cx = [{"url": U("Cannon"), "revid": 433597, "fetched": F,
        "raw": "pre-change revision 2025-12-22: |11||824||27.4||212||{{Dps|212|1}}"},
       {"url": U("Cannon"), "revid": 436508, "fetched": F,
        "raw": "2026-06-27: {{#vardefine: dmg_11 | 212 }} (copied from the pre-change manual table)"}]
add("cannon", "damage", 212, 212, None, 201, _cn, "split", "escalate",
    "VARDEFINE PROVABLY STALE. A revision walk shows dmg_11=212 is byte-identical to the level-11 damage "
    "in the 2025-12-22 revision, i.e. it predates the 6/4/2026 -5% change; the 2026-08-14 edit that added "
    "the history line did not touch it. Derived current = 212 * 0.95 = 201.4 -> 201 (the last digit is a "
    "rounding assumption, which is why this is escalate and not update). cannon is curated verified:false, "
    "and is one of the group's priority rows on that ground.", _cx)
add("cannon", "dps", 212, 212, None, 201, _cn, "split", "escalate",
    "Follows damage: dps = damage / hit_speed = 201 / 1.0 = 201 if the 6/4/2026 -5% is applied. Same "
    "rounding caveat as the damage line.", _cx)
add("cannon", "load_time_s", None, None, 1.0, 0.9,
    ["attributes table First Hit Speed column: 1 sec",
     "history 1/7/2019: 'increased ... its first attack interval to 1 second (from 0.8 seconds)'",
     "history 7/6/2021: 'decreased the Cannon's attack time interval to 0.9 seconds (from 1 second) and"
     " its first attack time interval to 0.9 seconds (from 1 second)'",
     "history 4/3/2025: 'increased the Cannon's attack time interval to 1 second (from 0.9 second)'"
     " -- names the attack interval ONLY, not the first attack"],
    "split", "escalate",
    "PRIORITY/gap: field absent from the KB row while every other turret building in the group carries it. "
    "The table says 1.0; the last dated history entry that names the FIRST attack interval leaves it at 0.9 "
    "(4/3/2025 raised only the regular interval). Table and history cannot both be right.")

# ---------------- elixir_collector ----------------
_ec = ["current vardefines: hp_11=1070, life=93",
       "attributes table row: |6||13 sec||1 sec||1 min 33 sec||Building||Rare"
       " (columns: Cost, Production Speed, Deploy Time, Lifetime, Type, Rarity)",
       "intro prose: 'Every 12 seconds, the Elixir Collector will passively generate 1 Elixir."
       " When defeated, it will also generate 1 Elixir.'",
       "history 4/4/2022: 'decreased its lifetime to 65 seconds (from 70 seconds), increased its production"
       " time interval to 9 seconds (from 8.5 seconds), and made the Elixir Collector produce 1 additional"
       " Elixir upon death'",
       "history 14/5/2024: 'increased the production time interval to 12 seconds (from 9 seconds), but"
       " increased its lifetime to 86 seconds (from 65 seconds)'",
       "history 03/11/2025: 'increased the production time interval to 13 seconds (from 12 seconds), but"
       " increased its lifetime to 93 seconds (from 86 seconds)'"]
add("elixir_collector", "gen_every_s", 8.5, None, 13.0, 13.0, _ec, "2of3", "update",
    "HIGH IMPACT. The curated 8.5 (flagged '# VERIFY' in cards.yaml) is the PRE-4/4/2022 value - three "
    "balance changes have landed since (8.5 -> 9 -> 12 -> 13). The attribute table (13) and the history "
    "reconstruction (13) agree; the intro prose still says 12 and is itself one patch behind. The "
    "elixir_collector block carries no `verified` key, so update is in scope. Effect: over the 93 s life "
    "the sim pays the opponent ~11 elixir where the live card pays ~7 - the pump is ~50% over-valued, "
    "which directly distorts the rocket-the-fresh-pump economy the curation comment describes. The "
    "comment's own arithmetic ('~8 over its life, +2 net') is consistent with ~12 s, not with 8.5 s.")
add("elixir_collector", "lifetime", 70, 93, 93, 93, _ec, "3of3", "update",
    "The curated lifetime:70 (also flagged '# VERIFY') is the PRE-4/4/2022 value (70 -> 65 -> 86 -> 93). "
    "All three paths agree on 93. Note the same row ALREADY carries lifetime_s: 93.0 (correct), so the row "
    "holds two disagreeing lifetimes; recommend deleting the stale `lifetime` key rather than keeping both.")
add("elixir_collector", "on_death_elixir", None, None, 1, 1, _ec, "2of3", "update",
    "PRIORITY/gap: field absent. The prose and the 4/4/2022 history entry both give the collector +1 elixir "
    "on death, so in the sim destroying a pump denies one elixir more than it actually does.")

# ---------------- goblin_cage ----------------
_gc = ["current vardefines: cage_hp_11=780, life=20, hp_11=1080, dmg_11=337, atk_speed=1.1",
       "primary attributes table: |4||1 sec||20 sec||Building||Rare"
       " (columns: Cost, Deploy Time, Lifetime, Type, Rarity -- NO hit speed, NO range, NO damage)",
       "secondary attributes table (Goblin Brawler): |1.1 sec||0.2 sec||Fast (90)||Melee: Short (0.8)"
       "||Ground||x1||Ground",
       "intro prose: 'When defeated, it will spawn a Goblin Brawler, which is a fast, single-target,"
       " ground-targeting, melee, ground troop with high hitpoints and high damage.'"]
add("goblin_cage", "hit_speed", 1.1, 1.1, None, None, _gc, "split", "escalate",
    "CONTAMINATION RESIDUE (the 2020-incident pattern). atk_speed=1.1 and the '1.1 sec' Hit Speed cell both "
    "belong to the Goblin Brawler in the SECONDARY table; the cage's own primary table publishes no "
    "hit-speed column at all, because the cage never attacks. The curation correctly zeroed damage/dps and "
    "split cage_hp_11 780 from the Brawler's hp_11 1080, but left hit_speed 1.1 on the cage. It is already "
    "carried where it belongs, in spawn_unit_stats.hit_speed.")
add("goblin_cage", "sight", 20.0, None, None, None, _gc, "split", "escalate",
    "No wiki support on any path - the cage's table has no range or sight column. 20.0 is exactly the "
    "lifetime (20 s) and exceeds the arena width, so it looks like a lifetime value that leaked into the "
    "sight field in card_mechanics.json (which also carries an unrelated _range_tiles 5.0 for a building "
    "with no attack). Record null + escalate.")

# ---------------- goblin_drill ----------------
_gd = ["current vardefines: drill_hp_11=1313, life=10, spawn_11=84, spawn_crown_11=26, hp_11=202,"
       " dmg_11=120, atk_speed=1.1",
       "primary attributes table: |4||3 sec||1 sec||10 sec||Building||Epic"
       " (columns: Cost, Spawn Speed, Deploy Time, Lifetime, Type, Rarity)",
       "intro prose: 'Every 3 seconds, the Goblin Drill will passively summon a Goblin. However, its first"
       " wave of Goblins will spawn 0.8 seconds after it is deployed. When defeated, it will also spawn"
       " two Goblins.'",
       "history 6/10/2025: 'increased the Goblin Drill's first spawn time to 1 seconds (from 0.8 seconds)'",
       "history 4/8/2026: '* On 4/8/2026, a Balance Update, the Goblin Drill spawn damage to towers has"
       " been removed entirely (from 30% of the full spawn damage)'"]
add("goblin_drill", "spawn_crown_damage", 26.0, 26, None, 0, _gd, "split", "escalate",
    "HIGH CONFIDENCE that the current value is 0. The 4/8/2026 entry says the tower spawn damage was "
    "removed 'entirely (from 30% of the full spawn damage)', and 26/84 = 30.95% identifies "
    "spawn_crown_11 = 26 as exactly the pre-change 30% figure that entry describes - the vardefine simply "
    "was not zeroed. Filed escalate only because P1 still literally reads 26, so the paths split. "
    "Behavioural: a surfacing Drill should no longer chip the crown tower at all.")
add("goblin_drill", "spawns.delay", 1.0, None, 0.8, 1.0, _gd, "2of3", "pin",
    "CURATION CONFIRMED CORRECT. The intro prose still says 0.8 s, but the 6/10/2025 balance entry raised "
    "the first spawn time to 1 s, and the curation comment already documents exactly this reasoning. A "
    "curated verified:true value intentionally contradicting the lagging prose - keep as is, do not re-open.")

# ---------------- inferno_tower ----------------
_it = ["current vardefines: hp_11=1748, 1_dmg_11=43, 2_dmg_11=158, 3_dmg_11=847, life=30, atk_speed=0.4",
       "attributes table row: 5 / 0.4 sec / 1 sec / 30 sec / 6 / Air & Ground / Building / Rare"
       " (columns: Cost, Hit Speed, Deploy Time, Lifetime, Range, Target, Type, Rarity -- NO First Hit"
       " Speed column)",
       "intro prose: 'It spawns a single-target, air-targeting, long-ranged, building with high hitpoints"
       " and various damage stage.'",
       "Common modifier: '-100% charge time ... Inferno Tower's charge speed is increased by 100%, for a"
       " total of 1 second'",
       "history: last entry 31/3/2025 (hitpoints -0.05%); nothing later, so the vardefines are current"]
add("inferno_tower", "attacks", None, None, ["air", "ground"], None, _it, "2of3", "update",
    "PRIORITY: inferno_tower is one of the group's unverified rows (no `verified` key, and no entry at all "
    "in icebow/config/cards.yaml) and is the thinnest row in the group. The Target column says 'Air & "
    "Ground' and the intro says 'air-targeting', but the KB row has no `attacks` field while every other "
    "building in the group has one. Inferno Tower is the group's primary anti-air and anti-tank answer, so "
    "a missing or defaulted air capability is a live behaviour bug, not a bookkeeping gap.")
add("inferno_tower", "range_tiles", None, None, 6.0, None, _it, "2of3", "update",
    "PRIORITY: field absent; the row carries only sight 6.0. The attribute table publishes Range 6, and "
    "every other turret building in the group carries range_tiles. Corroborated by card_mechanics.json "
    "_range_tiles 6.0, which is what feeds the sight value.")
add("inferno_tower", "deploy_time", None, None, 1.0, None, _it, "2of3", "update",
    "PRIORITY: field absent; the attribute table publishes Deploy Time 1 sec. Corroborated by "
    "card_mechanics.json _deploy_time_s 1.0.")
add("inferno_tower", "targets", None, None, "any", None, _it, "2of3", "update",
    "PRIORITY: field absent. The tower is not building-restricted, and every comparable building row in the "
    "group carries targets: any.")
add("inferno_tower", "load_time_s", 1.2, None, None, None, _it, "split", "escalate",
    "Null on all three paths: this page's attribute table has NO First Hit Speed column, no vardefine covers "
    "it, and no history entry names a first-hit change (3/2/2022 changed RE-TARGETING time by -0.4 s, which "
    "is a different quantity). 1.2 comes only from card_mechanics.json. Record null + escalate.")
add("inferno_tower", "charge_time_s", None, None, 2.0, None, _it, "split", "escalate",
    "PRIORITY/gap: the row has damage_stages [43, 158, 847] but nothing saying how long each stage takes, so "
    "the sim cannot model the ramp or a stun/shield reset - the single most important mechanic of this card, "
    "and the whole reason Zap/Freeze/Electro counter it. The only derivable source is the Common modifier "
    "('charge speed is increased by 100%, for a total of 1 second'), implying a 2 s base charge time. "
    "Single-path derivation, so escalate for an owner ruling rather than update.")

# ---------------- mortar ----------------
_mo = ["current vardefines: hp_11=1369, dmg_11=266, life=30, atk_speed=5",
       "attributes table row: |4||5 sec||1 sec||3.5 sec||30 sec||3.5-11.5||2||300||Ground||Building||Common"
       " (columns: Cost, Hit Speed, First Hit Speed, Deploy Time, Lifetime, Range, Splash Radius,"
       " Projectile Speed, Target, Type, Rarity)",
       "history 4/8/2026: '* On 4/8/2026, a Balance Update, decreased the Mortar's hit speed to 4.7 seconds"
       " (from 5 seconds)'"]
add("mortar", "hit_speed", 5.0, 5, 5.0, 4.7, _mo, "split", "escalate",
    "VARDEFINE AND TABLE BOTH LAG A DATED ENTRY. atk_speed=5 and the table's '5 sec' cell are the "
    "pre-4/8/2026 value; the 4/8/2026 entry states 4.7 'from 5 seconds' - exactly what both still publish, "
    "which proves neither absorbed the change. A literal 2-of-3 count favours 5.0, but those two surfaces "
    "are a single editorial act and the history is strictly newer, so this is filed escalate with all raw "
    "strings rather than 'match'; scoring it a match would bury a documented balance change. mortar is "
    "curated verified:true, so it must not be auto-overwritten in any case.")
add("mortar", "dps", 53, None, 53, 57, _mo, "split", "escalate",
    "Follows hit_speed: 266/5 = 53.2 -> 53 (current) versus 266/4.7 = 56.6 -> 57 once the 4/8/2026 change "
    "is applied. Same reasoning and same caveat as the hit_speed line.")
add("mortar", "load_time_s", 4.0, None, 1.0, None, _mo, "split", "escalate",
    "current_db 4.0 versus the table's First Hit Speed of 1 sec - a 3-second gap on a siege building, which "
    "decides whether a Mortar gets a shell away before it is answered. 4.0 comes only from "
    "card_mechanics.json; no vardefine and no history entry supports it. Note the same import path is the "
    "source of the already-known range_tiles 3.5 bug (cards_stats.json still carries the dead-zone minimum "
    "as the reach; the curation layer overrides it to 11.5, so the merged value is correct today).")

# ---------------- tesla ----------------
_te = ["current vardefines: hp_11=1152, dmg_11=220, life=25, atk_speed=1.1",
       "attributes table row: |4||1.1 sec||0.5 sec||1 sec||25 sec||5.5||Air & Ground||Building||"
       "{{Rarity|Common}}",
       "intro prose: 'The Tesla is a {{Rarity|Common}} card that is unlocked from the Hog Mountain"
       " (Arena 10).'",
       "history 1/6/2026: '* On 1/6/2026, a Balance Update, decreased the Tesla's lifetime to 25 seconds"
       " (from 30 seconds). It also increased its hitpoints by 3%'",
       "cached pre-change rev 436245: attr row '|4||1.1 sec||0.5 sec||1 sec||30 sec||5.5||Air & Ground'"
       " and manual level table '|11||1,152||220||{{Dps|220|1.1}}||38.4'",
       "Tesla Evolution page: Evolved_Card_Infobox Cost=4 CycleCost=2 Rarity=Common; secondary table"
       " '|2||6||0.5 sec' (Cycles, Pulse Radius, Pulse Stun Duration); pulse_dmg_11=174; life=25;"
       " 'It spawns a Tesla with identical stats to the original'"]
_tx = [{"url": U("Tesla"), "revid": 436245, "fetched": F,
        "raw": "pre-1/6/2026 revision: lifetime 30 sec, level-11 hitpoints 1,152, Rarity Common"},
       {"url": U("Tesla Evolution"), "revid": None, "fetched": F,
        "raw": "Tesla Evolution: cycles 2, pulse radius 6, pulse stun 0.5 sec, pulse_dmg_11 174, life 25"}]
add("tesla", "lifetime_s", 30.0, 25, 25.0, 25.0, _te, "3of3", "update",
    "CLEAN 3-OF-3. Vardefine life=25, the attribute table's '25 sec', and the dated 1/6/2026 entry "
    "('decreased the Tesla's lifetime to 25 seconds (from 30 seconds)') all agree, and the cached "
    "pre-change revision 436245 still shows 30 - so the wiki did fully propagate this one. The sim's 30.0 "
    "comes from card_mechanics.json overriding cards_stats.json, which already held 25.0. lifetime_s is not "
    "part of tesla's curated block, so this is in scope for update. Effect: the sim currently gives Tesla "
    "20% more uptime than it has.", _tx)
add("tesla", "rarity", "rare", None, "common", None, _te, "2of3", "escalate",
    "CURATED verified:true, so escalate rather than update. Three independent surfaces say Common: the "
    "attribute table's Rarity cell, the intro sentence, and the Evolution page's infobox (Rarity=Common). "
    "cards_stats.json also imports 'common'; only the curated block says rare. Rarity drives level scaling "
    "and the rarity floors, so this is not cosmetic.", _tx)
add("tesla", "hitpoints", 1152, 1152, 1152, 1187, _te, "split", "escalate",
    "The 1/6/2026 entry claims '+3% hitpoints' in the same breath as the lifetime change, but hp_11 is 1152 "
    "on the current page AND 1,152 in the cached pre-change revision 436245 - the number did not move "
    "across the same edit boundary that did move the lifetime. Either the hp figure lags (1152 * 1.03 = "
    "1186.6 -> ~1187) or the history entry's hp clause is wrong. Cannot be settled from this page; needs an "
    "in-game reading.", _tx)
add("tesla", "evolution.hitpoints", 1152, 1152, 1152, 1187, _te, "split", "escalate",
    "Inherits the base-Tesla ambiguity above: the curation deliberately sets the evo's hp to the base card's "
    "published level-11 value because the wiki says the evo 'spawns a Tesla with identical stats to the "
    "original', and the Evolution page's own hp_11 is likewise 1152. If the base resolves to ~1187 this must "
    "move with it. Curated verified:true. Everything else in the evolution block verified clean against the "
    "Evolution page: cycles 2, pulse_radius 6, pulse_stun 0.5, pulse_damage 174, lifetime 25, damage 220, "
    "hit_speed 1.1, dps 200.", _tx)
add("tesla", "load_time_s", 0.7, None, 0.5, None, _te, "split", "escalate",
    "The attribute table's First Hit Speed column says 0.5, and it says 0.5 in the pre-change revision "
    "436245 too, so it is not a lagging cell. current_db 0.7 comes only from card_mechanics.json with no "
    "wiki path supporting it.", _tx)

# ---------------- tombstone ----------------
_tb = ["current vardefines: tomb_hp_11=529, life=30, hp_11=81, dmg_11=81, atk_speed=1.1",
       "primary attributes table: |3||4 sec||1 sec||30 sec||Building||Rare"
       " (columns: Cost, Spawn Speed, Deploy Time, Lifetime, Type, Rarity)",
       "intro prose: 'Every 3.5 seconds, the Tombstone will passively summon a group of two Skeletons, with"
       " a 0.5 seconds delay from each other. When destroyed, it will also spawn four Skeletons.'",
       "Common modifier: 'Tombstone's spawn speed is doubled, for a total of 1.75 seconds' (1.75 * 2 = 3.5)",
       "history 7/12/2021: 'increase its spawn time interval to 3.3 seconds (from 3.1 seconds)'",
       "history 4/4/2022: 'increased its spawn time interval to 3.5 seconds (from 3.3 seconds)'"]
add("tombstone", "spawn_interval_s", 4.0, None, 3.5, 3.5, _tb, "2of3", "update",
    "The attribute table's '4 sec' Spawn Speed cell is stale and is contradicted three ways on its own page: "
    "the prose says 3.5, the Common modifier's arithmetic ('doubled, for a total of 1.75 seconds') implies "
    "3.5, and the last dated change (4/4/2022) set 3.5. spawn_interval_s is imported from that stale cell "
    "into cards_stats.json and is NOT curated, so it is in scope for update. Same one-concept-two-fields "
    "hazard as barbarian_hut: the row already carries the correct 3.5 in spawns.interval, so whichever field "
    "the engine actually reads decides the behaviour.")
add("tombstone", "spawns.interval", 3.5, None, 3.5, 3.5, _tb, "3of3", "pin",
    "CURATION CONFIRMED CORRECT, and its stated reasoning verified verbatim on the live page. A curated "
    "verified:true value intentionally contradicting the stale attribute table - keep, do not re-open.")

# ---------------- x_bow ----------------
_xb = ["current vardefines: hp_11=1600, dmg_11=43, life=30, atk_speed=0.3",
       "attributes table row: |6||0.3 sec||0.3 sec||3.5 sec||30 sec|| 11.5||Ground||Building|| Epic"
       " (columns: Cost, Hit Speed, First Hit Speed, Deploy Time, Lifetime, Range, Target, Type, Rarity"
       " -- NO Projectile Speed column)",
       "history 4/8/2026: '* On 4/8/2026, a Balance Update, increased the X-Bow's hit speed to 0.4 seconds"
       " (from 0.3 seconds), increased its damage by 35%, and increased its projectile speed by 14%'"]
add("x_bow", "hit_speed", 0.3, 0.3, 0.3, 0.4, _xb, "split", "escalate",
    "VARDEFINE AND TABLE BOTH LAG THE 4/8/2026 ENTRY, which states 0.4 'from 0.3 seconds' - exactly what "
    "both still publish, proving neither absorbed the change. x_bow is curated verified:true, so it must not "
    "be auto-overwritten regardless. The same 4/8/2026 patch also hit mortar and goblin_drill and is "
    "un-propagated on all three pages.")
add("x_bow", "damage", 43, 43, None, 58, _xb, "split", "escalate",
    "Same 4/8/2026 entry: '+35% damage'. dmg_11=43 is the pre-change value - the hit-speed clause of that "
    "same entry proves the row it sits in had not been updated. Derived 43 * 1.35 = 58.05 -> 58; the last "
    "digit is a rounding assumption.")
add("x_bow", "dps", 143, None, None, 145, _xb, "split", "escalate",
    "Follows damage and hit_speed: 43/0.3 = 143.3 -> 143 (current) versus 58/0.4 = 145 after the 4/8/2026 "
    "change. Note the change is close to DPS-neutral, so the sim's headline DPS is nearly right while both "
    "underlying numbers are wrong - per-shot damage and cadence matter separately for X-Bow, which wins by "
    "chip rate against towers and by shots-per-target on defence.")
add("x_bow", "projectile_speed", None, None, None, None, _xb, "split", "escalate",
    "Null on all three paths: this page's attribute table has no Projectile Speed column and there is no "
    "vardefine for it, so the 4/8/2026 '+14% projectile speed' has no published baseline anywhere on the "
    "page to apply it to. The field is also absent from the KB row. Record null + escalate.")
add("x_bow", "load_time_s", None, None, 0.3, 0.4, _xb, "split", "escalate",
    "PRIORITY/gap: field absent from the KB row. The table publishes First Hit Speed 0.3, but that cell is "
    "part of the same stale pre-4/8/2026 row as Hit Speed, so it most likely tracks to 0.4. Resolve together "
    "with the hit_speed line.")

with io.open("ledger/r2_buildings.jsonl", "w", encoding="utf-8") as fh:
    for r in R:
        fh.write(json.dumps(r, ensure_ascii=False) + "\n")

from collections import Counter
c = Counter(r["verdict"] for r in R)
print("lines:", len(R), dict(c))
print("keys with lines:", len(set(r["key"] for r in R)))
for k in sorted(REV):
    n = sum(1 for r in R if r["key"] == k)
    print("  %-18s %d" % (k, n))
