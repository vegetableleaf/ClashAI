# R2 — Owner Decision Sheet

**316 escalations from the sim-parity stat sweep, grouped into 14 decisions.**
Generated 2026-08-26 from `ledger/stat_diffs.jsonl` (179 keys, 3,321 fields checked, 2,838 matched).

Nothing has been changed in the sim. Tick a decision and I apply that whole group in Phase I.

---

## Decision summary

| # | Decision | Rows | My recommendation |
|---|---|---|---|
| 1 | Fields the wiki publishes that the sim leaves EMPTY | 110 | Apply all as additions. |
| 2 | The wiki's stat block LAGS the wiki's own balance history | 77 | Apply all; they are what the third extraction path exists to catch. |
| 3 | Crown-tower damage still stale after the 1/6/2026 sweep | 15 | Apply all, AND fix the audit tool's regex. |
| 4 | The sim holds the PARENT's or SPAWNED unit's stat instead of the card's own | 7 | Apply all — these are unambiguous mix-ups. |
| 5 | Rows YOU marked verified:true that the sources contradict | 19 | Read each one — your ruling outranks the wiki, but these look like real errors. |
| 6 | One shared constant, not a per-card field | 6 | One ruling sets it for every chain card. |
| 7 | floor() vs round() convention on derived DPS | 10 | One ruling covers all of them: adopt the wiki's floor(). |
| 8 | The data is agreed; the decision is a SCHEMA or ENGINE change | 6 | Defer to Phase I implementation — no data decision needed now. |
| 9 | The wiki page contradicts ITSELF | 6 | Review — or settle by checking in-game. |
| 10 | Sources genuinely disagree and no 2-of-3 majority formed | 22 | Review individually — these are the only ones that truly need your judgement. |
| 11 | No source publishes the value ANYWHERE | 21 | Keep the sim's current value, mark it `unsourced: true`, and measure in-game when convenient. |
| 12 | Two sweep agents claimed the same field and disagreed | 13 | Apply the merge's pick (more sources wins); listed here for transparency. |
| 13 | Field-name collisions / snapshot hygiene | 2 | Cosmetic; apply with the rest. |
| 14 | Uncategorised leftovers | 2 | Review individually. |

Decisions 1-4, 7, 8 and 13 are bulk 'yes/no'. Decisions 5, 10, 11 and 14 need row-by-row reading;
that is **49 rows total**, not 316.

---

## 1. Fields the wiki publishes that the sim leaves EMPTY

**Rows:** 110  |  **Recommendation:** Apply all as additions.

These are gaps, not conflicts: the sim has no value at all, so nothing owner-verified is being overwritten. Filling them can only move the sim toward the real game. A few are big (three_musketeers has no damage; inferno_tower has no `attacks`).

- [ ] Accept recommendation for all 110
- [ ] I want to go row by row

<sub>families: evos_b 33, champions 23, evos_a 17, troops_a 8, troops_b 8, spells 8, troops_c 7, buildings 6</sub>

| card | field | sim has | wiki says | why |
|---|---|---|---|---|
| `barbarian_hut` | spawn_delay_s | None | 0.5 | PRIORITY/gap: field absent from the KB row. The intra-wave stagger is published in prose only (this page's attribute table has no Spawn Delay column, ... |
| `bomb_tower` | death_damage_targets | None | Air & Ground | PRIORITY/gap: the KB row carries death_damage 222 / death_radius_tiles 3.0 / death_delay_s 3.0 but no target spec, while attacks:[ground] describes on... |
| `cannon` | load_time_s | None | 0.9 | PRIORITY/gap: field absent from the KB row while every other turret building in the group carries it. The table says 1.0; the last dated history entry... |
| `inferno_tower` | charge_time_s | None | 2.0 | PRIORITY/gap: the row has damage_stages [43, 158, 847] but nothing saying how long each stage takes, so the sim cannot model the ramp or a stun/shield... |
| `x_bow` | projectile_speed | None | - | Null on all three paths: this page's attribute table has no Projectile Speed column and there is no vardefine for it, so the 4/8/2026 '+14% projectile... |
| `x_bow` | load_time_s | None | 0.4 | PRIORITY/gap: field absent from the KB row. The table publishes First Hit Speed 0.3, but that cell is part of the same stale pre-4/8/2026 row as Hit S... |
| `archer_queen` | ability_attack_speed_boost | None | On 4/4/2022, decreased the Cloaking Cape's attack speed buff to 180% (from 200%). | conflicts.md C8 open item, now narrowed: history ("to 180% from 200%") and prose ("80% increase") BOTH describe a x1.8 multiplier -> hit speed 1.2/1.8... |
| `archer_queen` | ability_cast_time_s | None | none | conflicts.md C7 boilerplate, reconfirmed live on all 8 champion pages: prose 1 s delay vs table Cast Time 0.933 / 0.944 / 0.766. Engine needs one conv... |
| `boss_bandit` | leap_invulnerable | None | 8/7/2025 and 12/1/2026 entries do not touch dash invulnerability | CURATED COMMENT IS CONTRADICTED BY THE LIVE PAGE. icebow/config/cards.yaml (boss_bandit block) states: "NOTE she is NOT described as immune during it ... |
| `boss_bandit` | ability_delay_s | None | no entry | C7 again. The sim gives mighty_miner ability_delay_s 1.0 but boss_bandit no delay field at all, so her grenade resolves instantly in-engine. Also load... |
| `goblinstein` | lightning_link_damage | None | 4/8/2026 Ability DPS -12% -> 107/0.5 = 214 dps -> 188.32 -> damage 94.16 -> 94 | KB row carries NO lightning-link damage field at all. Two unresolved layers: (a) 107 is pre-4/8/2026 (same lag proof as the Doctor row); (b) the note ... |
| `goblinstein` | ability_radius_tiles | None | none | Value is published (2 tiles) but conflicts.md C8 geometry is still unresolved: 2 tiles measured from the Doctor, from the Monster, or from the line be... |
| `golden_knight` | ability_dash_travel_speed | None | not published | NULL on all three paths -> escalate per the missing-value rule. Confirms decisions.md ruling 10 amendment. The placeholder analog is 500 speed units (... |
| `golden_knight` | ability_dash_delay_s | None | On 3/11/2025, a Balance Update, decreased Dashing Dash Delay to 0.05 seconds (from 0.2 seconds). | decisions.md ruling 10 amendment calls this "defined nowhere". Its VALUE and lineage are now sourced (0.2 -> 0.05 on 3/11/2025) but its SEMANTICS are ... |
| `golden_knight` | ability_cast_time_s | None | none | C7. Note GK's 0.766 differs from the 0.933 used by five of the other champions and 0.944 for Little Prince, so this is not pure boilerplate. |
| `little_prince` | guardienne damage (spawn_unit_stats) | None | 3/6/2025 +1%; 3/11/2025 +7%; 4/8/2026 Guardian Melee Damage +7% -> 217 x 1.07 = 232.19 -> 232 | TWO defects in one field. (a) spawn_unit_stats carries only hit_speed/range_tiles/speed_tiles -- the Guardienne has NO damage and NO hitpoints in the ... |
| `little_prince` | guardienne hitpoints (spawn_unit_stats) | None | 3/1/2024 decreased the Guardienne's hitpoints by 11%; no change on 4/8/2026 | Missing from spawn_unit_stats. 1600 is NOT affected by the 4/8/2026 note (damage only), so it is current as published. |
| `little_prince` | royal_rescue_dash_range_tiles | None | 13/11/2023 decreased the Royal Rescue's dash range to 4.5 tiles (from 5 tiles) -- last dated entry | Table (4) and strategy prose (4) agree against the newest dated history entry (4.5). Unlike the other lag cases the history is here the OLDER reading,... |
| `little_prince` | ability_cost | None | none | KB row has no ability block. Note this is the most expensive champion ability in the group (3 elixir on a 3-elixir card). |
| `little_prince` | ability_uses | None | 4/8/2026 single use (page History + master log) | verified:true row. |
| `little_prince` | guardienne deploy_time_s | None | none | Missing from spawn_unit_stats. |
| `little_prince` | guardienne first_hit_speed_s | None | 17/6/2024 increased Guardienne's first attack time interval to 0.5 seconds (from 0.2 seconds) |  |
| `little_prince` | first_hit_speed_s | None | none | KB row lacks the field; verified:true row so not an auto-update. load_time_s/mass/sight/collision do NOT come from the wiki: import_mechanics.py reads... |
| `little_prince` | ability_cast_time_s | None | none | C7. |
| `mighty_miner` | ability_cast_time_s | None | none | C7. Mighty Miner is the one in-group card where the KB already picks a convention (ability_delay_s 1.0 = the prose/Deploy Time reading), so whichever ... |
| `monk` | combo_damage | None | On 17/6/2024, increased the Monk's combo damage by 0.47%. It also fixed certain issues with damage multipliers on the Monk. | conflicts.md C3 CONFIRMED: the value IS published (422 @L11) and the cards.yaml comment "The 3rd hit's EXTRA DAMAGE is not published, so only the shov... |
| `monk` | ability_tornado_immune | None | 12/12/2025 blanket knockback immunity does not mention Tornado | Tornado-pull immunity is stated ONLY as ability-scoped, while knockback immunity has since become permanent (12/12/2025). Whether the pull immunity fo... |
| `monk` | ability_cast_time_s | None | none | C7. |
| `skeleton_king` | ability_cast_time_s | None | none | C7. |
| `baby_dragon_evo` | aura_linger_after_death_s | None | 2.0 | MISSING FIELD: the KB row has no post-death aura lifetime. Wiki prose says the wind persists ~2 s after the Evo Baby Dragon dies (prose hedges with 'a... |
| `battle_ram_evo` | charge_pushback_damage | None | 212 | MISSING FIELD. The Evo Battle Ram damages everything it ploughs through on the way to its target -- 212 at level 11, published as its own vardefine wi... |
| `battle_ram_evo` | self_pushback_tiles | None | 2.0 | MISSING FIELD: `ram_bounce` is a bare boolean; the wiki publishes the bounce distance (2 tiles), which sets the re-ram period together with the 2.0-ti... |
| `battle_ram_evo` | hit_speed | None | - | PRIORITY FLAG from the brief (evo rows missing hit_speed) -- RESOLVED AS GENUINELY UNPUBLISHED. Neither the Evo page nor the base page publishes a hit... |
| `bomber_evo` | bounce_no_repeat_target | None | True | MISSING FIELD (flag, not a number). Since 16/12/2024 a unit inside two overlapping bounce radii takes the 225 ONCE, not twice. The KB carries bounces:... |
| `cannon_evo` | volley_radius_tiles | None | 2.0 | MISSING FIELD. The KB has deploy_volley 9 / volley_damage 304 / volley_crown_damage 89 but no splash radius for the barrage, even though the wiki publ... |
| `dart_goblin_evo` | poison_stage_thresholds | None | [1, 4, 7] | MISSING FIELD, AND THE CURATED MODEL IS WRONG IN KIND. cards.yaml says the poison 'becomes stronger the longer the Dart Goblin remains alive' and gues... |
| `dart_goblin_evo` | poison_radius_tiles | None | 1.5 | MISSING FIELD: the poison is an AREA effect with a published 1.5-tile radius; the KB models poison_dps/poison_stages with no radius, so the sim curren... |
| `elite_barbarians_evo` | javelin_trigger_band_tiles | None | [3.5, 5.0] | MISSING FIELD, newly available. The KB has a cooldown but no throw condition, so the sim has no rule for when a spear is released. The Card Evolution ... |
| `elite_barbarians_evo` | javelin_rage_trail | None | rage trail: boosts movement AND attack speed | MISSING FIELD and NO NUMBERS ANYWHERE. The rage trail is confirmed to exist and to boost both movement and attack speed, but no source publishes its m... |
| `executioner_evo` | smash_damage | None | 241 | MISSING FIELD: the KB models the smash's range and knockback but not its damage, which is the whole point of the ability (the axe hits for close_11 in... |
| `giant_snowball_evo` | roll_speed | None | 300 | MISSING FIELD. The KB has carry_roll/roll_tiles but no roll SPEED, so the sim has no duration for the pull. 300 in wiki speed units is 5.0 tiles/s on ... |
| `goblin_cage_evo` | ability_cooldown_s | None | 0.3 | MISSING FIELD: the re-grab cooldown between one troop being released and the next being pulled in. The KB models hook_time_s 1.2 / hook_speed_tiles 8.... |
| `goblin_drill_evo` | relocate_thresholds | None | [0.66, 0.33] | MISSING FIELDS behind a bare boolean. `drill_relocate: true` carries none of the mechanism: the two hp thresholds (66%, 33%), the goblin counts per su... |
| `goblin_giant_evo` | backpack_spear_goblins | None | 1.6 | MISSING SUB-UNIT (extracted from the Spear Goblin attributes tables on Goblin Giant/Evolution). The Evo row's spawn_unit_stats describes the low-hp Go... |
| `goblin_giant_evo` | low_hp_spawn_offset_tiles | None | 2.5 | MISSING FIELD, minor but concrete: the trickle of Goblins appears 2.5 tiles BEHIND the Giant, not at his feet, so they arrive at a defender later than... |
| `ice_spirit_evo` | blast_repeat_delay_s | None | 3.0 | MISSING FIELD, AND IT IS THE WHOLE EVOLUTION. The Evo Ice Spirit hits TWICE: the initial 110 damage + 1.1 s freeze, then a SECOND identical 110 damage... |
| `mega_knight_evo` | uppercut_every_hits | None | 4/8/2026 Balance Update: 'the Evolved Mega Knight knocks back troops every 2 hits instead of every hit', and large-troop knockback restored to 4 tiles (2.5 between 1/6/2026 and 4/8/2026) | P3 catch: curation (2026-08-14 sweep) modeled the uppercut on EVERY attack; since 4/8/2026 it fires every 2nd hit. uppercut_tiles 4.0 itself is curren... |
| `minion_horde_evo` | evo_cycles | None | Evolved_Card_Infobox CycleCost=1 | PRIORITY null field. Infobox-only source (page is a stub; no vardefines, no attribute tables). Proposed evo_cycles=1; row curated verified:true -> own... |
| `minion_horde_evo` | hitpoints | None | - | PRIORITY null-hitpoint row. Null on all three paths -- wiki stub publishes no stats. Base minion_horde carries 230; the evo quote implies same minions... |
| `minion_horde_evo` | damage | None | - | Null on all paths (base minion_horde: 107). |
| `minion_horde_evo` | hit_speed | None | - | PRIORITY missing-hit_speed row. Null on all paths (base: 1.2). NB the 4/8/2026 invisible hit-speed multiplier makes the effective value phase-dependen... |
| `minion_horde_evo` | dps | None | - | Null on all paths (base: 89). |
| `minion_horde_evo` | count | None | - | Null on all paths (base: 6). |
| `minion_horde_evo` | range_tiles | None | - | Null on all paths (base: 2.5). |
| `minion_horde_evo` | speed_tiles | None | - | Null on all paths (base: 1.5, Fast). |
| `minion_horde_evo` | invisible_hit_speed_mult | None | 4/8/2026 Balance Update: 'increased the Evolved Minion Horde's invisible hit speed multiplier to x0.67 (from x0.5)' | P3-only mechanic the sim does not model: during the invincibility veil a hit-speed multiplier (now x0.67) applies. Direction of the multiplier (attack... |
| `mortar_evo` | spawn_goblin_deploy_time_s | None | 1/6/2026 Balance Update 'increased the Evolved Mortar's Goblin Deploy Time to 0.5 seconds (from 0.2 seconds)' -- postdates the table | Sim's spawn_unit_stats (hit_speed/range/speed) has no deploy_time field, so spawned goblins act instantly; real value 0.5 s since 1/6/2026 (tertiary t... |
| `mortar_evo` | first_hit_speed_s | None | 8/10/2024 Balance Update 'added a 1 second delay in the Evolved Mortar's first attack' -- consistent with the table | Mechanic the sim does not model: evo mortar's first shot is delayed 1 s (base mortar has no such delay). Affects siege-race timing. New-field modeling... |
| `princess_evo` | volley_slow_radius_tiles | None | no radius change in History | Sim's curated pair (every/duration) carries no radius; page gives 3 tiles (prose only, page is a stub -- single path). Needed if the slow is modeled s... |
| `princess_evo` | volley_slow_pct | None | no change in History | Slow magnitude 30% missing from sim row; single-path prose on a stub -> escalate not update. |
| `princess_evo` | death_slow_zone | None | 4/8/2026 duration nerf may or may not cover the death zone | Unmodeled mechanic: sim princess_evo has no death effect at all. 'Area-damaging' zone damage value unpublished. Escalate for modeling decision. |
| `princess_evo` | hitpoints | None | page is a June-2026 stub: no vardefines, no attribute/statistics tables; prose only says 'low hitpoints and moderate damage' | PRIORITY null-hp/missing-stats row: null on all three paths. Base princess carries 261; prose implies base-identical stats but publishes nothing. Keep... |
| `princess_evo` | damage | None | page is a June-2026 stub: no vardefines, no attribute/statistics tables; prose only says 'low hitpoints and moderate damage' | PRIORITY null-hp/missing-stats row: null on all three paths. Base princess carries 168; prose implies base-identical stats but publishes nothing. Keep... |
| `princess_evo` | hit_speed | None | page is a June-2026 stub: no vardefines, no attribute/statistics tables; prose only says 'low hitpoints and moderate damage' | PRIORITY null-hp/missing-stats row: null on all three paths. Base princess carries 3.0; prose implies base-identical stats but publishes nothing. Keep... |
| `princess_evo` | dps | None | page is a June-2026 stub: no vardefines, no attribute/statistics tables; prose only says 'low hitpoints and moderate damage' | PRIORITY null-hp/missing-stats row: null on all three paths. Base princess carries 56; prose implies base-identical stats but publishes nothing. Keep ... |
| `princess_evo` | count | None | page is a June-2026 stub: no vardefines, no attribute/statistics tables; prose only says 'low hitpoints and moderate damage' | PRIORITY null-hp/missing-stats row: null on all three paths. Base princess carries 1; prose implies base-identical stats but publishes nothing. Keep n... |
| `princess_evo` | range_tiles | None | page is a June-2026 stub: no vardefines, no attribute/statistics tables; prose only says 'low hitpoints and moderate damage' | PRIORITY null-hp/missing-stats row: null on all three paths. Base princess carries 9.0; prose implies base-identical stats but publishes nothing. Keep... |
| `princess_evo` | speed_tiles | None | page is a June-2026 stub: no vardefines, no attribute/statistics tables; prose only says 'low hitpoints and moderate damage' | PRIORITY null-hp/missing-stats row: null on all three paths. Base princess carries 1.0; prose implies base-identical stats but publishes nothing. Keep... |
| `royal_ghost_evo` | invisibility_time_s | None | 2/3/2026 Balance Update 'decreased the Evolved Royal Ghost's invisibility delay to 2 seconds (from 1.8 seconds)' -- verb says decreased but 2 > 1.8; postdates the table | Merged evo row carries no invisibility_time_s (base royal_ghost: 1.8, verified:true). The 2/3/2026 entry moves the EVO's re-cloak delay to 2.0 s with ... |
| `skeleton_army_evo` | shadow_skeleton_speed_tiles | None | 12/01/2026 Balance Update 'decreased the Shadow Skeletons' speed to 60 (from 90), classifying them as Medium' -- table already reflects it | The sim's army_ghosts mechanic has no separate stats for the ghost bodies; if they inherit skeleton speed 1.5 they now move 50% too fast (1.0 since 12... |
| `skeleton_barrel_evo` | spawn_count (MISSING) | None | base card 12/2/2018 skeletons on death -> 6 (from 8), then 25/4/2018 -> 7; the evo page has never changed the per-barrel count, so 7 stands | MISSING FIELD. The KB row carries spawn_unit_stats (hit_speed/range/speed) but no skeleton COUNT, and 14 skeletons is essentially the whole card. With... |
| `tesla_evo` | pulse_damage | None | chain: launch ~227 -> 17/6/2024 -22.9% (~175) -> 9/4/2025 +17% (~205) -> 4/5/2026 -15% (~174) -- lands on the vardefine, so 174 is current | The sim models NO Electro Pulse -- the card's entire evolution mechanic is absent (uncurated row, no yaml entry). Pulse fires on surfacing and deploym... |
| `tesla_evo` | pulse_radius_tiles | None | no radius change in History | Companion to pulse_damage; 6 tiles. |
| `tesla_evo` | pulse_stun_s | None | 17/6/2024 stun 1 -> 0.5 s; unchanged since | Companion to pulse_damage; 0.5 s stun, Lumberjack Ghost immune since 4/2/2025. |
| `wall_breakers_evo` | damage_vs_troops | None | 6/4/2026 Balance Update 'decreased the Evolved Wall Breakers' damage to troops by 26%' -> vs troops ~289, vs buildings still 391 | Attack damage is now split by target class; sim has a single damage 391 (which stays correct vs buildings, their target -- the splash that clips troop... |
| `wall_breakers_evo` | runner_spawn | None | 14/5/2024: Runner damage -50% (392->196) + speed 90->120 -- table and vardefines already reflect it; 3/11/2025 'runner's death damage' -7% | MISSING SUB-UNIT: each evo Wall Breaker spawns a Runner on death (incl. after its own attack-explosion) -- a second wave of 2 building-targeting bombe... |
| `witch_evo` | max_hitpoints (MISSING) | None | 4/8/2026 'increased her max hitpoints by 40%' -> 1039*1.40 = 1454.6 ~ 1455; independently 839*1.73 = 1451.5 ~ 1452 (agree to within rounding) | The KB row stores the cap only implicitly as hitpoints*overheal_frac. Both reconstructions land at ~1452-1455, which is the cross-check that base hitp... |
| `witch_evo` | heal_source_cap (MISSING) | None | 4/8/2026 'made it to where she can only be healed by the first 4 skeletons that she spawns' | NEW MECHANIC the sim does not model at all. Without it the sim heals her off every skeleton she ever spawns, which together with the (also unmodelled)... |
| `witch_evo` | spawn_count_per_wave (MISSING) | None | base 1/4/2019 added 'spawn 3 additional Skeletons upon death' | The row has spawn_interval_s 7.0 but no COUNT per wave (4), no first-wave delay (1 s, not the generic 7 s), and no death-spawn (3). For the Evo specif... |
| `barbarian_barrel` | spawn_unit_stats.deploy_time | None | 1.0 | MISSING FIELD AND THE PATHS DISAGREE. The spawned Barbarian's deploy time is 1.0s per the 1/12/2025 balance entry, but the secondary attributes table ... |
| `clone` | cloning_time_s | None | 0.5 | MISSING FIELD, history path only. 12/6/2017 decreased the cloning time to 0.5s (from 0.8s) and nothing later changes it; no table cell corroborates, s... |
| `goblin_curse` | slow_pct | None | - | NULL ON ALL PATHS. A 4/8/2026 balance update 'added a slowdown mechanic to the Goblin Curse' with no magnitude and no duration published anywhere on t... |
| `mirror` | elixir | None | Cost of previous card played +1 | NULL BY DESIGN, BUT UNMODELLED. Mirror has no fixed cost (infobox Cost=? '(Cost of previous card played +1)'). The DB row is {count, display, kind, ra... |
| `rocket` | knockback_tiles | None | - | NULL ON ALL PATHS, already documented as deliberate. The lead says Rocket 'inflicts knockback' but no pushback range is published on the page and no b... |
| `the_log` | roll_speed | None | 200 | MISSING FIELD, history path only. 20/10/2016 set The Log's projectile speed to 200 (from 170) and its casting speed to 360 (from 300), and neither has... |
| `tornado` | zone_s | None | 2.05 | MISSING FIELD AND THE PATHS DISAGREE. The attributes table gives Duration = 1.05 sec and the lead agrees ('for 1.05 seconds'), but the last duration e... |
| `void` | first_strike_delay_s | None | 1.0 | MISSING FIELD, history path only. 17/6/2024 'increased the Void's first strike interval to 1 second (from 0.5 seconds)'. With a 1.0s first strike and ... |
| `baby_dragon` | evolution.available | None | True | SYSTEMIC GATE BUG -- 10 of my 32 keys. The parent row has evolution:null while a fully populated baby_dragon_evo row exists carrying the correct evo_c... |
| `battle_ram` | evolution.available | None | True | SYSTEMIC GATE BUG -- 10 of my 32 keys. The parent row has evolution:null while a fully populated battle_ram_evo row exists carrying the correct evo_cy... |
| `bomber` | evolution.available | None | True | SYSTEMIC GATE BUG -- 10 of my 32 keys. The parent row has evolution:null while a fully populated bomber_evo row exists carrying the correct evo_cycles... |
| `electro_dragon` | evolution.available | None | True | SYSTEMIC GATE BUG -- 10 of my 32 keys. The parent row has evolution:null while a fully populated electro_dragon_evo row exists carrying the correct ev... |
| `executioner` | evolution.available | None | True | SYSTEMIC GATE BUG -- 10 of my 32 keys. The parent row has evolution:null while a fully populated executioner_evo row exists carrying the correct evo_c... |
| `firecracker` | evolution.available | None | True | SYSTEMIC GATE BUG -- 10 of my 32 keys. The parent row has evolution:null while a fully populated firecracker_evo row exists carrying the correct evo_c... |
| `furnace` | evolution.available | None | True | SYSTEMIC GATE BUG -- 10 of my 32 keys. The parent row has evolution:null while a fully populated furnace_evo row exists carrying the correct evo_cycle... |
| `ghost_souldier` | spawn_damage | None | 81 | Missing field: the Souldier deals a spawn burst (spawn_11 = 81 at level 11) that the KB does not carry at all, and P3 confirms it is a separately trac... |
| `goblin_machine` | rocket_ability | None | {'hit_speed': 5, 'projectile_speed': 350} | The KB row carries no rocket at all, so the Goblin Machine's locking AOE missile is unmodelled. Published: damage 304, crown 152, radius 1.5, range 2.... |
| `heal_spirit` | heal_ability | None | {'heal_11': 100.25, 'heal_speed': 0.25} | The KB row carries no heal at all -- a Heal Spirit that does not heal. Published: 100.25 heal per pulse at L11, 4 pulses every 1 second (0.25 s interv... |
| `ice_golem` | death_radius_tiles | None | 2.0 | KB row carries death_damage 84 but no radius for it, so the death blast currently has no area. Published radius 2. Carried over from pass 1 and re-ver... |
| `ice_wizard` | spawn_slow | None | {'radius': 3.0, 'spawn_slow_duration_s': 1.0, 'slowdown_pct': -30} | The KB row carries spawn_damage 84 but none of the spawn's area or slow, so the Ice Wizard's deploy blast currently damages nothing around it and slow... |
| `lumberjack` | drops_rage.damage | None | dated entries 9/4/2025 (-23%) and 4/8/2025 (+21%) both describe "the Rage's damage" | The Lumberjack's dropped Rage DEALS DAMAGE in the current game (179 at L11, 54 to crown towers) and the KB's drops_rage dict has no damage key at all,... |
| `lumberjack` | evolution | None | 9/4/2025 increased the cycles required to 2 (from 1) | The Lumberjack has an Evolution (added 3/2/2025) and a lumberjack_evo key exists in the KB, but the base lumberjack row has no `evolution` sub-dict --... |
| `lumberjack_ghost` | untargetable | None | - | Mechanic gap rather than a number. The page is explicit that the ghost 'can't be targeted by troops, buildings and towers, but can be affected by spel... |
| `musketeer` | evolution.cycles | None | 2 | The musketeer row's curated `evolution` dict (verified:true) carries available/effect/gains but no `cycles`, where the comparable knight row carries c... |
| `ram_rider` | rider_attack (rider_damage / rider_hit_speed / rider_range_tiles / rider_projectile_speed) | None | 104 | PRIORITY / MISSING FIELDS. The KB models only the Ram (damage 250, charge 501) and the snare magnitude (slow_pct -70). The RIDER's own attack -- 104 d... |
| `royal_recruit` | range_tiles | None | 1.6 | PRIORITY / MISSING FIELD on a sub-unit row. Sourced from the PARENT spell page Royal Delivery, section 'Royal Recruit Attributes' -- royal_recruit has... |
| `royal_recruit` | dps | None | 102 | PRIORITY / MISSING FIELD. Derived exactly as on the sibling row royal_recruits.dps (102), which matches. Same body, same stats -- confirmed by Royal D... |
| `rune_giant` | enchant (bonus_damage / enchant_range_tiles / enchant_limit / enchant_every_nth / enchant_duration_after_death_s) | None | 220 | PRIORITY / MISSING FIELDS -- the card's entire identity is unmodelled. The KB row carries no enchant fields at all, so in the sim a Rune Giant is just... |
| `three_musketeers` | dps | None | melee 242 / ranged 157 | PRIORITY / MISSING FIELD, a consequence of the damage gap above. Uses the current atk_speed 1.3; if the 2/2/2026 entry (1.2) is accepted instead, thes... |
| `three_musketeers` | range_tiles | None | 6 (ranged) / 1.6 (melee) | PRIORITY / MISSING FIELD. The KB carries range: 'long' but no range_tiles, so nothing tells the engine how far a Musketeer shoots. PATHS PUBLISHING: P... |
| `three_musketeers` | attacks | None | ['air', 'ground'] | PRIORITY / MISSING FIELD. The KB row has no `attacks` list at all, so air-targeting is undefined for a card whose ranged mode explicitly hits air. The... |

---

## 2. The wiki's stat block LAGS the wiki's own balance history

**Rows:** 77  |  **Recommendation:** Apply all; they are what the third extraction path exists to catch.

The card's #vardefine still holds a pre-balance number while the page's own dated History says it changed. This is the known failure mode that made a naive re-import dangerous. Each row carries the dated entry that supersedes it. Bulk of these are the 4/8/2026 update.

- [ ] Accept recommendation for all 77
- [ ] I want to go row by row

<sub>families: evos_a 20, troops_b 13, buildings 10, evos_b 9, troops_a 8, troops_c 8, spells 8, champions 1</sub>

| card | field | sim has | wiki says | why |
|---|---|---|---|---|
| `barbarian_hut` | spawns.interval | 13.5 | 14.0 | CURATED verified:true, so never auto-overwritten. The curated 13.5 is refuted by every path: the attribute table AND the intro prose both say 15, and ... |
| `cannon` | damage | 212 | 201 | VARDEFINE PROVABLY STALE. A revision walk shows dmg_11=212 is byte-identical to the level-11 damage in the 2025-12-22 revision, i.e. it predates the 6... |
| `cannon` | dps | 212 | 201 | Follows damage: dps = damage / hit_speed = 201 / 1.0 = 201 if the 6/4/2026 -5% is applied. Same rounding caveat as the damage line. |
| `goblin_drill` | spawn_crown_damage | 26.0 | 0 | HIGH CONFIDENCE that the current value is 0. The 4/8/2026 entry says the tower spawn damage was removed 'entirely (from 30% of the full spawn damage)'... |
| `mortar` | hit_speed | 5.0 | 4.7 | VARDEFINE AND TABLE BOTH LAG A DATED ENTRY. atk_speed=5 and the table's '5 sec' cell are the pre-4/8/2026 value; the 4/8/2026 entry states 4.7 'from 5... |
| `mortar` | dps | 53 | 57 | Follows hit_speed: 266/5 = 53.2 -> 53 (current) versus 266/4.7 = 56.6 -> 57 once the 4/8/2026 change is applied. Same reasoning and same caveat as the... |
| `tesla` | hitpoints | 1152 | 1187 | The 1/6/2026 entry claims '+3% hitpoints' in the same breath as the lifetime change, but hp_11 is 1152 on the current page AND 1,152 in the cached pre... |
| `x_bow` | hit_speed | 0.3 | 0.4 | VARDEFINE AND TABLE BOTH LAG THE 4/8/2026 ENTRY, which states 0.4 'from 0.3 seconds' - exactly what both still publish, proving neither absorbed the c... |
| `x_bow` | damage | 43 | 58 | Same 4/8/2026 entry: '+35% damage'. dmg_11=43 is the pre-change value - the hit-speed clause of that same entry proves the row it sits in had not been... |
| `x_bow` | dps | 143 | 145 | Follows damage and hit_speed: 43/0.3 = 143.3 -> 143 (current) versus 58/0.4 = 145 after the 4/8/2026 change. Note the change is close to DPS-neutral, ... |
| `little_prince` | attack_ramp.mults[1] | 1.5 | 17/11/2023 increased the number of attacks required to change stages to 3 (from 2); no stage-2 hit-speed change ever logged | REAL SIM ERROR, quantified. engine.py applies atk_ramp_mults as a CADENCE divisor (u.cooldown = hit_speed / spd / rm), so mults [1.0,1.5,3.0] with hit... |
| `archers_evo` | power_mult | 1.5 | 1.25 | CURATED verified:true (power_mult 1.5) so flagged, never auto-overwritten -- but ALL THREE paths agree on 1.25, including a dedicated vardefine (Pow d... |
| `barbarians_evo` | hit_rage_s | 3.0 | 5.0 | CURATED verified:true (3.0) so flagged, not overwritten -- but every available path says 5 s. Recommend 5.0. NOTE the page's own INTRO PROSE is stale ... |
| `barbarians_evo` | hitpoints | 716 | 691 | WIKI IS SELF-INCONSISTENT. The 4/8/2026 rule is 'Evo HP = base HP', yet the Evo page says 716 and the base page says 691; both cannot be right. Time-m... |
| `barbarians_evo` | damage | 192 | 191 | Small but real: since 3/10/2023 the Evo has NO damage boost, so its damage must equal the base's, yet the Evo page says 192 and the base page says 191... |
| `bats_evo` | hit_speed | 1.3 | 1.2 | CLASSIC VARDEFINE-LAGS-HISTORY CASE, so do not read the raw 2-1 count as support for 1.3. The two 1.3s are one page's stat block (the vardefine and th... |
| `bomber_evo` | hitpoints | 332 | 304 | Both the Evo page's own intro and the Card Evolution table say the Evo Bomber has IDENTICAL stats, and the Evo page's History logs no hitpoint boost s... |
| `cannon_evo` | damage | 212 | 201 | VARDEFINE PROVABLY LAGS. Do not read this as 2-of-3 for 212: the level table is generated from the same vardefine, so P1 and P2 are one witness, and t... |
| `dart_goblin_evo` | poison_s | 2.0 | 1.0 | CURATED verified:true (2.0) so flagged only, but three independent statements say 1 second, and the change that produced it is dated 4/8/2025 -- more ... |
| `dart_goblin_evo` | damage | 156 | 144 | Both the base and the Evo page carry 156 and both log the 12/1/2026 -8% in their History, but the time machine shows 156 was already there in Nov 2025... |
| `executioner_evo` | smash_range_tiles | 3.5 | 2.5 | CURATED verified:true (3.5) so flagged, but four independent statements say 2.5, and the page's edit comment on the live revision is literally 'Evo Ex... |
| `executioner_evo` | smash_knockback_tiles | 2.0 | 1.0 | CURATED verified:true, and the current 2.0 matches NO source. Two independent History paths date a 1.5 -> 1.0 nerf to 2/3/2026; the Card Evolution tab... |
| `executioner_evo` | damage | 168 | 180 | Both the base and Evo pages log a 2/3/2026 +7% damage buff in their History and neither applied it to the number. Derived current ~180 (168*1.07 = 179... |
| `executioner_evo` | projectile_range | 7.5 | 7.0 | Imported field, and the two History paths (Evo page + Version History master) both date the 7.5 -> 7.0 cut to 4/8/2026 while the hand-typed attributes... |
| `firecracker_evo` | projectile_speed | 550.0 | 500.0 | UNRESOLVABLE FROM THE WIKI, recorded with all raws. The changelog says the value went 400 -> 500 on 6-7/4/2026, but the attributes cell said 550 both ... |
| `furnace_evo` | hit_speed | 1.8 | 1.7 | Third stale field on the same card. Recommend hit_speed 1.7 with dps 105 (179/1.7) instead of 99. The Version History wording explicitly says the chan... |
| `furnace_evo` | speed_tiles | 0.75 | 1.0 | The Evo page's Speed cell was never updated for the 6/10/2025 Slow -> Medium change that its own History records and that the base page's cell already... |
| `giant_snowball_evo` | slow_duration_s | 4.0 | 3.0 | CURATED verified:true. The 4/5/2026 change REMOVED the Evo's bonus slow duration, so it now equals the base spell's 3 s -- which the base page's table... |
| `goblin_barrel_evo` | decoy_goblin.damage | 89 | 66 | CLEAN RECONSTRUCTION, two nerfs deep. 120 -> (-26%) -> 89 is visible in the time machine; the second -26% (4/8/2026) was never applied, giving 89*0.74... |
| `goblin_barrel_evo` | damage | 120 | 125 | The Goblin Barrel/Evolution page's copy of the Goblin stat block lags the 4/8/2026 +4% that the Goblins page already applied -- and here the direction... |
| `goblin_giant_evo` | hitpoints | 3223 | 3113 | Two problems at once. (1) The Card Evolution table says the Evo has identical stats, yet the two pages have published 3223 vs 3022 for months. (2) BOT... |
| `mortar_evo` | hit_speed | 4.0 | 4/8/2026 Balance Update 'increased the Evolved Mortar's hit speed to 4.7 seconds (from 4 seconds)' -- POSTDATES the vardefine -> current must be 4.7 | THE vardefine-lag case P3 exists for: P1+P2 still say 4.0 (== sim) but a dated 4/8/2026 history entry moves it to 4.7. Evo's edge over base (5.0) shra... |
| `pekka_evo` | kill_heal | 470 | 8/10/2024 12.5%->10%; 14/11/2024 ->7.5%; 8/1/2025 heal now BASED ON TARGET'S HITPOINTS; 5/5/2025 small +13%/medium +8%/large +2%; 2/2/2026 all forms +5% -- the flat-12.5% model died 8/1/2025 | Curated verified:true kill_heal 470 is the LAUNCH-era 12.5%-of-3760 model, four balance changes out of date. Current: 3-tier heal by victim max-hp (16... |
| `princess_evo` | volley_slow_every | 3 | 4/8/2026 Balance Update: slow attacks now every 2 hits (from every 3) -- postdates the Ability prose | Curated verified:true (2026-08-14 sweep quoted the launch ability). The 4/8/2026 nerfset moved the cadence to every 2 hits; the stub's Ability section... |
| `princess_evo` | volley_slow_s | 7.0 | 4/8/2026: slowdown duration 5.5 s (from 7) | Curated verified:true; same 4/8/2026 entry -> propose 5.5. Ambiguous whether the death-zone 7 s (see death_slow_zone row) was also cut to 5.5 -- the b... |
| `royal_hogs_evo` | air_drop_damage | 115 | 2/3/2026 Landing Damage -27% (launch ~158 -> 115, matching the vardefine); 4/5/2026 Landing Damage -49% POSTDATES it -> current = 115*0.51 = 58.65 ~ 59 | Vardefine-lag catch. The 2026-08-14 curation note itself reads '115 (post 2/3/2026 -27% nerf)' -- it missed the 4/5/2026 -49%. No rounding chain makes... |
| `valkyrie_evo` | attack_nado_damage | 76 | 14/5/2024 tornado damage +11%; 4/8/2026 tornado damage -50%. Chain fit: launch 76 -> x1.11 = 84.4~84 (the vardefine) -> x0.5 = 42 current. The alternate reading (84 post-both, launch ~151) requires a launch value no source ever shows | Three-way split: sim 76 (the LAUNCH value -- predates even the May-2024 buff), vardefine 84 (post-buff, pre-4/8/2026), derived current 42. The curated... |
| `witch_evo` | overheal_frac | 1.238 | 4/8/2026 'increased her overheal ratio to x1.73 (from x1.24)' -> current 1.73 | ESCALATE - curated verified:true (cards.yaml line 218), never auto-overwrite. The history gives an ABSOLUTE new value (x1.73) and names the old one (x... |
| `witch_evo` | spawn_death_heal | 76 | heal chain 3/6/2025 -12%, 8/7/2025 -12%, 4/8/2025 +36%, 6/10/2025 -21%, 2/2/2026 -11%, then 4/8/2026 '+189%'. 76*2.89 = 219.6 -> ~220 | ESCALATE - curated verified:true. Proof the vardefine predates 4/8/2026: maks_hp_11/hp_11 is still exactly the OLD x1.24 ratio, so that update was fol... |
| `zap_evo` | zap_pulses | 3 | 8/10/2024 'increased the second pulse's damage by 100%, but REMOVED THE THIRD PULSE' -> 2 pulses | ESCALATE - curated verified:true so not auto-updated, but the evidence is 3-of-3 and unambiguous: the third pulse was REMOVED on 8/10/2024 and the cur... |
| `barbarian_barrel` | roll_tiles | 5.0 | 4.5 | STALE BY ONE BALANCE UPDATE. cards.yaml pins roll_tiles 5.0 quoting the 3/9/2018 entry ('decreased its rolling distance to 5 tiles (from 7 tiles)'), b... |
| `earthquake` | build_damage | 283 | 287 | Same stale-curation as `damage`: vardefine build_dmg_11 = 287 vs DB 283. Ratio sanity check against the lead's 'doing 3.5 times damage to buildings': ... |
| `fireball` | crown_tower_damage | 207 | 172 | HIGHEST-TRAFFIC MISS IN THE GROUP. TWO independent 2026 history entries agree the value is now 172 -- one states the arithmetic outright ('207-172', l... |
| `goblin_barrel_decoy` | spawns_troop.decoy_goblin.damage | 89 | 66 | Sourced from Goblin Barrel/Evolution -- the 'Decoy Goblin Damage' column of unit-statistics-table plus the de_* vardefine block; this key has no page ... |
| `graveyard` | zone_spawn_edge | True | 3.3 | SPAWN RING IS 3.3 TILES, NOT THE 4-TILE EDGE. The DB models Skeletons appearing on the edge of the 4-tile radius (zone_spawn_edge true + radius_tiles ... |
| `vines` | stun_duration_s | 2.5 | 2 | PROSE LAGS HISTORY, AND THE CURATOR QUOTED THE PROSE. The attributes table gives Duration = 2 sec AND 8/10/2025 'decreased duration to 2 seconds (from... |
| `vines` | crown_tower_damage | 78 | 70 | 1/6/2026 -> 23% of full. Per hit: 153*0.23 = 35.19 -> 35, x2 hits = 70. The DB's 78 is the vardefine's 39/hit x2, i.e. the 25% era. Missed by the audi... |
| `void` | zone_tiers | [[1, 696, 97], [3, 294, 51], [99, 153, 35]] | [[1, 696, 97], [4, 294, 51], [99, 153, 35]] | TIER BOUNDARY OFF BY ONE -- read from the vardefine NAME instead of the column LABEL. The vardefines are named 1_/3_/5_, but the table headers they fe... |
| `bats` | hit_speed | 1.3 | 1.2 | P1 and P2 both say 1.3 and agree with current_db, but the 2/3/2026 entry is garbled: it says 'hitpoints' while quoting SECONDS and naming exactly the ... |
| `bush_goblin` | damage | 227 | 256 | 227 * 1.12 = 254.2 and the page's current vardefine is 256, so current_db looks like the pre-9/4/2025 value. Confirmed this is the right vardefine for... |
| `bush_goblin` | deploy_time | 0.2 | 1.0 | P2's SECONDARY table -- the Bush Goblin's own row -- says 1 sec. Curated verified:true -> escalate. See the ghost_souldier/deploy_time line: these two... |
| `dark_prince` | splash_radius_tiles | 1.25 | 1.1 | P2 and P3 both give 1.1. 1.25 is the value set on 6/5/2019 and superseded twice since (1/7/2019 -> 1.2, 2/9/2019 -> 1.1). Behaviourally live and worse... |
| `firecracker` | projectile_speed | 550.0 | 500 | P2 says 550 and agrees with current_db; P3 says the value became 500 from 400 -- and 400 is not what the table held either, so these paths do not mere... |
| `fisherman` | slow_pct | -30 | removed | Three different published answers for one field: prose 35%, history -30% (6/10/2025), history removed (6/4/2026). Pairs with slow_duration_s above -- ... |
| `furnace` | hit_speed | 1.8 | 1.7 | P1 and P2 agree with current_db at 1.8; only P3 says 1.7. I treated the Bowler/Executioner/Furnace-range cases as updates because there the table prin... |
| `furnace` | lifetime_s | 28.0 | 28.0 | 28 s is correct as of 4/4/2023 and current_db matches it, but on 4/8/2025 the Furnace stopped being a building and became a walking troop, and the att... |
| `goblin_demolisher` | hit_speed | 1.2 | 1.1 | Genuinely contested, so escalating rather than proposing an overwrite. The two paths that say 1.2 (vardefine + attributes table) are both renderings o... |
| `goblin_gang` | load_time_s | 0.7 | 0.5 | Frozen-dump field (card_mechanics.json goblin_gang, character 'Goblin', load_time_s 0.7, source_frozen 2023-10-18). The wiki's First Hit Speed is 0.6 ... |
| `goblin_giant` | spawn_unit_stats.hit_speed | 1.7 | 1.6 | Confirmed stale by time machine: at oldid 436715 (2026-07-16, before the 4/8/2026 update) spear_atk_speed was already 1.7 and it is still 1.7 today, s... |
| `goblin_machine` | hitpoints | 2150 | 2258 | Page proven stale across a documented change. 2150 x 1.05 = 2257.5, so ~2258. ESTIMATE, not an exact figure: Supercell's quoted percentages are rounde... |
| `goblin_machine` | damage | 212 | 231 | Page proven stale across the same change. 212 x 1.09 = 231.1, so ~231 -- same estimate caveat as the hitpoints line above. |
| `lumberjack` | drops_rage.duration_s | 4.5 | 5.5 | Two independent paths agree on 5.5 and differ from the KB's 4.5, which would normally be an update -- but drops_rage is curated verified:true in cards... |
| `magic_archer` | damage | 133 | 125 | Page proven stale across a documented change: 133 before 4/8/2026 and still 133 now, while History records a 6% cut. 133 x 0.94 = 125.02, so ~125 (EST... |
| `magic_archer` | load_time_s | 0.6 | 0.4 | Frozen-dump field. Wiki gives hit speed 1.1 / First Hit Speed 0.7 -> 0.4, and a dated entry moved the first attack interval to 0.7 (from 0.8) on 5/3/2... |
| `miner` | load_time_s | 0.7 | 0.8 | Frozen-dump field. Wiki gives hit speed 1.3 / First Hit Speed 0.5 -> 0.8; dump says 0.7. Note the dump's own cross-check field records _hit_speed_s 1.... |
| `mini_pekka` | hitpoints | 1433 | 1390 | Page proven stale across a documented change: time machine oldid 433647 (2025-12-25, before 12/1/2026) has the hardcoded L11 row '/11//1,433//755//{{D... |
| `minion_horde` | load_time_s | 0.5 | 0.6 | Frozen-dump field (shared 'Minion' character row with minions). Against the Minion Horde page's stale 1.1 the identity gives 0.6; against the correct ... |
| `minions` | load_time_s | 0.5 | 0.7 | Frozen-dump field. Wiki gives hit speed 1.2 / First Hit Speed 0.5 -> 0.7; dump says 0.5. The dump's cross-check field records _hit_speed_s 1.0, and th... |
| `musketeer` | load_time_s | 0.2 | 0.3 | Three-way conflict, so no auto-import. The KB and card_mechanics.json say 0.2; the wiki gives hit speed 1 s / First Hit Speed 0.7 s -> 0.3; and engine... |
| `phoenix` | egg.reborn_frac | 0.8 | 1.0 | STRONGEST SINGLE FINDING IN THE GROUP. P2 (prose) and P3 (dated 2025-11-03 entry) agree on 1.0 against current_db 0.8, and no path supports 0.8 -- the... |
| `ram_rider` | hitpoints | 1697 | 1765 | PROVEN LAG: the pre-change revision already carried today's value, so the wiki never applied the balance entry. P1/P2 are NOT independent here -- the ... |
| `rascals` | hitpoints (and components[0].hitpoints -- Rascal Boy) | 1940 | 1824 | PROVEN LAG: the pre-change revision already carried today's value, so the wiki never applied the balance entry. P1/P2 are NOT independent here -- the ... |
| `rune_giant` | hitpoints | 2662 | 2822 | PROVEN LAG: the pre-change revision already carried today's value, so the wiki never applied the balance entry. P1/P2 are NOT independent here -- the ... |
| `rune_giant` | damage | 120 | 154 | PROVEN LAG: the pre-change revision already carried today's value, so the wiki never applied the balance entry. P1/P2 are NOT independent here -- the ... |
| `skeleton_dragons` | damage | 161 | 151 | PROVEN LAG: the pre-change revision already carried today's value, so the wiki never applied the balance entry. P1/P2 are NOT independent here -- the ... |
| `three_musketeers` | hit_speed | 1.3 | 1.2 | WEAKEST of the P3 conflicts -- flagged, but treat this History entry with suspicion. rev 434538 (2026-01-26, days BEFORE the 2/2/2026 entry) shows Hit... |
| `wall_breakers` | damage | 391 | 313 | PROVEN LAG: the pre-change revision already carried today's value, so the wiki never applied the balance entry. P1/P2 are NOT independent here -- the ... |

---

## 3. Crown-tower damage still stale after the 1/6/2026 sweep

**Rows:** 15  |  **Recommendation:** Apply all, AND fix the audit tool's regex.

The sweep looked complete because `crown_damage_audit.py` FALSE-PASSES: its regex demands 'of the full damage' while the 2026 line reads 'of ITS full damage'. It matched a 2020 line and printed ok. Every pin also landed on a parent card and missed its evolution.

- [ ] Accept recommendation for all 15
- [ ] I want to go row by row

<sub>families: spells 6, evos_b 4, evos_a 2, troops_a 1, xc_crown 1, champions 1</sub>

| card | field | sim has | wiki says | why |
|---|---|---|---|---|
| `goblinstein` | lightning_link_crown_tower_damage | None | 17/10/2024 decreased its Crown Tower Damage by 36%; 16/12/2024 fixed King Tower reduced damage; 4/8/2026 Ability DPS -12% | Doubly derived: 23 is pre-4/8/2026 and 23/107 = 21.5% of link damage, so a post-nerf value (~20) depends on resolving the link-damage row first. KNOWN... |
| `dart_goblin_evo` | poison_stages | [51, 115, 307] | [64, 128, 307] | CURATED verified:true AND provably stale. The time machine shows 51/115/307 predate the 1/6/2026 buff and never moved, so P1 is disqualified as eviden... |
| `giant_snowball_evo` | crown_tower_damage | 54 | 45 | The Evo's crown-tower damage was cut to 25% of full on 1/6/2026 but its vardefine still holds the 30% figure it shares with the base spell. Derived cu... |
| `lumberjack_evo` | death_crown_damage | None | 4/8/2025 rage damage +21% is the last rage change; 179*0.3=53.7~54 is the standard 30% crown factor, self-consistent | Sim models the rage-drop blast via death_damage 179 (matches wiki) but carries NO crown-tower figure for it; wiki publishes 54. Row is curated verifie... |
| `valkyrie_evo` | attack_nado_crown_damage | None | if the 4/8/2026 -50% also halves the crown chip, current would be ~18; vardefine likely lags like tor_11 | Sim has no crown-tower figure for the attack-tornado; wiki publishes 37 (probably pre-4/8/2026). Crown-tower family is re-curated post-1/6/2026 -> own... |
| `wall_breakers_evo` | death_damage | 291.0 | chain: pre-8/1/2025 194 -> +50% = 291 -> 6/10/2025 +11% = 323 -> 3/11/2025 -10% = 290.7~291 (the vardefine's timepoint) -> 4/8/2026 -20% = 232.8~233 CURRENT. The 4/8/2026 entry postdates the vardefine | Vardefine-lag catch: the +50%/+11%/-10% chain closes exactly on 291, so 291 is the 3/11/2025 value and the Aug-2026 -20% is missing from it. Sim (and ... |
| `wall_breakers_evo` | death_crown_damage | None | 8/1/2025: death damage deals 66% of full to Crown Towers; if death drops to ~233 post-4/8/2026, crown chip ~154 | Sim carries no crown-tower figure for the death blast -- it chips towers at the full 291 instead of 66% (and post-Aug-2026, ~154). Crown-tower family ... |
| `arrows` | crown_tower_damage | 31 | 24 | 1/6/2026 cut Arrows crown damage to 20% of full; 122*0.20=24.4 -> 24. Vardefine 31 is the pre-1/6/2026 25% value (122*0.25=30.5 -> 31) and is what the... |
| `freeze` | crown_tower_damage | 35 | 29 | 1/6/2026 cut Freeze crown damage to 25% of full: 115*0.25 = 28.75 -> 29. Vardefine 35 is the 30% value. Freeze was never audited at all -- it is absen... |
| `giant_snowball` | crown_tower_damage | 54 | 45 | 1/6/2026 cut it to 25% of full: 179*0.25 = 44.75 -> 45; vardefine 54 is the 30% value. Missed by the audit tool for a THIRD distinct reason: this page... |
| `rage` | crown_tower_damage | 54 | 45 | 1/6/2026 -> 25% of full: 179*0.25 = 44.75 -> 45; vardefine 54 is the 30% value. Like Freeze, Rage is absent from crown_damage_audit.py's CARDS list, s... |
| `royal_delivery` | damage | 133 | 385 | SAME INVERTED MAPPING AS BARBARIAN BARREL, and here it propagated into a curated comment. The landing/area damage is spawn_11 = 437; dmg_11 = 133 is t... |
| `void` | zone_tick_s | 1.333 | 1.2 | STALE BY TWO BALANCE UPDATES. The strike interval went 1.3 -> 1.0 (4/3/2025) -> 1.2 (4/8/2026). The DB's 1.333 is not any published value: it is 4s du... |
| `electro_giant` | crown_tower_damage | None | 97 | Missing field: the Zap Pack's reflected damage to crown towers (crown_11 = 97) has no KB counterpart. Deliberately NOT proposing a write -- the brief ... |
| `goblin_drill_evo` | spawn_crown_damage | 26.0 | 0 | STALE CROWN, and the most recent of the batch -- 4/8/2026, three weeks ago. 26/84 = 31% is precisely the fraction that update REMOVED; the correct val... |

---

## 4. The sim holds the PARENT's or SPAWNED unit's stat instead of the card's own

**Rows:** 7  |  **Recommendation:** Apply all — these are unambiguous mix-ups.

The exact failure class that once gave 4 buildings their spawned unit's stats. Tell-tale: the stored number is EXACTLY another vardefine on the same page.

- [ ] Accept recommendation for all 7
- [ ] I want to go row by row

<sub>families: troops_a 2, spells 2, buildings 1, evos_b 1, xc_spawn_anchor 1</sub>

| card | field | sim has | wiki says | why |
|---|---|---|---|---|
| `goblin_cage` | hit_speed | 1.1 | 1.1 | CONTAMINATION RESIDUE (the 2020-incident pattern). atk_speed=1.1 and the '1.1 sec' Hit Speed cell both belong to the Goblin Brawler in the SECONDARY t... |
| `skeleton_barrel_evo` | death_damage | 238.0 | 4/8/2025 death damage -> 164% of original (from 176%); then 12/1/2026 '-8%'; then 6/4/2026 '-13%'. Reconstruction 238*0.92*0.87 = 190.5 -> ~190 per barrel (ratio form 164%*0.92*0.87 = 131.3% of base 145 = 190.3) | ESCALATE - do not auto-update. P1 and P2 are NOT independent here (the prose and the vardefine are one 4/8/2025 snapshot), so the apparent 2-of-3 for ... |
| `barbarian_barrel` | damage | 191 | 230 | INVERTED SPAWN/PARENT MAPPING. The statistics table's 'Barbarian Barrel Area Damage' column is rendered from spawn_11 (230); the 'Damage' column (dmg_... |
| `barbarian_barrel` | spawn_damage | 230.0 | 191 | Mirror of the damage row: spawn_damage currently holds the barrel's own 230 area damage while the spawned Barbarian's 191 sits in `damage`. The two fi... |
| `electro_wizard` | spawn_damage | 115 | 192 | Same contamination shape as ghost_souldier: current_db spawn_damage 115 is EXACTLY the Electro Wizard's own per-bolt damage on the same page. The leve... |
| `ghost_souldier` | damage | 261 | 81 | PARENT-STAT CONTAMINATION. current_db 261 is EXACTLY the Royal Ghost's own dmg_11 on the same page; the Souldier's own vardefine is soul_dmg_11 = 81. ... |
| `fire_spirit` | hitpoints | 215 | 215 | Cross-page conflict on the spawned unit: 215 (card page) against 230 (Furnace page), about 7%. The KB uses the card page, which is the right default, ... |

---

## 5. Rows YOU marked verified:true that the sources contradict

**Rows:** 19  |  **Recommendation:** Read each one — your ruling outranks the wiki, but these look like real errors.

Per your standing rule these are never auto-overwritten. Several are severe (zap_evo's removed 3rd pulse, dark_prince's doubled splash).

- [ ] Accept recommendation for all 19
- [ ] I want to go row by row

<sub>families: evos_a 7, troops_a 3, troops_c 2, buildings 2, troops_b 1, spells 1, evos_b 1, champions 1, xc_spawn_anchor 1</sub>

| card | field | sim has | wiki says | why |
|---|---|---|---|---|
| `tesla` | rarity | rare | common | CURATED verified:true, so escalate rather than update. Three independent surfaces say Common: the attribute table's Rarity cell, the intro sentence, a... |
| `tesla` | evolution.hitpoints | 1152 | 1187 | Inherits the base-Tesla ambiguity above: the curation deliberately sets the evo's hp to the base card's published level-11 value because the wiki says... |
| `boss_bandit` | leap_towers | True | no entry | Unsupported either way. The intro gates the dash on "ground UNITS" (which would exclude Crown Towers); the table's Target=Ground is about air-vs-groun... |
| `baby_dragon_evo` | aura_radius_tiles | 4.0 | 8x9 square area (no radius published) | The only published geometry is an 8x9 TILE RECTANGLE; the sim models a 4.0-tile RADIUS (a circle, i.e. an 8x8 bounding box). The 8-tile axis matches 2... |
| `bats_evo` | hit_heal | 99 | 76 | LIKELY CURATION ARITHMETIC ERROR, not a wiki lag. cards.yaml derives 99 as '76 hp/s at the level-11 row x 1.3 s hit speed = ~99 per attack'. But 76 is... |
| `firecracker_evo` | spark_radius_tiles | 0.75 | 2.5 (big) / 1.2 (small) | CURATED verified:true and badly understated. Two independent sources publish TWO radii -- 2.5 tiles for the centre spark and 1.2 for each of the five ... |
| `firecracker_evo` | spark_duration_s | 2.5 | 3 / 2.5 | CURATED verified:true. The single spark_duration_s 2.5 is correct for the SMALL sparks and 0.5 s short for the BIG one, which lasts 3.0 s on all three... |
| `giant_snowball_evo` | roll_tiles | 4.5 | 4.0 | CURATED verified:true (4.5) so flagged, but three independent sources say 4.0 and only the card's own attributes table and intro (which the same edit ... |
| `giant_snowball_evo` | attacks | ['ground'] | ['air', 'ground'] | CURATED verified:true, and it narrows the spell rather than describing it. cards.yaml overrides attacks to [ground] for the Evo while the base row kee... |
| `hunter_evo` | net_range_tiles | 5.5 | 4.0 | CURATED verified:true, and the curation note says so: 'curated to his sight [verify]'. The wiki now publishes the number in a named column -- Net Rang... |
| `valkyrie_evo` | attack_nado_radius_tiles | 5.5 | 1/12/2025 Balance Update 'decreased the Evolved Valkyrie's tornado radius by half a tile, from 5.5 down to 5' -- postdates the table | Curated verified:true 5.5 is the pre-Dec-2025 value; dated history entry moves it to 5.0 and the wiki table was never updated. Propose 5.0. |
| `earthquake` | damage | 81 | 84 | The curated row pins damage 81 but the live vardefine is 84. PROOF the curator already had 84 in hand: the same row's crown_tower_damage 49 is only re... |
| `bomber` | rarity | rare | common | Two independent places on the page (attributes table and intro prose) say Common; current_db says rare. The Bomber has been a Common since release and... |
| `decoy_goblin` | deploy_time | 1.0 | 1.1 | Small but real: P2 gives 1.1 s. Everything else on this key matches exactly -- its own de_* vardefines (hitpoints 81, damage 89, hit_speed 1.1) and th... |
| `ghost_souldier` | deploy_time | 1.0 | 0.2 | The Souldier's own attributes table says 0.2 sec; current_db says 1.0. Mirror image of bush_goblin/deploy_time -- see that line. Curated verified:true... |
| `lava_pups` | speed | fast | medium | Internal contradiction inside a curated verified:true row: lava_pups carries speed_tiles 1.0 (correct -- the wiki's 'Medium (60)') alongside the categ... |
| `spirit_empress` | damage | 307 | 309 | NOT edit-war noise -- separate from the hitpoints pin and needs its own ruling. dmg_11 read 309 at rev 436748 (2026-07-16) before the August churn and... |
| `suspicious_bush` | range_tiles | 0.5 | 1.6 | Wiki self-contradiction: the History entry names the old value (0.5), the new value (1.6) AND the new classification, yet the table still reads 'Melee... |
| `furnace` | spawns.interval | 5.0 | 7.0 | SELF-CONTRADICTING CURATION, and the sim believes the wrong half. The cards.yaml line reads spawns: {unit: fire_spirit, count: 1, interval: 5.0} with ... |

---

## 6. One shared constant, not a per-card field

**Rows:** 6  |  **Recommendation:** One ruling sets it for every chain card.

The sim hardcodes _CHAIN_TILES = 3.0; THREE independent pages publish 4 tiles; cards.yaml's own comment says 3.5. All three disagree. This is the Electro Dragon chain issue you raised.

- [ ] Accept recommendation for all 6
- [ ] I want to go row by row

<sub>families: evos_a 3, troops_a 2, champions 1</sub>

| card | field | sim has | wiki says | why |
|---|---|---|---|---|
| `little_prince` | royal_rescue_pushback_tiles | None | 17/11/2023 pushback -> 2.5 (from 3.5); 17/6/2024 -> 2 tiles (from 2.5); 1/9/2025 increased the Royal Rescue's pushback to 2.5 tiles (from 2 tiles) | RESOLVES the little_prince half of conflicts.md C8 ("prose 0-2 tiles vs History 1/9/2025 2.5 tiles"): the history chain is complete and monotone, so 2... |
| `electro_dragon_evo` | hits_per_attack | 12 | 3 | CURATED verified:true and materially wrong as a model, not just as a number. The KB uses hits_per_attack 12 as 'practical infinity', which the engine ... |
| `electro_dragon_evo` | chain_range_tiles | 3.0 | 4.0 | ENGINE CONSTANT, NOT A KB FIELD -- hogeq/src/clashrl/sim/engine.py line 98 defines _CHAIN_TILES = 3.0 globally and line 3602 applies it to every chain... |
| `electro_dragon_evo` | late_chain_damage | None | 89 | MISSING FIELD plus a clean stale-derivation proof. 64 is exactly 192 * 0.67 * 0.50 = 64.3 -- the two documented late-chain nerfs applied to the OLD ba... |
| `electro_dragon` | chain_range_tiles | 3.0 | 4.0 | The sim uses a GLOBAL constant _CHAIN_TILES = 3.0 (engine.py), whose comment states the arc range is 'not published by the wiki'. That premise is FALS... |
| `electro_spirit` | chain_range_tiles | 3.0 | 4.0 | A second, independent page giving the same 4-tile arc, which is what makes the engine comment's 'not published by the wiki' claim clearly wrong. Pairs... |

---

## 7. floor() vs round() convention on derived DPS

**Rows:** 10  |  **Recommendation:** One ruling covers all of them: adopt the wiki's floor().

e.g. goblins 125/1.1 -> floor 113 (what the wiki renders) vs the sim's 114. Each is off by one and harmless alone, but the convention should match the game's.

- [ ] Accept recommendation for all 10
- [ ] I want to go row by row

<sub>families: troops_b 10</sub>

| card | field | sim has | wiki says | why |
|---|---|---|---|---|
| `goblin_demolisher` | dps | 155 | 169 | Dependent on the hit_speed ruling above: 186/1.1 = 169.1 -> 169. The current 155 = floor(186/1.2) matches the wiki's rendered L11 DPS, which is comput... |
| `goblin_machine` | dps | 177 | 192 | Two separate problems in one field. (a) It trails the damage ruling: 231/1.2 = 192.5 -> 192. (b) Even on today's published numbers 177 is wrong: floor... |
| `goblins` | dps | 114 | 113 | floor(125/1.1) = 113 and the wiki renders 113; 114 is a round(). Escalating rather than auto-updating: engine.py line 524 lets a present `dps` overrid... |
| `golem` | dps | 125 | 124 | floor(312/2.5) = 124 and the wiki renders 124; 125 is a round(). Same engine caveat as goblins.dps -- adopting 124 would give hit_dmg 310 against a tr... |
| `ice_golem` | dps | 34 | 33 | floor(84/2.5) = 33; 34 is a round(). Same engine caveat as goblins.dps. |
| `inferno_dragon` | dps | 88 | 87 | floor(35/0.4) = 87; 88 is a round(). This is stage-1 of the ramp only (damage_stages [35,120,422] all verified matching). Same engine caveat as goblin... |
| `lava_hound` | dps | 41 | 40 | floor(53/1.3) = 40 and the wiki renders 40; 41 is a round(). Same engine caveat as goblins.dps. |
| `magic_archer` | dps | 121 | 113 | Two problems stacked. (a) On today's published damage, floor(133/1.1) = 120 and the wiki renders 120; 121 is a round(). (b) If the damage ruling above... |
| `mega_knight` | dps | 158 | 157 | floor(268/1.7) = 157 and the wiki renders 157; 158 is a round(). Same engine caveat as goblins.dps. Everything else on this card verified clean, inclu... |
| `mini_pekka` | dps | 472 | 471 | floor(755/1.6) = 471 and the wiki renders 471; 472 is a round(). Same engine caveat as goblins.dps. Independent of the hitpoints question above -- dam... |

---

## 8. The data is agreed; the decision is a SCHEMA or ENGINE change

**Rows:** 6  |  **Recommendation:** Defer to Phase I implementation — no data decision needed now.

The sim's schema cannot hold the real shape (e.g. three_musketeers' second melee attack mode; electro_dragon_evo's 'full damage for 3, reduced for the rest').

- [ ] Accept recommendation for all 6
- [ ] I want to go row by row

<sub>families: troops_c 2, troops_a 1, spells 1, champions 1, xc_spawn_anchor 1</sub>

| card | field | sim has | wiki says | why |
|---|---|---|---|---|
| `little_prince` | ramp_move_grace_s | None | 4/8/2026: Little Prince will now maintain his charged-up Hit Speed for up to 0.3 seconds while moving | NEW MECHANIC the sim does not model. engine.py resets ramp_shots on movement with no grace window (and the 14/12/2023 entry fixed a bug where the ramp... |
| `rage` | attacks | ['buildings'] | air, ground | IMPORT BUG. attacks:['buildings'] looks like the Target cell 'Friendly Troops & Buildings' mis-parsed into the sim's attacks schema, where it means 't... |
| `dark_prince` | charge_splash_radius_tiles | 2.2 | 1.2 | current_db 2.2 is roughly double every published figure. P2's charge Splash Radius column reads 1.1; the history walk lands at 1.2, because the 2/9/20... |
| `ram_rider` | slow_duration_s | None | 2.0 | PRIORITY / MISSING FIELD. slow_pct -70 is present but the KB carries no duration, so the engine cannot know the snare lasts 2 s. PATHS PUBLISHING: P2 ... |
| `three_musketeers` | damage | None | melee 314 / ranged 204 | THE 3/11/2025 REWORK IS NOT MODELLED. History: '*On 3/11/2025, a Balance Update, reworked the Three Musketeers so that it now spawns three different t... |
| `<levels.py>` | base_for vs rarity ladders | REF_LEVEL=11 + PERCENT table | - | THE 'CHECK base_for AGAINST FULL WIKI LADDERS PER RARITY' TASK CANNOT BE DONE THE OBVIOUS WAY, and the reason matters. The wiki does not PUBLISH per-l... |

---

## 9. The wiki page contradicts ITSELF

**Rows:** 6  |  **Recommendation:** Review — or settle by checking in-game.

Prose, table and history give different answers on one page. Fisherman's slow is the worst: prose says 35%, one history entry says -30%, another removes it entirely.

- [ ] Accept recommendation for all 6
- [ ] I want to go row by row

<sub>families: troops_c 2, troops_a 1, spells 1, evos_a 1, xc_crown 1</sub>

| card | field | sim has | wiki says | why |
|---|---|---|---|---|
| `inferno_dragon_evo` | ramp_keep_s | 9.0 | 7.0 | CURATED verified:true (9.0) so flagged, but three independent sources say 7 s and the change is dated 1/6/2026 -- and note the Evo page's own INTRO PR... |
| `royal_delivery` | spawn_damage | 437.0 | 133 | Mirror of the damage row -- the two fields are swapped. Whatever the owner decides about the 12% cut, `spawn_damage` should hold the Recruit-side numb... |
| `fisherman` | slow_duration_s | 1.5 | removed | The 6/4/2026 entry removes the slow outright, but THE PAGE CONTRADICTS ITSELF THREE WAYS: the intro prose still describes 'slow their movement and att... |
| `phoenix` | spawn_interval_s | 3.8 | 4.3 | UNRESOLVED, needs an owner ruling. The revision trail contradicts the History entry in BOTH directions: the Spawn Speed cell read 4.3 sec continuously... |
| `royal_ghost` | invisibility_time_s | 1.8 | 2.0 | CLEAN 2-of-3 against current_db, and the two paths ARE independent here: invisibility has no vardefine, so P2 is the table cell itself rather than a v... |
| `cannon_evo` | volley_crown_damage | 89 | 76 | LOW CONFIDENCE -- OWNER DECISION, NOT A MIX-UP. The field mapping is CORRECT: bar_dmg_11=304 -> volley_damage and bar_crown_dmg_11=89 -> volley_crown_... |

---

## 10. Sources genuinely disagree and no 2-of-3 majority formed

**Rows:** 22  |  **Recommendation:** Review individually — these are the only ones that truly need your judgement.

No automated rule can settle these. Each row shows all three readings.

- [ ] Accept recommendation for all 22
- [ ] I want to go row by row

<sub>families: troops_b 5, evos_a 5, troops_c 4, buildings 3, champions 3, troops_a 1, evos_b 1</sub>

| card | field | sim has | wiki says | why |
|---|---|---|---|---|
| `bomb_tower` | load_time_s | 1.1 | 0.5 | current_db 1.1 has no wiki support; the attribute table's First Hit Speed column publishes 0.5. The value originates in icebow/config/card_mechanics.j... |
| `mortar` | load_time_s | 4.0 | 1.0 | current_db 4.0 versus the table's First Hit Speed of 1 sec - a 3-second gap on a siege building, which decides whether a Mortar gets a shell away befo... |
| `tesla` | load_time_s | 0.7 | 0.5 | The attribute table's First Hit Speed column says 0.5, and it says 0.5 in the pre-change revision 436245 too, so it is not a lagging cell. current_db ... |
| `mighty_miner` | ability_bomb_radius | 2.5 | no radius figure in any dated entry | conflicts.md C2 RECONFIRMED against the live revision: NULL on all three paths -> escalate per the missing-value rule. The sim's 2.5 tiles remains an ... |
| `mighty_miner` | damage_stages[1] / damage_ramp.damages[1] | 204 | {{Balance|Buff}}[[Mighty Miner]]: Base Damage +8% -> 204 (base-only reading) or 204 x 1.08 = 220.3 -> 221 (all-stages reading) | AMBIGUOUS, do not auto-write. "Base Damage +8%" may mean the stage-1 figure only, or the single underlying base that all stages derive from. Evidence ... |
| `mighty_miner` | damage_stages[2] / damage_ramp.damages[2] | 409 | {{Balance|Buff}}[[Mighty Miner]]: Base Damage +8% -> 409 (base-only) or 442 (all-stages) | Same ruling as damage_stages[1]; the two must be decided together. |
| `cannon_evo` | attacks | ['ground'] | Ground (turret) / Air & Ground (barrage) | attacks:[ground] is right for the Cannon's own turret and WRONG for its deploy barrage, which the Card Evolution page says hits air and ground. One ro... |
| `executioner_evo` | hit_speed | 2.4 | 2.4 | WIKI-INTERNAL CONFLICT, recorded rather than resolved: the same page states 2.4 s (vardefine, and the DPS column computed from it) and 0.9 s (attribut... |
| `furnace_evo` | spawn_interval_s | 7.0 | 5.0 | Three History witnesses (Evo page, base page, Version History) say the IDLE spawn period is now 5 s; both attributes tables still say 7 s. Recommend 5... |
| `furnace_evo` | range_tiles | 6.0 | 5.5 | Same shape as spawn_interval: three dated History witnesses say 5.5, both tables still say 6. Recommend 5.5 for furnace_evo and base furnace. |
| `goblin_barrel_evo` | decoy_goblin.hitpoints | 81 | 81 | UNRESOLVED CONFLICT, and worth the owner's eye precisely because the sibling damage claim on the same Card Evolution line checked out perfectly. Here ... |
| `mortar_evo` | dps | 66 | post-4/8/2026 derived: 266/4.7 = 56.6 | Dependent on hit_speed: if 4.7 is accepted, dps drops 66 -> ~57. Damage itself (266) matches on all paths. |
| `ghost_souldier` | invisibility_time_s | 1.8 | 2.0 | Genuine split. P2 (both the parent table and the Souldier table) says 1.8; P3 says 2. The P3 wording is self-contradictory -- 'decreased ... to 2 seco... |
| `giant_skeleton` | collision | 1.0 | 0.75 | Only P3 carries a collision number (there is no attributes-table column for it). Recommend 0.75. Two reasons to take it seriously: (a) the other three... |
| `giant_skeleton` | load_time_s | 1.1 | 1.0 | Frozen-dump field (card_mechanics.json, 2023-10-18), not a wiki field. The wiki's First Hit Speed column supports the identity load_time_s = hit_speed... |
| `goblins` | load_time_s | 0.7 | 0.5 | Same frozen-dump case as goblin_gang (identical 'Goblin' character row). Wiki FHS 0.6 against hit speed 1.1 -> 0.5. Recommend 0.5, ruled together with... |
| `guards` | load_time_s | 0.6 | 0.5 | Frozen-dump field. Wiki Guard attrs give hit speed 1.0 / First Hit Speed 0.5 -> 0.5; dump says 0.6. Recommend 0.5. |
| `hunter` | load_time_s | 1.4 | 1.5 | Frozen-dump field. Wiki gives hit speed 2.2 / First Hit Speed 0.7 -> 1.5; dump says 1.4. Recommend 1.5. Checked and CLEARED separately: hunter.dps 38 ... |
| `phoenix` | egg.hatch_s | 3.8 | 4.3 | Duplicate carrier of the identical fact -- phoenix.egg.hatch_s and phoenix.spawn_interval_s both hold the egg lifetime, so they must move together wha... |
| `ram_rider` | hit_speed | 1.8 | 1.7 | LIKELY A HISTORY ERROR, NOT A LAG -- the opposite conclusion to the hitpoints line above, and the time machine is what separates them. The Hit Speed c... |
| `skeleton_barrel` | death_spawn_delay_s | 0.5 | 0.5 (Skeleton Attributes) / 0.6 (Skeleton Container Attributes) | LOW PRIORITY / AMBIGUITY ONLY -- no change recommended. The page exposes two different 'Deploy Time' cells that could each map to this one KB field: 0... |
| `spirit_empress_air` | damage | 307 | 309 | Same 307-vs-309 question as the ground form; both rows curate 307 and must move together. |

---

## 11. No source publishes the value ANYWHERE

**Rows:** 21  |  **Recommendation:** Keep the sim's current value, mark it `unsourced: true`, and measure in-game when convenient.

The sweep looked on all three paths and found nothing. Mighty Miner's bomb radius (2.5) is the flagship case. Leaving them flagged is honest; silently keeping them is what produced the 'not published in the KB' comments that turned out to be false.

- [ ] Accept recommendation for all 21
- [ ] I want to go row by row

<sub>families: troops_a 13, buildings 2, troops_b 1, spells 1, xc_crown 1, evos_a 1, evos_b 1, xc_spawn_anchor 1</sub>

| card | field | sim has | wiki says | why |
|---|---|---|---|---|
| `goblin_cage` | sight | 20.0 | - | No wiki support on any path - the cage's table has no range or sight column. 20.0 is exactly the lifetime (20 s) and exceeds the arena width, so it lo... |
| `inferno_tower` | load_time_s | 1.2 | - | Null on all three paths: this page's attribute table has NO First Hit Speed column, no vardefine covers it, and no history entry names a first-hit cha... |
| `elite_barbarians_evo` | javelin_damage | 284 | - | FULL RE-SOURCE, as instructed. NULL ON ALL THREE PATHS: the 284 is still sourced only from the release announcement that cards.yaml quotes, and nothin... |
| `minion_horde_evo` | first_hit_immune_s | 3.0 | - | Curated 3.0 (2026-08-14 sweep quoted 'invincible for 3 seconds'); today's page says only 'briefly invincible' -- the number is no longer published any... |
| `poison` | radius_tiles | 3.5 | - | NULL ON ALL PATHS. The Poison page has NO unit-attributes-table (verified: zero occurrences of that id in the wikitext), no radius vardefine, and no r... |
| `balloon` | knockback_tiles | 1.0 | - | NULL ON ALL THREE PATHS. Neither attributes table has a knockback/pushback column, no vardefine carries one, and no history entry on the page mentions... |
| `barbarians` | _row_audit:verified_false | False | - | PRIORITY FLAG (verified:false row), not a discrepancy in itself. Re-sourced today: hitpoints 691, damage 191, hit_speed 1.4 (the 2/3/2026 entry sets 1... |
| `bats` | _row_audit:verified_false | False | - | PRIORITY FLAG (verified:false row), not a discrepancy in itself. Re-sourced today: hitpoints 81, damage 81, dps 62, count x5, range 1.2, speed Very Fa... |
| `battle_healer` | _row_audit:verified_false | False | - | PRIORITY FLAG (verified:false row), not a discrepancy in itself. Re-sourced today: hitpoints 1920, damage 268, hit_speed 2.0, dps 134, range 1.6, spee... |
| `berserker` | _row_audit:verified_false | False | - | PRIORITY FLAG (verified:false row), not a discrepancy in itself. Re-sourced today: hitpoints 896, damage 102, hit_speed 0.6 (P1+P2, and the 6/10/2025 ... |
| `bowler` | _row_audit:verified_false | False | - | PRIORITY FLAG (verified:false row), not a discrepancy in itself. Re-sourced today: hitpoints 2081, damage 289, hit_speed 2.5, dps 116, attack range 4,... |
| `cannon_cart` | _row_audit:verified_false | False | - | PRIORITY FLAG (verified:false row), not a discrepancy in itself. Re-sourced today: hitpoints 1809, damage 212, hit_speed 0.9, dps 236, range 5.5, proj... |
| `dart_goblin` | _row_audit:verified_false | False | - | PRIORITY FLAG (verified:false row), not a discrepancy in itself. Re-sourced today: hitpoints 261, damage 156, hit_speed 0.8 (the 4/8/2025 entry sets 0... |
| `electro_giant` | _row_audit:verified_false | False | - | PRIORITY FLAG (verified:false row), not a discrepancy in itself. Re-sourced today: hitpoints 3952 (the 6/7/2026 +3% is applied), damage 163, range 1.2... |
| `electro_spirit` | _row_audit:verified_false | False | - | PRIORITY FLAG (verified:false row), not a discrepancy in itself. Re-sourced today: hitpoints 215 (the 4/8/2026 -6% is applied), damage 99, range 2.5, ... |
| `elite_barbarians` | _row_audit:verified_false | False | - | PRIORITY FLAG (verified:false row), not a discrepancy in itself. Re-sourced today: hitpoints 1341, damage 384, hit_speed 1.4, dps 274, count x2, range... |
| `fire_spirit` | _row_audit:verified_false | False | - | PRIORITY FLAG (verified:false row), not a discrepancy in itself. Re-sourced today: hitpoints 215 (the 4/8/2026 -6% is applied), damage 207, range 2.5 ... |
| `flying_machine` | _row_audit:verified_false | False | - | PRIORITY FLAG (verified:false row), not a discrepancy in itself. Re-sourced today: hitpoints 614, damage 171, hit_speed 1.1, dps 155, range 6, project... |
| `lumberjack_ghost` | hitpoints | 4000 | - | No path publishes a hitpoint value: the Ghost Attributes table has no Hitpoints column and there is no ghost_hp vardefine, because the page states the... |
| `royal_delivery` | crown_tower_damage | 40 | - | UNSOURCED, AND MEASURED AGAINST THE WRONG NUMBER. The live page (revid 437384) carries no crown data of any kind -- no vardefine, no column, no histor... |
| `furnace_evo` | lifetime_s | 28.0 | - | A 2023 GAME-FILE BELIEF IS OUTLIVING THE LIVE WIKI -- via the merge order, not via curation. MEASURED: build_spec(db,'furnace_evo',11) returns lifetim... |

---

## 12. Two sweep agents claimed the same field and disagreed

**Rows:** 13  |  **Recommendation:** Apply the merge's pick (more sources wins); listed here for transparency.

Not a data problem — a process one. Shown so a disagreement can't hide.

- [ ] Accept recommendation for all 13
- [ ] I want to go row by row

<sub>families: xc_crown 3, evos_a 3, buildings 2, spells 2, troops_b 1, troops_c 1, xc_spawn_anchor 1</sub>

| card | field | sim has | wiki says | why |
|---|---|---|---|---|
| `elixir_collector` | lifetime | 70 | 93 | The curated lifetime:70 (also flagged '# VERIFY') is the PRE-4/4/2022 value (70 -> 65 -> 86 -> 93). All three paths agree on 93. Note the same row ALR... |
| `tombstone` | spawns.interval | 3.5 | 3.5 | CURATION CONFIRMED CORRECT, and its stated reasoning verified verbatim on the live page. A curated verified:true value intentionally contradicting the... |
| `goblin_cage_evo` | hitpoints | 1080 | 780 | THE SPAWNED-UNIT SUBSTITUTION THE BRIEF WARNED ABOUT, caught in this group. goblin_cage_evo's hitpoints 1080 / hit_speed 1.1 / dps 306 are the GOBLIN ... |
| `goblin_cage_evo` | hit_speed | 1.1 | 1.0 | Same root cause as the hitpoints row and recorded separately because it is a separately dated fact: the cage's trap attack has been 1.0 s since 8/10/2... |
| `goblin_cage_evo` | damage | 337 | 367 | The 4/8/2026 edit applied the cycles half of the change and not the DPS half -- provable, because the same editor touched the same table on 2026-08-11... |
| `goblin_curse` | damage | 120 | 35 | SPAWNED-UNIT STATS SUBSTITUTED FOR THE SPELL -- the largest numeric error in this group. The statistics table's 'Area Damage' column is rendered from ... |
| `rocket` | crown_tower_damage | 342 | 341 | OFF BY ONE AGAINST ITS OWN PIN. The pin registry says 341 and the owner's own tool says 341; cards.yaml has 342 with the comment '# post-1/6/2026 (see... |
| `lumberjack_ghost` | crown_tower_damage | None | 1/6/2026 decreased the Ghost's Tower Damage by 50% | The KB row has no crown_tower_damage, so the ghost currently hits crown towers for its full 256 -- exactly double what the game does. All three paths ... |
| `phoenix_egg` | hitpoints | 239 | 317 | Two separate problems in one field. (a) current_db 239 vs wiki 240 is a stale off-by-one: cards.yaml's own comment says '239 hp at level 11 per the wi... |
| `firecracker_evo` | spark_dps_small | 60 | 48 | KNOWN CASE -- CONFIRMED, AND THE DIAGNOSIS SHARPENS. 60 is not a mis-scaled 48. 60 = Small_Crown_dmg_11(15) / spark_atk_speed(0.25), exactly the wiki'... |
| `giant_skeleton` | death_crown_mult | 2.0 | - | UNSOURCED, AND POINTING THE WRONG WAY. The page (revid 436713) has no crown vardefine, no crown column and no crown history line. Everything else on t... |
| `zap_evo` | crown_tower_damage | 58 | 48 | THE OWNER PIN LANDED ON THE PARENT AND MISSED THE EVOLUTION. zap.crown_tower_damage = 48 = round(192*0.25), correct post-1/6/2026. zap_evo.crown_tower... |
| `spear_goblins` | hit_speed | 1.7 | 1.6 | THE CONTAMINATION RUNS BOTH WAYS, and this is the one instance that leaked. The KB holds 1.7, which is the GOBLIN HUT page's copy of the Spear Goblin,... |

---

## 13. Field-name collisions / snapshot hygiene

**Rows:** 2  |  **Recommendation:** Cosmetic; apply with the rest.

No gameplay effect.

- [ ] Accept recommendation for all 2
- [ ] I want to go row by row

<sub>families: champions 2</sub>

| card | field | sim has | wiki says | why |
|---|---|---|---|---|
| `goblinstein` | range_tiles (card level) | 5.5 | none | SNAPSHOT HYGIENE, not a wiki conflict. The card-level goblinstein row mixes the two bodies: hitpoints 2393 / damage 128 / hit_speed 1.5 are the MONSTE... |
| `little_prince` | royal_rescue_damage | 0 | 17/6/2024 Royal Rescue damage -48.1%; 3/6/2025 +11%; 1/9/2025 +11% | NAMING COLLISION worth an owner ruling. The KB field charge_damage: 0 is a deliberate curation meaning "he has no Prince-style charge attack", and tha... |

---

## 14. Uncategorised leftovers

**Rows:** 2  |  **Recommendation:** Review individually.

Only the rows no rule matched.

- [ ] Accept recommendation for all 2
- [ ] I want to go row by row

<sub>families: troops_b 1, xc_crown 1</sub>

| card | field | sim has | wiki says | why |
|---|---|---|---|---|
| `lumberjack_ghost` | ghost_life_s | 5.0 | 5.5 | The ghost's lifetime is defined by the mechanic as the Rage pool's duration ('his invisible Ghost seeks vengeance as long as it's in a pool of Lumberj... |
| `firecracker_evo` | spark_dps_large | 192 | 48 | 192 = Small_dmg_11(48)/0.25, the wiki's single 'Spark Damage per second' column -- not a large-spark figure. Big and Small sparks deal the SAME per-ti... |

---
