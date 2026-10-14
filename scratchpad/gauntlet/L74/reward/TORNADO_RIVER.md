# Tornado vs the river (owner fact 2026-10-14)

Owner fact: in real CR a Tornado cannot drag GROUND troops over the river; they are held at the bank. Air units cross.

## Task A: does RoyaleSim respect it?

**Verdict: depends on the runtime.**
- **royalesim 0.1.33 (`ROYALE_RUNTIME=20261012[-linux]`, build cacb700): yes, it matches.** Ground units are held at the water edge. Air units cross.
- **royalesim 0.1.17 (`20261005` / `20261006[-linux]`): no, it does not match.** The Tornado drags ground units through the water to the far bank.
- The rule is a calibration arm: `status.ATTRACT_WATER_EDGE`.
  - `walk_rule` = the old arm, which pulls units into the river. The 20261005 and 20261006 runtimes ship this one (it is in their `royalesim/data/calibration.json`).
  - `client15535_pull_stops` = 0.1.33's shipped arm, which holds them at the edge.
  - The 0.1.17 binary also accepts `calibration_overrides={"status.ATTRACT_WATER_EDGE": "client15535_pull_stops"}`. With it, its Knight and Goblins stop at y 17000 (measured).

**Probe** (`tornado_river_probe.py`, pod 12037, venv33, 1 process, nice 19). Raw outputs: `tornado_river_probe_0133.json` and `tornado_river_probe_0117.json`.
- **Setup:** one Red unit is placed already deployed with `MatchSetup.spawns`. Blue casts a Tornado from hand on the other bank.
- **What is recorded:** `debug_units` positions every tick for 40 ticks.
- **Geometry** (`Battle.passable_half_cells`): water is y 15000..17000. The bridges are x 2500..4500 and x 13500..15500.

Units are placed at (9000, 18000) and the Tornado lands at (9500, 13500), unless the row says otherwise. Results on 0.1.33 (shipped arm):

| case | per-tick result |
|---|---|
| Knight, own bank | Pulled about 230 mt/tick in -y on t2..t5. Stands exactly on **y = 17000 for t6..t22** (17 ticks), 0 ticks in water. Its x drifts 8840 -> 8641: its own walk toward the left bridge minus the pull's +x part. The pull ends after t22 (cast + 1..+21). It then walks off along the bank to (7575, 17141). Never crosses. |
| Goblin (1 body) | Held on y = 17000 for t3..t22, 0 ticks in water, never crosses. |
| Skeleton (1 body) | Held on y = 17000 for t4..t11. The Tornado's damage kills it on t11 (81 hp at level 11). |
| **Minion (air control)** | **5 ticks over water (t4..t8)**, crosses to y 14747 on t9, then circles the centre within about 0.3 tiles until t22. |
| Knight ON the right bridge (14542, 15958), Tornado at (11500, 14500) | Moves down and left along the bridge. Held at the bridge's edge **x = 13500 on t7..t8**. Once it reaches y < 15000 (land) it keeps going -x on Blue's bank. It crosses **by the bridge**, with 0 ticks in water. |
| Knight on the bridge (14542, 16458), Tornado straight below at (14500, 13500) | Pulled straight down the bridge to the centre by t12. Crosses by the bridge. |
| Contrast: Knight, own bank, `walk_rule` override (0.1.33) | **In water for 11 ticks (t6..t16)** and ends at y 13313 on the far side. |
| Same scenes on the 0.1.17 runtime (shipped `walk_rule`) | Knight: 11 water ticks, ends at y 13285. Goblin: 5 water ticks, ends at y 11999. Skeleton: 8 water ticks, crosses to y 14908. |

**Does the held unit path to a bridge?** No. The pull does not re-route the unit:
- The step is clamped per axis. At the edge the y part is zeroed, while the pull's x part and the unit's own walk continue.
- The Knight was already walking toward the left bridge as its normal route, and it resumed that route when the Tornado ended.

**Code path** (research/ext/Royale/RoyaleSim, crates/royalesim/src):
- `state.rs:23463` builds the pull vector `attract[i]`. This is the ATTRACT_LAW step, catalog speed x 360 / 100 (Knight 216).
- `state.rs:24227` decides whether the hold applies: `let pull_edge = !flying && attract[i] != (0, 0) && calib.attract_water_edge == AttractWaterEdge::Client15535PullStops;`
- That flag goes to `move16402::grid_move`, `pushback_step_extra` and `move_towards_extra`, on every write that carries the pull: `state.rs:24370, 24582, 24650, 25429`.
- `move16402.rs:705 grid_move`: when `flag && is_water(next cell)`, it clamps that axis to the cell edge, separately for x and for y.
- The arm's definition and its evidence are at `state.rs:6130-6146`. Measured on client 15.535.29 (sp-form-Valkyrie-evo-s0): 31 unit-ticks held at the edge, and across the 15.535 captures no pushed or pulled step ever entered water from land.
- The Python serde default for snapshots older than format 20 is `walk_rule` (`state.rs:3039`). So a blob saved by an old build would load the old arm.

**Training consequence:**
- 34 of the 46 `ROYALE_RUNTIME=` settings in L74 shell scripts use `20261006-linux`. The Rocket+Tornado SIM verdicts (rocket_value2: 6x `20261006-linux`, 1x `20261006`) were measured where the Tornado drags far-bank ground clumps over the river.
- Inference, not re-run: that overstates the combo for the cross-river case.
- The deployed live checkpoint (newsim_r1) was trained on 0.1.33, which holds units at the bank.

## Task B: our combo aiming

**Aim logic** (shared by SIM and live): `pipeline/decision_options.py:1468-1493 best_tornado_centre`.
- `:1480 inside = dist <= reach`. A body counts as "pulled" if its straight-line distance to the centre is within the Tornado radius (5.5, + the body's radius under `edge`).
- The only exception is immobile buildings (`:1482-1485`). The rule makes **no river and no air/ground distinction**.
- The centre must be at y >= 16 (my half, which includes the near half of the river).
- The **Rocket and the Tornado are aimed at that same cell**:
  - live: `pipeline/live_gen_v2.py:259` `xy = cell_xy(cell, ...)` is used for the Rocket, and `:264` uses it for the Tornado follow-up;
  - SIM: `decision_options.py:1633`.
- **So no: ground units on opposite banks are NOT treated as separate groups.**

**Live count:** `tornado_river_live.py` -> `tornado_river_live.out`. It covers 47 logs, live_play_20261010_031608 .. 20261014_184013.
- **56 `why=rocket_tornado` decisions.** 54 Tornado follow-ups were played and 2 were cancelled.
- The rule's aim was **reproduced 56/56** from the logged `model_bodies` (lattice grid), so these are exactly the bodies it saw.
- 43/56 aimed at **y = 16.0 exactly**, the river's midline (the closest legal point to the enemy bank).
- **45/56 counted ground bodies on the enemy bank (y < 15) as pulled.**
- **17/56 spanned both banks**: ground bodies counted on the enemy bank AND on mine (y >= 17).
- Share of all value the rule counted:

  | source | share |
  |---|---|
  | enemy-bank ground | **48.6 %** |
  | my-bank ground | 18.5 % |
  | air | 18.7 % |
  | rest: bodies on the river rows (bridges) | 14.2 % |

- 111 enemy-bank ground bodies were counted. Only **63** are inside the Rocket blast at the point where the river holds them (x unchanged, y = 15). This is conservative: no slide along the bank is credited. The other **48 are not inside**.
- Without those 48 bodies, **6/56 combos fall below V = 9 and would not have fired**. This is a lower bound, because bodies on the enemy bank inside the bridge columns were kept as "can cross". The split-lane opens show the gap:
  - 20261012_004348 t496: Three Musketeers split plus Golden Knight in front of both bridges, centre (8.5, 16.0);
  - 20261013_061203 t351: Archers plus Elite Barbarians split, centre (9.0, 16.0).
  - In both, one Tornado "gathers" two lanes about 9.5 tiles apart, across the river.

**Related, same assumption:** `pipeline/extrapolate.py`. The live board is extrapolated 24 ticks ahead, and its Tornado pull ignores the river:
- `:373` pull step;
- `:416` `x, y = x + vx*m + ex, ...`;
- `:69-70` its docstring says "NOT modelled: ... river / building collisions".
- So after my own Tornado, the model's input shows far-bank ground bodies dragged into or over the river.

## Proposed fixes (not applied; live code untouched)

1. **`best_tornado_centre`** (one shared function, so SIM and live change together; same pattern as the existing building rule at `:1482-1485`):
   - Take a body that is ground (`log_air_traits()[cls][0]` is False), at y < 15, and outside the bridge columns.
   - Count it for a centre only if the Rocket blast at that centre covers its held point: `hypot(bx - cx, 15 - cy) <= rocket_radius (+ radius under edge)`.
   - Use the held point in the plateau tie-break as well.
   - Optional stricter version: a body in front of a bridge counts as crossing only if the pull direction keeps it inside the bridge columns.
2. **`extrapolate.retrack`**: give ground bodies RoyaleSim's per-axis water stop. If a pull step would move one into a water half-cell, clamp that axis at y 15000 or 17000 (raw), or at the bridge's x edge. This is the same rule as `move16402.grid_move` with the flag on.
3. **SIM runs on the 20261006 runtime** (anything that judges the combo): pass `status.ATTRACT_WATER_EDGE=client15535_pull_stops`, or run on 20261012. On 0.1.17 that override was measured to hold units at the bank.
