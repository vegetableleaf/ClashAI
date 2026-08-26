# -*- coding: utf-8 -*-
"""Emit research/sim_parity/ledger/r2_troops_c.jsonl -- one line per (key, field) carrying a
discrepancy or a priority flag. Matching fields are counted only (see r2_troops_c_tally.json)."""
import json, io, sys
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

W = "https://clashroyale.fandom.com/wiki/"
F = "2026-08-26"
REV = {"Phoenix": 437212, "Ram Rider": 437334, "Rascals": 437287, "Royal Ghost": 437224,
       "Royal Giant": 437219, "Royal Delivery": 437384, "Rune Giant": 437296,
       "Skeleton Army/Evolution": 436959, "Skeleton Barrel": 436976,
       "Skeleton Dragons": 437268, "Spear Goblins": 437502, "Spirit Empress": 437418,
       "Suspicious Bush": 437381, "Three Musketeers": 437182, "Wall Breakers": 437357}

R = []


def row(key, field, cur, p1, p2, p3, page, raw, vote, verdict, notes):
    R.append({"key": key, "field": field, "current_db": cur, "p1_vardefine": p1,
              "p2_table": p2, "p3_history": p3,
              "sources": [{"url": W + page.replace(" ", "_"), "revid": REV[page],
                           "fetched": F, "raw": raw}],
              "vote": vote, "cross_checks": {"edit_war": "pass"},
              "verdict": verdict, "notes": notes})


LAG = ("PROVEN LAG: the pre-change revision already carried today's value, so the wiki never "
       "applied the balance entry. P1/P2 are NOT independent here -- the statistics table is "
       "generated from the vardefine, so they are one source.")

# ---------------------------------------------------------------- phoenix
row("phoenix", "spawn_interval_s", 3.8, None, 3.8, 4.3, "Phoenix",
    "attr table 'Spawn Speed | 3.8 sec'; prose 'If the egg is not defeated within 3.8 seconds, it "
    "will hatch into another Phoenix'; History '*On 2/3/2026, a Balance Update, increased the "
    "Phoenix Egg's hitpoints by 32%, and increased the Egg's lifetime to 4.3 seconds (from 3.8 "
    "seconds).'", "split", "escalate",
    "UNRESOLVED, needs an owner ruling. The revision trail contradicts the History entry in BOTH "
    "directions: the Spawn Speed cell read 4.3 sec continuously from rev 423656 (2025-08-19) "
    "through rev 435583 (2026-03-22) -- already 4.3 seven months BEFORE the 2/3/2026 entry that "
    "claims it rose 'to 4.3 (from 3.8)'. Then rev 436371 (2026-06-13, no edit summary) changed "
    "that ONE cell 4.3->3.8 and touched nothing else (verified by diffing 435583..436371: a "
    "single-line change) and added no History entry. So current_db 3.8 rests only on that lone "
    "uncommented edit, while the page's own History and 10 months of prior table state say 4.3. "
    "Row is verified:true -> owner batch review.")
row("phoenix", "egg.hatch_s", 3.8, None, 3.8, 4.3, "Phoenix",
    "same cell / prose / History entry as spawn_interval_s above", "split", "escalate",
    "Duplicate carrier of the identical fact -- phoenix.egg.hatch_s and phoenix.spawn_interval_s "
    "both hold the egg lifetime, so they must move together whatever the owner decides.")
row("phoenix", "egg.reborn_frac", 0.8, None, 1.0, 1.0, "Phoenix",
    "prose 'it will hatch into another Phoenix with the original's hitpoints and damage' (the "
    "'80%' wording is gone from the page); History '*On 3/11/2025, a Balance Update, made it so a "
    "reborn Phoenix would spawn with 100% of the original Phoenix's hitpoints and damage (instead "
    "of 80%). The reborn Phoenix would also be the same size as the original.'",
    "2of3", "escalate",
    "STRONGEST SINGLE FINDING IN THE GROUP. P2 (prose) and P3 (dated 2025-11-03 entry) agree on "
    "1.0 against current_db 0.8, and no path supports 0.8 -- the sim is giving reborn Phoenixes "
    "80% of hitpoints AND damage where the game gives 100%. Field is curated verified:true in "
    "icebow/config/cards.yaml (phoenix ... egg: {hatch_s: 3.8, reborn_frac: 0.8}) -> escalate, "
    "do not auto-overwrite. Also unmodelled on the same page: 'a reborn Phoenix does not deal "
    "death damage or spawn an egg once it is defeated', and the 4/8/2025 removal of the Phoenix's "
    "Crown Tower damage reduction.")
# ---------------------------------------------------------------- phoenix_egg
row("phoenix_egg", "hitpoints", 239, 240, 240, 317, "Phoenix",
    "vardefine egg_11=240; statistics table column 'Phoenix Egg Hitpoints' L11 = 240 (literal 240 "
    "in revs 423656/425303/432021/433741/434458/435583/436371, unchanged since 2025-08-19); "
    "History '*On 2/3/2026 ... increased the Phoenix Egg's hitpoints by 32%'",
    "split", "escalate",
    "Two separate problems in one field. (a) current_db 239 vs wiki 240 is a stale off-by-one: "
    "cards.yaml's own comment says '239 hp at level 11 per the wiki', so the wiki moved to 240 "
    "(most likely the 31/3/2025 +0.41%, since 239*1.0041 = 239.98) and the KB kept 239. (b) the "
    "2/3/2026 +32% was never applied by the wiki -- 240 predates it by six months and is "
    "unchanged since 2025-08-19 -- so the true current value would be ~317 (240*1.32) if that "
    "entry shipped. The P3 figure is my reconstruction, not a published number. Row verified:true, "
    "and it is coupled to phoenix.egg.hatch_s above (same balance entry).")
# ---------------------------------------------------------------- ram_rider
row("ram_rider", "hitpoints", 1697, 1697, 1697, 1765, "Ram Rider",
    "vardefine hp_11=1697; statistics table L11 Hitpoints = 1,697 (literal) at rev 436414 "
    "(2026-06-22), which PREDATES the buff; History '* On 6/7/2026, a Balance Update, increased "
    "her hitpoints by 4%'", "split", "escalate",
    LAG + " rev 436414 (2026-06-22) already read 1,697 and today's rev 437334 still reads 1697, "
    "so the 6/7/2026 +4% is unapplied; reconstructed 1697*1.04 = 1765. Row is verified:false, but "
    "the current value agrees with two NON-independent paths, so I am not proposing an "
    "auto-update -- the real choice is 'trust the dated History entry' vs 'trust the stale table'.")
row("ram_rider", "hit_speed", 1.8, 1.8, 1.8, 1.7, "Ram Rider",
    "vardefine atk_speed=1.8; attr table 'Ram Attributes' Hit Speed = 1.8 sec; History '* On "
    "12/1/2026, a Balance Update increased the Ram Rider's attack speed to 1.7 (from 1.8)'",
    "split", "escalate",
    "LIKELY A HISTORY ERROR, NOT A LAG -- the opposite conclusion to the hitpoints line above, "
    "and the time machine is what separates them. The Hit Speed cell read 1.8 sec BEFORE the "
    "change (rev 431207, 2025-11-24), AFTER it (rev 434292, 2026-01-22), again at rev 436414 "
    "(2026-06-22) and today. A real 1.8->1.7 change would have been picked up by at least one of "
    "four edits spanning eight months. Recommend KEEPING current_db 1.8; logged so the owner can "
    "rule once. If it ever were changed to 1.7, dps must go 139 -> 147.")
row("ram_rider",
    "rider_attack (rider_damage / rider_hit_speed / rider_range_tiles / rider_projectile_speed)",
    None, 104, 104, None, "Ram Rider",
    "vardefines rider_dmg_11=104, rider_atk_speed=1.1; attr table 'Rider Attributes': Hit Speed "
    "1.1 sec | First Hit Speed 0.4 sec | Snare Duration 2 sec | Slowdown -70% | Range 5.5 | "
    "Projectile Speed 600 | Target 'Air & Ground (Troops only)' | Count x1",
    "2of3", "escalate",
    "PRIORITY / MISSING FIELDS. The KB models only the Ram (damage 250, charge 501) and the snare "
    "magnitude (slow_pct -70). The RIDER's own attack -- 104 damage every 1.1 s at 5.5 tiles, "
    "projectile speed 600, hitting AIR as well as ground, troops only -- is absent, so in the sim "
    "a Ram Rider does no ranged chip and cannot touch air at all. current_db is null because no "
    "such field exists on the row.")
row("ram_rider", "slow_duration_s", None, None, 2.0, None, "Ram Rider",
    "attr table 'Rider Attributes' Snare Duration = 2 sec", "2of3", "escalate",
    "PRIORITY / MISSING FIELD. slow_pct -70 is present but the KB carries no duration, so the "
    "engine cannot know the snare lasts 2 s. PATHS PUBLISHING: P2 only -- no vardefine and no "
    "dated history entry for this quantity.")
# ---------------------------------------------------------------- rascals
row("rascals", "hitpoints (and components[0].hitpoints -- Rascal Boy)", 1940, 1940, 1940, 1824,
    "Rascals",
    "vardefine boy_hp_11=1940; statistics table L11 'Rascal Boy Hitpoints' = 1,940 (literal) at "
    "rev 436024 (2026-04-28), which PREDATES the nerf; History '* On 1/6/2026, a Balance Update, "
    "decreased the Rascal Boy's Hitpoints by 6%'", "split", "escalate",
    LAG + " rev 436024 (2026-04-28) already read 1,940 and today's rev 437287 still reads 1940, "
    "so the 1/6/2026 -6% is unapplied; reconstructed 1940*0.94 = 1824. Row verified:true. This "
    "value is carried TWICE on the row (top-level hitpoints and components[0].hitpoints) and both "
    "must move together. Every other Rascals number matches exactly: boy 204 dmg / 1.5 s / 0.8 "
    "tiles, girl 261 hp / 125 dmg / 1.0 s / 5.0 tiles / 800 projectile / x2.")
# ---------------------------------------------------------------- royal_ghost
row("royal_ghost", "invisibility_time_s", 1.8, None, 2.0, 2.0, "Royal Ghost",
    "attr table column 'Invisibility Time' = 2 sec; History '* On 2/3/2026, a Balance Update, "
    "decreased the Royal Ghost's invisibility delay to 2 seconds (from 1.8 seconds).'",
    "2of3", "escalate",
    "CLEAN 2-of-3 against current_db, and the two paths ARE independent here: invisibility has no "
    "vardefine, so P2 is the table cell itself rather than a vardefine echo. The History wording "
    "is self-contradictory ('decreased ... to 2 (from 1.8)' is an increase) but both paths agree "
    "the value is now 2.0. Field is explicitly curated verified:true in cards.yaml (royal_ghost: "
    "{... invisibility_time_s: 1.8, verified: true}) -> escalate, never auto-write. Recommended "
    "2.0. All 13 other Royal Ghost fields match.")
# ---------------------------------------------------------------- royal_giant
row("royal_giant", "hit_speed", 1.8, 1.8, 1.8, 1.7, "Royal Giant",
    "vardefine atk_speed=1.8; attr table Hit Speed = 1.8 sec; History '* On 2/3/2026, a Balance "
    "Update, decreased the Royal Giant's hitpoints to 1.7 seconds (from 1.8 seconds).'",
    "2of3", "match",
    "RESOLVED IN FAVOUR OF current_db -- logged because the History entry reads as a conflict "
    "until you date it. The entry is garbled twice over: it says 'hitpoints' but gives seconds, "
    "and it states the direction backwards. rev 434690 (2026-02-05, BEFORE 2/3/2026) shows Hit "
    "Speed 1.7 sec and today's rev 437219 shows 1.8 sec, so the real 2/3/2026 change was a NERF "
    "1.7 -> 1.8 and current_db 1.8 is correct. No action. This is the control case proving a "
    "History entry can be wrong, which is why the other P3-only findings are escalated rather "
    "than auto-applied.")
# ---------------------------------------------------------------- royal_recruit
row("royal_recruit", "range_tiles", None, None, 1.6, None, "Royal Delivery",
    "attr table 'Royal Recruit Attributes': Hit Speed 1.3 sec | First Hit Speed 0.5 sec | Speed "
    "Medium (60) | Deploy Time 0.25 sec | Range 'Melee: Long (1.6)' | Target Ground | Count x1",
    "2of3", "escalate",
    "PRIORITY / MISSING FIELD on a sub-unit row. Sourced from the PARENT spell page Royal "
    "Delivery, section 'Royal Recruit Attributes' -- royal_recruit has no wiki page of its own. "
    "The six-body card page Royal Recruits independently gives the same 'Melee: Long (1.6)'. Row "
    "is verified:true. PATHS PUBLISHING: P2 only -- range is never vardefined on this wiki.")
row("royal_recruit", "dps", None, 102, 102, None, "Royal Delivery",
    "vardefines dmg_11=133 and atk_speed=1.3 -> 133/1.3 = 102.3", "2of3", "escalate",
    "PRIORITY / MISSING FIELD. Derived exactly as on the sibling row royal_recruits.dps (102), "
    "which matches. Same body, same stats -- confirmed by Royal Delivery's own vardefines "
    "hp_11=547, Shield_11=240, dmg_11=133, atk_speed=1.3, all identical to the Royal Recruits "
    "page, which is the owner's 2026-08-20 ruling holding up under re-source.")
# ---------------------------------------------------------------- rune_giant
row("rune_giant", "hitpoints", 2662, 2662, 2662, 2822, "Rune Giant",
    "vardefine hp_11=2662; statistics table L11 Hitpoints = 2,662 (literal) at rev 436055 "
    "(2026-05-03) and vardefined 2662 at rev 436714 (2026-07-16), BOTH predating the buff; "
    "History '* On 4/8/2026, a Balance Update, increased the Rune Giant's Hitpoints by 6%, her "
    "Enchantment Cast Time Delay has been removed, and she no longer enchants suicide troops "
    "(such as Wall Breakers, Spirits, etc.)'", "split", "escalate",
    LAG + " Confirmed at two pre-change timepoints: 2,662 at rev 436055 (2026-05-03) and 2662 at "
    "rev 436714 (2026-07-16), and still 2662 today. Reconstructed 2662*1.06 = 2822. Row "
    "verified:true. Corroboration that the update itself is real: the wiki DID apply other parts "
    "of the same 4/8/2026 update (Spear Goblins 1.7->1.6, Zappies 2.1->2.2), so this page was "
    "missed rather than the entry being fictional.")
row("rune_giant", "damage", 120, 120, 120, 154, "Rune Giant",
    "vardefine dmg_11=120; statistics table L11 Damage = 120 (literal) at rev 436055 (2026-05-03), "
    "which PREDATES the buff; History '* On 1/6/2026, a Balance Update, increased the Rune "
    "Giant's damage by 28%'", "split", "escalate",
    LAG + " A SECOND unapplied update on the same card: rev 436055 (2026-05-03) read 120 and today "
    "still reads 120, so the 1/6/2026 +28% never landed; reconstructed 120*1.28 = 154. If "
    "accepted, dps follows: 120/1.5 = 80 becomes 154/1.5 = 103. Rune Giant is therefore two "
    "balance updates behind on the wiki, hitpoints and damage both.")
row("rune_giant",
    "enchant (bonus_damage / enchant_range_tiles / enchant_limit / enchant_every_nth / "
    "enchant_duration_after_death_s)", None, 220, 220, None, "Rune Giant",
    "vardefine bonus_11=220; attr table 'Enchant': Enchant Range 8.5 tiles | Enchant Limit x2 | "
    "Enchant Shot 'Every 3rd Attack' | 'Enchant duration after she dies' 5 sec; statistics table "
    "carries a 'Bonus Damage' column (L11 = 220); prose 'Rune Giant enchants Troops closest to "
    "her, having them deal Bonus Damage every third attack. Only two Troops can be enchanted at "
    "once.'", "2of3", "escalate",
    "PRIORITY / MISSING FIELDS -- the card's entire identity is unmodelled. The KB row carries no "
    "enchant fields at all, so in the sim a Rune Giant is just a weak 4-elixir building-targeting "
    "body (120 damage) that grants nothing to anyone. Published and ready to wire: +220 bonus "
    "damage at L11 on every 3rd attack, to the 2 nearest troops, within 8.5 tiles, persisting 5 s "
    "after she dies. The 4/8/2026 entry also removed the Enchantment Cast Time Delay and stopped "
    "her enchanting suicide troops (Wall Breakers, Spirits).")
# ---------------------------------------------------------------- skarmy_general
row("skarmy_general", "range_tiles", 0.5, None, 1.6, None, "Skeleton Army/Evolution",
    "attr table 'General Gerry Attributes': Hit Speed 1 sec | First Hit Speed 0.5 sec | Speed "
    "Fast (90) | Deploy Time 1 sec | Range 'Melee: Long (1.6)' | Target Ground | Transport Ground",
    "2of3", "update",
    "RESOLVES A STANDING [verify] MARKER. cards.yaml says 'General stats unpublished -- guard-like "
    "curation [verify]', but the Evolution page now publishes them in section 'General Gerry "
    "Attributes', and every other curated guess is confirmed exactly: hitpoints 81 (gen_hp_11), "
    "shield_hp 81 (gen_shield_11), damage 81 (gen_dmg_11), hit_speed 1.0 (gen_atk_speed), "
    "speed_tiles 1.5 (Fast 90). Only the reach is wrong -- 0.5 vs the published 1.6, a 3.2x "
    "under-reach. Verdict 'update' because range_tiles is NOT among the fields curated in "
    "cards.yaml for this key (the row's verified:true covers the fields listed there); flagged "
    "explicitly so the owner can veto. PATHS PUBLISHING: P2 only -- range is never vardefined. "
    "Extracted from the PARENT page Skeleton Army/Evolution; skarmy_general has no page of its own.")
# ---------------------------------------------------------------- skeleton_barrel
row("skeleton_barrel", "death_spawn_delay_s", 0.5, None,
    "0.5 (Skeleton Attributes) / 0.6 (Skeleton Container Attributes)", None, "Skeleton Barrel",
    "attr table 'Skeleton Attributes': Hit Speed 1.1 sec | Speed Fast (90) | Range 'Melee: Short "
    "(0.5)' | Deploy Time 0.5 sec | Target Ground | Count x7; attr table 'Skeleton Container "
    "Attributes': Death Damage Splash Radius 2 | Deploy Time 0.6 sec | Target Air & Ground",
    "split", "escalate",
    "LOW PRIORITY / AMBIGUITY ONLY -- no change recommended. The page exposes two different "
    "'Deploy Time' cells that could each map to this one KB field: 0.5 s on the seven Skeletons "
    "and 0.6 s on the Skeleton Container. current_db 0.5 matches the Skeletons' cell and matches "
    "the wiki prose the curation already quotes ('the 0.5 SECOND ANIMATION where neither the "
    "Barrel nor the Skeletons are considered as entities'), so 0.5 is very likely right; logged "
    "only so the 0.6 cell is on record and nobody re-derives it later. All 16 other Skeleton "
    "Barrel fields match exactly, including death_damage 145 and death_radius_tiles 2.0.")
# ---------------------------------------------------------------- skeleton_dragons
row("skeleton_dragons", "damage", 161, 161, 161, 151, "Skeleton Dragons",
    "vardefine dmg_11=161; statistics table L11 'Area Damage' = 161 (literal) at rev 435908 "
    "(2026-04-15), which PREDATES the nerf; History '* On 4/5/2026, a Balance Update, decreased "
    "the Skeleton Dragons' damage by 6%'", "split", "escalate",
    LAG + " rev 435908 (2026-04-15) already read 161 and today's rev 437268 still reads 161, so "
    "the 4/5/2026 -6% is unapplied; reconstructed 161*0.94 = 151, and dps would follow 80 -> 76. "
    "Row is verified:false, but the only evidence for 151 is the reconstruction, so not an "
    "auto-update. The same page's OTHER recent entry (6/4/2026: splash radius 0.8 -> 1.5 and hit "
    "speed 1.9 -> 2.0) IS applied in both the table and the KB, which is why this one reads as a "
    "genuine miss rather than a bogus History line.")
# ---------------------------------------------------------------- spear_goblins
row("spear_goblins", "hit_speed", 1.7, 1.6, 1.6, 1.6, "Spear Goblins",
    "vardefine atk_speed=1.6; attr table Hit Speed = 1.6 sec; History '* On 4/8/2026, a Balance "
    "Update, decreased the Spear Goblins' hit speed to 1.6 seconds (from 1.7 seconds).'",
    "3of3", "update",
    "CLEANEST FINDING IN THE GROUP -- all three paths agree on 1.6 and all three differ from "
    "current_db 1.7, which is exactly the pre-4/8/2026 value the History names. Row is "
    "verified:false and the field is not curated in cards.yaml (spear_goblins: {range: long, "
    "verified: false}), so this is a straight update. The wiki applied the same 4/8/2026 update "
    "to Zappies (2.1 -> 2.2, already matching the KB), confirming the update shipped.")
row("spear_goblins", "dps", 48, 51, 51, 51, "Spear Goblins",
    "derived from vardefines dmg_11=81 and atk_speed=1.6 -> 81/1.6 = 50.6", "3of3", "update",
    "Consequence of the hit_speed update above, not an independent finding. current_db 48 is "
    "exactly 81/1.7 = 47.6, which confirms the KB dps was computed from the stale 1.7. 81/1.6 = "
    "50.6 -> 51 under the round-half-up convention the rest of the DB uses (verified against "
    "night_witch 314/1.3=242, skeleton_army 81/1.1=74, zappies 117/2.2=53). Ship with hit_speed.")
# ---------------------------------------------------------------- spirit_empress
EW = ("EDIT-WAR PIN, and the revision history now VINDICATES the curation rather than merely "
      "asserting it. At rev 436748 (2026-07-16) the wiki itself carried hp_11=1121 and "
      "air_atk_speed=1.4 -- precisely the curated values. Between 2026-08-09 and 2026-08-14 an "
      "editor churned the page (hp 1121 -> 2023 at rev 437131 -> 1798 at rev 437272; air hit "
      "speed 1.4 -> 1.6) with NO corresponding History entry, and the edit summary on rev 437082 "
      "reads 'alright you I'll, air spirit empress gets a rework next balance changes but she was "
      "oversh[adowed]' -- an editor's opinion about a FUTURE rework, not a shipped change. "
      "cards.yaml already documents this ('the 2026-08-14 wiki import caught the Fandom page "
      "mid-edit-war ... with no balance change behind it'). Verdict pin: keep the curated value, "
      "do not re-litigate.")
row("spirit_empress", "hitpoints", 1121, 1798, 1798, None, "Spirit Empress",
    "vardefine hp_11=1798 (a single Hitpoints column shared by both forms); History carries no "
    "hitpoint entry after '* On 4/5/2026 ... decreased the Sprirt Empress' Ground Hitpoints by 3% "
    "and decreased her Air Hitpoints by 5%'", "split", "pin", EW)
row("spirit_empress", "damage", 307, 309, 309, None, "Spirit Empress",
    "vardefine dmg_11=309 -- also 309 at rev 436748 (2026-07-16), i.e. BEFORE the edit war",
    "split", "escalate",
    "NOT edit-war noise -- separate from the hitpoints pin and needs its own ruling. dmg_11 read "
    "309 at rev 436748 (2026-07-16) before the August churn and reads 309 now, so 309 is the "
    "wiki's stable value while the KB curates 307. A 2-point gap, small but real. Row is "
    "verified:true and the value came from Supercell's balance posts, so escalate rather than "
    "update; worth re-checking that source post, since the same 307 is curated on both forms.")
row("spirit_empress_air", "hitpoints", 1121, 1798, 1798, None, "Spirit Empress",
    "vardefine hp_11=1798 -- the page publishes ONE Hitpoints column for both forms",
    "split", "pin",
    EW + " EXTRA: the page is structurally incapable of holding this field correctly -- its "
    "History records SEPARATE Ground and Air hitpoint changes (2/3/2026, 4/5/2026) but the "
    "statistics table has a single shared Hitpoints column, so the wiki cannot represent the two "
    "forms differing at all. Another reason not to import from it.")
row("spirit_empress_air", "damage", 307, 309, 309, None, "Spirit Empress",
    "vardefine dmg_11=309 (shared Damage column for both forms)", "split", "escalate",
    "Same 307-vs-309 question as the ground form; both rows curate 307 and must move together.")
row("spirit_empress_air", "hit_speed", 1.4, 1.6, 1.6, 1.4, "Spirit Empress",
    "vardefine air_atk_speed=1.6; attr table 'Air Form Attributes' Hit Speed = 1.6 sec; History "
    "'*On 10/7/2025, a maintenance break, ... decreased her Air Form's attack time interval to "
    "1.4 seconds (from 1.5 seconds)' with no later air hit-speed entry", "split", "pin",
    "P3 SUPPORTS THE KB AGAINST P1/P2 -- the wiki's own History says 1.4 and nothing since changes "
    "it, so the table's 1.6 contradicts the same page's history. Combined with the edit trail "
    "(air_atk_speed was still 1.4 at rev 436748 on 2026-07-16 and was flipped to 1.6 during the "
    "same uncommented 2026-08-09/14 burst that inflated hitpoints), the curated 1.4 is correct. "
    "Keep 1.4.")
# ---------------------------------------------------------------- suspicious_bush
row("suspicious_bush", "range_tiles", 0.5, None, 0.5, 1.6, "Suspicious Bush",
    "attr table 'Suspicious Bush Attributes' Range = 'Melee: Short (0.5)'; History '* On 6/4/2026, "
    "a Balance Update, increased the Bush range to 1.6 tiles (from 0.5 tiles), now classified as "
    "Melee: Long'", "split", "escalate",
    "Wiki self-contradiction: the History entry names the old value (0.5), the new value (1.6) AND "
    "the new classification, yet the table still reads 'Melee: Short (0.5)'. rev 435486 "
    "(2026-03-14, before the change) also read 'Melee: Short (0.5)', so the table simply was not "
    "updated -- the same unapplied-change pattern as Rune Giant and Wall Breakers, and here the "
    "History is unusually specific, which strengthens it. Recommended 1.6. Field IS explicitly "
    "curated verified:true in cards.yaml (suspicious_bush: {... range_tiles: 0.5}) -> escalate. "
    "Matters more than it looks: this is the reach at which a kamikaze bush connects.")
# ---------------------------------------------------------------- three_musketeers
TM = ("THE 3/11/2025 REWORK IS NOT MODELLED. History: '*On 3/11/2025, a Balance Update, reworked "
      "the Three Musketeers so that it now spawns three different troops called \"Elite "
      "Musketeers\" that have different damage statistics from the Musketeer and A MELEE ATTACK.' "
      "The page now publishes two attack modes -- 'Ranged Attack' (Range 6, Air & Ground) and "
      "'Melee Attack' (Range 'Melee: Long', Ground) -- with separate vardefines 'melee dmg_11'=314 "
      "and 'range dmg_11'=204. NOTE: those two vardefine NAMES CONTAIN SPACES, so the standard "
      "[A-Za-z0-9_]+ vardefine pattern silently misses them -- any re-run must use a permissive "
      "name pattern or it will report this page as having no damage vardefine at all.")
row("three_musketeers", "damage", None, "melee 314 / ranged 204", "melee 314 / ranged 204", None,
    "Three Musketeers",
    "vardefines hp_11=883, 'melee dmg_11'=314, 'range dmg_11'=204, atk_speed=1.3; attr tables "
    "'Ranged Attack': Range 6 | Target Air & Ground -- and 'Melee Attack': Range 'Melee: Long' | "
    "Target Ground", "2of3", "escalate",
    TM + " The KB row has NO damage and NO dps at all, so three_musketeers currently deals ZERO "
    "damage in the sim -- a 9-elixir card that cannot hurt anything. Highest-impact gap in the "
    "group. It also cannot be fixed by writing one number: the schema has a single `damage` field "
    "and this unit now has two attack modes.")
row("three_musketeers", "dps", None, "melee 242 / ranged 157", "melee 242 / ranged 157", None,
    "Three Musketeers", "derived: 314/1.3 = 241.5 and 204/1.3 = 156.9", "2of3", "escalate",
    "PRIORITY / MISSING FIELD, a consequence of the damage gap above. Uses the current atk_speed "
    "1.3; if the 2/2/2026 entry (1.2) is accepted instead, these become 262 and 170.")
row("three_musketeers", "range_tiles", None, None, "6 (ranged) / 1.6 (melee)", None,
    "Three Musketeers",
    "attr table 'Ranged Attack' Range = 6; attr table 'Melee Attack' Range = 'Melee: Long' "
    "(1.6 tiles by this wiki's own Melee: Long convention, cf. Prince and Royal Recruits)",
    "2of3", "escalate",
    "PRIORITY / MISSING FIELD. The KB carries range: 'long' but no range_tiles, so nothing tells "
    "the engine how far a Musketeer shoots. PATHS PUBLISHING: P2 only. The melee figure is my "
    "reading of 'Melee: Long' -- that particular cell omits the parenthesised number every other "
    "page gives, so it is inferred, not quoted.")
row("three_musketeers", "attacks", None, None, ["air", "ground"], None, "Three Musketeers",
    "attr table 'Ranged Attack' Target = 'Air & Ground'; attr table 'Melee Attack' Target = "
    "'Ground'", "2of3", "escalate",
    "PRIORITY / MISSING FIELD. The KB row has no `attacks` list at all, so air-targeting is "
    "undefined for a card whose ranged mode explicitly hits air. The strategic tags are also now "
    "only half true: flags [ranged] and range 'long' describe one of the unit's two modes.")
row("three_musketeers", "hit_speed", 1.3, 1.3, 1.3, 1.2, "Three Musketeers",
    "vardefine atk_speed=1.3; attr table Hit Speed = 1.3 sec; History '* On 2/2/2026, increased "
    "attack speed to 1.2 seconds (from 1.3 seconds).'", "split", "escalate",
    "WEAKEST of the P3 conflicts -- flagged, but treat this History entry with suspicion. rev "
    "434538 (2026-01-26, days BEFORE the 2/2/2026 entry) shows Hit Speed '1 sec', not the 1.3 the "
    "entry claims it changed FROM, so the page's numbers around the 3/11/2025 rework are "
    "internally inconsistent; the entry is also the only one on the page with no update name "
    "attached. Recommend resolving this together with the rework gap above rather than alone.")
# ---------------------------------------------------------------- wall_breakers
row("wall_breakers", "damage", 391, 391, 391, 313, "Wall Breakers",
    "vardefine dmg_11=391 -- also hp_11=330 / dmg_11=391 at rev 436975 (2026-07-31), which "
    "PREDATES the nerf; statistics table column 'Area Damage'; History '* On 4/8/2026, a Balance "
    "Update, decreased the Wall Breakers' damage by 20%'", "split", "escalate",
    LAG + " rev 436975 (2026-07-31) already carried dmg_11=391 and today's rev 437357 still "
    "carries 391, so the 4/8/2026 -20% is unapplied; reconstructed 391*0.8 = 313. Row "
    "verified:true. Same corroboration as Rune Giant: the wiki DID apply other parts of the "
    "4/8/2026 update (Spear Goblins, Zappies), so the update shipped and this page was missed. "
    "High impact -- this number IS the card.")

OUT = "C:/Users/benpe/ClashBot/research/sim_parity/ledger/r2_troops_c.jsonl"
with open(OUT, "w", encoding="utf-8") as f:
    for r in R:
        f.write(json.dumps(r, ensure_ascii=False) + "\n")

from collections import Counter
c = Counter(r["verdict"] for r in R)
print("lines:", len(R), dict(c))
print("keys with lines:", len({r["key"] for r in R}))
