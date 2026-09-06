# Engine observation schema audit (L63)

Read-only audit, 2026-09-05. Citations are file:line. Items marked (inferred) were not read directly.

## 1. Engine observation schema

### 1.1 Where it comes from
- `NativeRoyaleEnv.observe()` = RPC `{"op":"observe"}` -> `state`, then `_enrich_state` (research/ext/cr-native-sandbox/native_core/env.py:187-189).
- `observe_compact()` = RPC `observe_compact_v1`, contract-checked: `schema_version==1`, `kind=="libg_native_compact_state_v1"`, `coherent is True`, `entities` list, `players` list of len 2, `episode` mapping (env.py:191-204).
- The raw dict is produced by the native host (libg.so read via /proc/self/mem, research/CR_NATIVE_SANDBOX_ASSESSMENT.md:62-64); the Python side only ADDS keys. Fields marked (native) below are asserted by contract checks or read by callers, not defined in Python.

### 1.2 Top-level keys of a full observation (env.py:206-255 + trace contract env.py:614-625)
| key | type | source |
|---|---|---|
| `tick` | int, engine tick (20 Hz: `tick_seconds 0.05`, scripts/accept_match_rules.py:97) | native |
| `elapsed_seconds` | float = tick*0.05 | added env.py:208 |
| `coherent` | bool | native |
| `state_hash` (str), `state_hash_scope` ("public-observe-v6"), `state_hash_certificate` | native (env.py:621-623) |
| `players` | list[2] of player dicts | native + enriched |
| `entities` | list of entity dicts | native + enriched |
| `projectiles` | list (native; contract-checked only in the trace path, env.py:694-715, but `record_full` reads it from plain `observe()` too, replay_drive.py:326) |
| `effects` | list (read by replay_drive.py:328; not contract-checked anywhere in env.py) |
| `episode` | mapping: `terminated`, `outcome`, `winner`, `crowns` [s0,s1], `crowns_by_side` {0:..,1:..} (added env.py:257-265), `termination_reason`, `terminal_tick`, `crown_towers` list (replay_drive.py:398-404) |
| `schema_version`, `kind` | only asserted for the compact op (env.py:195-196) |

Match schedule (scripts/accept_match_rules.py:96-99): regulation 3600 ticks (180 s), overtime 2400 ticks, total 6000, double elixir at tick 2400, triple at 4800. **There is no explicit `overtime` flag in the observation** -- overtime = `tick > 3600` (inferred from the schedule; the observed replay terminates at tick 6085 by `native_tiebreak_hp_drain`, ext/batch_v2/replay_000YLY0JCPGL.json `final`).

### 1.3 Player dict (env.py:212-233)
| field | type | note |
|---|---|---|
| `side` | int 0/1 | native |
| `elixir` | number (native; fallback in replay_drive.py:319) |
| `elixir_raw` | int, elixir*10000 (native) |
| `elixir_exact` | float = elixir_raw/10000, e.g. 9.9338 | added env.py:215 |
| `hand_deck_indices` | list[4] of deck index 0..7 (-1 = empty slot) | native |
| `cycle_deck_indices` | list[4] deck indices of the queue, front-first | native (env.py:628) |
| `next_deck_index` | int | native (env.py:629) |
| `refill_timer` | int | native (env.py:630) |
| `hand` | list of {hand_index, deck_index, card_id, level, form_flags, has_evolution, has_hero, name} | added env.py:222-232 from the deck the CALLER passed in (`self.decks`): the hand card `level` is the configured level, not read from memory |

Both players' hands, queues and exact elixir are visible (server-side state; no fog of war).

### 1.4 Entity dict (env.py:234-254, trace contract env.py:632-693)
| field | type | note |
|---|---|---|
| `side` | int 0/1 | |
| `x`, `y` | int engine units; 1000 units = 1 tile; x in [0,18000), y in [0,32000) (CR_NATIVE_SANDBOX_ASSESSMENT.md:28,62,99) | measured in batch_v2 frames: x 0..17750, y 250..31500 |
| `card_id` | int native card id; -1 for crown towers (recorded name '-1') | |
| `native_card_id`, `base_card_id`, `form_name`, ... | added env.py:249-251 via `observed_card()` (evolution/hero forms fold to a base id) |
| `name` | str display name from the live card catalog, e.g. 'Skeletons', 'Xbow', 'HogRider' | added env.py:252-254 |
| `hp`, `max_hp` | int | e.g. king 4824, princess 3052 at the batch level |
| `kind` | int (native). Seen in recordings: 12/13 on towers AND buildings (Cannon/Tesla/Xbow), 14/15 on troops; 14 at spawn (tick 221) and 15 later -> (inferred) `kind` is a behaviour/lifecycle state code, NOT a unit class. Not decoded anywhere in the repo. |
| `category` -> `entity_id` | int, libg generation key (5,000,000 + creation ordinal), stable per entity | added env.py:238 |
| `generation_key`, `creation_ordinal` | ints (trace contract env.py:648-655) |
| `ability_state_code` -> `ability_state_name` | int -> str via ABILITY_STATE_NAMES (env.py:42-56) |
| `level` | claimed by the assessment (line 63) but NOT read by any repo consumer; unverified in any recording |
| `behavior_state` | int; 10 = casting (scripts/accept_native_card_forms.py:121) |
| `target_previous_x/y`, `movement_direction_x/y`, `collision_accumulator_x/y`, `collision_count`, `avoidance_offset`, `path_segment_direction_x/y`, `path_node_consumed`, `path_nodes` (<=115 ints), `pending_damage`, `event_timer_ms`, `attack_progress_ms`, `attack_load_timer_ms` | trace-path ("rich") only, env.py:632-690; whether plain `observe()` carries them is not established (inferred: no -- the trace contract exists to require them). No explicit target entity-id field was found. |

Crown towers appear BOTH as entities (card_id -1, name '-1', kind 12 king / 13 princess) AND in `episode.crown_towers` as {side, type 'king'|'princess', lane null|'left'|'right', x, y, hp, max_hp, destroyed} (replay_drive.py:323-324, 402-403). A destroyed tower may drop out of the list (L62/engine_env.py:188-190 treats absence as 0 hp).

### 1.5 Projectile / effect dicts
Projectile (trace contract env.py:700-713): `generation_key, side, x, y, x2, y2, card_id, target_x, target_y` ints + `vtable_rva`. Effect: at least `side, x, y, card_id` (replay_drive.py:328-329). Recorded example (ext/replay_00LYPLJLC80L_run1.json, record_every=1, record_full=True, 5268 frames): projectile `[1, 14335, 23408, 13887, 18164, '-1']` = [side, x, y, target_x, target_y, name]; effect `[1, 3468, 25202, '-1']`. Tower projectiles/effects carry card_id -1; entries like `[0, 1500, 15000, 1500, 15000, 'Cannon']` sit at building positions with target == self (inferred: building attack effects).

### 1.6 Coordinate frame / tick / sides (measured)
- Units: 1000 per tile; board 18 tiles wide (x 0..18000) x 32 tiles long (y 0..32000). Tower centres (batch_v2 frame 0): side 0 king (9000,3000), princesses (3500,6500),(14500,6500); side 1 king (9000,29000), princesses (3500,25500),(14500,25500). **Side 0 = low y = bottom half; side 1 = high y = top**; +y runs from side 0 towards side 1; origin is side 0's corner.
- `orientation` string stored in every batch record: "side0 low rows / side1 high rows (matches RoyaleAPI red/blue)" (replay_000YLY0JCPGL.json). Blue/red is NOT a fixed side: icebow's own side is `entry["icebow_side"]` (L62/engine_env.py:290) and the trainer MIRRORS side 1 into side 0's frame (X,Y = 18000-x, 32000-y; engine_env.py:151-167).
- Tick: 20 Hz (0.05 s), same clock as the RoyaleAPI plays CSV (CR_NATIVE_SANDBOX_ASSESSMENT.md:97). `tick_after_reset` = 10.
- Elixir: exact to 1e-4.

### 1.7 Recorded frame formats (replay_drive.py:317-330; L61/replay_drive_rec.py:325-336)
Compact frame (`record_every=N`; batch_v2 uses N=20, 364 frames/match): keys `tick, elixir[2], entities[[side,x,y,name,hp,max_hp]], towers[[side,type,lane,x,y,hp,max_hp]]`.
Full frame (`record_full`, or every `play_frames` entry): adds `kind` as entities[6], plus `projectiles[[side,x,y,target_x,target_y,name]]`, `effects[[side,x,y,name]]`. `play_frames` (L61 recorder, replay_drive_rec.py:382-384) additionally carry `play_index, side, card, x, y` (the pro's play) and `players[{side, elixir, hand[4 names], hand_pos[4], cycle_pos[4], next}]`.
Example play_frame top-level keys: `['tick','elixir','entities','towers','projectiles','effects','play_index','side','card','x','y','players']`.
Example entity (batch_v2, tick 221): `[1, 8421, 30935, 'Skeletons', 81, 81, 14]`.
Example raw `observe()` entity DICT: none exists on disk (grep `hand_deck_indices` over scratchpad/gauntlet/**/*.json: no hit) -- only the list-encoded frames above; the dict keys are those in 1.4.

## 2. Training obs builder(s): engine board -> BC v2 dataset

### 2.1 The builder
`scratchpad/gauntlet/L61/build_bc_v2.py` (reuses L60's `build_bc_dataset.py` for stages/keys). Input: `scratchpad/gauntlet/ext/batch_v2/replay_<tag>.json` from `L61/replay_drive_rec.py` (full `play_frames` before every driven play + compact drift frame every 20 ticks). Output: `icebow/data/bc_pro_v2/dataset.npz` (+ meta.csv, split.json, report.txt, name_stats.json).

Pipeline (build_bc_v2.py:109-158 `frame_to_engine`, 204-323 `assemble_tag`):
1. Frame list-entities -> `FakeUnit(spec, team, x, y, hp, deploying)` + `FakeEngine(t, units, towers, elixir)` duck-typing the sim engine (build_bc_v2.py:73-97).
2. The FakeEngine is swapped into a real `clashrl.sim.env.SimMatchEnv` (`env.eng = eng`; build_bc_v2.py:233-237) and `env._update_vectors()` (icebow/src/clashrl/sim/env.py:613-624) renders hand/next/elixir/threat vectors + the image exactly as the sim/PPO trainer does. So the v2 dataset's observation IS the sim observation, fed with engine truth.
3. Only frames where `fr["side"] == focus_side` (the icebow player) and `entry["accepted"]` are emitted as samples (build_bc_v2.py:247, 262). Drift frames only advance the env's history (canvas stack, threat velocity, opponent memory).

### 2.2 Coordinate transform engine -> policy (build_bc_v2.py:111-119; L62/engine_env.py:151-167)
- `mirror = (focus_side == 1)`; if mirror: `X,Y = 18000-x, 32000-y`.
- `nx = X/18000`, `ny = 1 - Y/32000`  -> policy frame: **"me" = team 0 = bottom = ny near 1.0, enemy = top = ny near 0**, river at ny 0.5.
- Sides: `team_of(side) = (1-side) if mirror else side` (build_bc_v2.py:118-119).
- Tower slots: princess `x<0.5` -> index 0 (L), else 1 (R); king -> 2; towers ABSENT from the engine list are re-created at fixed anchors with hp 0 (destroyed) (build_bc_v2.py:105-107, 121-135).

### 2.3 Which engine fields are USED vs DROPPED
Used: entity `side, x, y, name, hp, max_hp (hp only; max_hp is read but unused by FakeUnit), kind` (kind only as `deploying = kind in (12,14)`, build_bc_v2.py:151); `towers` (side, type, x, y, hp, max_hp); `elixir[2]` (exact floats); `tick` (-> `t = tick*0.05`); `players[focus].hand` names (for the hand-consistency check only, build_bc_v2.py:255-261; the hand actually encoded comes from the sim's own cycle model seeded with the ENGINE queue from `V1.engine_queue(rec, focus_side)`, build_bc_v2.py:214-220 -> `hand_source` 'engine' or 'heuristic'); the pro's play `card, x, y` (label).
Dropped: `projectiles`, `effects` (counted into meta only: `n_projectiles`, `n_effects`), entity `card_id`/`entity_id`/`ability_state`, `level` (spec built at fixed level 11, build_bc_v2.py:189), `max_hp` of units, entity target/path fields, `elixir_raw`, opponent hand/queue (opponent memory block sees only recognised enemy units on the board, not the hidden hand), `crowns`/`outcome`, the opponent's `elixir` beyond a single mirrored scalar (see 2.6). Entities with `hp<=0` and crown-tower entities (`name=='-1'`) are skipped (build_bc_v2.py:143-146).
Unit identity: engine display name -> sim `cards.yaml` key via `_ALIAS_INV` + CamelCase->snake (build_bc_v2.py:44-69); unmapped names fall back to a generic knight spec (`__generic__`, build_bc_v2.py:148-150,183). report.txt: rows with n_units_unmapped>0 = 0 of 9444.

### 2.4 Tensor layout (measured from icebow/data/bc_pro_v2/dataset.npz)
| array | shape | dtype | range |
|---|---|---|---|
| `obs` | (9444, 96, 64, 12) HWC | uint8 | 0..255 |
| `hands` | (9444, 10) | float32 | one-hot of cards in hand (1.0 x4) |
| `nexts` | (9444, 10) | float32 | graded upcoming order: Next=1.0, 0.75, 0.5, 0.25 ... (clashrl/cycle.py:28-34) |
| `elixirs` | (9444, 1) | float32 | own elixir / 10 (sim/env.py:621); measured 0.103..1.0 |
| `threats` | (9444, 52) | float32 | 0..1 |
| `acts` | (9444, 3) | int64 | [card_id 0..9, gx 0..17, gy 0..23] |
| `grid` | (2,) | int64 | [18, 24] |
| `deck` | (10,) | str | tornado, tesla, tesla_evo, ice_wizard, x_bow, rocket, knight, knight_evo, the_log, skeletons (card_id = index) |

Image channels (H=96 rows = board y, W=64 cols = board x; `observation.arena_size [64,96]` config.yaml:183; count from `detect_obs.obs_in_channels`, detect_obs.py:102-110 = 3 + (6+3)x1 with `use_detector_canvas: true`, `use_predictive_canvas: true`, `use_hp_canvas: false`, `canvas_stack: 1`, config.yaml:258-299):
| ch | name | encoding | source |
|---|---|---|---|
| 0-2 | RGB synthetic arena (`view.render_obs`, sim/view.py:81-114) | grass fill, 1-px river row at oh//2, towers as 5x5 (princess) / 7x7 (king) blocks in you/enemy colour, each unit as a single pixel; colours domain-randomised per match (disabled in the builder: `env.domain_rand.enabled=False`, build_bc_v2.py:175) | towers+units x,y,team,hp>0 |
| 3 | enemy_ground | 255 in a radius-sized rectangle (spec.radius tiles -> px) around each ALIVE, FULLY DEPLOYED enemy ground troop (deploy_left>0 skipped, view.py:160) | |
| 4 | enemy_air | same, enemy flying | |
| 5 | enemy_building | same, enemy building or siege | |
| 6 | my_ground | my troop (air or ground) | |
| 7 | my_building | my building/siege | |
| 8 | spell | team-agnostic spell/AOE units | |
| 9 | enemy_predicted | ellipse at dead-reckoned t+1.0 s position (`predictive_canvas_dt_s 1.0`), intensity = detector conf (1.0) | interactions.mover_forecast |
| 10 | my_predicted | same, own units | |
| 11 | enemy_urgency | ellipse at CURRENT position, intensity = closeness-in-time to predicted target | |
(detect_obs.py:28-43, 220-247; view.py:117-127, 145-178). Measured non-zero fraction on 300 samples: ch3 0.0079, ch4 0.0007, ch5 0.0001, ch6 0.0041, ch7 0.0025, ch8 0.0003, ch9 0.0019, ch10 0.0026, ch11 0.0009 (sparse maps; RGB channels are dense).
No HP channel: `use_hp_canvas: false`, so unit hp enters the obs only through `hp<=0` filtering, the 16-dim threat block, and the tower vector.

### 2.5 Action space (icebow/src/clashrl/actions.py; config.yaml:498-510)
- `action.grid: [18, 24]` -> gw=18, gh=24, `n_cells = 432` (actions.py:159,196). The module docstring "18x32 = one cell per board tile" (actions.py:4) is STALE. Flat cell = `gy*18 + gx`; action = (card_id, gx, gy).
- Cell centre: `warp.board_to_frame((gx+0.5)/gw, (gy+0.5)/gh)` (actions.py:203), clamped to the frame arena band; in the sim the warp is identity (actions.py:198-200) but the grid is anchored to `arena_box [0.03,0.10,0.97,0.86]` so the 24 rows span 19.7 board tiles (rows 7.91..27.62) -> **row pitch 0.499 tiles, column pitch 1.026 tiles** (measured, HANDOFF.md:1948-1952, L62i). The dataset label snaps the pro's (nx,ny) to the nearest cell centre in tile metric (`nearest_cell`, build_bc_v2.py:197-201); `snap_dist_tiles` mean 0.383, max 0.833 (report.txt).
- Deploy mask (`deployable_mask`, actions.py:316-380): non-"anywhere" cards only rows `gy >= min_own_gy` (first row whose centre is below `deploy_board 0.53125` = river bottom + 1 tile, actions.py:174-177), minus `unplayable` cells (river-bank ledge columns 0/17 in the water band rows 14/32..18/32, back-row corners outside the king strip x 1/3..2/3, king platforms rows 1..4/32 from either end; actions.py:26-53) and own princess-tower footprints; pocket rules open one enemy lane-half when that princess is down. `anywhere` (rocket/miner) = every cell except those whose blast clips the enemy king (`no_king_mask`, actions.py:287-315).

### 2.6 Scalar/context features (the 52-dim `threats` + the three small vectors)
threat_vec = concat (sim/env.py:627-664): 
| slice | dims | content |
|---|---|---|
| [0:16] | 16 (`_THREAT_DIM`, env.py:34) | view.threat_vector (view.py:200-222): only [0..5] filled = enemy mass (sum min(1,hp/800)), count/6, biggest hp/3000, left-flag (cx<0.4), right-flag (cx>0.6), depth past river; [6..15] zero |
| [16:26] | 10 (IDENTITY_DIM, card_threat.py:186) | recognised-enemy role block: [0] any, [1] tank, [2] swarm, [3] flying, [4] siege/building, [5] win_condition, [6] building_targeting, [7] max depth, [8] approach velocity, [9] extrapolated depth (card_threat.py:274-296); in the builder computed from ground truth filtered to `observation.detector_cards` whitelist with `sim_detector_recall/precision` noise |
| [26:34] | 8 (OPP_MEMORY_DIM, card_threat.py:218) | opponent memory: [0:5] role flags seen, [5] = **our own elixir/10 substituted** (env.py:658 `mem[5] = eng.elixir[0]/10`; the sample shows 0.983 at index 31), [6] activity EWMA, [7] staging count |
| [34:46] | 12 (INTERACTION_DIM, interactions.py:27) | (value, urgency) x my 3 towers + x enemy 3 towers |
| [46:52] | 6 (TOWER_DIM, view.py:181-197) | HP fraction of (L, R, king) mine then theirs |
The opponent's exact elixir from the engine is NOT in the observation (it is in meta.csv `eng_elixir_them` only). Time/tick is NOT an input feature (used only for dt between frames and meta `seconds`); overtime/double-elixir has no feature.

### 2.7 Live engine PPO env (scratchpad/gauntlet/L62/engine_env.py)
Same path: `_frame_of(state)` (engine_env.py:171-185) reproduces the record_full list frame from a live `observe()` dict, then `V2.frame_to_engine` + `SimMatchEnv._update_vectors` (engine_env.py:270-284). Hand/cycle synced from the engine's `hand_deck_indices + cycle_deck_indices` (engine_env.py:257-268). The policy's cell is decoded back to engine units by the algebraic inverse (`cell_to_engine`, engine_env.py:154-161).

## 3. Hand-off fields: engine vs screen detector

Detector-side reference: `Detection` dataclass (icebow/src/clashrl/replay_mine.py:66-100): `cls` (one of 230 class names), `cx, cy, w, h` (normalised frame box), `conf`, `team` "mine"|"enemy"|"unknown" (inferred from HP-bar/body colour, replay_mine.py:75-79), `ground_cy` (shadow y for flyers), `bar_vote`, `body_vote`. Other live readers: own elixir from the bar's fill length (vision.py:427-445, fractional 0..10, ~1 pip resolution), princess-tower HP digits via a digit CNN (tower_hp.py:1-4, 191), troop HP fraction from the green bar above a DAMAGED unit (troop_hp.py:1-6), 1x/2x/3x elixir clock (clock.py:1-5), own hand via tray templates (hand_templates.py), own cycle by deterministic tracking (cycle.py), opponent elixir INFERRED from observed plays (opponent_elixir.py:1-5).

### 3.1 Engine gives, detector cannot plausibly give
| engine field | why not on screen |
|---|---|
| entity `hp`, `max_hp` exact ints (both sides) | live: troop HP only as a bar FRACTION and only once damaged; king-tower HP text not read (tower_hp reads princess numbers) |
| entity `card_id`/`base_card_id`/`form_name` exact identity; `entity_id` stable handle | detector gives a class + conf, no persistent id (perception tracker approximates) |
| entity `kind` (deploy/active state code), `ability_state_code`, `behavior_state`, `target_*`, `movement_direction_*`, `path_nodes`, `attack_progress_ms`, `pending_damage` | internal state |
| `projectiles` (side, x, y, x2, y2, target_x, target_y, card_id) and `effects` | not detected (detector has `*_aoe` classes for a few spells only) |
| opponent `hand_deck_indices`, `cycle_deck_indices`, `next_deck_index`, `refill_timer`, opponent `hand[].level` | hidden information in the real game |
| opponent `elixir_exact` (1e-4 resolution) | live only an inference (opponent_elixir.py) |
| own `elixir_exact` at 1e-4 | live ~fractional pip reading |
| exact `tick` (20 Hz), `state_hash`, `coherent` | live has wall-clock + clock.py phase only |
| `episode.crown_towers[].x,y,max_hp,destroyed`, `crowns`, `outcome`, `termination_reason` | live: tower alive/dead from HUD, outcome from banner OCR (outcome.py) |
| sub-metre positions (1/1000 tile) in board space | live: box centre in perspective frame space through `BoardWarp` (actions.py:55-150), shadow-corrected for flyers |

### 3.2 Detector gives, engine does not
| detector field | engine equivalent |
|---|---|
| `conf` per detection | none (truth) |
| `w, h` box size | none (engine has no sprite box; the sim uses `spec.radius` from the KB) |
| `team == "unknown"`, `bar_vote`, `body_vote` (uncertain team) | side is exact |
| `ground_cy` vs `cy` (sprite vs shadow) | engine x,y are ground positions already |
| distinct sub-spawn classes (`golemite`, `lava_pups`, `elixir_golemite`, `elixir_blob`, `royal_recruit`, `mother_witch_hog`) and `*_evo`, `*_hero`, `*_ability`, `*_aoe` classes | engine names the body by its PARENT CARD (see 4.3); evo/hero forms are folded to base by `observed_card` (env.py:249-254; `form_name` keeps the form) |
| damaged-only HP bar (absence = full) | engine hp always present |
| frame-space clutter (HUD, card tray, chat box) | n/a |
Nothing the detector reports is unavailable from the engine in substance; the differences are representation (frame vs board space, probabilistic vs exact).

## 4. Card / unit naming

### 4.1 Engine naming
Entities carry an int `card_id` (native, e.g. 26000000 = Knight; -1 = crown tower) and get a `name` = the live catalog's `display_name` for the BASE card (`CARD_NAMES`, env.py:37-40; `_enrich_state` env.py:249-254), e.g. 'Knight', 'Xbow', 'IceWizard', 'BarbLog', 'Log', 'AngryBarbarians'. Names are CamelCase internal display names, not RoyaleAPI slugs. Fallback when the form id is absent from `CARD_NAMES`: `form_name`, e.g. 'MergeMaiden_Mounted' (seen in name_stats.json). Catalog: research/ext/cr-native-sandbox/native_core/data/live_card_catalog.json (152 cards; 122 `standard_1v1 and not not_in_use and not not_visible`), fields card_id, internal_name, display_name, type, elixir, rarity, summon_character, evolution_form_id, hero_form_id (card_catalog.py:11-40).

### 4.2 Existing mappings
- RoyaleAPI slug <-> engine name: `SLUG_ALIASES` in research/sandbox_tools/replay_drive.py:62-112 (slug -> catalog internal name; `resolve_card`).
- Engine display name -> sim `cards.yaml` key (= detector base key): `_ALIAS_INV` + CamelCase->snake in scratchpad/gauntlet/L61/build_bc_v2.py:44-69 (`sim_key_for`). This IS the engine->detector-vocabulary map, because the detector's 230 classes (icebow/data/detect/classes.txt; config/detect_classes.yaml is the source, data.yaml:1) use the same base keys plus suffixes `_evo` (42), `_aoe` (20), `_hero`/`_ability` (40); 128 base classes. `card_threat.base_key` (card_threat.py:34-45) strips the suffixes.
- Icebow-deck-only map: `ENGINE_NAME` in scratchpad/gauntlet/L60/build_bc_dataset.py:35-37 (8 names).
- Recorded mapping actually applied to the v2 data: icebow/data/bc_pro_v2/name_stats.json `mapping` (101 distinct entity names seen, `unmapped_counts` = {}).

### 4.3 Coverage (computed: catalog display_name -> sim_key_for -> detector base set)
- 122 of 122 in-use catalog cards map to a detector base class; 0 unmapped.
- Of the 101 entity names seen in the v2 recordings, 1 has no detector base: 'MergeMaiden_Mounted' (-> sim key spirit_empress_air, no detector class).
- 6 detector base classes have NO catalog card: elixir_blob, elixir_golemite, golemite, lava_pups, mother_witch_hog, royal_recruit -- all sub-spawns. MEASURED on 120 batch_v2 recordings: the engine names sub-spawn bodies by the parent card, distinguishable only by `max_hp`: Golem {5120: 126, 1039: 28}, LavaHound {3581: 71, 215: 90}, ElixirGolem {1569, 762, 360}, Goblinstein {2385 monster, 721 doctor}, SkeletonArmy {81, 2}, Graveyard {81} (graveyard skeletons carry the spell's name), WitchMother {529} (the hog spawns were not seen). So a detector-class-level unit map from engine names needs a (name, max_hp) -> class rule for those 6 classes; name alone is not sufficient. The `summon_character` field in the catalog (e.g. Minions -> 'Minion') names the primary body only.
- The builder maps ALL of these to the parent card's spec (build_bc_v2.py:148-150), i.e. a golemite gets the Golem KB profile in the threat/identity blocks (inferred from the code path; not measured in the obs).

## 5. Caveats
- The raw native `observe()` dict was never dumped to disk in this repo; entity field names beyond those in 1.4 come from contract checks and callers, not from a printed example.
- `kind` value semantics (12/13/14/15) are inferred from recordings + the builder's `deploying = kind in (12,14)`; there is no decoder table in the repo.
- No repo file states an overtime flag; the phase is derived from `tick` against the schedule in accept_match_rules.py.

STATUS: complete
