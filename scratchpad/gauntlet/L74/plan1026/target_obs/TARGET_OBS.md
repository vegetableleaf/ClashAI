# TARGET-OBS: which unit targets which unit, as a model input (owner priority item 1, 10-30)

Grades: (a) measured (number + source), (b) plausible, untested, (c) contradicted.
Rule: this file and every tracked file it names are READER-AGNOSTIC. Reader internals (field names, layouts) stay in the
git-ignored `icebow/data/reader_targets/`. Tracked code consumes only the per-unit interface below.

## STATUS + restart point (keep current)
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
- **Live is NOT wired** (no live change without the lead). Owed in `live_gen.GenPilot.row`, next to the cue block:
  `if getattr(self.model, "tgt_in", None) is not None:` -> require `self.cues`, then
  `rows, idx = live_target_rows(self.cues, raw_frame, prev, tok, mask, side)`; `b["tgt"] = T(rows, torch.float32)`;
  `b["tgt_idx"] = T(idx)`. Until then a tgt checkpoint must not go live (without b["tgt"] its layers are skipped: it
  plays target-blind, silently).
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

## Concerns (graded)
- (b) SIM / live "acquired" rules differ: the facade keeps a reference within target radius + sight + own radius (+ the
  crown-tower / building extra) by centre distance; live drops one whose EDGE distance > max(sight, range) + 1.5 tiles.
  Near the boundary the two can disagree. M1c measures exactly this (acq agreement on exact frames).
- (b) 18.7% of live attacker names have no 10-06 table row: LiveCues then takes the reach from the reader's own
  definition rows, and keeps a far reference when that is missing too (reach 0), so such a unit may show its path
  tower as a target live while the SIM shows none. Count it in M1c.
- The feature is untrained: it changes play only after training (owner step iv) + the SIM gate.
