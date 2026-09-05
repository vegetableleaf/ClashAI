# L62 -- ENGINE feed for the sim debugger (`sim_view.render_frame` on real-engine frames)

Code: `C:\Users\benpe\ClashBot\scratchpad\gauntlet\L62\engine_view.py` (one renderer, two feeds; sim_view.py NOT edited).
Outputs: `C:\Users\benpe\ClashBot\scratchpad\gauntlet\ext\engine_view\` (outside git).

## 1. Recording format (measured, before writing any code)

* batch_v2 compact recordings (213 files): `frames` every 20 ticks = 1.0 s (`tick, elixir[2], entities [side,X,Y,name,hp,max_hp,kind], towers [side,type,lane,X,Y,hp,max_hp]`),
  `play_frames` = a FULL observe (adds `projectiles`, `effects`, `play_index, side, card(slug), x, y, players[hand...]`) at every driven play.
* `replay_00LYPLJLC80L_run1.json` (record_full=True, record_every=1): 5268 frames, EVERY tick 10..5275, each with `projectiles` + `effects`; `play_frames` absent, plays come from `log` (93, all accepted).
* `projectiles` = `[side, X, Y, target_X, target_Y, name]`; `effects` = `[side, X, Y, name]`. MEASURED: in all 5268/5268 full frames `effects == [p[:3]+[p[5]] for p in projectiles]`
  -- the effect list is the projectile list minus the target, so there is NO separate effect shape to draw (nothing is lost by drawing projectiles only). Name `-1` = a crown-tower shot (1904 of the 4141 projectile-frames).
* `kind` codes, MEASURED on the full recording by following every played card for 45 ticks after its play tick:
  troops: kind 14 for ticks +1..+19, kind 15 from tick +20 (Hog, Knight, Skeletons, Ice Spirit, Ice Golem, Musketeer, Ice Wizard all identical);
  buildings: kind 12 for +1..+19, kind 13 from +20 (Tesla, Cannon). That is exactly a 1.0 s deploy time, so the L61 reading "kind in (12,14) = deploying" is now (a) MEASURED for a 1 s deploy on those 9 cards
  (it is still (b) untested for cards with other deploy times and for buildings whose kind may also flip while hidden/inactive -- Tesla shows 152 kind-12 frames across 1487 kind-13, consistent with ~7 deploys, not with underground time).
  King towers: kind 12 while INACTIVE, 13 once activated (side 1's king flipped 12->13 at tick 3125; side 0's at 5265). Princess towers are 13 throughout. So kind on a `-1` entity is a king-awake bit and the feed uses it for `Tower.active`.
* One anomaly seen: an Ice Wizard went 14 -> 15 at +21 then back to 14 at +25 (right after an enemy Ice Spirit was played) -- kind may ALSO encode "cannot act" (frozen/stunned). (b) untested; checked further in section 6.

## 2. What was built (engine_view.py)

* `view_engine_from_frame(frame, focus_side, spec_of, full=False, sim_eng=None, stats=None)` -> `EngineView` (subclass of L61 `FakeEngine`)
  that `render_frame(eng, width, note, acts, radii=True)` accepts unmodified. Mirror = L61 `frame_to_engine` verbatim (focus = team 0 = bottom).
  Units are `ViewUnit` (L61 `FakeUnit` + stun/slow/shield/flying/dash/souls/ability_active_s/ability_left/attacking/cloned/taunt_ref, all zero/None),
  projectiles are `ViewProjectile` (x,y,tx,ty,team,label,radius,pierce,parent,ground_only,width) built from `[side,X,Y,TX,TY,name]`:
  label = sim key (`-1` -> `tower`), radius = `spec.spell_radius` for spell cards else 0, pierce = `spec.rolls`, ground_only = `spec.ground_only or not attacks_air`.
  Board constants (lanes, tower_range 8.0, king_range 8.5, siege_sight 11.5, regulation 180, overtime 120, db) are copied from the live `SimMatchEnv.eng`, so
  `radii_of` / `board_from_engine` / `placement_from_spec` score identically to the sim feed. `crowns(team)` = the sim's rule (3 on a dead king, else dead princesses).
  Every list the engine does not export is EMPTY (zones, spells, rolls, vortices, splash/arc/ability events, rage/spark zones, _ability_pending, _banner, _antenna).
* Per-unit `spec` is a per-(key, max_hp) copy with `hp = engine max_hp` (`_spec_with_hp`). REASON, measured over all 211 batch_v2 play frames: the engine names spawned
  bodies after the PARENT card -- `SkeletonBalloon` skeletons have max_hp 81 (sim spec 532), `Witch`/`DarkWitch` skeletons 81 (839 / 906), `Goblinstein` doctor 721
  (2393), `GoblinGang` spear goblins 133 (202), `Rascals` girls 261 (1824) -- so `u.hp / u.spec.hp` (what render_frame draws) would show a full-health Witch skeleton
  at 10 %. Collision radius / flying / reach still come from the parent's sim spec (the engine exports none of them) -- (b) untested how far that is wrong for sub-bodies.
* `render_recording(path, focus_side, out_mp4, radii=True, width=460, fps=20, grid=True)`: merges `frames` + `play_frames` in tick order (play frame first at a tick),
  renders every frame through `render_frame`, writes mp4v (fallback: PNG folder, reported). Focus-side accepted plays: `eng.last_deploy[0] = (spec, x, y, t)` +
  the exact `_score_last_placement` scoring (`score_placement(board_from_engine(eng, 0), placement_from_spec(spec, x, y, db=db, **kw))`) -> the P1 annulus + term
  readout for 1.5 s. Opponent plays: orange diamond + card label for 1.5 s (post-render overlay, not inside render_frame). A play whose card has no sim spec gets a
  red `?` suffix and is counted (`unmapped_plays`). Play spec comes from `log.hand_before[hand_index]` (the engine display name, exact) with a slug fallback.
  The last frame carries `done=True, outcome=<final.outcome> crowns [a,b]` so the HUD prints the recording's verdict.
* HUD honesty tag: `render_frame`'s own note = `ENGINE FEED: no status/zone/arc export` (top right, 38 chars; render_frame clips at 46), plus a bottom-strip line
  `<tag> s<focus> engine_full|engine_compact tick N | status timers/zones/arcs/abilities not exported`.
* `--check` (one recording): assertions (a)-(e) below. `--ranges [--idle N]`: first-shot firing range from a record_full recording (section 6).

## 3. --check numbers (replay_000YLY0JCPGL, focus 1) -- all (a) MEASURED, all asserts pass

(a) tower pixel positions, engine feed vs `SimMatchEnv.reset()` at width 460: **max error 0 px** on all 6 towers
    (sim and engine both: team 0 L/R/K = (89,705) (370,705) (230,794); team 1 = (89,219) (370,219) (230,130)). Engine X=3500/14500/9000, Y=6500/3000 are exactly the sim's
    tile anchors (3.5/18, 6.5/32, 9/18, 3/32) because 1 tile = 1000 engine units on both axes.
(b) mirror: focus_side=1 puts engine side 1 (high rows, Y>16000 in the file) at the BOTTOM: team-0 colour pixels only in board rows 611..792 (of 810), team-1 only in 24..205;
    the focus=1 and focus=0 views are exact reflections of each other (|dx|,|dy| < 1e-9 with the L/R princess slots swapped).
(c) radii overlay: radii=True vs False differ in **5197 px** (tick 221, 3+ units on board).
(d) scored placement: first focus play (Skeletons at the king, no threat) changes **379 px** (marker + "skeletons vs -" line); first BUILDING with a real P1 band --
    Tesla at tick 2795 vs threat goblinstein, band 2.2..5.5 tiles, terms p1_close_penalty -0.10, p2_cover +0.50, p5_timing +1.00 -- changes **42603 px** (the shaded annulus).
(e) every attribute render_frame / _draw_radii / board_from_engine reads is PRESENT on the view object (30 engine attrs, 19 unit attrs) -- no getattr default is silently
    masking a missing field.

## 4. Renders (both with --radii, width 460, grid on)

Folder: `C:\Users\benpe\ClashBot\scratchpad\gauntlet\ext\engine_view\`

| recording | frames | ms/frame (render_frame only, measured) | focus plays scored | opponent plays | unmapped plays | unmapped entities |
|---|---|---|---|---|---|---|
| replay_00LYPLJLC80L_run1.json (record_full, every tick), focus 1 (x-bow side) | 5268 | 1.8-2.1 | 45 | 48 | 0 | 0 |
| batch_v2/replay_000YLY0JCPGL.json (compact 1 s + 121 play frames), focus 1 (icebow side) | 485 | 1.7-1.9 | 64 | 57 | 0 | 0 |

Whole-pipeline wall time: full recording 19.7 s (5268 frames incl. JSON load + mp4 encode), compact 2.8 s.
mp4s: `00LYPLJLC80L_s1_full.mp4` (20 fps = real time, 61 MB), `000YLY0JCPGL_s1_compact.mp4` (written at 4 fps: one compact frame = 1 s of match, so 4 fps is ~4x real time;
at --fps 20 it would run 20x). mp4v opened fine both times; the PNG fallback was not needed.

Stills (owner: look at these):
* `00LYPLJLC80L_s1_full_early_tick536.png`
* `00LYPLJLC80L_s1_full_readout_tick1591.png` -- the_log play scored, the Log as a rolling projectile with its 1.95-tile blast ring and the pierce cross
* `00LYPLJLC80L_s1_full_mid_tick2644.png` -- opponent Skeletons play = orange diamond; Hog + Ice Golem + Cannon on the top side
* `00LYPLJLC80L_s1_full_late_tick4751.png`
* `000YLY0JCPGL_s1_compact_early_tick701.png`
* `000YLY0JCPGL_s1_compact_readout_tick2192.png` -- x_bow placement: p2_cover +0.50, p6_siege +0.96, its 11.5-tile ring, a `tower*` shot in flight
* `000YLY0JCPGL_s1_compact_mid_tick3358.png`
* `000YLY0JCPGL_s1_compact_late_tick5562.png`

Unmapped-card count: 0 plays and 0 entity names in BOTH renders, and 0 unmapped entity names across all 211 batch_v2 recordings' play frames (101 distinct names) --
so the `?` path is (b) UNTESTED on real data (the code path exists, nothing exercised it).

## 5. Which sim_view features render on engine frames

(a) MEASURED = seen in the stills / asserted by --check; (b) = reasoned from the recording format, not pixel-tested.

Renders, from engine data:
* board, tile grid, placement grid, playable border, bridges -- constant, (a).
* towers: position (a, 0 px error), hp + hp bar (a), dead tower as grey X when it drops out of the `towers` list (b: the code path is L61's, exercised in L61 assembly, not
  pixel-checked here), `king`/`princess` tag (a), **king AWAKE** from the `-1` entity's kind 12->13 (a, section 1).
* units: position, team colour, `..` while deploying (kind 12/14, a), collision radius from the sim spec (b), flying ring from the sim spec's `flying` (b), hp bar with the ENGINE's
  max_hp (a, section 2), short label (a). `cloned` mark shows for entities named `Clone` (section 8.3; the copied card's identity is not exported).
* projectiles (full frames + play frames only): position, tower shots `tower*`, card shots `<key>*`, spell blast ring for Log/BarbLog/Rocket/Fireball/Arrows/Snowball/Lightning/GoblinBarrel
  (they are in the engine's projectile name set; Log/Rocket/Fireball seen, a), pierce marker for the two logs (rolls=True, a), hollow marker for ground-only shooters (b).
  Compact drift frames carry NO projectiles, so between play frames the feed shows none (tagged `engine_compact` in the bottom strip).
* HUD: clock from tick*0.05 (a), 1x/2x/3x from the sim's regulation (b: the ENGINE's own elixir phase is not exported; the compact still at 109.6 s says 1x, the full at 132 s says 2x,
  both consistent with CR's 120 s double-elixir), crowns from dead towers (a), both elixir bars from `frame.elixir` (a), final outcome on the last frame (b).
* --radii: attack ring + dotted sight per alive body/tower from `radii_of` (a, 5197 px), P1 annulus + term readout for each focus play (a, 42603 px), threat link.

Blank, and why (attribute -> reason):
* `stun_left / slow_left / shield_left / invis_left / flying_left / dash_left / souls / ability_active_s / ability_left / attacking / taunt_ref` -> the RECORDED frame carries
  only side/x/y/name/hp/max_hp/kind per entity; no status, no target, no ability state. All zero. The `kind` code MAY carry a can-act bit (section 1 anomaly + section 6.3) but
  it cannot be separated from "deploying" without entity ids, so it is not used for status.
  SEE SECTION 8: the bridge's raw observe DOES export target / attack timers / event timer / ability state; the recorder
  dropped them, so on disk they are absent. `view_engine_from_observe` consumes them when present.
* `zones` (Poison/Void/Graveyard/Heal), `vortices` (Tornado), `rage_zones`, `spark_zones`, `spells` (pending casts), `rolls` (the Log corridor) -> none are exported; Tornado, Zap,
  Poison, Graveyard, Freeze, Rage, Clone, Earthquake never appear in `projectiles` across all 211 recordings, so those plays are visible ONLY as the play marker for 1.5 s.
  The Log / Barbarian Barrel ARE visible, as a moving projectile with a blast ring (the engine models the roll as a projectile), not as the sim's corridor.
* `splash_events`, `arc_events`, `ability_events`, `_ability_pending`, `_banner`, `_antenna` -> per-hit / per-press engine records that only the sim engine produces. Empty.
* `u.target` -> None, so `board_from_engine` gets `target_xy=None` for every body (any reward term that reads the target link is scored as "no lock"). (b) untested how much that moves the terms.
* `effects` list of the recording -> measured identical to projectiles minus the target (section 1); nothing to draw.

Not a blocker anywhere: NO change to sim_view.py was needed (no proposed diff). sim_view tests: `tests/test_sim_view_visibility_i9.py` + `tests/test_rolling_spells_swept_r21.py`
= 52 tests OK (run with unittest; pytest is not installed in the venv), `git status` clean under `icebow/src/clashrl/`.

## 6. ONE observation: the radius table vs the engine (first ground-truth read; numbers as measured, not smoothed)

Method (`--ranges --idle 40`, replay_00LYPLJLC80L_run1, 5268 full frames): a projectile is a NEW shot when it sits within 1.2 tiles of a same-side body of its name (towers for `-1`)
and that shooter had no shot in the previous 40 ticks (2 s, longer than every hit period here: X-Bow 0.3 s, tower 0.8 s, Cannon 0.9 s, Musketeer 1.0 s, Ice Wizard 1.7 s).
Range = shooter centre -> the enemy body nearest (target_x, target_y) at that tick; "edge" subtracts the SIM's own hitbox radius of that target (1.5 for a tower target),
because the sim tests reach centre-to-target-EDGE (`engine._gap`) while `radii_of` returns the bare `reach` that the overlay draws and the reward scores.
Tesla emits NO projectile (0 in 5268 frames -- its zap is hit-scan), so its reach is read from enemy hp-drops of exactly 220 = the level-11 Tesla hit (sim: dps 200 x 1.1 s = 220.0)
while a Tesla exists: n=26, all with kind-13 (active) Teslas, targets Hog 17 / Ice Golem 9.

| defender | sim `radii_of` (r_atk) | engine first-shot distance, centre-to-centre max / p90 / median (n) | centre-to-target-EDGE max / p90 / median | engine edge max minus table |
|---|---|---|---|---|
| princess tower | 8.0 | 8.98 / 8.89 / 8.05 (n=30 troop targets) | 8.48 / 8.29 / 7.52 | **+0.48** |
| king tower | 8.5 | 8.89 (n=1, Hog) | 8.29 | -0.21 (one shot; lower bound only) |
| cannon | 5.5 | 6.34 / 6.33 / 6.29 (n=3, all Knight) | 5.84 / 5.83 / 5.79 | **+0.34** |
| x_bow | 11.5 | 12.30 (Ice Golem, n=2) and 13.04 (a princess TOWER target) | 11.60 / 11.59 / 11.54 | **+0.10** (tower target: 13.04 - 1.5 = 11.54) |
| tesla (hp-drop) | 5.5 | 6.27 / 5.42 / 2.76 (n=26) | 5.57 / 4.77 | **+0.07** |
| ice_wizard | 5.5 | 6.33 troop (n=5); 6.94 at a tower | 5.63 / 5.54 / 5.37 | **+0.13** (tower: 6.94 - 1.5 = 5.44) |
| musketeer | 6.0 | 7.03, 7.03, 6.98, 6.29 ... and ONE at 8.88 (n=8) | 6.53 typical; 8.38 once | **+0.53** typical; +2.38 once |

What this says (plainly):
1. Every engine first shot is released at or OUTSIDE the table radius once the target's hitbox edge is used: the engine's reach is centre-to-edge, exactly the sim's `_gap` convention,
   and the X-Bow at a tower (13.04 = 11.5 + 1.5) and the Ice Wizard at a tower (6.94 ~ 5.5 + 1.5) both land within 0.06 tiles of table + target radius. So the TABLE values for
   x_bow / tesla / ice_wizard / cannon are right to within 0.1-0.35 tiles -- but the rings the overlay DRAWS (bare `reach`, centre-to-centre) are 0.5-1.0 tiles smaller than where the
   engine actually fires on a Hog/Knight/Golem-sized body, and the reward's P-terms are scored with those bare radii. The sim engine itself adds `_REACH_SLOP` 0.6 on top of the
   edge test, which the table does not carry either.
2. The princess tower fires from further than the table: centre-to-edge max 8.48 / p90 8.29 over 30 first shots vs 8.0 (and the CR wiki's 7.5). Since the first shot is released after
   the tower's wind-up while the target keeps walking IN, 8.48 is a LOWER bound on the engine's acquisition range. (a) measured for this recording; whether it is 8.5 or 9.0 needs
   the acquisition tick (b, needs an entity id or a target-lock export).
3. The Musketeer's single 8.88-tile shot (tick 3340, target a Skeleton at (10306,18390), shot aimed at (10316,18493) -- a genuine lock) comes from side 0's `Musketeer@evolution`;
   it is consistent with the evolution's extended-range sniper mode and NOT with the sim's 6.0-tile (non-evo) spec. (b) untested: one shot, no evo-cycle bookkeeping here.
4. Side note on `kind`: 9 bodies older than 25 ticks flipped 15->14 (Knight x3, Hog x2, Ice Golem x2, Musketeer x2), each within ~1.5 s of an Ice Spirit / Ice Wizard / Log
   interaction (ticks 1687, 1823-1826, 3268, 3698-3733). So kind 14 most likely means "cannot act right now" (deploying OR frozen/stunned/knocked), which the L61 reading collapses
   into "deploying". The feed draws such a body as `..` for those ticks. (b) -- 9 events, no engine-side confirmation.

## 7. Traps / notes for whoever picks this up

* Compact recordings: ~1 frame per second plus a full frame per play; projectiles only on the play frames. Use `--fps 4` or so, not 20.
* `render_frame` uses `u.spec.hp` for the HP bar -> the feed MUST hand it a spec whose hp is the engine max_hp (done; see section 2), or sub-bodies read as nearly dead.
* The threat pick and P1 band come from `geometry_reward` unchanged; a play with no enemy on the board prints `<card> vs -` and no annulus -- that is the reward's answer, not a feed gap.
* Both renders have focus 1. `--focus 0` works (check (b) compared both) but was not rendered end to end.
* Files: engine_view.py (code), engine_view.md (this), ranges_00LYPLJLC80L.json (the raw --ranges output incl. every first shot with tick / target / distance).

## 8. SCOPE ADDITION: what the bridge's full observe exports vs what the recordings kept (coordinator ask)

Sources read: `research/ext/cr-native-sandbox/android_probe/native/jni_bridge.cpp` lines 1240-1745 (the entity / effect /
projectile serializer), `docs/API.md` 3-4 and 10, `docs/SANDBOX_RUNTIME_TECHNICAL.zh-CN.md` 20 (entity field list + ability
state-code table), `native_core/env.py` `_enrich_state` (adds `name`, `entity_id`, `ability_state_name`, hand names), and the
recorders `research/sandbox_tools/replay_drive.py` `snapshot()` line 317 and the L61 copy `scratchpad/gauntlet/L61/replay_drive_rec.py`
line 325 (the one that wrote every recording on disk).

### 8.1 The recorder dropped almost every per-entity field -- (a) measured from the recorder source

Per entity the bridge's FULL observe emits: `id` (raw pointer), `generation_key`/`category`/`creation_ordinal`, `kind`, `side`, `x`, `y`,
`x2`, `y2`, `card_id`, `level`, `hp`, `max_hp`, `behavior_state`, `ability_slot`, `ability_state_code`, `ability_available`,
`ability_cooldown_remaining_ms`, `ability_charges_remaining`, `ability_pending_ms`, `ability_mana_cost`, `pending_damage`,
`event_timer_ms`, `target` (pointer or null), `target_previous_x/y`, `attack_progress_ms`, `attack_load_timer_ms`,
`movement_direction_x/y`, `collision_accumulator_x/y`, `collision_count`, `avoidance_offset`, `path_segment_direction_x/y`,
`path_node_consumed`, `path_nodes[<=115]`; the env adds `name`, `entity_id`, `ability_state_name`, `native_card_id`, form identity.
The recorder kept `[side, x, y, name, hp, max_hp, kind]` and NOTHING else (compact frames: no `kind` either).
Per effect the bridge emits `id, vtable_rva, category, kind, side, x, y, x2, y2, card_id, source, target, attached_owner,
projectile_x/y_candidate`; the recorder kept `[side, x, y, name]`. Per projectile the bridge emits the same plus `target_x/y`;
the recorder kept `[side, x, y, target_x, target_y, name]`. `effects_classified` / `unclassified_effect_count` were not kept.
The compact observe also carries `behavior_state` and all seven ability fields; the recorder dropped those too.

So on disk, for the 211 batch_v2 recordings and the every-tick recording, NONE of target / deploy countdown / attack timers /
ability state / level / paths exist. Recovering them needs a re-record with a richer `snapshot()` (one-line change: keep the raw dict)
-- NOT a new bridge offset. I did not boot the VM.

### 8.2 Lingering zones are NOT in `effects` -- (c) contradicted, measured on disk

The coordinator's expectation was that Poison / Graveyard / Tornado / Void live in the 4,000,000-series `effects`. Measured over ALL
23,169 full frames on disk (211 x batch_v2 play frames + 5,268 every-tick frames): `effects` == `projectiles` (same side/x/y/name
multiset) in 23,169 / 23,169 frames; zero non-projectile effects ever. That is not a sampling accident: the play frames are taken
before each play, and 58 graveyard, 57 poison, 184 tornado, 43 freeze, 30 rage, 66 earthquake, 60 goblin-drill, 18 void, 8 goblin-curse
and 3 heal-spirit plays have a LATER full play-frame captured inside that zone's lifetime (e.g. graveyard played tick 831, next
play frame tick 863; poison 2896 -> 2961), and every one of those frames has 0 extra effects. In the every-tick recording the three
Tornado plays (ticks 3016, 4632, 5082) show no Tornado effect in the 60 ticks after each.
Reading of the bridge code: an effect row is emitted only if `category in [4M, 5M)`, `vtable_rva != 0 and < 0x3000000`, `side in (0,1)`,
and (for non-projectile vtables) `0 <= x <= 18000, 0 <= y <= 32000`. Either area effects are not 4M-series objects in this registry, or
they fail the side / bounds gate (a zone with side = -1 or team-less would be dropped). Which one cannot be told from disk.
STATUS: lingering zones = NOT EXPORTED by the current bridge (needs a new libg registry/offset, not a recorder change).
What IS visible for those cards: only the play marker (1.5 s). Spells that the engine models as projectiles ARE visible: Log,
BarbLog, Fireball, Rocket, Arrows, Snowball, Lightning, GoblinBarrel (+ every ranged attack). Zap, Poison, Tornado, Graveyard,
Freeze, Rage, Clone, Earthquake, Void, Mirror, GoblinCurse: never a projectile, never an effect.

### 8.3 Sub-bodies and clones ARE recoverable from the name + max_hp -- (a) measured, now rendered

Entities named after a spell card in batch_v2 play frames: `Graveyard` x471 (max_hp 81 in all 471 = a level-11 skeleton; kinds 15/14),
`Clone` x17 (max_hp 1 in all 17 = the 1-hp clone), `Heal` x29 (217 hp = the Heal Spirit body), plus spawner children named after the
parent (`SkeletonBalloon`/`Witch` 81, `GoblinGang` 133, `Rascals` 261, `Goblinstein` 721, `GoblinDrill` 202 goblins / 1313 building /
2560 = the travelling drill, `RageBarbarian` 1282 and 17 rows with max_hp 2 -- unexplained, (b)).
Before this addition a `Graveyard` skeleton was drawn with the graveyard SPELL spec (kind spell, r 0.5) and a `Clone` with the clone
spell spec. Now `_SUBBODY[(name, max_hp)]` remaps `Graveyard`/`SkeletonBalloon`/`Witch` @81 -> Skeletons and `Clone`@1 -> generic body
with `u.cloned = True` (render_frame appends the `'` clone mark). The copied card's identity is NOT exported for clones. Other
spawner children keep the parent's spec (collision radius / flying may be wrong for them, (b)).

### 8.4 The feature table

Status key: rendered = drawn from data that exists in the recordings on disk; inferred = the engine field exists in the bridge's
observe and `view_engine_from_observe` maps it as stated, but no recording on disk carries it and the semantics are not verified
(exercised only by the synthetic check (f)); not exported = no bridge field carries it (needs a new libg offset in jni_bridge.cpp).

| sim_view feature | engine source field(s) | status |
|---|---|---|
| body position, team, label | entity `x`, `y`, `side`, `card_id` -> `name` | rendered |
| body hp bar | entity `hp`, `max_hp` (spec.hp replaced by engine max_hp) | rendered |
| deploying (`..` outline) | entity `kind` in (12, 14) | rendered (L61 reading; kind 14 also flips on 9 old bodies near Ice Spirit/Ice Wizard/Log, so 14 likely = "cannot act", 1) |
| `deploy_left` countdown value | entity `event_timer_ms` while kind in (12, 14) | inferred: `deploy_left = event_timer_ms/1000` (the bridge names it an event timer; the docs give no semantics) |
| collision radius, flying ring | none -- from the sim spec of the card name | rendered from the sim table, not the engine (b for sub-bodies) |
| tower position / hp / dead X | `episode.crown_towers` (side, type, lane, x, y, hp, max_hp); absent = destroyed | rendered |
| king AWAKE (`active`) | the king's `-1` entity `kind` 12 -> 13 | rendered (measured 1) |
| projectiles (position, target, label) | `projectiles[]` `side, x, y, target_x, target_y, card_id` | rendered |
| spell blast ring on a projectile | `card_id` -> sim `spell_radius` | rendered (Log/BarbLog/Fireball/Rocket/Arrows/Snowball/Lightning/GoblinBarrel) |
| pierce marker (rolling spells) | `card_id` -> sim `rolls` | rendered |
| ground-only hollow shot | `card_id` -> sim `attacks_air`/`ground_only` | rendered (b: not pixel-checked) |
| attack target link | entity `target` (attack component pointer) resolved against entity `id` (towers included) | inferred: `u.target`; drawn as a post-render line by `_overlay_targets` (sim_view itself draws no target line; `board_from_engine` reads it as `target_xy` for the march line) |
| `attacking` marker (triangle) | `attack_progress_ms` > 0 with a live target | inferred |
| `attack_load_timer_ms`, `target_previous_x/y`, `pending_damage` | exported | kept on the ViewUnit; no sim_view feature reads them |
| `level` | entity `level` | kept on the ViewUnit; specs stay level 11 (sim_view shows no level) |
| `behavior_state` | entity `behavior_state` | kept; no code table anywhere in the docs -> no meaning assigned |
| movement direction / path nodes | `movement_direction_x/y`, `path_nodes` | not drawn (sim_view has no path feature); available in the raw observe |
| `[ABIL]` tag (use available) | `ability_state_code` == 2 (ready) and `ability_charges_remaining` > 0 -> `ability_left` | inferred from the docs' state-code table (API.md 2 / technical 20) |
| cast-in-flight ring (`_ability_pending`) | `ability_state_code` 10 (pending) / 11 (casting), `ability_pending_ms`, `ability_mana_cost` | inferred: ring + "cast N.NNs"; whether `ability_pending_ms` is the refund window is not verified |
| running ability on the body (`ability_active_s`) | none (no active-duration field; cooldown is `ability_cooldown_remaining_ms` = after the ability, not during) | not exported |
| ability cooldown | `ability_cooldown_remaining_ms` (state 3) | exported, but sim_view has no cooldown feature -> not drawn |
| ability events (`ability_events`), Hero Goblins banner, Goblinstein antenna/link | none | not exported |
| clone mark (`cloned`) | entity `name` == "Clone" (max_hp 1) | rendered (8.3) |
| lingering zones: Poison, Void, Graveyard, Heal field (`zones`) | expected in non-projectile `effects` -- measured absent (8.2) | not exported (code path `eng.zones` from `effects` exists, exercised only synthetically) |
| Tornado vortex (`vortices`), rage zones, spark zones, Log corridor (`rolls`) | same as above; the Log is a projectile in the engine | not exported (Log drawn as a projectile instead) |
| pending spells (`spells`) | none | not exported |
| splash flashes, chain arcs (`splash_events`, `arc_events`) | none (per-hit records) | not exported |
| stun / slow / freeze / shield / invisibility / thrown-airborne / dash / souls / taunt | none | not exported (blank and labelled) |
| elixir bars, clock, crowns, 1x/2x/3x, outcome | `players.elixir_exact`, `tick`, dead towers, sim regulation constants, `final` | rendered (elixir phase from the sim's 120 s rule, not an engine field) |
| P1 band + term readout (`--radii`) | focus play from `log` + the board above | rendered (measured 3d) |

### 8.5 What the code now does about it

* `observe_to_frame(state)` turns a RAW full observe (bridge schema) into the recorder's frame shape without dropping anything;
  `view_engine_from_observe(state, focus_side, spec_of, ...)` applies the "inferred" rows above (target link, deploy_left, attacking,
  `[ABIL]`, cast ring, zones from non-projectile effects). It is the entry point for a live engine feed or a re-record that keeps
  the raw dicts. `_card_name` reuses the recorder's naming through `native_core` when it imports (it did on this box), else the raw id.
* `--check` (f): a synthetic full observe built from play frame tick 1883 with `event_timer_ms=600` on a deploying body, a Goblinstein
  given `target` = enemy tower + `attack_progress_ms=250` + `ability_state_code=11, ability_pending_ms=300`, and one non-projectile
  `Poison` effect. Result: `deploy_left 0.6`, `target -> Tower`, `attacking True`, pending ring 0.30 s "casting", zone poison r 3.5,
  1 target link; 1,131 px differ from the plain-frame render. Still: `ext/engine_view/000YLY0JCPGL_s1_observe_SYNTHETIC_tick1883.png`
  (labelled SYNTHETIC in the filename: those values are made up to exercise the path).
* Both recordings were re-rendered after the change (same counts: 5268 / 485 frames, 1.74 ms/frame both, 45+48 / 64+57 plays,
  0 unmapped); 52 sim_view tests still OK; sim_view.py still untouched.

### 8.6 Proposed recorder change (NOT applied -- owner's recorder, and it needs a re-record with the VM)

In `scratchpad/gauntlet/L61/replay_drive_rec.py` `snapshot()` (and `research/sandbox_tools/replay_drive.py` line 320), keep the raw dicts:
`frame["entities_raw"] = state.get("entities")`, `frame["effects_raw"] = state.get("effects")`, `frame["projectiles_raw"] = ...`
on full frames -- then `view_engine_from_observe` consumes them unchanged. Size cost: ~1.5 KB per entity per frame with paths (the
every-tick recording's JSON would grow from 9.3 MB to a few hundred MB); dropping `path_nodes` keeps it ~10x smaller.

STATUS: complete
