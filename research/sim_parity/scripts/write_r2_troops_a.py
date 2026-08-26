# -*- coding: utf-8 -*-
import json, os
L = r"C:/Users/benpe/ClashBot/research/sim_parity/ledger"
LIVE = json.load(open(os.path.join(L, "r2_troops_a_livecheck.json"), encoding="utf-8"))
F = "2026-08-26"

PG = {"archers":"Archers","baby_dragon":"Baby Dragon","balloon":"Balloon","bandit":"Bandit",
      "barbarians":"Barbarians","bats":"Bats","battle_healer":"Battle Healer","battle_ram":"Battle Ram",
      "berserker":"Berserker","bomber":"Bomber","bowler":"Bowler","bush_goblin":"Suspicious Bush",
      "cannon_cart":"Cannon Cart","dark_prince":"Dark Prince","dart_goblin":"Dart Goblin",
      "decoy_goblin":"Goblin Barrel/Evolution","electro_dragon":"Electro Dragon",
      "electro_giant":"Electro Giant","electro_spirit":"Electro Spirit","electro_wizard":"Electro Wizard",
      "elite_barbarians":"Elite Barbarians","elixir_golem":"Elixir Golem","elixir_golemite":"Elixir Golem",
      "elixir_blob":"Elixir Golem","executioner":"Executioner","fire_spirit":"Fire Spirit",
      "firecracker":"Firecracker","fisherman":"Fisherman","flying_machine":"Flying Machine",
      "furnace":"Furnace","ghost_souldier":"Royal Ghost/Evolution","giant":"Giant"}


def src(page, raw):
    m = LIVE[page]
    return {"url": m["url"], "revid": m["live_revid"], "fetched": F, "raw": raw}


R = []


def rec(key, field, cur, p1, p2, p3, sources, vote, verdict, notes):
    R.append({"key": key, "field": field, "current_db": cur,
              "p1_vardefine": p1, "p2_table": p2, "p3_history": p3,
              "sources": sources, "vote": vote,
              "cross_checks": {"edit_war": "pass"},
              "verdict": verdict, "notes": notes})


# ================= UPDATES: vardefine/table lags a dated balance entry =================
rec("electro_giant", "hit_speed", 2.1, 2.1, 1.8, 1.8,
    [src("Electro Giant", "{{#vardefine: atk_speed | 2.1 }}"),
     src("Electro Giant", "|7||1.8 sec||1 sec||Slow (45)||1 sec||Melee: Medium (1.2)||Buildings||x1||Ground||Troop||Epic"),
     src("Electro Giant", "On 4/5/2026, a Balance Update, decreased the Electro Giant's attack time interval to 1.8 seconds (from 2.1 seconds) and his first attack time interval to 1 second (from 1.5 seconds), but also decreased his reflected tower damage by 24%.")],
    "2of3", "update",
    "P1 vardefine still carries the pre-4/5/2026 value 2.1; P2 table and P3 history both give 1.8, and P3 names 2.1 as the OLD value, which is exactly what P1 and current_db still hold. Textbook vardefine lag. Row is verified:false, so no owner gate.")

rec("electro_giant", "dps", 78, None, None, 91,
    [src("Electro Giant", "{{#vardefine: dmg_11 | 163 }}"),
     src("Electro Giant", "On 4/5/2026 ... decreased the Electro Giant's attack time interval to 1.8 seconds (from 2.1 seconds)")],
    "2of3", "update",
    "Consequential on the hit_speed update: damage 163 (unchanged, P1-confirmed) / 1.8 s = 90.6 -> 91. current_db 78 is 163/2.1 and only stays correct while hit_speed stays 2.1.")

rec("dark_prince", "hit_speed", 1.3, 1.3, 1.4, 1.4,
    [src("Dark Prince", "{{#vardefine: atk_speed | 1.3 }}"),
     src("Dark Prince", "|4||1.4 sec||0.6 sec||Medium (60)||1 sec||Melee: Medium (1.2)||1.1||Ground||x1||Ground||Troop||Epic"),
     src("Dark Prince", "On 4/5/2026, a Balance Update, increased the Dark Prince's Hit Speed to 1.4s (from 1.3s)")],
    "2of3", "update",
    "Same lag pattern as electro_giant, dated the same day. NOTE the 2018 entry ('decreased his attack time interval to 1.3 seconds (from 1.4)') argues for 1.3 and is what P1 still holds -- it is superseded by 4/5/2026. hit_speed is NOT among dark_prince's curated fields, so this is a plain update.")

rec("dark_prince", "dps", 205, None, None, 190,
    [src("Dark Prince", "{{#vardefine: dmg_11 | 266 }}"),
     src("Dark Prince", "On 4/5/2026, a Balance Update, increased the Dark Prince's Hit Speed to 1.4s (from 1.3s)")],
    "2of3", "update",
    "Consequential: damage 266 (P1-confirmed, unchanged) / 1.4 s = 190. current_db 205 is 266/1.3.")

rec("bowler", "projectile_range", 7.5, None, 7.5, 7.0,
    [src("Bowler", "|5||2.5 sec||0.5 sec||Slow (45)||1 sec||4||7.5||3.6||170||Ground||1x||Ground||Troop||Epic"),
     src("Bowler", "On 4/8/2026, a Balance Update, decreased the Bowler's projectile range to 7 tiles (from 7.5 tiles)")],
    "2of3", "update",
    "P2 still prints 7.5, which is precisely the value P3 names as the pre-change one -- the table lags rather than genuinely disagreeing. Attack range 4.0 and projectile width 3.6 both still match.")

rec("executioner", "projectile_range", 7.5, None, 7.5, 7.0,
    [src("Executioner", "|5||0.9 sec||0.5 sec||1.5 sec||Medium (60)||1 sec||4.5||7.5||2||550||Air & Ground||x1||Ground||Troop||Epic"),
     src("Executioner", "On 4/8/2026, a Balance Update, decreased the Executioner's projectile range to 7 tiles (from 7.5 tiles)")],
    "2of3", "update",
    "Same 4/8/2026 update that cut the Bowler's projectile range; P2 still shows the stated old value 7.5.")

rec("furnace", "range_tiles", 6.0, None, 6.0, 5.5,
    [src("Furnace", "|4||1.8 sec||Medium (60)||1 sec||7 sec||6||Air & Ground||1x||Ground||Troop||Rare"),
     src("Furnace", "On 1/6/2026, a Balance Update, decreased the Furnace's range to 5.5 tiles (from 6 tiles)")],
    "2of3", "update",
    "P2 prints 6, the value P3 names as the old one. The Furnace became a walking troop on 4/8/2025, so its attack range is live in the sim.")

rec("furnace", "spawn_interval_s", 7.0, None, 7.0, 5.0,
    [src("Furnace", "|4||1.8 sec||Medium (60)||1 sec||7 sec||6||Air & Ground||1x||Ground||Troop||Rare"),
     src("Furnace", "On 7/8/2025, a maintenance break reduced the Furnace's hitpoints by 19% and increased the spawn time for its Fire Spirits to 7 seconds (from 5 seconds)."),
     src("Furnace", "On 4/8/2026, a Balance Update, decreased the Furnace's spawn duration to 5 seconds (from 7 seconds)")],
    "2of3", "update",
    "Full timeline reconstructed: 5 s (4/4/2023) -> 7 s (7/8/2025) -> 5 s (4/8/2026). Current = 5. IMPORTANT: the curated spawns.interval is ALREADY 5.0 and engine.py reads spawns.interval for spawner_interval, so the sim's behaviour is correct today; spawn_interval_s=7.0 is a STALE DUPLICATE that contradicts it. Update or drop the duplicate so the two cannot drift apart.")

rec("firecracker", "sight", 8.5, None, None, 8.0,
    [src("Firecracker", "On 4/8/2025, the August 2025 Update decreased the Firecrackes's sight range to 8 tiles (from 8.5 tiles) and decreased her recoil range to 1 tile (from 1.5 tiles)")],
    "2of3", "update",
    "current_db 8.5 is exactly the pre-4/8/2025 value P3 names. The same entry's other half (recoil 1 tile) IS already correct in the KB (recoil_tiles=1), which corroborates that this entry was applied only half-way. sight comes from the 2023-frozen mechanics dump, so it could not have picked this up on its own.")

rec("dart_goblin", "speed", "fast", None, "very_fast", None,
    [src("Dart Goblin", "|3||0.8 sec||0.35 sec||Very Fast (120)||1 sec||6.5||800||Air & Ground||x1||Ground||Troop||Rare")],
    "2of3", "update",
    "Categorical label only: P2 says Very Fast (120). current_db speed_tiles=2.0 is already the correct Very-Fast number, so the sim moves him at the right speed; the 'fast' label simply contradicts it. Curated in cards.yaml but the row is verified:false, so no owner gate.")

rec("fire_spirit", "range", "melee", None, "short", None,
    [src("Fire Spirit", "|1||Very Fast (120)||1 sec||2.5||2.3||Air & Ground||x1||Ground||Troop||Common"),
     src("Fire Spirit", "On 4/2/2025, a Balance Update, increased the Fire Spirit's range to 2.5 tiles (from 2 tiles).")],
    "2of3", "update",
    "P2 prints a bare '2.5' with no 'Melee:' prefix, i.e. a ranged attacker. current_db range_tiles=2.5 already matches and WINS in cards.py (a curated range_tiles beats the bucket), so there is no behavioural change today -- but the 'melee' bucket resolves to 1.2 tiles if range_tiles is ever dropped. Row verified:false.")

rec("battle_ram", "spawn_unit_stats.speed_tiles", 2.0, None, 1.0, None,
    [src("Battle Ram", "|1.3 sec||Medium (60)||1 sec||Melee: Short (0.7)||Ground||x2||Ground"),
     src("Barbarians", "|5||1.4 sec||0.4 sec||Medium (60)||1 sec||Melee: Short (0.7)||Ground||x5||Ground||Troop||Common")],
    "2of3", "update",
    "The Battle Ram page's TERTIARY attributes table (its death-spawn Barbarians) gives Medium (60) = 1.0 tiles/s, and the Barbarians card page independently agrees. current_db 2.0 is Very-Fast and looks copied from the ram's CHARGE speed (charge_speed_tiles=2.0; the secondary table reads 'Very Fast (120)'). Cross-page note: the Battle Ram page's own barbarian vardefines (hp 670 / atk 1.3) LAG the Barbarians card page (691 / 1.4) -- the card page is current and current_db barbarians already matches it, so do not re-source barbarians from this page.")

rec("electro_spirit", "projectile_speed", None, None, None, 1000,
    [src("Electro Spirit", "On 1/12/2025, the Heroes Update, decreased the Electro Spirit's projectile speed to 1000 (from 2000), and increased it's Shock Chain Period to 0.25 seconds (from 0.2 seconds)")],
    "2of3", "update",
    "Field absent from the KB row entirely; P3 gives an unambiguous current value. Row verified:false.")

rec("electro_spirit", "chain_period_s", None, None, None, 0.25,
    [src("Electro Spirit", "On 1/12/2025, the Heroes Update ... increased it's Shock Chain Period to 0.25 seconds (from 0.2 seconds)")],
    "2of3", "update",
    "Field absent from the KB row. This is the delay between chain hops; engine.py's _multi_hit currently resolves every hop in the same instant, so there is nothing for the value to drive yet -- record it, then decide whether to model the delay.")

rec("cannon_cart", "building_activation_pct", None, None, 50, 50,
    [src("Cannon Cart", "|50%||0.9 sec||0.5 sec||15 sec||5.5||1000||Ground||x1||Building"),
     src("Cannon Cart", "When its hitpoints are lowered below 50%, it becomes a [[:Category:Building Cards|building]] with a 15-second lifetime.")],
    "2of3", "update",
    "Missing field. P2's secondary table has an explicit 'Activation 50%' column and the prose agrees. lifetime_s=15 is already correct and comes from that same table. NOTE the 5/5/2025 update REMOVED the Cannon Cart's shield hitpoints, so the absence of shield_hp in the KB is correct rather than a gap.")

rec("battle_healer", "heal_per_pulse", None, 25, None, None,
    [src("Battle Healer", "{{#vardefine: heal_11 | 25 }}"),
     src("Battle Healer", "|4 pulses every 1 sec||0.25 sec||3||Friendly Troops")],
    "2of3", "update",
    "The whole heal mechanic is absent from the KB row -- Battle Healer's defining behaviour is unmodelled. P1 heal_11 = 25 per pulse at level 11.")

rec("battle_healer", "heal_interval_s", None, 0.25, 0.25, None,
    [src("Battle Healer", "{{#vardefine: heal_speed | 0.25 }}"),
     src("Battle Healer", "|4 pulses every 1 sec||0.25 sec||3||Friendly Troops")],
    "2of3", "update",
    "P1 and P2 agree: 4 pulses per second, 0.25 s between pulses.")

rec("battle_healer", "heal_radius_tiles", None, None, 3.0, 3.0,
    [src("Battle Healer", "|4 pulses every 1 sec||0.25 sec||3||Friendly Troops"),
     src("Battle Healer", "|4 pulses every 1 sec||0.25|| 2.5||Friendly Troops"),
     src("Battle Healer", "On 4/8/2026, a Balance Update, increased the Battle Healer's damage by 81%, increased her hit speed to 2 seconds (from 1.5 seconds), decreased her heal radius to 3 tiles (from 4 tiles), decreased her heal area to 28.3 square tiles (from 50.3 square tiles)")],
    "2of3", "update",
    "The page carries TWO heal tables that disagree (3 vs 2.5). Resolved by arithmetic rather than majority: pi*3^2 = 28.27 = the stated 28.3 sq tiles, and pi*4^2 = 50.27 = the stated old 50.3 sq tiles. Radius 3 is therefore confirmed twice over and the 2.5 table is stale.")

rec("battle_healer", "spawn_heal", None, 50, None, None,
    [src("Battle Healer", "{{#vardefine: spawn_heal_11 | 50 }}"),
     src("Battle Healer", "On 31/3/2025, the 2025 Quarter 1 Update, increased the Battle Healer's healing by 0.99% and her spawn healing by 0.49%.")],
    "2of3", "update",
    "One-off heal burst on deploy, 50 at level 11; absent from the KB row. P3 confirms spawn healing is a distinct tracked quantity.")

rec("electro_giant", "reflect_damage", 120, 192, 192, None,
    [src("Electro Giant", "{{#vardefine: reflect_11 | 192 }}"),
     src("Electro Giant", "| 11 || {{#var:hp_11}} || {{#var:dmg_11}} || {{Dps|{{#var:dmg_11}}|{{#var:atk_speed}} }} || {{#var:reflect_11}} || {{#var:crown_11}}")],
    "2of3", "update",
    "The level-11 statistics row maps reflect_11 to the 'Reflect Damage' column, so P1 and P2 are the same published number: 192. current_db 120 is 37.5% low. Row verified:false. The Zap Pack radius (3.0) and stun (0.5 s) DO match the secondary table, so only the damage number is wrong.")

# ================= ESCALATIONS: curated verified:true, or a genuine split =================
rec("ghost_souldier", "damage", 261, 81, None, 81,
    [src("Royal Ghost/Evolution", "{{#vardefine: soul_dmg_11 | 81 }}"),
     src("Royal Ghost/Evolution", "{{#vardefine: dmg_11 | 261 }}  (this is the ROYAL GHOST's own damage on the same page)"),
     src("Royal Ghost/Evolution", "On 3/11/25, a balance update decreased the Souldier's damage by 49%."),
     src("Royal Ghost/Evolution", "On 1/12/2025, a Balance Update nerfed the Souldier's melee and spawn damage by 22%."),
     src("Royal Ghost/Evolution", "On 6/4/2026, a Balance Update, decreased the Souldier Spawn Damage by 60% and the souldier damage by 21%")],
    "2of3", "escalate",
    "PARENT-STAT CONTAMINATION. current_db 261 is EXACTLY the Royal Ghost's own dmg_11 on the same page; the Souldier's own vardefine is soul_dmg_11 = 81. Three separate nerfs (3/11/25 -49%, 1/12/25 -22%, 6/4/2026 -21%) cut the Souldier while the parent was untouched, which is how the two came to differ by 3.2x. Every OTHER field on this key correctly reads from the soul_* vardefines (hitpoints 81, hit_speed 1.8, range 1.2, speed 1.5) -- only damage was taken from the parent. Curated verified:true, so escalating rather than auto-writing. This is the exact spawned-unit/parent substitution class the brief warns about.")

rec("electro_wizard", "spawn_damage", 115, 192, 192, None,
    [src("Electro Wizard", "{{#vardefine: zap_11 | 192 }}"),
     src("Electro Wizard", "{{#vardefine: dmg_11 | 115 }}  (the Electro Wizard's own per-bolt damage)"),
     src("Electro Wizard", "| 11 || {{#var:hp_11}} || {{#var:dmg_11}} x{{#var:dmg_hits}} ({{#expr: {{#var:dmg_11}} * {{#var:dmg_hits}} }})|| ... || {{#var:zap_11}}"),
     src("Electro Wizard", "His spawn damage behaves identically to a [[Zap]] of equal Level.")],
    "2of3", "escalate",
    "Same contamination shape as ghost_souldier: current_db spawn_damage 115 is EXACTLY the Electro Wizard's own per-bolt damage on the same page. The level-11 statistics row puts zap_11 under the 'Zap Damage' column = 192, and the prose says the spawn damage behaves as a Zap of equal level. Curated verified:true -> owner batch. spawn_radius_tiles=3.0 and stun 0.5 s DO match the secondary table.")

rec("dark_prince", "charge_splash_radius_tiles", 2.2, None, 1.1, 1.2,
    [src("Dark Prince", "|Very Fast (120)||3||1.1||Ground||Ground   (secondary table: Speed | Charge Range | Splash Radius | Target | Transport)"),
     src("Dark Prince", "On 6/5/2019, a Balance Update, increased his range to 1.25 tiles (from 1.05 tiles) and increased his area radius and charge area radius to 1.25 tiles (from 1 tile)."),
     src("Dark Prince", "On 1/7/2019, the July 2019 Update, decreased the Dark Prince's range to 1.2 tiles (from 1.25 tiles), now classified as Melee: Medium, and decreased his area radius and charge area radius to 1.2 tiles (from 1.25 tiles)."),
     src("Dark Prince", "On 2/9/2019, a Balance Update, decreased the Dark Prince's area radius to 1.1 tiles (from 1.2 tiles).")],
    "split", "escalate",
    "current_db 2.2 is roughly double every published figure. P2's charge Splash Radius column reads 1.1; the history walk lands at 1.2, because the 2/9/2019 cut to 1.1 names only the plain 'area radius' and not the charge one. Behaviourally live: engine.py reads charge_splash_radius_tiles directly, so the charge splash is about 2x too wide. Curated verified:true -> escalate. The two paths differ (1.1 vs 1.2) so the owner should pick; either way 2.2 is unsupported by any path.")

rec("dark_prince", "splash_radius_tiles", 1.25, None, 1.1, 1.1,
    [src("Dark Prince", "|4||1.4 sec||0.6 sec||Medium (60)||1 sec||Melee: Medium (1.2)||1.1||Ground||x1||Ground||Troop||Epic"),
     src("Dark Prince", "On 2/9/2019, a Balance Update, decreased the Dark Prince's area radius to 1.1 tiles (from 1.2 tiles).")],
    "3of3", "escalate",
    "P2 and P3 both give 1.1. 1.25 is the value set on 6/5/2019 and superseded twice since (1/7/2019 -> 1.2, 2/9/2019 -> 1.1). Behaviourally live and worse than it looks: engine.py takes splash_radius_tiles in PREFERENCE to splash_radius, and this row's own splash_radius field is already the correct 1.1 -- so the stale curated field is shadowing a correct one sitting right beside it. Curated verified:true -> escalate.")

rec("fisherman", "slow_duration_s", 1.5, None, 1.5, "removed",
    [src("Fisherman", "It spawns a single-target, ground-targeting, melee, ground troop ... and slow their movement and attack speed by 35% for 1.5 seconds.  (INTRO PROSE, line 7)"),
     src("Fisherman", "On 8/1/2025, a Balance Update, decreased the Fisherman's slow duration to 1.5 seconds (from 2.5 seconds)."),
     src("Fisherman", "On 6/10/2025, a Balance Update decreased the slowdown effect to -30% (from -35%)."),
     src("Fisherman", "On 6/4/2026, a Balance Update, removed the FIsherman's slowdown effect entirely   (history line 180, no trailing period)")],
    "split", "escalate",
    "The 6/4/2026 entry removes the slow outright, but THE PAGE CONTRADICTS ITSELF THREE WAYS: the intro prose still describes 'slow their movement and attack speed by 35% for 1.5 seconds' (a pre-6/10/2025 strength), the 6/10/2025 entry says -30%, and the 6/4/2026 entry says removed entirely. current_db 1.5 / -30 is exactly the 6/10/2025 state, i.e. the KB tracked the first two changes and missed the third. Behaviourally live: engine.py sets slows=True from EITHER the flag or a non-zero slow_duration_s/slow_pct, so the sim still applies a slow the game may no longer have. Curated verified:true and the page is self-inconsistent -> escalate as one bundle with slow_pct and the flags:[slow] entry; do not strip the slow on the strength of a single unpunctuated history line.")

rec("fisherman", "slow_pct", -30, None, -35, "removed",
    [src("Fisherman", "... slow their movement and attack speed by 35% for 1.5 seconds.  (INTRO PROSE -- still the pre-6/10/2025 strength)"),
     src("Fisherman", "On 6/10/2025, a Balance Update decreased the slowdown effect to -30% (from -35%)."),
     src("Fisherman", "On 6/4/2026, a Balance Update, removed the FIsherman's slowdown effect entirely")],
    "split", "escalate",
    "Three different published answers for one field: prose 35%, history -30% (6/10/2025), history removed (6/4/2026). Pairs with slow_duration_s above -- removing either alone still leaves engine.py's slows= test true, so flag, duration and pct must move together. The hook itself is unaffected and fully matches on every path: hook_time 1.3 s, hook range 3.5-7 tiles, hook speed 800 game-units = 13.33 tiles/s.")

rec("bomber", "rarity", "rare", None, "common", "common",
    [src("Bomber", "|2||1.8 sec||0.2 sec||Medium (60)||1 sec||4.5||1.5||400||Ground||x1||Ground||Troop||{{Rarity|Common}}"),
     src("Bomber", "The Bomber is a {{Rarity|Common}} [[Cards|card]] that is unlocked from the [[Arenas|Bone Pit (Arena 2)]].")],
    "3of3", "escalate",
    "Two independent places on the page (attributes table and intro prose) say Common; current_db says rare. The Bomber has been a Common since release and the history section shows no rarity change ever. Curated verified:true -> escalate. Not cosmetic: rarity drives level scaling and the rarity floors used elsewhere in this audit.")

rec("bush_goblin", "damage", 227, 256, None, None,
    [src("Suspicious Bush", "{{#vardefine: dmg_11 | 256 }}"),
     src("Suspicious Bush", "On 9/4/2025, a Balance Update, increased the Bush Goblins' damage by 12%."),
     src("Suspicious Bush", "On 4/8/2026, a Balance Update, increased the Bush Goblins' hitpoints by 11%")],
    "2of3", "escalate",
    "227 * 1.12 = 254.2 and the page's current vardefine is 256, so current_db looks like the pre-9/4/2025 value. Confirmed this is the right vardefine for this key: on this page bush_hp_11=81 is the Suspicious Bush itself and hp_11/dmg_11/atk_speed are the Bush Goblin's. hitpoints 304 and hit_speed 1.4 both MATCH. Curated verified:true -> escalate.")

rec("bush_goblin", "deploy_time", 0.2, None, 1.0, None,
    [src("Suspicious Bush", "|1.4 sec||Medium (60)||1 sec||Melee: Short (0.8)||Ground||x2||Ground   (unit-attributes-table-secondary = the Bush Goblin)")],
    "2of3", "escalate",
    "P2's SECONDARY table -- the Bush Goblin's own row -- says 1 sec. Curated verified:true -> escalate. See the ghost_souldier/deploy_time line: these two keys hold each other's published values (0.2 here where the wiki says 1.0; 1.0 there where the wiki says 0.2), which reads like a single transposition at curation time rather than two independent errors. TRAP AVOIDED: the PRIMARY table on this page describes the Bush (range 0.5, Target Buildings) and the 6/4/2026 'Bush range to 1.6 tiles' entry refers to that Bush, NOT to this key -- range 0.8 here is correct, and count=1 is correct because suspicious_bush carries spawns.on_death=2.")

rec("ghost_souldier", "deploy_time", 1.0, None, 0.2, None,
    [src("Royal Ghost/Evolution", "|1.8 sec||0.6 sec||Fast (90)||0.2 sec||1.8 sec||Melee: Medium (1.2)||Ground||x2||Ground   (third table = the Souldier)")],
    "2of3", "escalate",
    "The Souldier's own attributes table says 0.2 sec; current_db says 1.0. Mirror image of bush_goblin/deploy_time -- see that line. Curated verified:true -> escalate.")

rec("ghost_souldier", "invisibility_time_s", 1.8, None, 1.8, 2.0,
    [src("Royal Ghost/Evolution", "|1.8 sec||0.6 sec||Fast (90)||0.2 sec||1.8 sec||Melee: Medium (1.2)||Ground||x2||Ground"),
     src("Royal Ghost/Evolution", "On 2/3/2026, a Balance Update, decreased the Evolved Royal Ghost's invisibility delay to 2 seconds (from 1.8 seconds).")],
    "split", "escalate",
    "Genuine split. P2 (both the parent table and the Souldier table) says 1.8; P3 says 2. The P3 wording is self-contradictory -- 'decreased ... to 2 seconds (from 1.8)' is an increase -- so I will not derive a value from it. It also attributes the change to the Evolved Royal Ghost, which may not govern the Souldier's own invisibility. Raw strings supplied; owner call.")

rec("ghost_souldier", "spawn_damage", None, 81, None, None,
    [src("Royal Ghost/Evolution", "{{#vardefine: spawn_11 | 81 }}"),
     src("Royal Ghost/Evolution", "On 6/4/2026, a Balance Update, decreased the Souldier Spawn Damage by 60% and the souldier damage by 21%")],
    "2of3", "escalate",
    "Missing field: the Souldier deals a spawn burst (spawn_11 = 81 at level 11) that the KB does not carry at all, and P3 confirms it is a separately tracked quantity. Curated row is verified:true, so flagging rather than writing.")

rec("decoy_goblin", "deploy_time", 1.0, None, 1.1, None,
    [src("Goblin Barrel/Evolution", "|1.1 sec||Very Fast (120)||1.1 sec||Melee: Short (0.5)||Ground||x3||Ground")],
    "2of3", "escalate",
    "Small but real: P2 gives 1.1 s. Everything else on this key matches exactly -- its own de_* vardefines (hitpoints 81, damage 89, hit_speed 1.1) and the table (range 0.5, speed Very Fast = 2.0). Curated verified:true -> escalate.")

rec("balloon", "knockback_tiles", 1.0, None, None, None,
    [src("Balloon", "|5||2 sec||0.2 sec||Medium (60)||1 sec||Melee: Short (0.1)||Buildings||x1||Air||Troop||Epic"),
     src("Balloon", "|3||3 sec||Air & Ground   (second table: Death Damage Splash Radius | Deploy Time | Target)")],
    "split", "escalate",
    "NULL ON ALL THREE PATHS. Neither attributes table has a knockback/pushback column, no vardefine carries one, and no history entry on the page mentions knockback or pushback for the Balloon at all -- its death bomb deals damage, not displacement. current_db asserts 1.0 tiles with no traceable source. Curated verified:true -> escalate for removal, or for the owner to name the source. Everything else on this key matches: death_damage 240 (death_11), death_radius_tiles 3 and death_delay_s 3 (second table).")

rec("bats", "hit_speed", 1.3, 1.3, 1.3, 1.2,
    [src("Bats", "{{#vardefine: atk_speed | 1.3 }}"),
     src("Bats", "|2||1.3 sec||0.6 sec||Very Fast (120)||1 sec||Melee: Medium (1.2)||Air & Ground||x5||Air||Troop||Common"),
     src("Bats", "On 2/3/2026, a Balance Update, decreased the Bats' hitpoints to 1.2 seconds (from 1.3 seconds).")],
    "split", "escalate",
    "P1 and P2 both say 1.3 and agree with current_db, but the 2/3/2026 entry is garbled: it says 'hitpoints' while quoting SECONDS and naming exactly the 1.3 that atk_speed holds, so it is very likely a hit-speed buff to 1.2 that neither the table nor the vardefine picked up. I am NOT updating on a mis-worded entry. If it is real, hit_speed 1.2 and dps 68 (81/1.2) follow. hitpoints 81 is unchanged on every path either way.")

rec("furnace", "hit_speed", 1.8, 1.8, 1.8, 1.7,
    [src("Furnace", "{{#vardefine: atk_speed | 1.8 }}"),
     src("Furnace", "|4||1.8 sec||Medium (60)||1 sec||7 sec||6||Air & Ground||1x||Ground||Troop||Rare"),
     src("Furnace", "On 12/1/2026, a Balance Update increased Furnace's attack speed to 1.7 (from 1.8)")],
    "split", "escalate",
    "P1 and P2 agree with current_db at 1.8; only P3 says 1.7. I treated the Bowler/Executioner/Furnace-range cases as updates because there the table printed exactly the old value a LATER dated entry moved -- the same reasoning would apply here, but this page's table is demonstrably stale in BOTH of its other 2026 entries (range and spawn interval), so I cannot use table agreement as evidence of currency for one field while calling it stale for two others on the same page. Escalating rather than guessing. If 1.7 is real, dps becomes 105 (179/1.7).")

rec("firecracker", "projectile_speed", 550.0, None, 550, 500,
    [src("Firecracker", "|3||3 sec||0.65 sec||Fast (90)||1 sec||6||11||0.4||550||Air & Ground||x1||Ground||Troop||Common"),
     src("Firecracker", "On 6/4/2026, a Balance Update, increased her projectile speed to 500 (from 400)")],
    "split", "escalate",
    "P2 says 550 and agrees with current_db; P3 says the value became 500 from 400 -- and 400 is not what the table held either, so these paths do not merely lag one another, they disagree about the whole series. No majority. Escalating with both raw strings rather than picking. Everything else on this key matches: projectile_range 11, projectile_radius 0.4, hits_per_attack 5, recoil_tiles 1 (the 4/8/2025 recoil change IS applied).")

rec("furnace", "lifetime_s", 28.0, None, None, 28.0,
    [src("Furnace", "|4||1.8 sec||Medium (60)||1 sec||7 sec||6||Air & Ground||1x||Ground||Troop||Rare   (no Lifetime column)"),
     src("Furnace", "On 4/4/2023, a Balance Update, decreased the Furnace's spawn time interval to 5 seconds (from 6 seconds), and its lifetime to 28 seconds (from 33 seconds)."),
     src("Furnace", "On 4/8/2025, the August 2025 Update changed the Furnace into a troop that can walk and deal damage, as well as increasing the hitpoints by 5%, and removing the death spawn.")],
    "split", "escalate",
    "28 s is correct as of 4/4/2023 and current_db matches it, but on 4/8/2025 the Furnace stopped being a building and became a walking troop, and the attributes table no longer prints a Lifetime column at all. Whether a lifetime still applies is unresolved on every path, so I am flagging rather than asserting either way. Related and already correct: kind=troop in the KB matches that same entry, and speed Medium=1.0 matches the 6/10/2025 speed buff.")

rec("electro_giant", "crown_tower_damage", None, 97, None, None,
    [src("Electro Giant", "{{#vardefine: crown_11 | 97 }}"),
     src("Electro Giant", "| 11 || {{#var:hp_11}} || {{#var:dmg_11}} || {{Dps|{{#var:dmg_11}}|{{#var:atk_speed}} }} || {{#var:reflect_11}} || {{#var:crown_11}}"),
     src("Electro Giant", "On 4/5/2026, a Balance Update, ... but also decreased his reflected tower damage by 24%.")],
    "2of3", "escalate",
    "Missing field: the Zap Pack's reflected damage to crown towers (crown_11 = 97) has no KB counterpart. Deliberately NOT proposing a write -- the brief pins the crown-tower damage family as re-curated post-1/6/2026, and the 4/5/2026 entry moved this number again, so it belongs in the owner's pinned batch rather than an auto-update.")

rec("electro_dragon", "chain_range_tiles", 3.0, None, 4.0, None,
    [src("Electro Dragon", "The Electro Dragon launches an attack that hits its target, which will arc and strike up to 2 other targets within 4 tiles of each other."),
     src("Electro Dragon", "The Electro Dragon has a chain lightning attack wherein each attack that the Dragon fires has the ability to spread out to a maximum of 2 other nearby targets.")],
    "2of3", "escalate",
    "The sim uses a GLOBAL constant _CHAIN_TILES = 3.0 (engine.py), whose comment states the arc range is 'not published by the wiki'. That premise is FALSE: this page publishes 4 tiles, and the Electro Spirit page independently publishes 4 tiles as well. Escalating rather than updating because it is one shared constant, not a per-card KB field -- moving it changes every chain card at once, and the brief notes the evo Electro Dragon's comment says 3.5. Target count is already correct: 1 + 2 others = 3 = hits_per_attack.")

rec("electro_spirit", "chain_range_tiles", 3.0, None, 4.0, None,
    [src("Electro Spirit", "If it jumps onto a unit, its attack will arc and strike up to 8 other targets within 4 tiles of each other."),
     src("Electro Spirit", "{{Quote|Jumps on enemies, dealing Area Damage and stunning up to 9 enemy Troops.")],
    "2of3", "escalate",
    "A second, independent page giving the same 4-tile arc, which is what makes the engine comment's 'not published by the wiki' claim clearly wrong. Pairs with the electro_dragon line -- one shared constant, one decision. Target count IS correct: 8 others plus the jumped-on unit = 9 = hits_per_attack.")

# ================= PARENT EVOLUTION GATE (10 keys) =================
EVO = [("baby_dragon", 2, True), ("barbarians", 1, False), ("bats", 2, False), ("battle_ram", 2, True),
       ("bomber", 2, True), ("dart_goblin", 2, False), ("electro_dragon", 1, True),
       ("executioner", 1, True), ("firecracker", 2, True), ("furnace", 2, True)]
for k, cyc, is_verified in EVO:
    rec(k, "evolution.available", None, None, True, True,
        [src(PG[k], "{{SubpageNavBox|Evolution=yes|...}} -- the card page advertises an Evolution subpage"),
         src(PG[k], "Cycles column on %s/Evolution = %d; DB %s_evo.evo_cycles = %d (they already agree)" % (PG[k], cyc, k, cyc))],
        "2of3", "escalate" if is_verified else "update",
        "SYSTEMIC GATE BUG -- 10 of my 32 keys. The parent row has evolution:null while a fully populated %s_evo row exists carrying the correct evo_cycles=%d. cards.py evo_cycles() short-circuits on the PARENT's evolution.available and returns 0, documented as 'never evolves', so the evo row's cycles is unreachable through that path and these cards read as non-evolving. archers is the only key in this group whose parent field IS populated, which is what makes the inconsistency visible at all. The cycles value itself needs no research: wiki and DB already agree at %d. Note sim/opponents.py takes a different route (it builds '<key>_evo' directly and defaults cycles to 2), so the opponent still evolves -- the two code paths disagree with each other, which is the real hazard." % (k, cyc, cyc))

# ================= verified:false row audits (priority flag) =================
CLEAN = {
 "berserker": "hitpoints 896, damage 102, hit_speed 0.6 (P1+P2, and the 6/10/2025 entry sets 0.6 explicitly), dps 170, range 0.8, speed Fast=1.5, elixir 2, rarity Common, deploy 1 s -- every wiki-checkable field matches. No mechanics-dump entry exists for this card (added 3/2/2025), which correctly explains its absent load_time_s/sight/collision/mass.",
 "elite_barbarians": "hitpoints 1341, damage 384, hit_speed 1.4, dps 274, count x2, range 1.2, speed Fast=1.5, elixir 6, rarity Common -- all match; the page has no 2025 or 2026 history entries at all.",
 "flying_machine": "hitpoints 614, damage 171, hit_speed 1.1, dps 155, range 6, projectile speed 800, speed Fast=1.5, elixir 4, rarity Rare -- all match; no 2025/2026 history entries.",
 "barbarians": "hitpoints 691, damage 191, hit_speed 1.4 (the 2/3/2026 entry sets 1.4), dps 136, count x5, range 0.7, speed Medium=1.0, elixir 5, rarity Common -- all match. Only nit: load_time_s 0.9 no longer satisfies the first-hit identity because it is frozen-2023 data predating the 2026 hit-speed change.",
 "bowler": "hitpoints 2081, damage 289, hit_speed 2.5, dps 116, attack range 4, projectile width 3.6, projectile speed 170, speed Slow=0.75, elixir 5, rarity Epic, knockback_immune -- all match; only projectile_range is stale (separate line).",
 "cannon_cart": "hitpoints 1809, damage 212, hit_speed 0.9, dps 236, range 5.5, projectile speed 1000, lifetime 15 s, elixir 5, rarity Epic -- all match; only the 50% activation field is missing (separate line). The absence of shield_hp is CORRECT: 5/5/2025 removed the shield.",
 "electro_spirit": "hitpoints 215 (the 4/8/2026 -6% is applied), damage 99, range 2.5, speed Very Fast=2.0, elixir 1, rarity Common, stun 0.5 s, hits_per_attack 9 (page: 8 others plus the jumped-on unit) -- all match.",
 "battle_healer": "hitpoints 1920, damage 268, hit_speed 2.0, dps 134, range 1.6, speed Medium=1.0, elixir 4, rarity Rare -- all match, and the 4/8/2026 damage +81% and hit-speed-2s changes are both already applied. The heal mechanic is missing entirely (four separate lines).",
 "dart_goblin": "hitpoints 261, damage 156, hit_speed 0.8 (the 4/8/2025 entry sets 0.8), dps 195, range 6.5, projectile speed 800, sight 7.5 (the 2/3/2026 entry sets 7.5), elixir 3, rarity Rare -- all match; only the speed label is wrong (separate line).",
 "fire_spirit": "hitpoints 215 (the 4/8/2026 -6% is applied), damage 207, range 2.5 (4/2/2025), splash radius 2.3, speed Very Fast=2.0, elixir 1, rarity Common, kamikaze -- all match; only the range bucket label (separate line). NOTE the Furnace page's fire_hp_11=230 is STALE; the Fire Spirit card page's 215 is current and the KB already uses the right one.",
 "electro_giant": "hitpoints 3952 (the 6/7/2026 +3% is applied), damage 163, range 1.2, speed Slow=0.75, elixir 7, rarity Epic, reflect radius 3.0, reflect stun 0.5 s, knockback_immune -- these match. hit_speed, dps, reflect_damage and the missing crown figure are separate lines.",
 "bats": "hitpoints 81, damage 81, dps 62, count x5, range 1.2, speed Very Fast=2.0, elixir 2, rarity Common -- all match; hit_speed is the one open item (separate line).",
}
for k, note in CLEAN.items():
    rec(k, "_row_audit:verified_false", False, None, None, None,
        [src(PG[k], "row carries verified:false in icebow/config/cards.yaml; re-sourced against all three paths on " + F)],
        "3of3", "escalate",
        "PRIORITY FLAG (verified:false row), not a discrepancy in itself. Re-sourced today: " + note + " Recommend flipping verified:true once the linked open items (if any) are settled.")

out = os.path.join(L, "r2_troops_a.jsonl")
with open(out, "w", encoding="utf-8") as fh:
    for r in R:
        fh.write(json.dumps(r, ensure_ascii=False) + "\n")
print("wrote", out, len(R), "lines")
from collections import Counter
print(Counter(r["verdict"] for r in R))
print("keys touched:", len(set(r["key"] for r in R)))
