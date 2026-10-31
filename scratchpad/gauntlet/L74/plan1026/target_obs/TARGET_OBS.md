# TARGET-OBS: which unit targets which unit, as a model input (owner priority item 1, 10-30)

Grades: (a) measured (number + source), (b) plausible, untested, (c) contradicted.
Rule: this file and every tracked file it names are READER-AGNOSTIC. Reader internals (field names, layouts) stay in the
git-ignored `icebow/data/reader_targets/`. Tracked code consumes only the per-unit interface below.

## STATUS + restart point (keep current)
- **LIVE-TGT 10-31 (worker, lead account 3; owner-agreed 10-30): live wiring + reader target rule DONE, deploy recipe
  written, NOT applied.** Section "LIVE-TGT" below = what changed, evidence, recipe. Nothing of mine runs anywhere.
  Live was not started / stopped by me; the lead's ~21:30 EDT restart (lethal_rocket log) already imported this code with
  CLXIII = the absent path, proven identical below.
  Codex: `.foreman/scratch/a2/codex/LIVE-TGT_1.md` (effort low, 459 s): tval_score + tval_agg on 33903 CPUs 200-211 over
  tv_f4/5/6 -> `tval_fresh456_85.txt`; it reported BLOCKED only because the ticket expected 108 scored matches (85 =
  every unflagged one; the scorer skips flagged matches by design); numbers checked against the file. Pod outputs
  `/workspace/tval/lt_f{4,5,6}.jsonl`, `lt_agg.txt`, env `/workspace/tval/tv_env_lt.sh` (nothing left running).
  Re-run the replays: `PY=icebow/.venv/Scripts/python.exe; T=scratchpad/gauntlet/L74/plan1026/target_obs/live_tgt_replay.py;
  $PY -B $T mkckpt icebow/data/models/ICEBOW/ICEBOW_Mark_CLXIII_NOLEAK.pt Z.pt P.pt; HEAD_CODE=d6cd6d0 $PY -B $T run
  <CLXIII> A.pt; $PY -B $T run <CLXIII> B.pt; $PY -B $T diff A.pt B.pt` (FORCE_ACQ=engine for the rule effect; LOG args
  for other logs). Reader-rule identity (local): `$PY -B icebow/data/reader_targets/acq_check.py .foreman/scratch/tval/reader
  .foreman/scratch/tval/matches.txt OUT.json` (~30 min).
- 10-30 13:45 EDT: started. 14:05 M1 committed (de0f05e). 14:10 M2 + M3 code written, laptop tests pass.
- 14:05 UTC (10:05 EDT pod clock) two REAL `rl_royale --smoke` runs on 33903 (tree `/workspace/tobs/cb` = pod tree c51efd9
  + origin match_memory + this change, crforge 5e8089a4 plain, tables 16.635.3, config `stepd/cfg/succ48_x_s101.yaml`):
  `tobs_absent` CPUs 186-189, `tobs_on` (`target_obs=on`) CPUs 190-193; logs `/workspace/tobs/logs/<run>.log`, wait for
  `SMOKE PASS`. Restart: `ssh ... -p 33903 'cd /workspace/tobs && setsid nohup ./tobs_smoke.sh tobs_on 190-193 target_obs=on &'`.
- 14:25 smoke `tobs_on` try 1 CRASHED at u0 `KeyError('tgt')` (a): `e1_eval.Match` record filter (cfg["record"]) had no
  GEN_TGT_KEYS -> fixed; re-run as `tobs_on2` (same CPUs). Laptop tests could not see it (no SIM match in them).
- 14:50 BOTH SMOKES PASS (a): `tobs_absent` config sha b5e2a2bbafef (= the earlier oplc_base1 smoke's sha on the
  same yaml: the historical hash), `tobs_on2` (target_obs=on) config sha 15a4bbcf919e; both: u0 round trip identical,
  resume check all True, `SMOKE PASS`. In the smoke only the value head moves (critic warm-up), so the target layers
  stay 0 there; `test_zero_layers_get_gradients` shows all three get non-zero gradients from real rows.
- 14:55 M2+M3 code COMMITTED (see git log "TARGET-OBS M2+M3"). Pod tree `/workspace/tobs/cb` kept (1.3 GB; delete when
  done). No process of mine runs on any pod.
- **TARGET-VAL (M1c) 10-30 ~15:00 UTC, running.** Pod 33903 CPUs 238-249 (shared with the opponent arm's floating
  workers, affinity 180-185,240-255: load ~80% there before start). (1) gate re-run on FRESH4/5/6, ASSIGN off (=
  the byte-identity references), `/workspace/smeR/runs/tv_f{4,5,6}` via `/workspace/smeR/runs/tv_gate.sh` (log
  `tv_gate.out`); (2) engine dump = SmeRun copy `SME_TGT=2` (`target_obs/patch_smerun.py`; raw ref + `CfCore.acquired`
  verbatim + attacking + self flags; P rows owner + target), built at `/workspace/tval/build`; sim identical to the gate
  build on 151109 (6,213 ticks, 0 differing ticks with the new fields stripped; only `CharacterEntity@hash` strings in
  `ab` differ between ANY two builds, same class file too) (a); (3) reader rows = per-unit interface, made locally
  (git-ignored converter), at `/workspace/tval/reader/`; (4) `target_obs/tval_score.py` via `target_obs/tv_env.sh`.
  Restart: `cd /workspace/tval && bash tv_env.sh python3 tval_score.py /workspace/smeR/runs/tv_fN/results.jsonl
  /workspace/smeR/runs/tv_fN /workspace/smeR/data/freshN/frames reader tv_fN.jsonl` (gate first if tv_fN missing).
  **~15:20 UTC FIRST RESULT (section M1c-R): 33 FRESH4 matches** (the 43 of 78 the gate had finished; 33 unflagged).
  acq agreement today 0.9812 (CI 0.965-0.993) FAILS the 0.99 bar; the proposed engine-formula rule 0.9983 (CI
  0.9977-0.9988) passes it. Gate still running for the rest of FRESH4 + FRESH5/6; re-score all with the restart
  command above, then `python3 tval_agg.py tv_f4.jsonl tv_f5.jsonl tv_f6.jsonl`.
- CFTGT (10-30 ~10:50 EDT, the Java fast-loop builder, M2 owed item (3)): code written + committed (see git log "CFTGT"):
  `speed/crforge/obsid/CfTgt.java` (target_rows line for line on the facade; CfCue's token match copied verbatim),
  CfTrain `enableTargets()` + tgt / tgt_idx buffers built in the cue stage right after CfCue, producer.py (`target_obs`
  on -> enableTargets, `Rows.targets`, batch tgt / tgt_idx for a model with tgt_in, fast_traj), serve.py ROW keys.
  Absent key: no CfTgt call, no buffer. Pod tree `33903:/workspace/cftgt/cb` (= /workspace/opplearnc/cbd + HEAD code +
  these files; jbuild_fe364ceb compiled). Exactness (compare.py on a target_obs-on dump) + fast-loop smoke: PENDING.
  1974fbf was cut on a stale base and reverted FAST-LIVEOPP's hunks; bfc560e restores them (net vs f79166f = CFTGT only).
- 11:05 EDT RUNNING on 33903 CPUs 170-177: `/workspace/cftgt/chain.sh b` = for arm on / absent: fast-loop `rl_royale
  --smoke` (ref_v0.yaml, `target_obs=on` for arm on, FASTLOOP_DUMP) then compare.py on its `fast_msg_u0000.pkl`
  (`/workspace/cftgt/cmp_{on,absent}_b.json`). Logs `/workspace/cftgt/logs/{cftgt_fl_on_b,cftgt_fl_absent_b}.log`, rc
  lines `logs/chain_b.rc` (CHAIN_DONE at the end). Launcher `/workspace/cftgt/fl.sh` (= opp/learner/fl_pod.sh fixed to
  this tree; NOT /workspace/opplearnc/fl.sh, which hard-codes the cbc tree). Restart: `ssh ... -p 33903 'cd /workspace/cftgt
  && (setsid nohup bash chain.sh d > logs/chain_d.out 2>&1 < /dev/null &)'` (new tag = new run names).
- 11:35 EDT chain b's on-arm SMOKE FAIL (a): producer guard "a model with target layers in a run without target_obs":
  rl_royale's actor_base carries no `target_obs` key. Fix 933d7d0: the producer enables CfTgt when the learner state
  dict has `tgt_in.weight`. Chain b stopped by PID; chain c = same recipe, tag c, logs `*_c`.
- 12:10 EDT CFTGT RESULT (a), chain c on 33903 (tree = 933d7d0 code, crforge fe364ceb, tables 16.635.3, ref_v0.yaml, CPU):
  on: fast-loop `rl_royale --smoke target_obs=on` SMOKE PASS (config sha cf723ac91ec8, resume check all True);
  compare.py on its u0000 message 8 / 8 matches identical, first_div_keys {}, lp maxdiff 0.0. compare.py skips a key one
  side lacks, so `/workspace/cftgt/tgt_probe.py` (scratch, not tracked) checked it: tgt + tgt_idx in BOTH paths' learner
  trajs, byte + dtype + shape equal on all 8 (2,388 rows; 6 side 1, 2 side 0): 12,871 known tokens, 6,011 unit edges
  (idx >= 0 exactly on the flag), 1,836 tower targets, 3,387 frac > 0, 1,559 tower-targets-me.
  absent: fast-loop smoke SMOKE PASS (config sha 3708e44383a5), compare.py 8 / 8 identical, first_div_keys {}.
  Pod results: `/workspace/cftgt/cmp_{on,absent}_c.json`, `probe_on_c.json`. No process of mine left running on the pod.
- NEXT (owner steps, not started): (1) M1c exact validation (recipe below; SME-REBUILD 18f614a now has rebuild scripts
  for the SME gate on 33903: `crforge/pilot/sme/recon/rebuild_gate.sh`); (2) live wiring in live_gen (lead approval);
  (3) CfTgt Java builder: DONE (CFTGT above); (4) train with `target_obs: on` from B0 / CLXIII + SIM gate.

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

### M1c-R. Result, FRESH4 partial: 33 unflagged matches (26 strictly exact), 71,052 prefix-exact frames (a)
Run as the recipe, with these choices (fixed in code, 1e0a00f, before any score): gate = `sme/recon/runR.sh` with
ASSIGN off on 33903; engine = SmeRun `SME_TGT=2` (`patch_smerun.py`: raw ref + `CfCore.acquired` verbatim);
exact frames = recorded ticks before the match's first divergence and not torn (so the lock HISTORY is equal too);
bodies paired by unique (side, x, y), co-located bodies (a hero + its companion) by unique name. Paired 763,607 /
763,702 reader body rows (99.99%), 59,740 / 59,970 projectiles. CI = 95% bootstrap over matches (2,000 resamples).
Full table: `target_obs/tval_f4_33.txt`. "active" = rows where either side has a target.

| metric (all 33 matches) | agree / n | rate | 95% CI |
|---|---:|---:|---|
| raw reference, all bodies | 643,383 / 763,607 | 0.8426 | 0.830-0.856 |
| raw, troops / air / building-only / buildings / X-Bow+Mortar | -- | 0.9997 / 0.9991 / 1.0000 / 1.0000 / 1.0000 | |
| raw, crown towers | 296,341 / 416,481 | 0.7115 | 0.692-0.734 |
| **acq (what the feature uses), today's live rule** | 749,242 / 763,607 | **0.9812** | **0.965-0.993: FAILS the 0.99 bar** |
| acq active, today's rule | 231,057 / 245,422 | 0.9415 | 0.897-0.977 |
| acq today: troop / air / bld-only / building / siege / tower | -- | 0.9838 / 0.9894 / 0.9892 / 0.9525 / 1.0000 / 0.9804 | |
| **acq2 = PROPOSED rule (CfCore.acquired's formula on the reader's inputs)** | 762,305 / 763,607 | **0.9983** | **0.9977-0.9988: passes** |
| acq2 active | 234,077 / 235,379 | 0.9945 | 0.9926-0.9961 |
| acq2: troop / air / bld-only / building / siege / tower | -- | 0.9949 / 0.9995 / 1.0000 / 1.0000 / 1.0000 / 0.9999 | |
| projectile target (attack shots / spells) | 49,344 / 49,348; 10,392 / 10,392 | 0.9999 / 1.0000 | |
| projectile source, attack shots | 49,347 / 49,348 | 1.0000 | |
| strict cohort (26 matches): acq / acq2 | -- | 0.9793 / 0.9983 | 0.960-0.993 / 0.9976-0.9989 |
| planted: rotate targets among a frame's attackers / shift reader one frame | 78,625 / 232,381; 729,657 / 759,386 | 0.338 / 0.961 | both drop (locks persist, so the shift drops little) |

Disagreement classes (a, counts over the 33 matches), each with the fix in the ONE shared acquired rule
(`LiveCues.units`' far-reference filter, which `target_obs.live_target_rows` consumes; no per-card case):
1. **Range edge vs centre rule, crown-tower targets: 4,236 acq rows (engine keeps, live drops)**, e.g. Skeleton 734,
   IceWizardHero companion 577, Knight 339 -> PrincessTower. Engine: keep iff centre distance <= target radius + own
   SIGHT + own radius + 2.0 tiles (`EXTRA_SIGHT_RANGE_TO_CROWN_TOWERS = 2000`, building extra 0, read with javap from the
   5e8089a4 lib); live: drop iff EDGE distance > max(sight, range) + 1.5 tiles. Vs a crown tower live is 0.5 tile short.
2. **No-reach bodies keep a far reference: 10,043 acq rows (live keeps, engine drops)**: tower troops DaggerDuchess
   4,891 / ChefTower 2,864 + 371, TombstoneHero dummies 1,484 + 235. A name without a table row (and no definition
   reach) skips the live filter (`if reach and ...`), so its default target survives; the engine's reach is radii only.
   This is the M1a "18.7% no table row" concern (b), now (a): it is the larger error.
   - **Fix for 1 + 2 (one rule): acq = ref if attacking, else ref iff centre <= r_target + sight + r_own + (2 tiles if
     the target is a crown tower), with sight 0 when unknown.** Measured as acq2 above: 14,365 -> 1,302 disagreements.
3. **Remaining acq2 disagreements, 1,216 rows: hero / evo / spawned forms with no table row** (IceWizardHero companion
   310, TombstoneHeroSkeleton ~300, BowlerHero 125, Witch_EV1 skeletons ~170) at 5.6-13.9 tiles: their sight is
   unknown, so acq2 drops what the engine keeps. Fix (b, untested): the table lookup falls back to the definition's
   SightRange, then to the base card's row (the table owes those names); still one rule, a lookup gap, not a case.
4. **Path-tower default in the RAW reference, crown towers: 120,157 raw rows**: the engine's King Tower holds a Princess
   Tower (or a tower troop) as its raw reference; the reader's King Tower holds none. acq is equal on all of them
   (both none). Fix: none needed for the feature (acq only); a raw comparison must treat tower defaults as none.
5. **Retarget timing: 5 rows in 763,607** (offsets +1, +1, -2, -4, -6 ticks), 21 `rd_none` rows (reader has no
   reference where engine has one, not a tower), 19 MiniPekkaHero -> PrincessTower (raw differs too), 41 target
   unpaired. Retarget timing is NOT a material error class on exact frames (a).
6. Projectile source for spell / spawned projectiles (Log, Firecracker explosion, Cannon_EV1 barrage: 10,392): the
   engine owner is id 0 (no body), the reader's none: a labelling difference, the targets agree 10,392 / 10,392.
Not covered: per-card Mortar / Inferno rates (a Mortar is in 1 scored match, 201103, whose exact prefix ends at 1606;
Inferno in 2, 162534 / 173440; they sit in the siege / building rows, not split out), FRESH5/6 and the other
28 FRESH4 matches (gate still running). Grades: rates above (a) on this cohort; generalising to other decks (b).

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
- **Live: WIRED (LIVE-TGT 10-31, section below).** `live_gen.GenPilot.row`: a checkpoint with `tgt_in` gets
  `b["tgt"]` / `b["tgt_idx"]` = `live_target_rows(self.cues, raw_frame, prev, tok, mask, side)` (refuses without a cue
  source); `live_play.load_pilot` refuses it without `--cue-inputs on` and builds its LiveCues with `acq_rule="engine"`.
- **Java fast loop: BUILT** (CFTGT in STATUS; the spec it was built from:) a `CfTgt.build` beside
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
- `pipeline/tests/test_target_obs.py`, 7 / 7 pass (live venv `icebow/.venv`, CPU, 30 s): CLXIII NOLEAK (fv6, cue_in)
  + zero target layers = CLXIII **bit-identical** (`torch.equal` on gate, card, wait, value, g, cell) on 60 recorded
  live decisions (`live_play_20261026_161448`) with random target rows, with the real live target rows, and without
  them; non-zero weights change g (wired in); all-none rows with non-zero weights = identical (no bias); state-dict round
  trip. Real live rows on those 60 decisions: 135 matched tokens, 68 target edges (all to ENEMY tokens, 0 own-side), 11
  tower targets, 28 tokens targeted by a tower.
- Config hash absent / null / false == the pre-change rl_royale's (de0f05e) and != on.
- pyflakes clean on the 5 files (2 pre-existing warnings in e1_eval untouched). Existing absent-key tests still pass:
  `test_cue_inputs` TestModel + TestConfig 7 / 7, `test_decide_identity::test_live_recorded_decisions_identical_to_base` 1 / 1.
- SIM rows on crforge 5e8089a4 (`sim_rows.py 4` on 33903, 4 recorded self-play matches, tiny learner): 1,132 rows,
  4,308 matched tokens, 1,042 target edges, **0 edges onto the attacker's own side**, 725 tower targets, 640 tokens
  targeted by a tower, 700 with attack progress > 0. (Live 60 decisions: 135 / 68 / 0 / 11 / 28; other decks and
  policies, so the rates are not comparable.)
- Real `rl_royale --smoke` x 2 on 33903 (absent + target_obs=on): PASS (STATUS above).

## LIVE-TGT (10-31): reader target rule + target_obs live wiring + deploy recipe
### What changed (all opt-in by checkpoint CONTENT; CLXIII = the absent path)
- `pipeline/live_unit_state.py`: `LiveCues(acq_rule="live" | "engine")`, default "live" = the S6 far-target rule, code
  path unchanged. "engine" = M1c-R's proposed rule exactly (= `icebow/data/reader_targets/tval_reader.py eng_rule`, the
  scored acq2 column): keep the reference while engaged, else iff centre distance <= target radius + own sight (table,
  else the reader's definition, else 0) + own radius (+ 2 tiles, `CROWN_EXTRA_MT`, to a crown tower). One rule; it
  replaces the S6 filter AND the "no attack holds none" rule (eng_rule has neither). It feeds the cue rows too (state,
  has_target, target_is_tower, phase, frac all read the acquired target), which is right for a crforge-trained model:
  crforge's SIM cue and target rows both come from `CfCore.acquired`.
- `pipeline/live_gen.py` GenPilot.row: a `tgt_in` model gets `b["tgt"]` / `b["tgt_idx"]` = `live_target_rows(self.cues,
  raw_frame, prev, tok, mask, side)` (the cue block's frame / prev / tokens); no cue source -> ValueError (never
  target-blind); `self.tgt_log` = {known, edges, tower, acq_rule} -> `live_gen_v2._audited` puts it in the decision as
  'tgt' (live_play logs it in the 'decision' event). No `tgt_in` = not one new line runs.
- `live_play.py` load_pilot: a `tgt_in` model needs `--cue-inputs on` (SystemExit otherwise) and gets
  `LiveCues(acq_rule="engine")`; any other model `LiveCues()` as before. `cue_log` (--check JSON / start event) adds
  `targets: true, acq_rule: engine` for a target model only. 'tgt' added to the decision-event key list (absent for CLXIII).
- `b0_identity.compare` strips the log-only 'tgt' like 'xb_lock_p'. Harness: `target_obs/live_tgt_replay.py` (run with
  FORCE_ACQ / HEAD_CODE, mkckpt, diff).
- Why the rule is keyed to target layers and not on for CLXIII: CLXIII reads has_target / target_is_tower / state /
  phase / frac cue floats, so the rule moves its inputs (counts below); owner rule = CLXIII unchanged while the key is
  absent. (b) a crforge-trained successor WITHOUT target layers would want "engine" too: a one-line live_play flag if
  that case appears.

### Evidence
- (a) Reader rule = the scored rule, row for row: `icebow/data/reader_targets/acq_check.py` (local; re-runs the TARGET-VAL
  converter with each acq_rule) on all 108 FRESH4/5/6 matches: 238,108 usable frames, 2,534,433 body rows;
  `LiveCues(acq_rule="engine")` == stored acq2 on 2,534,433 / 2,534,433, default "live" == stored acq on 2,534,433 /
  2,534,433 (the old rule reproduced exactly); the two rules differ on 52,170 rows (2.06%). Result
  `icebow/data/reader_targets/ACQ_CHECK.json`.
- (a) Agreement with the engine (tval_score / tval_agg re-run by Codex on 33903 on every UNFLAGGED match of FRESH4/5/6 =
  61 + 12 + 12 = 85; 174,416 prefix-exact frames, 1,836,210 paired body rows; `target_obs/tval_fresh456_85.txt`):
  acq (S6 rule) 0.9852 [0.9763, 0.9918] -> **acq2 = the new rule 0.9985 [0.9982, 0.9988]** (bar: lower bound >= 0.99);
  active rows 0.9522 -> 0.9951; strict cohort (68 matches) 0.9864 -> 0.9986 [0.9982, 0.9989]. Per class (acq2): troop
  0.9957, air 0.9996, bld_only 0.9996, building 0.9999, siege 1.0000, tower 0.9999. Remaining acq2 errors: 2,322
  `acq_filter_eng_keeps` (class 3 above: names without a table sight) + 278 rd_none + 45 unpaired + 20. Planted controls
  drop (rotate 0.342, shift 0.966). The 33-match M1c-R cohort (subset) was 0.9983.
- (a) Absent path identical, 4 recorded CLXIII logs (test_decide_identity.LOGS, 1,718 decisions, 229 plays), CPU:
  pre-change code (HEAD d6cd6d0, run before any edit) vs this tree: decision dicts 1,718 / 1,718, taps 1,718 / 1,718,
  RNG states 1,718 / 1,718, max |log-prob diff| 0 on gate, card, cell, value, wait, g -> IDENTICAL.
  16 newest full 10-30 CLXIII logs (19:32-21:13 EDT, incl. one after the 21:03 rule strip; 6,030 decisions;
  `live_tgt_replay.py run` with HEAD_CODE=d6cd6d0 vs this tree, `diff`): dicts 6,030 / 6,030, taps 0 differ, RNG 6,030,
  log-probs 0 on the 5,737 decisions through `_policy_forward` (293 = the legacy decide path of the post-strip log,
  options inactive then: compared by dict incl. p_play) -> IDENTICAL.
- (a) Zero-init target checkpoint (CLXIII + zero tgt_in / tgt_out / tgt_back, sha 4c2e8900): (i) with the S6 rule forced
  (wiring alone) vs CLXIII: IDENTICAL on all 1,718 (dicts, taps, RNG, log-probs 0); (ii) as loaded (load_pilot picks
  "engine") vs CLXIII with "engine" forced: IDENTICAL on all 1,718 -> the zero layers are inert and the only change a
  target model brings beyond its weights is the reader rule. 16 logs: zero-target as loaded vs CLXIII-engine: 6,030 /
  6,030 dicts, 0 taps, log-probs 0 -> IDENTICAL.
- (a) Planted (non-zero target weights, normal 0, .05): vs CLXIII-engine 170 / 1,718 taps differ, max |dlogp| gate 3.95,
  cell 31 -> the target rows reach the model. Unit test: g moves on exactly the decisions with >= 1 known token
  (`test_target_obs.TestLiveWiring`).
- (a) If the engine rule were applied to CLXIII (NOT done; key absent): 4 logs: 198 / 1,718 decisions change p_play (max
  |dp| 0.060, 28 > 0.01), 2 / 1,718 taps differ (182408 t2812 Knight play -> wait at p .234 -> .189; t3166 Rocket
  follow-up changed). 16 logs: 418 / 6,030 p_play change (max |dp| 0.046, 44 > 0.01), 2 / 6,030 taps differ (both
  wait -> play: 200700 t3516 Skeletons p .449 -> .453; 195801 t1410 IceWizard .322 -> .368). So CLXIII DOES read the
  rule (cue floats has_target, target_is_tower, state, phase, frac); with the key absent it is not applied: 0 changes.
- Tests (icebow/.venv, CPU): `test_target_obs` 9 / 9 (2 new: load_pilot rule + log + refusal; zero = CLXIII decisions on
  60, planted g moves iff known tokens), `test_live_cues` 47 / 47 (2 new: engine rule on a synthetic frame -- both
  disagreement classes flip, engaged keeps; GenPilot.row target rows + refusal). Live-path subset (19 files: live_cues,
  live_decision_options, live_gen_afford, gate_sample_identity, cue_inputs, live_options, identity_ext, live_anti_leak,
  posture_live, public_decision_audit, memory_s1b, own_effects + L68 cue_inputs_live, cues_reader, live_entry, iw_press,
  pipeline_decisions, capture_p3, ckpt_alternate): 267 passed, 8 skipped, 12 failed. 11 of the 12 fail identically with
  HEAD's live path loaded (`live_tgt_replay.py pytest_head d6cd6d0`): pre-existing (5 live_options = the stripped
  LIVE_OPTIONS; ckpt_alternate = --iw-press head in LIVE_OPTIONS; posture_live = the single-pass forward bypasses its
  spy; own_effects / live_entry = stubs without .model / legal_guard; capture_p3 = a renamed helper binary). The 12th,
  L68 test_cue_inputs_live::test_decision_event_carries_the_cue_summary, failed only inside the 36-min suite run: it
  passes alone (this tree and HEAD) and after each of 9 earlier modules (b: order-dependent through one of
  gate_sample_identity / posture_live / anti_leak, not chased; this change only adds 'tgt' to an `if k in d` key list).
  test_decide_identity (BASE a76f57e vs this tree, live recorded + stress + SIM + cross-path): 5 / 5 passed.
- (a) Latency (CPU, 300 recorded decisions): GenPilot.row median 2.51 -> 3.17 ms, p90 3.52 -> 5.77 ms for a target
  model (live_target_rows 0.50 ms median); CLXIII unchanged.
- (a) `live_play.py --check` offline (merged reader env, --tau 0.35 --no-anti-leak, --device cpu): CLXIII from
  CKPT_OVERRIDE: LIVE_CHECK_PASS, cue_inputs without targets keys (unchanged); the zero-target checkpoint: PASS,
  cue_inputs.targets true, acq_rule engine; with the recipe options below: PASS.

### Deploy recipe for a target-aware + full-memory + sampled-gate successor (PILOT2) -- written, NOT applied
PILOT2 (`pilot2/pilot2.yaml`): T_gate 0.1, tau 0.35 single (tau_phase removed), decide_every 10, target_obs true,
memory v2 + e_max 256 + board snap, ability_head_from_init, no learner decide rule. Live reads targets and memory from
the checkpoint CONTENT (tgt_in -> target rows + acq_rule engine; mem.* + e_max / snap -> memory_rows): no flag for either.
1. Register the Mark (checkpoint naming convention; REGISTRY + hard link) -> `MARK=icebow/data/models/ICEBOW/<Mark>.pt`,
   `SHA16=$(sha256sum $MARK | cut -c1-16)`.
2. Back up, then add ONE line to `scratchpad/gauntlet/L70/live/LIVE_OPTIONS` right before the deploy (a supervisor
   restart in between would put CLXIII under the sampled gate, -6.9 pp at u0):
   `cp scratchpad/gauntlet/L70/live/LIVE_OPTIONS scratchpad/gauntlet/L70/live/LIVE_OPTIONS.pre_<Mark>`
   `printf -- '--gate-sample 0.1 --gate-sample-step-ticks 10\n' >> scratchpad/gauntlet/L70/live/LIVE_OPTIONS`
   Everything else stays: `--cue-inputs on` (required: the target model refuses without it), merged reader
   (`icebow/data/reader_notes/merged/live_env.sh`), `--iw-press head --iw-press-head-decode sample`, `--lethal-rocket
   log --lethal-log on --lethal-quiet 1.0` (owner's one rule; keeps decision options active, which --gate-sample needs:
   without it live refuses "gate_sample needs decision options active"). The learner trained WITHOUT the finisher.
3. --check (= start_live.sh's line, CKPT explicit):
   `(. icebow/data/reader_notes/merged/live_env.sh; icebow/.venv/Scripts/python.exe -B scratchpad/gauntlet/L68/live_reader/live_play.py --ckpt $MARK --tau 0.35 --no-anti-leak --check)`
   Expect: `"check": "LIVE_CHECK_PASS"`, checkpoint / sha256 = the Mark, feature_version 6, `cue_inputs` = {active: true,
   reader: merged_sf, table_sha256 babaa3d1..., **targets: true, acq_rule: engine**}, `live_options.from_file` has
   **gate_sample 0.1, gate_sample_step_ticks 10**, `decision_options.lethal_rocket "log"`, lethal_log on, every other
   rule off / argmax, tau 0.35, tau_phase null, iw_press head / sample, barrel_decoy true. (Measured with the zero-target
   stand-in + this recipe file: exactly that; the stand-in has no memory encoder.) First live match: the start event has
   gate_sample 0.1 / gate_sample_step_ticks 10 and cue_inputs.targets; 'decision' events carry 'tgt' {known, edges, tower,
   acq_rule engine} with edges > 0 on contested boards, and 'gate_draw' events.
4. Trial (owner's overnight bar): `MIN_WINS=6 RESTORE_OPTIONS=scratchpad/gauntlet/L70/live/LIVE_OPTIONS.pre_<Mark>
   BASE_CK=icebow/data/models/ICEBOW/ICEBOW_Mark_CLXIII_NOLEAK.pt BASE_SHA=8d328a43bf09fb7e BASE_LABEL=CLXIII
   bash scratchpad/gauntlet/L74/deploy/trial30.sh $MARK $SHA16 <Mark>`.
5. Revert line (manual):
   `cp scratchpad/gauntlet/L70/live/LIVE_OPTIONS.pre_<Mark> scratchpad/gauntlet/L70/live/LIVE_OPTIONS && bash scratchpad/gauntlet/L74/deploy/deploy_ckpt.sh icebow/data/models/ICEBOW/ICEBOW_Mark_CLXIII_NOLEAK.pt 8d328a43bf09fb7e "revert to CLXIII"`
   (options first: deploy_ckpt restarts live between matches and LIVE_OPTIONS is read at start).

## Concerns (graded)
- (a, resolved by M1c-R + LIVE-TGT) SIM / live "acquired" rules differed (centre + sight + 2-tile crown extra vs edge +
  max(sight, range) + 1.5): a target model now reads the engine formula (0.9985 on 85 exact matches).
- (a, resolved for target models) names without a table row kept their far path tower live (the bulk of the S6 rule's
  17,125 `acq_filter_rd_keeps` rows on the 85 matches; 10,043 of 14,365 in M1c-R); the engine rule drops them (sight 0). Still open (b): those names' real sight (class
  3, 2,322 rows): a definition / base-card sight fallback would close most of the rest.
- The feature is untrained: it changes play only after training (owner step iv) + the SIM gate.
