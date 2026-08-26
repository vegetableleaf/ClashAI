# -*- coding: utf-8 -*-
"""Emit r2_evos_b.jsonl rows for the 7 keys the earlier pass did not reach:
musketeer_evo, royal_recruits_evo, skeleton_barrel_evo, skeletons_evo,
witch_evo, wizard_evo, zap_evo.  Appends; never rewrites existing rows."""
import json, collections

LED = r'C:/Users/benpe/ClashBot/research/sim_parity/ledger/r2_evos_b.jsonl'
B = "https://clashroyale.fandom.com/api.php?action=parse&page=%s&prop=wikitext|revid&format=json"
F = "2026-08-26 live refetch; revid identical to the 00:52 evos_b fetchlog and cache byte-identical"

def S(page, revid, raw):
    return {"url": B % page.replace(' ', '%20'), "revid": revid, "fetched": F, "raw": raw}

OK = {"edit_war": "pass"}
R = []
def add(**k): R.append(k)

# ------------------------------------------------ musketeer_evo
add(key="musketeer_evo", field="_row_verification",
    current_db="hp721 dmg217 hit_speed1.0 dps217 elixir4 cycles2 count1 rare range6.0 speed1.0 proj1000 sniper_shots3 sniper_mult1.8",
    p1_vardefine="hp_11=721, dmg_11=217, snipe_dmg_11=390, snipe_hits=3, atk_speed=1",
    p2_table="Infobox Cost=4 CycleCost=2 Rarity=Rare Type=Troop; unit-attributes-table Hit Speed 1 sec | First Hit Speed 0.7 sec | Speed Medium (60) | Deploy Time 1 sec | Range 6 | Projectile Speed 1000 | Target Air & Ground | Count x1 | Transport Ground",
    p3_history="last stat change 31/3/2025 (hp -0.06%, damage -0.45%); sniper 180% since 14/11/2024; first-attack interval 0.7s since 4/2/2025 and the table already shows 0.7 -- nothing postdates the vardefines",
    sources=[S("Musketeer/Evolution", 436483,
               "{{#vardefine: hp_11 | 721 }} {{#vardefine: dmg_11 | 217 }} {{#vardefine: snipe_dmg_11 | 390 }} {{#vardefine: snipe_hits | 3 }} {{#vardefine: atk_speed | 1 }}"),
             S("Musketeer", 436481,
               "base attributes row Medium (60)||1 sec||6||1000||Air & Ground||x1||Ground; evo lead 'identical stats to the original'")],
    vote="3of3", cross_checks=OK, verdict="match",
    notes="All 17 compared fields match. sniper_mult 1.8 reproduces the published absolute snipe_dmg_11=390 (217*1.8=390.6 -> floor 390); worth confirming the engine floors rather than rounds, or Evo Musketeer snipes for 391. The wiki publishes First Hit Speed 0.7s, which the KB row does not carry -- a group-wide gap, not musketeer-specific.")

# ------------------------------------------------ royal_recruits_evo
add(key="royal_recruits_evo", field="charge_range",
    current_db=2.5, p1_vardefine=None,
    p2_table="lead prose: 'they gain the ability to charge towards their target after traveling 2 tiles' -- STALE",
    p3_history="8/1/2025 'increased the distance required for charging to 2 tiles (from 1.5 tiles)'; 6/10/2025 'increased the distance required for charging to 2.5 tiles (from 2 tiles)' -> current 2.5",
    sources=[S("Royal Recruits/Evolution", 436465,
               "After their shield is destroyed, they gain the ability to charge towards their target after traveling 2 tiles, dealing 2x damage ... | *On 6/10/2025, a Balance Update, increased the distance required for charging to 2.5 tiles (from 2 tiles).")],
    vote="split", cross_checks=OK, verdict="match",
    notes="PATH SPLIT but the sim is RIGHT. The lead prose (2 tiles) was never edited after the dated 6/10/2025 entry raised the charge distance to 2.5. current_db 2.5 matches the reconstruction, so no sim change. Recorded because any future re-import that trusts the prose would silently regress this to 2.0.")
add(key="royal_recruits_evo", field="_row_verification",
    current_db="hp547 shield240 dmg133 charge266 hit_speed1.3 dps102 range1.6 count6 elixir7 cycles1 speed1.0",
    p1_vardefine="hp_11=547, Shield_11=240, dmg_11=133, Charge_11=266, atk_speed=1.3",
    p2_table="Infobox Cost=7 CycleCost=1 Rarity=Common; attributes Hit Speed 1.3 sec | First Hit Speed 0.5 sec | Speed Medium (60) | Deploy Time 1 sec | Range Melee: Long (1.6) | Target Ground | Count x6",
    p3_history="5/3/2024 removed the damage boost and 14/5/2024 removed the hitpoints boost, so evo stats are now identical to base Royal Recruits (base vardefines 547/240/133/1.3 confirm); charge nerfs 3/1/2024 -8% and 8/1/2025 -3% are already folded in -- Charge_11 266 is exactly 2x dmg_11 133, matching the '2x damage' prose",
    sources=[S("Royal Recruits/Evolution", 436465,
               "{{#vardefine: hp_11 | 547 }} {{#vardefine: Shield_11 | 240 }} {{#vardefine: dmg_11 | 133 }} {{#vardefine: Charge_11 | 266 }} {{#vardefine: atk_speed | 1.3 }}"),
             S("Royal Recruits", 436459,
               "base hp_11 547, Shield_11 240, dmg_11 133, atk_speed 1.3 -- identical, confirming both boosts are gone")],
    vote="3of3", cross_checks=OK, verdict="match",
    notes="All 17 fields match including curated charge_damage 266 and charge_after_shield (prose 'After their shield is destroyed'). dps 102 = 133/1.3 = 102.3. Deploy Time is 1 sec; the 0.5 sec in the row is First Hit Speed -- separate columns, do not conflate.")

# ------------------------------------------------ skeleton_barrel_evo
SBE = S("Skeleton Barrel/Evolution", 437248,
        "{{#vardefine: death_11 | 238 }} {{#vardefine: death_hits | 2 }} | *On 12/1/2026, a Balance Update decreased the Skeleton Barrel's death damage by 8%. | *On 6/4/2026, a Balance Update, decreased the Skeleton Barrel's death damage by 13%")
SBB = S("Skeleton Barrel", 436976,
        "base {{#vardefine: death_11 | 145 }}; base History has NO 2026 entries at all (last entry 6/10/2025)")
add(key="skeleton_barrel_evo", field="death_damage",
    current_db=238.0,
    p1_vardefine="death_11=238 (= 164% of base death_11 145; the 4/8/2025 state)",
    p2_table="unit-statistics-table L11 renders 'death_11 x death_hits' = 238 x2 (476); lead prose 'death damage 64% higher than the original' = 164% -- the SAME 4/8/2025 snapshot, not an independent path",
    p3_history="4/8/2025 death damage -> 164% of original (from 176%); then 12/1/2026 '-8%'; then 6/4/2026 '-13%'. Reconstruction 238*0.92*0.87 = 190.5 -> ~190 per barrel (ratio form 164%*0.92*0.87 = 131.3% of base 145 = 190.3)",
    sources=[SBE, SBB], vote="split", cross_checks=OK, verdict="escalate",
    notes="ESCALATE - do not auto-update. P1 and P2 are NOT independent here (the prose and the vardefine are one 4/8/2025 snapshot), so the apparent 2-of-3 for 238 is a false majority; two dated 2026 nerfs postdate both. AMBIGUITY for the owner: the 2026 entries say 'the Skeleton Barrel's death damage', not 'the Evolved Skeleton Barrel's', and appear ONLY on the Evolution page. Reading (a) evo-specific -> evo death damage is now ~190 and current_db 238 overstates it by ~25%. Reading (b) base-card changes mislogged on the evo page -> but base death_11 is still 145 (145*0.92*0.87 = 116), so under (b) the BASE vardefine lags too. Either way at least one published number is stale. death_damage is NOT curated in cards.yaml (only count/damage/dps/mid_drop_frac are), so an update is permissible once the reading is settled.")
add(key="skeleton_barrel_evo", field="count",
    current_db=1,
    p1_vardefine="death_hits=2 (barrels; used as the x2 multiplier on the death-damage column)",
    p2_table="unit-attributes-table Count = x2",
    p3_history="never changed; the card has carried 2 barrels since release 7/7/2025",
    sources=[S("Skeleton Barrel/Evolution", 437248,
               "|3||Fast (90)||Melee: Short (0.35)||1 sec||Buildings  /next line/  |2||Air||Troop||Common  (Count column = 2)")],
    vote="2of3", cross_checks=OK, verdict="pin",
    notes="PIN, not a discrepancy. The wiki's Count=2 is the BARRELS-carried attribute; the card deploys ONE flying body. cards.yaml curates count:1 with that rationale written out. Deliberate, documented semantic re-interpretation -- do not 'fix' toward 2.")
add(key="skeleton_barrel_evo", field="damage",
    current_db=0,
    p1_vardefine="dmg_11=81 -- this is the SKELETON's swing, not the barrel's",
    p2_table="the statistics-table columns are headed 'Skeleton Barrel Hitpoints', 'Skeleton Barrel Death Damage', 'Skeleton Hitpoints', 'Skeleton Damage' -- dmg_11 sits under Skeleton Damage",
    p3_history="6/10/2025 'increased the Skeleton's attack time interval to 1.1 seconds' -- again the spawned skeleton, not the barrel",
    sources=[S("Skeleton Barrel/Evolution", 437248,
               "!scope=col|Skeleton Barrel Hitpoints !scope=col|Skeleton Barrel Death Damage !scope=col|Skeleton Hitpoints !scope=col|Skeleton Damage !scope=col|Skeleton Damage per second")],
    vote="3of3", cross_checks=OK, verdict="pin",
    notes="PIN. The column headers prove the curation is right: dmg_11 belongs to the spawned Skeleton, so the barrel itself has 0 contact damage (it is a building-targeting kamikaze). The original import evidently read the header-less column.")
add(key="skeleton_barrel_evo", field="dps",
    current_db=0,
    p1_vardefine="dmg_11/atk_speed = 81/1.1 = 74 -- the Skeleton's dps",
    p2_table="'Skeleton Damage per second' column",
    p3_history="n/a",
    sources=[S("Skeleton Barrel/Evolution", 437248, "!scope=col|Skeleton Damage per second")],
    vote="3of3", cross_checks=OK, verdict="pin",
    notes="PIN, companion to damage:0 -- the 74 dps belongs to the spawned Skeleton.")
add(key="skeleton_barrel_evo", field="spawn_count (MISSING)",
    current_db=None, p1_vardefine=None,
    p2_table="lead prose 'It spawns with 2 barrels, each with 7 Skeletons: one dropped when it reaches 75% hitpoints, and another dropped when it is defeated' -> 7 per barrel, 14 total",
    p3_history="base card 12/2/2018 skeletons on death -> 6 (from 8), then 25/4/2018 -> 7; the evo page has never changed the per-barrel count, so 7 stands",
    sources=[S("Skeleton Barrel/Evolution", 437248,
               "It spawns with 2 barrels, each with 7 [[Skeletons]]: one dropped when it reaches 75% hitpoints, and another dropped when it is defeated.")],
    vote="2of3", cross_checks=OK, verdict="escalate",
    notes="MISSING FIELD. The KB row carries spawn_unit_stats (hit_speed/range/speed) but no skeleton COUNT, and 14 skeletons is essentially the whole card. Without it the sim either drops the payload or falls back to a default. Propose spawn_count 7 per barrel (14 total). Escalated rather than auto-updated because it is a NEW field on a verified:true row.")
add(key="skeleton_barrel_evo", field="_row_verification",
    current_db="hp665 death238 death_radius2.0 hit_speed1.1 speed1.5 range0.35 deploy1.0 elixir3 cycles2 common air buildings mid_drop0.75",
    p1_vardefine="hp_11=665, death_11=238, death_hits=2, sk_hp_11=81, dmg_11=81, atk_speed=1.1",
    p2_table="Infobox Cost=3 CycleCost=2 Cycles=2 Rarity=Common; attributes Speed Fast (90) | Range Melee: Short (0.35) | Deploy Time 1 sec | Target Buildings | Count x2 | Transport Air. Base page's death-damage table gives Death Damage Splash Radius = 2",
    p3_history="hp 'hitpoints 25% higher than the original' and 665/532 = 1.2500 exactly; hit speed 1.1 since 6/10/2025 (current)",
    sources=[S("Skeleton Barrel/Evolution", 437248,
               "{{#vardefine: hp_11 | 665 }} {{#vardefine: atk_speed | 1.1 }}; 'hitpoints 25% higher ... one dropped when it reaches 75% hitpoints'"),
             S("Skeleton Barrel", 436976,
               "base hp_11 532, death_11 145; '!Death Damage Splash Radius' row renders |2||0.6 sec||Air & Ground")],
    vote="3of3", cross_checks=OK, verdict="match",
    notes="15 of 20 fields match: hitpoints 665, death_radius_tiles 2.0, hit_speed 1.1, speed 1.5 (=Fast(90)), range 0.35, deploy_time 1.0, elixir 3, evo_cycles 2, rarity common, movement air, attacks buildings, mid_drop_frac 0.75 (from the 75% prose), and all 3 spawn_unit_stats which match the Skeletons profile 1.1/0.5/Fast. The other 5 fields are the rows above.")

# ------------------------------------------------ skeletons_evo
add(key="skeletons_evo", field="_row_verification",
    current_db="hp81 dmg81 hit_speed1.1 dps74 count3 range0.5 speed1.5 elixir1 cycles2 spawn_on_hit_cap8",
    p1_vardefine="hp_11=81, dmg_11=81, atk_speed=1.1",
    p2_table="Infobox Cost=1 CycleCost=2 Rarity=Common; attributes Hit Speed 1.1 sec | First Hit Speed 0.5 sec | Speed Fast (90) | Deploy Time 1 sec | Range Melee: Short (0.5) | Target Ground | Count x3. Lead: 'It spawns 3 Skeletons, with identical stats to the originals ... an additional Evolved Skeleton will spawn, for a maximum total of 8'",
    p3_history="cap 8 (30/6/2023) -> 6 (8/8/2023) -> 8 (3/10/2023), current 8; deploy count 3 since 8/1/2025 (from 4); cycles 2 since 8/8/2023; attack interval 1.1s since 6/10/2025. Every dated change is already reflected in P1/P2 -- nothing postdates them",
    sources=[S("Skeletons/Evolution", 436451,
               "{{#vardefine: hp_11 | 81 }} {{#vardefine: dmg_11 | 81 }} {{#vardefine: atk_speed | 1.1 }}; 'for a maximum total of 8 Skeletons'; *On 8/1/2025, a Balance Update, decreased the number of Evolved Skeletons spawned to 3 (from 4).")],
    vote="3of3", cross_checks=OK, verdict="match",
    notes="Cleanest key in the group: all 15 fields match on all three paths, including both curated fields (spawn_on_hit skeletons_evo, spawn_on_hit_cap 8). dps 74 = 81/1.1 = 73.6. This row also independently validates skeleton_barrel_evo's spawn_unit_stats (1.1 / 0.5 / Fast 1.5).")

# ------------------------------------------------ witch_evo
W = S("Witch/Evolution", 437350,
      "* On 4/8/2026, a Balance Update, increased the Evolved Witch's heal per skeleton by 189%, increased her max hitpoints by 40%, increased her overheal ratio to x1.73 (from x1.24), and made it to where she can only be healed by the first 4 skeletons that she spawns.")
WV = S("Witch/Evolution", 437350,
       "{{#vardefine: hp_11 | 839 }} {{#vardefine: maks_hp_11 | 1039 }} {{#vardefine: dmg_11 | 135 }} {{#vardefine: atk_speed | 1.1 }} {{#vardefine: heal_11 | 76 }}")
WB = S("Witch", 436707,
       "base hp_11 839, dmg_11 135, atk_speed 1.1, Speed Medium (60), Range 5.5, Splash Radius 1.5, Projectile Speed 600, Spawn Speed 7 sec; evo lead 'spawns a Witch with identical stats to the original'")
add(key="witch_evo", field="overheal_frac",
    current_db=1.238,
    p1_vardefine="maks_hp_11/hp_11 = 1039/839 = 1.2384 -- STALE",
    p2_table="lead prose 'allowing her to achieve 24% more hitpoints at its maximum capacity' = 1.24 -- STALE (same snapshot as P1)",
    p3_history="4/8/2026 'increased her overheal ratio to x1.73 (from x1.24)' -> current 1.73",
    sources=[W, WV], vote="split", cross_checks=OK, verdict="escalate",
    notes="ESCALATE - curated verified:true (cards.yaml line 218), never auto-overwrite. The history gives an ABSOLUTE new value (x1.73) and names the old one (x1.24), which is exactly what P1/P2 still publish -- so both predate 4/8/2026 and the '2-of-3' for 1.238 is a false majority. Compounding note: the cards.yaml comment says this row was re-sourced on 2026-08-16 FROM these vardefines, so the re-source inherited the lag rather than introducing it.")
add(key="witch_evo", field="spawn_death_heal",
    current_db=76,
    p1_vardefine="heal_11=76 -- STALE (pre-4/8/2026)",
    p2_table="unit-statistics-table 'Skeleton Death Heal' column driven by heal_11; the Strategy text derives '14 Skeletons ... to go from 1 hitpoint to full overheal', and 14*76 = 1064 ~ maks_hp 1039 -- the same stale snapshot",
    p3_history="heal chain 3/6/2025 -12%, 8/7/2025 -12%, 4/8/2025 +36%, 6/10/2025 -21%, 2/2/2026 -11%, then 4/8/2026 '+189%'. 76*2.89 = 219.6 -> ~220",
    sources=[W, WV], vote="split", cross_checks=OK, verdict="escalate",
    notes="ESCALATE - curated verified:true. Proof the vardefine predates 4/8/2026: maks_hp_11/hp_11 is still exactly the OLD x1.24 ratio, so that update was folded into no vardefine on the page. Reconstructed ~220 per skeleton (~2.9x). The arithmetic cross-check is imperfect -- 4 heals x 220 = 880 would overshoot the 1.73 cap from full hp -- so the owner should confirm ~220 in-game rather than treat the derivation as final.")
add(key="witch_evo", field="max_hitpoints (MISSING)",
    current_db=None,
    p1_vardefine="maks_hp_11=1039 -- STALE",
    p2_table="unit-statistics-table 'Max Hitpoints' column",
    p3_history="4/8/2026 'increased her max hitpoints by 40%' -> 1039*1.40 = 1454.6 ~ 1455; independently 839*1.73 = 1451.5 ~ 1452 (agree to within rounding)",
    sources=[W, WV], vote="split", cross_checks=OK, verdict="escalate",
    notes="The KB row stores the cap only implicitly as hitpoints*overheal_frac. Both reconstructions land at ~1452-1455, which is the cross-check that base hitpoints 839 did NOT change on 4/8/2026 -- that update moved the CAP and the RATIO, not the base. Recorded so the owner can see the two derivations agree.")
add(key="witch_evo", field="heal_source_cap (MISSING)",
    current_db=None, p1_vardefine=None,
    p2_table="no table column; the lead prose still says only 'Once a Skeleton that the Evolved Witch has spawned is defeated, she is healed', with no cap",
    p3_history="4/8/2026 'made it to where she can only be healed by the first 4 skeletons that she spawns'",
    sources=[W], vote="2of3", cross_checks=OK, verdict="escalate",
    notes="NEW MECHANIC the sim does not model at all. Without it the sim heals her off every skeleton she ever spawns, which together with the (also unmodelled) larger per-skeleton heal is a large sustain overestimate. Note the cap partly OFFSETS the heal buff -- do not apply a ~220 heal without also applying the cap of 4.")
for fld, val, p1, p2, note in [
    ("damage", 135, "dmg_11=135",
     "unit-attributes-table + base Witch page identical (base dmg_11=135)",
     "Straight gap-fill: the row carries no damage at all."),
    ("hit_speed", 1.1, "atk_speed=1.1",
     "unit-attributes-table Hit Speed = 1.1 sec",
     "PRIORITY missing-hit_speed row (named in the task's priority list) -- resolved at 1.1."),
    ("dps", 123, "135/1.1 = 122.7",
     "unit-statistics-table DPS column = Dps(dmg_11, atk_speed)",
     "Derived from the two fields above: 135/1.1 = 122.7 -> 123."),
    ("speed_tiles", 1.0, None,
     "unit-attributes-table Speed = Medium (60) -> 60/60 = 1.0 tiles/s",
     "The row has no speed_tiles either; Medium(60) maps to 1.0 under the same convention the rest of the DB uses (Fast(90)=1.5)."),
]:
    add(key="witch_evo", field=fld + " (MISSING)", current_db=None,
        p1_vardefine=p1, p2_table=p2,
        p3_history="no History entry has ever changed the Evolved Witch's damage or attack speed; the 6/10/2025 'attack time interval to 1.1s' entry is the SKELETON's (skel_atk_speed=1.1), and her own atk_speed is independently 1.1 on the base page",
        sources=[WV, WB], vote="3of3", cross_checks=OK, verdict="update",
        notes=note + " Not curated in cards.yaml (only hitpoints/spawn_death_heal/overheal_frac are), so this is a permissible auto-update. Confirmed 3-of-3 by the evo vardefine, the evo attributes table, and the base Witch page under the 'identical stats to the original' clause. Propose " + repr(val) + ".")
add(key="witch_evo", field="spawn_count_per_wave (MISSING)",
    current_db=None, p1_vardefine=None,
    p2_table="base Witch lead: 'Every 7 seconds, the Witch will passively summon a group of four Skeletons surrounding her. However, her first wave of Skeletons will spawn 1 second after she is deployed.'",
    p3_history="base 1/4/2019 added 'spawn 3 additional Skeletons upon death'",
    sources=[WB], vote="2of3", cross_checks=OK, verdict="escalate",
    notes="The row has spawn_interval_s 7.0 but no COUNT per wave (4), no first-wave delay (1 s, not the generic 7 s), and no death-spawn (3). For the Evo specifically the spawn count drives the healing, so it is load-bearing twice over. Escalated as new fields on a verified:true row.")
add(key="witch_evo", field="_row_verification",
    current_db="hp839 spawn_interval7.0 proj600 range5.5 splash1.5 count1 elixir5 cycles1 epic deploy1.0",
    p1_vardefine="hp_11=839, skel_hp_11=81, skel_dmg_11=81, skel_atk_speed=1.1",
    p2_table="Infobox Cost=5 CycleCost=1 Cycles=1 Rarity=Epic; attributes Hit Speed 1.1 | First Hit Speed 0.7 | Speed Medium (60) | Deploy Time 1 sec | Spawn Speed 7 sec | Range 5.5 | Splash Radius 1.5 | Projectile Speed 600 | Target Air & Ground | Count x1",
    p3_history="4/8/2026 changed max hitpoints, overheal ratio and heal, but NOT base hitpoints -- 839*1.73 ~ 1039*1.40 confirms 839 held",
    sources=[WV, WB], vote="3of3", cross_checks=OK, verdict="match",
    notes="15 of 24 fields match: hitpoints 839 (survives 4/8/2026), spawn_interval_s 7.0, projectile_speed 600, range_tiles 5.5, splash_radius 1.5, count 1, elixir 5, evo_cycles 1, rarity epic, deploy_time 1.0, attacks air+ground, movement ground, and all 3 spawn_unit_stats (1.1/0.5/1.5, matching the Skeletons profile). The remaining 9 are the rows above.")

# ------------------------------------------------ wizard_evo
add(key="wizard_evo", field="_row_verification",
    current_db="hp832 shield192 dmg281 hit_speed1.4 dps201 range5.5 splash1.5 proj600 speed1.0 burst281/3.0/3.0 death_damage0",
    p1_vardefine="hp_11=832, shield_11=192, dmg_11=281, death_11=281, atk_speed=1.4",
    p2_table="Infobox Cost=5 CycleCost=1 Rarity=Rare; attributes Hit Speed 1.4 sec | First Hit Speed 0.4 sec | Speed Medium (60) | Deploy Time 1 sec | Range 5.5 | Splash Radius 1.5 | Projectile Speed 600 | Target Air & Ground | Count x1. Lead: 'Once the shield is destroyed, all pushback capable troops within 3 tiles of the Wizard will be pushed back by 3 tiles and take high damage'",
    p3_history="shield-hp chain ends 31/3/2025 (+1.05%) -> 192 current; pushback 3 tiles since 8/10/2024 (from 4); shield death damage +22% on 3/6/2025 -> 281 current. Every dated change is already in the vardefines; nothing postdates them",
    sources=[S("Wizard/Evolution", 437069,
               "{{#vardefine: hp_11 | 832 }} {{#vardefine: shield_11 | 192 }} {{#vardefine: dmg_11 | 281 }} {{#vardefine: death_11 | 281 }} {{#vardefine: atk_speed | 1.4 }}; 'within 3 tiles of the Wizard will be pushed back by 3 tiles'"),
             S("Wizard", 437068, "base page; evo lead 'spawns a Wizard with identical stats to the original'")],
    vote="3of3", cross_checks=OK, verdict="match",
    notes="All 20 fields match, including all four curated ones. The curation that death_11 is the SHIELD BURST rather than a death damage (hence death_damage:0, shield_burst_damage:281) is independently confirmed by the History, which calls the stat 'shield death damage' in both the 31/3/2025 and 3/6/2025 entries. dps 201 = 281/1.4 = 200.7. Only unmodelled nuance: the prose limits the knockback to 'pushback capable' troops.")

# ------------------------------------------------ zap_evo
Z = S("Zap/Evolution", 437306,
      "{{#vardefine: dmg_11 | 192 }} {{#vardefine: dmg_hits | 2 }} {{#vardefine: crown_dmg_11 | 58 }}; L11 row '{{#var:dmg_11}} x{{#var:dmg_hits}} ({{#expr: dmg_11*dmg_hits}})'; Quote 'Get two Zaps for the cost of one, with the second Zap hitting a larger area!'")
add(key="zap_evo", field="zap_pulses",
    current_db=3,
    p1_vardefine="dmg_hits=2 -- the statistics table renders Area Damage as '192 x2 (384)', so dmg_hits is unambiguously the pulse count",
    p2_table="Infobox quote 'Get TWO Zaps for the cost of one, with the SECOND Zap hitting a larger area'; lead prose describes exactly one follow-up ring: 'Once the initial hit is unleashed, the radius stays in the Arena, growing 0.5 tiles while doing the same damage and stun as the initial hit'",
    p3_history="8/10/2024 'increased the second pulse's damage by 100%, but REMOVED THE THIRD PULSE' -> 2 pulses",
    sources=[Z, S("Zap/Evolution", 437306,
                  "*On 8/10/2024, a Balance Update, increased the second pulse's damage by 100%, but removed the third pulse.")],
    vote="3of3", cross_checks=OK, verdict="escalate",
    notes="ESCALATE - curated verified:true so not auto-updated, but the evidence is 3-of-3 and unambiguous: the third pulse was REMOVED on 8/10/2024 and the curated 3 describes the pre-8/10/2024 card (the cards.yaml comment quotes the retired card text '3 pulses ... radii 2.5 -> 3.0 -> 3.5'). IMPACT: engine.py builds the ring as echoes = max(0, spec.zap_pulses - 1), so the sim fires 3 pulses for 3*192 = 576 area damage where the real card does 2*192 = 384 (+50%), and reaches 3.5 tiles where the real card stops at 3.0. INTERNAL CONTRADICTION: the same KB row already carries hits_per_attack 2.0, which card_import.py maps straight from dmg_hits -- the imported field is right and the curated override is wrong. Fixing zap_pulses to 2 also requires updating hogeq/tests/test_evo_t1.py:147, which asserts zap_pulses == 3.")
add(key="zap_evo", field="crown_tower_damage",
    current_db=58,
    p1_vardefine="crown_dmg_11=58 -- STALE; 58/192 = 30.2%, i.e. the OLD 30% rate",
    p2_table="unit-statistics-table 'Crown Tower Damage' column renders crown_dmg_11 x dmg_hits = 58 x2",
    p3_history="1/6/2026 'decreased the Zap's Crown Tower damage to 25% of the full damage (from 30%)' -> 192*0.25 = 48",
    sources=[Z, S("Zap/Evolution", 437306,
                  "* On 1/6/2026, a Balance Update, decreased the Zap's Crown Tower damage to 25% of the full damage (from 30%)"),
             S("Zap", 437305, "base page carries the SAME stale crown_dmg_11=58 and the SAME 1/6/2026 history entry")],
    vote="2of3", cross_checks=OK, verdict="update",
    notes="The sim is internally inconsistent and the owner's own pin supplies the target value. Base card `zap` is pinned at crown_tower_damage 48 (a KNOWN PIN, = 25% of 192, re-curated after 1/6/2026) while zap_evo still carries the stale wiki 58. Evo Zap is explicitly 'a Zap with identical stats to the original', so the two must agree -- the post-1/6/2026 crown-damage re-curation simply missed this evo row. Propose 48. crown_tower_damage is not curated for zap_evo in cards.yaml, so this is permissible; it should ride along with the pinned crown-tower family rather than be treated as a fresh finding.")
add(key="zap_evo", field="hitpoints",
    current_db=None,
    p1_vardefine="none published (no hp_11 on the page)",
    p2_table="Infobox Type=Spell; the attributes table has Cost / Radius / Stun Duration / Target only -- no hitpoints column exists for spells",
    p3_history="n/a",
    sources=[Z], vote="3of3", cross_checks=OK, verdict="match",
    notes="PRIORITY null-hitpoint row RESOLVED as correct-by-construction, not a data gap: zap_evo is kind='spell' and spells carry no hitpoints on the wiki or in the KB. No action. (The other null-hp priority rows in this group, minion_horde_evo and princess_evo, are genuine release stubs and were escalated separately.)")
add(key="zap_evo", field="_row_verification",
    current_db="dmg192 radius2.5 stun0.5 elixir2 cycles2 common hits_per_attack2.0 zap_radius_step0.5",
    p1_vardefine="dmg_11=192, dmg_hits=2, crown_dmg_11=58",
    p2_table="Infobox Cost=2 CycleCost=2 Rarity=Common Type=Spell; attributes Radius 2.5 | Stun Duration 0.5 sec | Target Air & Ground",
    p3_history="14/5/2024 pulses 2&3 -50%; 8/10/2024 pulse 2 +100% and pulse 3 removed, so both remaining pulses do full damage -- matching the prose 'the same damage and stun as the initial hit'; 1/6/2026 crown damage 25%",
    sources=[Z], vote="3of3", cross_checks=OK, verdict="match",
    notes="12 of 14 fields match: damage 192, radius_tiles 2.5, stun_duration_s 0.5, elixir 2, evo_cycles 2, rarity common, attacks air+ground, count, kind spell, hits_per_attack 2.0, zap_radius_step_tiles 0.5 (prose 'growing 0.5 tiles'), hitpoints null. The two exceptions are zap_pulses and crown_tower_damage above.")

with open(LED, 'a', encoding='utf-8') as fh:
    for r in R:
        fh.write(json.dumps(r, ensure_ascii=False) + '\n')
print("appended", len(R), "rows")
print(collections.Counter(r['verdict'] for r in R))
