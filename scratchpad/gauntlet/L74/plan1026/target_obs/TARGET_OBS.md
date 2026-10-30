# TARGET-OBS: which unit targets which unit, as a model input (owner priority item 1, 10-30)

Grades: (a) measured (number + source), (b) plausible, untested, (c) contradicted.
Rule: this file and every tracked file it names are READER-AGNOSTIC. Reader internals (field names, layouts) stay in the
git-ignored `icebow/data/reader_targets/`. Tracked code consumes only the per-unit interface below.

## STATUS + restart point (keep current)
- 10-30 13:45 EDT: started. Doc skeleton committed. Next: M1 live internal-consistency measurement (laptop).

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
