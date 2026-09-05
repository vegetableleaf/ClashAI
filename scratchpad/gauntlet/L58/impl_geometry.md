# L58 impl_geometry progress (step 0: geometry_reward module + sim-view --radii)

Started 2026-09-04. Brief: scratchpad/gauntlet/L58/BRIEF_impl_geometry.md

## 1. Reading
- Spec read: research/RADIUS_REWARD_PROPOSALS.md §1, §4 (P1-P7), §5, §7.2-7.5.
- Surveying engine / cards / sim_view / cli / tests next.

### Survey findings (engine / KB / debugger / tests)
- Engine facts in the brief confirmed: `SimEngine.units` (Unit.spec/team/x/y/hp/deploy_left/target),
  `engine.towers[team]` (Tower.x/y/hp/max_hp/king/alive/active/radius), `engine.vortices` (list of
  `_Vortex`), `_dist`/`tile_dist` (engine.py:1716), `_gap` (:1809, to the ref's hitbox EDGE via
  `_body_radius`), `_march_gap` (:2475, through the bridge nearest `u.x` when the river is between).
  `engine.lanes` = normalised bridge x, `engine.tiles_x/tiles_y`, `engine.river_width` (2.0),
  `engine.siege_sight` 11.5, `engine.tower_range` 8.0 (config), `engine.king_range` 8.5 (config).
  Tower.active = king AWAKE flag (sim_view tags it "AWAKE").
- `CardSpec.speed` is already TILES/s (engine.py:846 `speed_tiles`); the doc's "`CardSpec.speed` x 32"
  in §1 is stale -- I use `spec.speed` directly.
- `CardSpec.deploy_time` exists (1.0 default, 3.5 for X-Bow/Mortar, 0 for spells).
- Tornado: `spec.pull_radius` (5.5) and `_TORNADO_RADIUS` 5.5; pull strength scales with mass
  (`_pull_resist`) -- the doc's `clip(1 - d/r_pull)` weight is used as written (no mass).
- KB values (cards.load()): hog_rider atk 0.8 / sight 9.5 / speed 2.0 / elixir 4 / building_only;
  tesla 5.5/5.5; pekka 1.2/5.0; x_bow 11.5/11.5 (deploy 3.5 s); giant 1.2/7.5; skeletons 0.5/5.5;
  ice_wizard 5.5/5.5; tornado spell radius_tiles 5.5; knight 1.2/5.5. Roles via
  `card_threat.profile(db, base).roles()` (first = most salient).
- Debugger: `sim_view.render_frame(eng, width, note, acts)`; helpers `px()` / `rad_px()`; units loop
  at sim_view.py ~:272, towers ~:213. `sim_view()` at :546 drives `env.step(agent(env))`; a placement
  is visible as `env.eng.last_deploy[0] = (spec, x, y, t)` (engine.py:2266, set even when the
  deploy is latency-queued).
- CLI: `sim-view` subparser at cli.py:814, `_cmd_sim_view` at :409.
- Tests: `tests/` uses `unittest` (no pytest in the venv); `sys.path.insert(0, "../src")` idiom;
  run with `python -m unittest tests.test_x -v` from cwd icebow.
- `env.threat_credit_budget` / `threat_value.IGNORE_FRAC` exist; the brief's simpler "value >= 3
  elixir or building_only" filter is what I implement (`ACTUAL threat`).

## 2. Built: `icebow/src/clashrl/geometry_reward.py` (deliverable A)
Pure module (math/dataclasses only; engine + KB imported lazily inside `board_from_engine` /
`role_average_radii`). Public API as briefed: `BoardObj`, `Board`, `band`, `radii_of`,
`board_from_engine`, `placement_from_spec` (helper: CardSpec + tile -> placement dict),
`score_placement`, `role_average_radii`, plus `tile_dist` / `gap` / `march_gap` (re-implemented with
the engine's formulas so the module needs no engine import; parity-tested against `engine._dist`),
`threat_path`, `pick_threat`, `tornado_away`, `nonzero_terms` (for the overlay).

### FINDING that contradicts the spec (measured, 2026-09-04, `scratchpad/gauntlet/L58/_bowcheck.py`)
Doc P6 says the policy's corner bow (1.5, 18.5) "does not reach [the princess] either: L56's
hypothesis (b)(1) is CONTRADICTED by the engine's number (11.18 at y 0.56 / 12.34 at y 0.60)".
That number is the STALE comment at engine.py:2567, measured centre-to-centre on the old anchors.
The running engine (tile-derived towers: enemy princess at tile (3.5, 6.5), reach tested with `_gap`
to the tower's EDGE) gives `_gap((1.5,18.5) -> L princess) = 10.67 < 11.5`, and a real deploy of an
X-Bow at (1.5, 18.5) LOCKS the left princess (target type Tower, king=False) and takes it
4858 -> 4568 HP in 6 s. So in the current sim the corner tile IS an offensive bow, and P6 as
written scores it 1.0 (in band 8.5..11.5). L56 (b)(1) is therefore NOT contradicted by the engine;
the lead should re-read that conclusion. Other gaps from the same probe: (3.5,17.5) 9.5;
(2,19.5) 11.59 (0.91 credit -- just past the 11.5 edge); (8.5,22) 14.79 (0); (9,17.5) 10.8.

### Choices where the doc is ambiguous (all marked `CHOICE:` in the code)
- `d_march` / `d` / `_gap` are re-implemented (same formulas, same tile scaling) so the module has no
  engine import; `march_gap` routes through the bridge nearest the THREAT's x, like `_march_gap`.
- Threat selection (`pick_threat`): among enemy TROOPS with value >= 3 elixir or building_only, the
  most urgent one = smallest lane-aware distance to our nearest alive tower (the identity block's
  "deepest recognised enemy"); ties -> nearest to the placement. Enemy buildings are never the threat.
- P1 applies to every building placement vs the threat (not only building-targeters: a Tesla vs a
  PEKKA is the doc's own close-penalty example). The close penalty fires only for MELEE threats
  (r_atk <= 2.0 tiles) -- the doc's text says "a melee wincon"; the formula alone would penalise a
  building 5 tiles from a Musketeer. Flying threats use the straight distance for x.
- P2 `d(p, tower)` = tower centre to the PLACED body's hitbox edge (how the tower measures reach);
  own alive PRINCESS towers only (doc text), the king is not counted even when awake.
- P3 intercept point = the perpendicular foot of the landing tile on the threat's path polyline
  (threat -> bridge -> our nearest alive tower, or -> its locked target). `ahead`: 1 if the foot is
  strictly inside the path and the tile is within r_body(counter)+r_body(threat)+0.5 of it, 0.5 if
  inside but wider, 0 if the foot is at the threat (behind it) or at the goal (behind everything).
  The kite bonus is ADDED and the total capped at 1.0.
- P5: `t_cross` = distance to the bridge waypoint / v (flying: straight to the river line); `t_hit`
  = (path length to the tower's edge - r_atk(t)) / v; `t_resp` = deploy_time + (troop only) travel
  from the tile to the intercept point at the counter's speed. Now = 0. A stationary threat
  (speed 0) scores no P5.
- Bridge block (§7.4): |x - bridge_x| <= 1.5 tiles AND |y - river| <= 1.5 tiles; "approaching" = an
  enemy ground troop whose nearest bridge is that one, still on the FAR side of the river, within
  r_sight + 3 tiles of the bridge centre. Cases B1 (building_only ground), B2 (flying building_only
  with a ground escort in the lane), B3/B5 (KB tank role), B7 (wall_breakers vs a non-splash
  placement), B8 (princess) -> case 1; B9 (magic_archer / firecracker) and >= 3 enemy ground troops
  trailing the threat in the lane -> 0. B4 / B6 / B10 are NOT implemented (need tower HP thresholds,
  the enemy's hand, or the owner's confirmation). `bridge_block_held` needs time evolution and is
  left to the env integration (not a single-snapshot term). When detected: P5 = 1 if case else 0;
  P3's intercept = the bridge tile with ahead = 1; P1 unchanged.
- P4: push = enemy troops on OUR half (all enemy troops if none). `p4_spell_frac` uses
  spell_radius vs each body's hitbox edge; `p4_nado` needs `pull_radius` in the placement (the
  engine's spec.pull_radius, 5.5) and uses the doc's `clip(1 - d/r_pull)` weight (no mass term);
  `p4_king_activation` = 1 when >= 1 body is inside the pull radius, our king is ASLEEP
  (`active=False`) and the pull centre is within the king's reach (gap to the king's edge).
  For spells, `p2_cover` is the cover of the cast point.
- P6: `d(b, tower)` = gap to the tower's edge (what the engine's own reach test uses); NOTE the
  tower's reach on the bow is a different distance (tower centre -> bow edge), so a bow with gap
  8.5..8.9 reads "in band" while still inside the princess's 8.0 reach -- kept AS WRITTEN, flagged
  for the §3 gate calibration. Siege detected by `placement["siege"]` or base in (x_bow, mortar).
- P7: troop placements with 0 < hp_max <= 800 vs a SPLASH or MELEE (r_atk <= 2.0) threat that is
  not building_only (a Hog cannot hit troops); distance = gap to the threat's edge.
- Value = `spec.elixir` (spawned bodies carry their share). Towers value 0.
- Doc §1 says `v(t) = CardSpec.speed x 32`; the engine's `speed` is ALREADY tiles/s -- used directly.

## 3. Tests: icebow/tests/test_geometry_reward.py (deliverable B) -- 19 cases, unittest
Run: `cd icebow && .venv/Scripts/python.exe -m unittest tests.test_geometry_reward -v`
```
test_plateau_ramps_and_zero (tests.test_geometry_reward.BandShape.test_plateau_ramps_and_zero) ... ok
test_every_term_bounded_and_deterministic (tests.test_geometry_reward.Bounds.test_every_term_bounded_and_deterministic) ... ok
test_fragility (tests.test_geometry_reward.Bounds.test_fragility) ... ok
test_lone_skeleton_is_not_a_threat (tests.test_geometry_reward.Bounds.test_lone_skeleton_is_not_a_threat) ... ok
test_anti_cases (tests.test_geometry_reward.BridgeBlock.test_anti_cases) ... ok
test_detected_with_hog_approaching (tests.test_geometry_reward.BridgeBlock.test_detected_with_hog_approaching) ... ok
test_not_detected_away_from_the_bridge_or_far_hog (tests.test_geometry_reward.BridgeBlock.test_not_detected_away_from_the_bridge_or_far_hog) ... ok
test_not_detected_on_a_quiet_board (tests.test_geometry_reward.BridgeBlock.test_not_detected_on_a_quiet_board) ... ok
test_centre_beats_corner (tests.test_geometry_reward.P1PullBand.test_centre_beats_corner) ... ok
test_close_penalty_tesla_on_pekka (tests.test_geometry_reward.P1PullBand.test_close_penalty_tesla_on_pekka) ... ok
test_corner_vs_right_lane_hog_is_not_pulled (tests.test_geometry_reward.P1PullBand.test_corner_vs_right_lane_hog_is_not_pulled) ... ok
test_no_penalty_for_a_ranged_threat (tests.test_geometry_reward.P1PullBand.test_no_penalty_for_a_ranged_threat) ... ok
test_doc_tiles (tests.test_geometry_reward.P3Intercept.test_doc_tiles) ... ok
test_centre_bow_is_not_offensive_and_enemy_building_softens (tests.test_geometry_reward.P6Siege.test_centre_bow_is_not_offensive_and_enemy_building_softens) ... ok
test_dead_princess_scores_zero_and_king_is_in_band (tests.test_geometry_reward.P6Siege.test_dead_princess_scores_zero_and_king_is_in_band) ... ok
test_engine_adapter_and_metric_parity (tests.test_geometry_reward.RadiiOneSourceOfTruth.test_engine_adapter_and_metric_parity) ... ok
test_radii_of_shapes (tests.test_geometry_reward.RadiiOneSourceOfTruth.test_radii_of_shapes) ... ok
test_away_is_one_when_pulled_straight_back (tests.test_geometry_reward.TornadoAway.test_away_is_one_when_pulled_straight_back) ... ok
test_nado_terms (tests.test_geometry_reward.TornadoAway.test_nado_terms) ... ok

----------------------------------------------------------------------
Ran 19 tests in 1.092s

OK
```
Two expectation errors of mine were corrected while writing the tests (the module was right):
d_threat is the gap to the THREAT's hitbox edge (6.83, not the march distance 6.93), and a Tesla at
(9,21) vs a PEKKA at (4.5,20) is correctly NOT pulled (tower 4.09 tiles < Tesla 4.11).

## 4. Overlay: `sim-view --radii` (deliverable C)

Files: `icebow/src/clashrl/sim_view.py` (+102/-4), `icebow/src/clashrl/cli.py` (+6/-2). `score_placement`
gained four overlay-hook keys so the debugger draws exactly what was scored: `threat_x`, `threat_y`
(normalised), `p1_band_lo` (= r_atk + 1.0), `p1_band_hi` (= r_sight) -- set only when a threat exists;
they are not in `TERM_KEYS`, so `nonzero_terms()` never prints them.

What the flag draws (`_draw_radii`, called from `render_frame` before the bodies so rings sit under them):
- every ALIVE tower: solid 1 px ring at `r_atk` in the team colour; dotted dimmer ring at `r_sight` when it
  differs (for towers it never does -- radii_of returns (tower_range, tower_range) / (king_range, king_range));
  a taken tower draws nothing (doc 7.5).
- every unit with hp > 0 that is not a spell: solid `r_atk`, dotted `r_sight` (0.55 x team colour).
  Both from `geometry_reward.radii_of(spec, siege_sight=, tower_range=, king_range=)` -- the ONE table.
- `eng.last_placement` (set by `sim_view._score_last_placement` whenever `eng.last_deploy[0]` changes
  identity -- i.e. the moment the engine records YOUR tap, even while it is latency-queued): for 1.5 s
  of engine time draw a tilted-cross marker at the placement, a line to the scored threat, the P1 band
  annulus lo..hi shaded 30 % pale yellow (BUILDING placements only -- P1 is a building term; a troop or
  spell gets marker + line, no annulus), and the text `"<base> vs <threat_base>"` followed by one
  `name +v.vv` line per non-zero term (`bridge_block_` shortened to `bb_`). Readout flips to the left of
  the marker within 150 px of the right edge.
- Off by default: `render_frame(..., radii=False)` and `sim_view(..., radii=False)`; `_cmd_sim_view`
  passes `radii=bool(getattr(args, "radii", False))`.

Byte-identity check (flag off vs the COMMITTED sim_view): `scratchpad/gauntlet/L58/_clip.py` loads
`git show HEAD:icebow/src/clashrl/sim_view.py` as a sibling module and renders the same 103 engine
states with both: `frames {'f': 103, 'same': 103, 'diff': 0}` -- 103/103 identical arrays.
Neighbouring suites still pass: `tests.test_sim_view_visibility_i9 tests.test_rolling_spells_swept_r21`
-> `Ran 52 tests in 19.572s / OK`.

Verification artefacts in `scratchpad/gauntlet/L58/`:
- `radii.mp4` -- the brief's command verbatim (`run.py sim-view --radii --out ... --no-window --matches 1
  --seed 3`): one full random-vs-random match, 1822 frames @ 20 fps, 22 MB (there is no duration flag on
  `sim-view`; a match runs to its end -- 180 s here, `loss 1-2`).
- `radii_10s.mp4` -- the 10 s clip the brief asked for (first 10.2 s of seed 3 at 10 fps, 103 frames),
  written by `_clip.py` through `render_frame(radii=True)` directly.
- `radii_frame_1/2/3.png` -- the frame of each of the first three placements of seed 3 (knight, log,
  skeletons; all scored vs the enemy's opening baby_dragon: only p2_cover +0.50 is non-zero, which is
  right -- a troop / spell earns no P1 and the dragon is a flier the skeletons cannot intercept).
- `radii_frame_building.png` -- seed 11, t = 0.6: a random Tesla scored against a Giant:
  `p1_pull_band +0.75, p2_cover +0.50`; the 2.2..7.5-tile band annulus around the Giant is visible,
  the Tesla marker sits inside it.
The random agent hits the P1 band rarely (one building placement with p1 > 0 in the first 120 s of
10 seeds) -- expected: it places uniformly over 432 cells.

## 5. Report (deliverable D)

Files touched (all under `C:\Users\benpe\ClashBot\icebow\`):
- `src/clashrl/geometry_reward.py` -- NEW, 637 lines. Constants 29-66, `BoardObj` 72-97, `Board` 99-129,
  metric helpers (`band`, `clip01`, `tile_dist`, `gap`, `nearest_bridge`, `march_gap`) 132-176,
  `radii_of` 179-208, `board_from_engine` 211-260, `placement_from_spec` 263-284, `role_average_radii`
  287-319, threat path / projection / selection 322-405, `_p2_cover` 408-418, bridge block 421-465,
  `score_placement` 468-608 (overlay hooks 494-498), `tornado_away` 611-627, `nonzero_terms` 630-637.
- `tests/test_geometry_reward.py` -- NEW, 307 lines, 19 cases (unittest; the venv has no pytest).
- `src/clashrl/sim_view.py` -- `_BAND` :94; `_dim` :118, `_dotted_ellipse` :122, `_draw_radii` :128-179;
  `render_frame` signature + docstring :182-201, overlay call :285-287; `sim_view` signature :623-625,
  `seen` / `_score_last_placement` :642-657, `sink` :659-664.
- `src/clashrl/cli.py` -- `_cmd_sim_view` :417; `--radii` flag :831-834.
- NOT touched: `sim/env.py`, `env.py`, `reward.py`, `data/`, `config/config.yaml` (no `env.geometry:`
  block added either -- the module carries its defaults as constants, nothing in the env reads them yet;
  the gate (step 1) is the right place to decide which become config).

Test output verbatim: section 3 above (`Ran 19 tests in 1.092s` / `OK`; re-run after the overlay-hook
keys: `Ran 19 tests in 1.090s` / `OK`).

Where the doc's formula was NOT implemented as written, and what was done instead:
1. P6 worked example (doc 4.6 / 7.6): the doc says the corner bow (1.5,18.5) cannot reach the enemy
   princess; the RUNNING engine says it can (`_gap` = 10.67 < 11.5, the bow locks and damages the
   princess). Implemented the doc's formula (band on the gap to the tower's edge) -- the doc's NUMBER
   for that tile is what is wrong, not the formula; the corner tile scores p6 = 1.0. See section 2.
2. `CardSpec.speed` is already tiles/s: the doc's "x 32" was not applied (would inflate P3/P5 timing).
3. Bridge-block cases B4 (support behind), B6 (mirror), B10 (double bridge) and the `bridge_block_held`
   follow-up term need multi-tick state or a second placement -- not implementable in a pure per-placement
   scorer; left as 0 / not detected and recorded as CHOICE in the code. B1-B3, B5, B7-B9 + anti-cases done.
4. P1 is a snapshot at placement time as the doc writes it: a Tesla placed while the hog is still
   4 tiles short of the river scores only 0.28 for a tile that will be perfect 2 s later. Implemented as
   written; flagged for the section-3 gate (a path-relative or time-of-arrival variant is the fix).
5. Everything else listed under "Choices" in section 2 (threat = most urgent by march distance, P2 uses
   princess towers only, P3 kite capped at 1, P5 timing pads, bridge geometry 1.5 tiles, P4 push = enemy
   troops on our half, P7 hp_max <= 800 vs splash/melee).

Not run / not done: no `env.geometry:` config block (optional in the brief); no git commit (lead's).

STATUS: complete
