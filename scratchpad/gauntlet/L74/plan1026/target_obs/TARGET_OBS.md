# TARGET-OBS: which unit targets which unit, as a model input (owner priority item 1, 10-30)

Grades: (a) measured (number + source), (b) plausible, untested, (c) contradicted.
Rule: this file and every tracked file it names are READER-AGNOSTIC. Reader internals (field names, layouts) stay in the
git-ignored `icebow/data/reader_targets/`. Tracked code consumes only the per-unit interface below.

## STATUS + restart point (keep current)
- 10-30 13:45 EDT: started. 14:05 M1 committed (de0f05e). 14:10 M2 + M3 code written, laptop tests 6/6 pass.
- 14:05 UTC (10:05 EDT pod clock) two REAL `rl_royale --smoke` runs on 33903 (tree `/workspace/tobs/cb` = pod tree c51efd9
  + origin match_memory + this change, crforge 5e8089a4 plain, tables 16.635.3, config `stepd/cfg/succ48_x_s101.yaml`):
  `tobs_absent` CPUs 186-189, `tobs_on` (`target_obs=on`) CPUs 190-193; logs `/workspace/tobs/logs/<run>.log`, wait for
  `SMOKE PASS`. Restart: `ssh ... -p 33903 'cd /workspace/tobs && setsid nohup ./tobs_smoke.sh tobs_on 190-193 target_obs=on &'`.
- RESTART POINT if this account stops before the code commit: the shared-file hunks are in the working tree
  (`pipeline/model_gen.py` encode_gen hook + add_target_in / target_in / load_state_dict; `e1_eval.py`, `rl_royale.py`,
  `batched_rollout.py`: grep `TARGET-OBS` / `tgt`); MEM-FULL has its own uncommitted hunks in model_gen.py -- commit only
  the hunks with those markers (origin file + filtered `git diff` hunks, then `safe_commit.sh` REPO_PATH=LOCAL_FILE).

## Interface (reader-agnostic)
Per body, in `sim_unit_state.extract`'s schema (SIM: `extract(battle)`; live: `live_unit_state.LiveCues.units(frame, prev)`):
`uid` (SIM) / `generation` (live) = a match-local id; `team`; `x`, `y` (tiles, engine frame); `attack.target` = the id
of the body it targets (None = none); `attack.frac` = attack progress 0..1 (None = idle); tower flag.

## M1: validation of the live target references (item 1)

### M1a. Internal consistency, 20 live logs (a)
Script and raw output are LOCAL (`icebow/data/reader_targets/consistency.py`, `CONSISTENCY.txt`; 20 newest live logs,
`live_play_20261030_082128` .. `_093916`, 43,853 unique-tick frames). "raw" = the reader's logged reference; "acq" = after
`LiveCues.units` (the existing far-default filter: edge distance > max(sight, range) + 1.5 tiles -> none). Legality uses
the 10-06 card table (`attacks_air`, `target_only_buildings`, `flying_height`, `kind`).

| check | count | reading |
|---|---:|---|
| non-tower body rows / with a raw target / with an acq target | 228,846 / 194,556 / 128,580 | |
| raw target not among the same frame's bodies | 0 | referential integrity holds (a) |
| raw target on the attacker's own team (bodies; towers) | 0; 0 | (a) |
| ground-only attacker -> flying target | 0 | (a), on rows with a table entry |
| building-only attacker (Giant, Hog, Balloon...) -> non-building | 0 | (a), same |
| attacker name with no 10-06 table row (legality not checked) | 36,348 raw (18.7%) | (b) hero / evo / newer forms; a gap in this check, not a reader fault |
| raw target farther than reach + 1.5 tiles | 53,115, of which a crown tower 53,108 (99.99%) | far references are the default path tower (a); 7 far non-tower refs |
| raw tower targets / acq tower targets (bodies) | 91,323 / 25,354 | 72% of "targets a tower" refs are default path goals, not locks (a) |
| attack progress > 0 with no reference (bodies) | 4,463 / 228,846 (1.95%) | (b) target died / retarget gap between samples |
| reference switches (acq) / previous target still on board | 1,446 / 850 | (b) retarget after range loss or priority; needs engine truth |
| acq lock length (frames of 2 ticks): median / p10 / p90 | 14 / 3 / 49 | locks persist (a) |
| raw edge distance / reach: p50 / p90 / p99 | 0.83 / 2.85 / 4.18 | |

Conclusion (a for the counts): the references are internally consistent -- right team, legal type, resolvable, persistent.
This is NOT target correctness (no engine truth here). The model feature must keep the path goal apart from the
acquired lock: the raw reference alone would say "targets a tower" for 3.6x more body-frames than the acquired one.

### M1b. Prior exact evidence (a, small sample)
`crforge/pilot/sme/SME.md` section 4.0-1: on the 41 body-position onsets (dossier2, SmeRun `SME_TGT=1`), every paired
body's engine reference equals the recorded reference at the previous frame. Small and selected (onset bodies only).

### M1c. Exact-replay validation recipe (not run: the SME pods 32657 / 33920 / 30408 are stopped, /workspace wiped)
Semantics: SmeRun `SME_TGT=1` writes `TargetingState.getReference()` = the RAW reference (default path tower included);
`CfCore.acquired()` is the facade's filtered one = what the SIM feature uses. Compare raw with raw, acq with acq.
1. Pod with JDK 17 + `/workspace/crforge_main/5e8089a4/tickprobe/lib` + tables 16.635.3 (33903 has all three; check
   load, <= 8 threads). Rebuild the FRESH harness from the tracked tree: `crforge/pilot/sme` (+ `fresh/runF.sh` env,
   pointing SME_LIB at the 5e8089a4 tickprobe lib), frames from `live_frames.py`, inputs `fresh/FRESH4_inputs_all.jsonl`.
2. Normal scored run on FRESH4 (`runF.sh`, KEEP=1) -> the per-frame exact / torn flags and each match's `plan.json`.
3. Cohort = the strictly exact matches (FRESH4: 48 / 61, SME.md STATUS); all frames up to the first divergence of the
   others reported separately. Freeze the list before scoring.
4. Per cohort match: `run_batch([(runnable(plan), last_tick, 0)])` with `SME_TGT=1` (dossier2.py's call), every tick.
   Reader side: `tgt_frames.py` rows. Pair bodies by exact (side, x, y) on exact frames (dossier2's `simpos` map), map
   the recorded target gen to the sim id the same way.
5. Metrics, bootstrap by match: raw agreement = P(engine ref == reader ref) over paired body-frames; acq agreement
   after `CfCore.acquired`'s rule on the engine side and `LiveCues.units` on the reader side; per class (tower, building,
   troop, building-only, air); switch timing offset in ticks. Planted controls: shift reader targets one frame, swap two
   targets, side flip -> agreement must drop.
Bar (proposal, b): acq agreement lower 95% bound >= 0.99 on exact frames before the live path feeds `target_obs`.

## M2: opt-in observation feature `target_obs` (item 2)
- **One function** `pipeline/target_obs.py target_rows(units, tok, mask, side)` -> `tgt` [U, 8] float32 + `tgt_idx` [U]
  int64. Inputs = the extract-schema body list both sides already produce: SIM `sim_target_rows(match)` (=
  `sim_unit_state.extract` on the battle at the decision tick; on crforge its `attack.target` is `CfCore.acquired`, via
  `cueSave`), live `live_target_rows(cues, frame, prev, tok, mask, side)` (= `LiveCues.units`). Token match =
  `live_unit_state.align`'s rule (test: identical assignment on 200 random boards).
- Per unit token: [known, target is a unit token, target is a crown tower, attack frac, dx, dy (target - me, board
  frame), unit tokens targeting me / 4, a crown tower targets me]; `tgt_idx` = the target's token index (-1 = none / a
  tower / an untokened body). Aggro: a building-only unit's acquired building (a tower or our X-Bow / Tesla token) and its
  direction are in the row; the default PATH goal (before acquisition) is deliberately not a target (M1a: 72% of raw
  tower references are path goals).
- Wiring (absent key = byte-identical; config hash: `target_obs` absent / null / false popped -> the pre-change hash,
  pinned vs de0f05e in `pipeline/tests/test_target_obs.py`): `rl_royale` key `target_obs` (bool), init gets the zero layers;
  `e1_eval.GEN_TGT_KEYS = ("tgt", "tgt_idx")` in `gen_row_keys` / `gen_row` / the trajectory stack; rl_royale collate +
  `branch_row`; `batched_rollout` never vmaps a tgt model with plain ones.
- **Live is NOT wired** (no live change without the lead). Owed in `live_gen.GenPilot.row`, next to the cue block:
  `if getattr(self.model, "tgt_in", None) is not None:` -> require `self.cues`, then
  `rows, idx = live_target_rows(self.cues, raw_frame, prev, tok, mask, side)`; `b["tgt"] = T(rows, torch.float32)`;
  `b["tgt_idx"] = T(idx)`. Until then a tgt checkpoint must not go live (without b["tgt"] its layers are skipped: it
  plays target-blind, silently).
- **Java fast loop (CfTrain) not built** (no JDK on the laptop; pods busy). What it needs: a `CfTgt.build` beside
  `speed/crforge/obsid/CfCue.build` that reuses CfCue's token match verbatim (ti / ord-by-uid / argmin loop), records the
  body->token map, then per matched body: `CfCore.acquired(w)` -> entity id -> token index or tower flag, `frac` = CfCue's
  `prog % hs / hs` (0 when idle), dx / dy from the two entities' x / y (seat 1 mirrored), incoming counts over all units
  (towers included). CfTrain: buffers `tgtB` [rows, U, 8] float + `tgtIdxB` [rows, U] int64, a stage beside "cue", and
  `fastloop.py` handing them to the batch as `tgt` / `tgt_idx`. Identity test: Java rows == `sim_target_rows` on the same
  crforge states (the CfCue / sim_cue_rows identity harness in `speed/crforge/obsid/obs_id.py` is the template).

## M3: function-preserving model expansion (item 3)
`GenModel.add_target_in()`: `tgt_in` Linear(8 -> d), `tgt_out` Linear(d -> d) on the TARGET token's embedding (a
message "what I am locked on"), `tgt_back` Linear(d -> d) on the sum of the tokens targeting me; all no-bias, all
zero-initialised, added to each unit token's input embedding (the cue_in hook point). Loaded by content
(`tgt_in.weight` in the state dict builds them; a pre-target checkpoint into a model with them zero-fills those keys).

## Evidence (a)
- `pipeline/tests/test_target_obs.py`, 6 / 6 pass (live venv `icebow/.venv`, CPU, 31.5 s): CLXIII NOLEAK (fv6, cue_in)
  + zero target layers = CLXIII **bit-identical** (`torch.equal` on gate, card, wait, value, g, cell) on 60 recorded
  live decisions (`live_play_20261026_161448`) with random target rows, with the real live target rows, and without
  them; non-zero weights change g (wired in); all-none rows with non-zero weights = identical (no bias); state-dict round
  trip. Real live rows on those 60 decisions: 135 matched tokens, 68 target edges (all to ENEMY tokens, 0 own-side), 11
  tower targets, 28 tokens targeted by a tower.
- Config hash absent / null / false == the pre-change rl_royale's (de0f05e) and != on.
- pyflakes clean on the 5 files (2 pre-existing warnings in e1_eval untouched).

## Concerns (graded)
- (b) SIM / live "acquired" rules differ: the facade keeps a reference within target radius + sight + own radius (+ the
  crown-tower / building extra) by centre distance; live drops one whose EDGE distance > max(sight, range) + 1.5 tiles.
  Near the boundary the two can disagree. M1c measures exactly this (acq agreement on exact frames).
- (b) 18.7% of live attacker names have no 10-06 table row: LiveCues then takes the reach from the reader's own
  definition rows, and keeps a far reference when that is missing too (reach 0), so such a unit may show its path
  tower as a target live while the SIM shows none. Count it in M1c.
- The feature is untrained: it changes play only after training (owner step iv) + the SIM gate.
