# L58 brief: geometry_reward module + sim-view radius overlay (step 0 of the radius-graded reward)

Repo: C:\Users\benpe\ClashBot ; python env: `icebow/.venv/Scripts/python.exe`, run from cwd `icebow`
(Windows: use `C:/...` paths). NO third-party installs. NO git commits (the lead commits). Do NOT edit
`src/clashrl/sim/env.py`, `src/clashrl/env.py`, `src/clashrl/reward.py`, anything under `data/`, or
`config/config.yaml` VALUES (you may ADD a new `env.geometry:` block with defaults, nothing else).
Do not touch the live-play path.

Write progress to `C:\Users\benpe\ClashBot\scratchpad\gauntlet\L58\impl_geometry.md` INCREMENTALLY
(what you found, what you built, test output), and end with a line `STATUS: complete`.

## Spec to implement
Read `research/RADIUS_REWARD_PROPOSALS.md` §1 (definitions), §4 (P1-P7), §5 (implementation shape),
§7.2 (overlay), §7.3 (tornado), §7.4 (bridge block), §7.5 (alive towers only). Implement the FORMULAS
as written there; where the doc is ambiguous choose the simplest reading and record the choice in your
progress file.

### Engine facts you need (verified by the lead, 2026-09-04)
- `src/clashrl/sim/engine.py`: class `SimEngine`; `engine.units` (Unit: spec, team, x, y, hp,
  deploy_left, target, ...), `engine.towers[team]` (Tower: x, y, hp, max_hp, king, alive, radius,
  active), `engine.vortices`-like `_Vortex` objects (grep `_Vortex` for the list name).
- Coordinates are NORMALISED (x,y in 0..1); distances in TILES via `engine._dist(ax,ay,bx,by)`
  (public alias `tile_dist`), hitbox-edge gap via `_gap(ax, ay, ref)`; lane-aware march distance
  `engine._march_gap(u, ref)`. Board 18 x 32 tiles, river centre tile 16 (2 tiles thick), bridges at
  x tiles 3.5 / 14.5 (`_BRIDGES` normalised). Team 0's own half is HIGH y (own princess y ~0.797,
  king 0.906; enemy 0.203 / 0.094).
- CardSpec: `reach` (attack range, TILES), `sight` (aggro radius, TILES, default 5.5),
  `radius` (collision), `kind` ("troop"/"building"/"spell"/"tower"), `flying`, `building_only`
  (building-targeter), `siege`, `speed`, `elixir`, `hp`, `dps`, `spell_radius`, `splash`.
  `engine.siege_sight` (11.5) for siege; `engine.tower_range` (princess reach, config 8.0),
  `engine.king_range` (8.5). Towers measure reach from the target's hitbox EDGE (`_gap`).
- Existing reward hook for reference only (do not modify): `sim/env.py::_threat_response` ~line 970;
  ledger class `src/clashrl/reward_stats.py::RewardTerms.add(name, value)`.
- Debugger: `src/clashrl/sim_view.py::render_frame(eng, width, note, acts)` (OpenCV); CLI parser in
  `src/clashrl/cli.py` ~line 814 (`sim-view` subparser); `sim_view()` at ~546. Existing drawing
  helpers `px()`, `rad_px()` inside render_frame.

### Deliverables
A. `src/clashrl/geometry_reward.py` -- PURE module (numpy/math only, no engine import at module top;
   an adapter function may import the engine lazily). Public API:
   - `@dataclass BoardObj`: team, kind ("troop"/"building"/"tower"/"spell"), base (card key), x, y
     (normalised), r_atk, r_sight, r_body (tiles), hp, hp_max, value (elixir-equivalent), speed
     (tiles/s), flying, building_only, alive, king, target_xy (optional), deploying (bool).
   - `@dataclass Board`: objs: list[BoardObj], team (the scorer's team), t (seconds),
     tiles=(18,32), river_y (normalised), bridges_x (normalised tuple), tower_range, king_range.
   - `radii_of(spec_like, *, siege_sight, tower_range, king_range) -> (r_atk, r_sight)` -- the ONE
     source of truth used by both the reward and the overlay.
   - `band(x, lo, hi, w) -> float` per doc §1.
   - `board_from_engine(engine, team) -> Board` (lazy engine import; alive towers only; skip
     deploying units? NO -- include them with `deploying=True` so the timing term can see them).
   - `score_placement(board, placement) -> dict[str, float]` where placement = dict(card base key,
     kind, x, y, r_atk, r_sight, deploy_time, speed, building_only, is_spell, spell_radius) and the
     returned dict has one key per term: `p1_pull_band`, `p1_close_penalty`, `p2_cover`,
     `p3_intercept`, `p4_spell_frac`, `p4_nado`, `p4_king_activation`, `p5_timing`, `p6_siege`,
     `p7_fragility`, `bridge_block_detected`, `bridge_block_case`, plus `threat_base` (which
     enemy the terms were scored against) and `d_threat` tiles. Missing/irrelevant terms are 0.0.
     "ACTUAL threat" filter: score P1/P3/P5 only against enemy objs with value >= 3 elixir or
     building_only wincon; a lone Skeleton/Goblin is not a threat (doc §0 / owner).
   - `role_average_radii(base_key) -> (r_atk, r_sight)` : the role-level average (by KB role) so the
     gate can score with role-average radii too (doc §7.1 / §7.8). Use `clashrl.cards` KB; grep
     `sight_range_tiles`, `profile(` in `src/clashrl/card_threat.py` / `src/clashrl/cards.py`.
   - Everything deterministic; no RNG.
B. `tests/test_geometry_reward.py` (find the existing tests dir and its conventions first; run with
   the venv's pytest if present, else a `python -m` runner). Required cases: band() shape; P1 credits
   the pros' modal Tesla tile (9,21) vs a Hog at the bridge above the corner tile (1.5,18.5); P1
   close-penalty for a Tesla on top of a PEKKA; P6 = 0 for a dead princess and in-band for the king
   when both princesses are dead (doc §7.5); bridge block detected at (3.5,16) with a Hog approaching
   and NOT detected on a quiet board; tornado `away` = 1 when pulled straight away from the goal.
C. `sim-view --radii`: a flag on the `sim-view` subparser and `sim_view(...)`, passed into
   `render_frame(..., radii=False)`. When on: for every ALIVE unit/building/tower draw `r_atk` as a
   solid ring (team colour, 1 px) and `r_sight` as a dotted/dimmer ring; both read from
   `geometry_reward.radii_of`. Also, if the engine carries a `last_placement` attribute (set it in
   `sim_view` after each agent action: dict with x, y, base, t and the `score_placement` output), draw
   the P1 band annulus (lo..hi) around the scored threat and print the non-zero term values next to the
   placement for 1.5 s. Keep the flag OFF by default so existing behaviour is byte-identical.
   Verify by writing a 10 s mp4: `run.py sim-view --radii --out C:/Users/benpe/ClashBot/scratchpad/gauntlet/L58/radii.mp4 --no-window --matches 1`
   (check the real CLI flags first) and also dump 3 PNG frames to the L58 dir so the lead can look.
D. Report in the progress file: files touched with line ranges, the test output verbatim, any place
   where the doc's formula could not be implemented as written and what you did instead.

Rules from the project: one source of truth for radii; alive towers only; no penalties except
p1_close_penalty and p7_fragility (both bounded); never print secrets; write to disk as you go.
