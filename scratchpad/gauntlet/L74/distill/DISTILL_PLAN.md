# Step 4: distill the deployed player (D3) into the plain model

Goal (owner): the MODEL learns what the decision rules and grafted refine heads do, so they can later come out of live
play. Rules stay out of RL. This experiment: play SIM games with the deployed stack (D3), record what the model saw and
what the stack finally did, fine-tune the PLAIN model on those pairs, then score the plain model decoded greedily with
no add-ons (D1) against the stack (D3). Nothing here has run on the SIM yet; numbers marked "estimate" are unmeasured.

## One change
Only the training TARGET changes: the label is D3's final action instead of a pro's. Fixed: the student's start
(plain r1), the inputs (D3 game states), the losses and recipe (`pipeline/train_gen.losses` unchanged: cell CE, card CE
over the 4 hand positions, gate BCE, 0.5 wait CE, 0.5 value CE, mirror p 0.5; AdamW wd .01, grad clip 1, OneCycle
pct .05, bs 256), lr 1e-4 and 2 epochs (fine-tune values, chosen once; untested), the scoring (gap.py, 960 pairs).

## Facts the design rests on (measured today)
- Teacher `newsim_r1/newsim_base_r1_final_grafted.pt` (fce50ebb) = student `newsim_base_main/newsim_base_main_u0060.pt`
  (e95d158d) + 37 refine-head tensors (cell_refine, tower_refine) + 5 `projectile_target_*` tensors replaced by r3c's.
  Same card vocab (124), feature_version 6, grid lattice, so teacher rows are valid student inputs.
  The student is NOT in the laptop tree: copy `C:/Users/benpe/pod_backup_weekend/podC/x_NEWSIM_base/wt_newsim/icebow/
  data/bench/rl_royale/newsim_base_main/newsim_base_main_u0060.pt` (e95d158d; the `_try1` copy 884b52bb is a different file).
- gap.py D3 = `livecal.py --worker` -> `search_s0.Runner.round`: forward (GenPolicy row) -> `live_decide_batch` with
  `decision_options` (livecal.LIVE: tau_phase .35/.45/.55, hazard_below_tau gate at >= 9 elixir or threatened 2 s,
  tau_threatened .2, X-Bow class_sample, rocket_area aim, log_barrel aim, lethal rocket/log, dead-lane/dead-target
  blocks) -> `SelfPlaySide.apply`. `--own-effects` changes the model INPUT (look-ahead), not the action. D1 = the same
  command without `--own-effects` and the rules. Grafted heads act inside `cell_logits` / card logits.
- r1 D3, 960 games (pod1014_refit `D3_full_*`): mean 378 learner decisions/game (not 285: 285 is a regulation 3-min
  game; mean end tick 4,750 = 3:57 because of overtime), 44.4 plays attempted, 43.0 accepted, 24.0 s wall/game at 14
  workers on the 13.6-core L40 pod, win 41.88% (402/960).
- The 20261012 runtime (royalesim 0.1.33) is not installed on Windows (`activate()`: "Pinned royalesim must be 0.1.33,
  got None"), so no SIM game ran on the laptop; the pod `smoke` step is the first real-path run.

## (a) Generation: `gen_distill.py`
- Driver = `gap.prepare` + `gap.run_arm('D3', ...)` unchanged, except `gap.command` is wrapped so each worker process
  runs `gen_distill.py --worker <gap's exact D3 args>` (test: the args equal gap's D3 command). The worker wraps
  `SelfPlaySide.apply` and `Runner.play` in its own process, then calls `livecal.worker()`. No repo file changes, so
  there is no default-off flag to keep byte-identical; the test proves the wrappers pass the very same `p` and decision
  objects to the original code, never record the opponent, and store copies taken at decision time.
- Per learner decision: the GenPolicy row the model saw (`_gen_row`: tok, mask, sc, past, identity arrays, hand_slot,
  slot_card/form, unit_form, opp_past, opp_cycle, projectiles, effects, own_ability) + tick + FINAL play/slot/cell/why
  + gate p; per game `accepted` (the play landed and the engine took it) and a meta json (seed, census, crowns, vocab).
  One file per game: `<chunk>/distill_<seed>.npz`. A decision with follow-up second plays (`rocket_tornado`) fails
  closed: it has no decision row (not in SIM D3; it is in the live stack).
- Seeds: block i = `seed_start 750000 + 1000 i`, 480 games (240 seeds x evo/lad censuses, CAL c, E4 at T .1, Hero IW +
  live press as in gap.py). The driver refuses any block overlapping the evaluation seeds 741200.. / 742000...

## (b) Training: `train_distill.py`
- Rows are written in the imitation dataset's own array layout and fed to the imitation trainer's own code
  (`train_gen.GenRows` batches, `train_gen.losses`, `eval_gen.evaluate`). Test: a GenRows batch equals the recorded rows
  key for key, and a model gives bit-identical outputs on both, so the student is trained on exactly the teacher's input.
- Row sampling = `dataset.build_replay`'s (wait stride 40 ticks, play window 20). This is the main design decision:
  the gate was trained on pro rows (1.01M play : 2.51M wait = 29% play) and the deploy threshold tau .35 was set for
  that meaning of p. Training on every 10-tick decision would make "play" 11.4% of rows (43.0/378), pull p down and leave
  tau .35 almost never firing. PLAY rows = accepted plays only (imitation uses accepted plays; refused/unlanded plays
  are dropped and counted). WAIT rows = per 40-tick bucket, its first decision if it waited, no accepted play decided
  within the next 20 ticks, and an accepted play still to come (imitation drops rows after the last play). Labels:
  card = the played hand position / identity; cell = `cell_xy(cell)` (test: `cell_label` inverts it for all 2,304 cells);
  wait = the next accepted play's card; value = the game's crowns. Split by game, crc32(census:seed) < 10% = val.
- Refuses a student with refine heads (the point: no grafted heads at decode) and teacher rows with another vocab or
  feature version. Logs val agreement with the teacher (card_top1, cell_half_top1, gate_bal_acc, ...) at step 0 and
  each epoch, plus label provenance (`why:` counts: gate / hazard / tau_threat / lethal_*), so fit is visible before
  the SIM scoring.

## (c) Measurement: `score_distill.py` (run by `run_distill.sh score`)
gap.py on seed sets 741200 and 742000 (960 pairs), `validate.paired_drift` on the concatenated rows (10,000 paired
bootstrap draws within census/side), as in FINDING.md / REFIT_RESULT.md.

| Run | Checkpoint | Arm |
|---|---|---|
| student_D1 | distilled student | D1 (greedy, no rules, no heads, no own_effects) |
| teacher_D3 | teacher (live) | D3 (rerun = environment check; expect 402/960, `REF_TEACHER` checks game for game) |
| plain_D1 | plain r1 | D1 (FINDING.md u060: 39.69%; `PLAIN_D1=0` skips) |
| student_D3 (optional, `STUDENT_D3=1`) | distilled student | D3 rules without heads |

- PRIMARY: student_D1 - teacher_D3. Pass under the owner's SIM bar (pre-filter): not clearly worse, CI top >= 0.
- student_D1 - plain_D1 = what distillation added. student_D3 - student_D1 near 0 = the rules add nothing left.
- Plays/game per run is printed: the student's D1 should land near the teacher's 43.0 (gate calibration check).
- Power, contradicting the obvious reading: for r1 the thing to transfer is small. D3 - D1 = +2.19 pp
  [-1.88, +6.15] (FINDING.md), inside the noise of 960 pairs (+-3.9 pp). A pass on r1 shows non-inferiority, not that
  the model learned the add-ons. ADAPT's add-ons are worth +8.75 [+4.79, +12.60]: a measurable test of the method.

## Teacher choice
- Default (task): r1 live graft fce50ebb -> student e95d158d. Low power (above).
- Alternative, stronger in SIM: ADAPT. Student = `wk_adapt_main_latest.pt` (55c8f49e; r1's RL init per
  `newsim_base_main.yaml` `init:`; copy in `pod_backup_weekend/pod3/x_ADAPT/wk_adapt/icebow/data/bench/rl_royale/
  wk_adapt_main/`). Teacher = its graft used for FINDING.md's 47.08% D3 row. The copied match rows do not record the
  checkpoint sha; candidate `adaptive_final_grafted.pt` (ab5a5383, same folder), verify against that run's chunk
  `run.json` `gen_sha256` before use. Run with `TEACHER=... STUDENT=... OUT=... R=/workspace/results/DISTILL_adapt`.
  A distilled ADAPT is not a live candidate by itself (r1 is live); it tests whether distillation transfers add-ons.

## Volume and runtime (pod, 13 workers)
- Per game: 378 decisions recorded (raw ~8.3 KB each = ~3.1 MB/game before compression; compressed size unmeasured).
  Training rows ~125/game (estimate: 43 play + ~80 wait).
- Default 5 blocks = 2,400 games -> ~103k play + ~200k wait rows (estimate; pro set: 1.01M + 2.51M). Disk <= 7.5 GB
  raw upper bound. Trainer RAM ~1.5 GB (estimate).
- smoke ~2 min; gen 2,400 x 24.0 s / 13 ~= 74 min + recording overhead (unmeasured); train ~1,050 steps/epoch x 2
  (minutes on the L40; train_gen measured 150 ms/step bf16 on the laptop RTX 5050) + loading 2,400 files; score 3 x 960
  games ~= 90 min. Total ~3 h for r1; the ADAPT variant is another ~3 h.

## Pod steps (repo root, LF line endings)
1. Bundle must include: the distill/, gap/, livecal/, heroiw/ dirs, the teacher, the student at
   `icebow/data/bench/rl_royale/newsim_base_main/newsim_base_main_u0060.pt`, and everything gap.py already needs
   (E4, gen_s0, livecal manifest + CAL census sources: gap.prepare hashes them).
2. `sed -i 's/\r$//' scratchpad/gauntlet/L74/distill/run_distill.sh` if the bundle came from a Windows tree.
3. `bash scratchpad/gauntlet/L74/distill/run_distill.sh smoke` (2 real D3 games recorded + a 5-step train).
4. `nohup bash scratchpad/gauntlet/L74/distill/run_distill.sh all > /dev/null 2>&1 &` -> `$R/SUMMARY.txt`, `$R/DONE_*`.
   Optional `REF_TEACHER='/path/D3_full_{seed}'` (pod1014_refit copy) for the game-for-game environment check.

## Risks and open questions
1. Stochastic rules cannot be copied by a greedy decode. The hazard gate (play with a per-step probability at >= 9
   elixir or under threat) and X-Bow class_sample draw at random; the student learns their average and D1's argmax
   picks the most likely choice. If D1 falls short there, the remedy is a decode change (sample those heads), which is
   an owner decision, not another rule.
2. own_effects mismatch: the teacher's inputs include my recent spells applied in the look-ahead; D1 has no
   `--own-effects`, so the student trains on one input view and plays on another (small: only plays within 7.5 s of an
   own Log/Tornado/Rocket/IW press). Untested; a D1 + `--own-effects` arm would measure it (needs a gap.py arm).
3. SIM D3 is a subset of the live stack: live also has log_air block, rocket_value 9 (damage, edge), rocket_tornado
   only + follow-up taps, afford_ticks 23, extrapolate 24, card_levels. Those cannot be distilled from SIM D3; the
   follow-up plays would also need decision rows.
4. Confound in "only the target changes": fine-tuning on SIM states also trains the value head on SIM outcomes
   (train_gen.losses' 0.5 value CE). student_D1 - plain_D1 includes that. Untested control: self-distillation (same
   states, labels = the plain model's own D1 choices) needs a second forward in the generator; add only if the result
   is positive and needs attributing.
5. Covariate shift: the student is trained on states the TEACHER reaches; at D1 it reaches its own. If D1 trails D3,
   the standard next step is DAgger-style rounds (student plays, teacher labels its states), which needs the teacher's
   D3 decision computed on the student's states: a larger hook, not built.
6. Gate meaning after RL: r1's gate was shaped by PPO on every decision, not by pro row odds. The row sampling restores
   imitation semantics; whether that moves r1's play rate is untested. The plays/game line in SUMMARY.txt shows it.
7. lr 1e-4 / 2 epochs / 2,400 games are untested choices; the val agreement curve in the train log is the check.

## Files (all new, `scratchpad/gauntlet/L74/distill/`; no existing file changed)
`gen_distill.py` (generator), `train_distill.py` (row builder + fine-tune), `score_distill.py` (960-pair report),
`run_distill.sh` (pod runner: smoke | gen | train | score | all), `test_distill.py` (9 tests, CPU, ~20 s):
`icebow/.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider scratchpad/gauntlet/L74/distill/test_distill.py`

## Iteration 2: DAgger rounds (code + tests 2026-10-14; nothing run on the SIM yet)

### Why (iteration 1, ADAPT, 960 pairs; `results/ITER1_SUMMARY.txt`)
Teacher D3 47.08%, plain ADAPT D1 38.33%, distilled student D1 30.00% = -8.33 pp [-12.19, -4.48] vs plain (tower HP
diff/game ~-1700 vs ~-1030). Held-out agreement with the teacher rose (gate .86 -> .94, card .83 -> .91, cell .52 -> .62);
pro VAL (v3val, 12,237 rows) top-1 kept (cell .199 -> .205, card .655 -> .646, gate bal .749 -> .769), cell NLL 3.10 ->
4.71. Forgetting: contradicted. Leading hypothesis, untested: covariate shift (risk 5 above) -- the student only saw
states the TEACHER reaches. DAgger labels the student's OWN states with the teacher's decision.

### What changed (all in `scratchpad/gauntlet/L74/distill/`; no repo file changed)
- `gen_distill.py --teacher T --p-teacher p`: the learner = the acting student under gap's D1 command, unchanged; the
  worker's `apply` wrapper computes the teacher's D3 decision on the same prepared state and the same input row
  (`Teacher.decide` = `search_s0.Runner.round` for one side: teacher forward -> `pre` -> `live_decide_batch` with
  `match_kwargs` under the D3 cfg; the D3 flags are exactly what gap's D3 command adds to D1's). Recorded: the
  student's row, the teacher's decision as the label (`play/slot/cell/why/p`), the student's own (`s_*`) and
  `teacher_exec`. With probability p the teacher's action is executed, else the student's (own per-match stream; p 0
  never draws). The rule state (threat / dead tower / lethal history, `rng_decision_options`) lives on the side, so it
  evolves along the student's trajectory as D3's would along its own. Refuses a teacher with another vocab / feature
  version (= another input row).
- BUG FIX: `distill_command` broke with gap.py b62f394 (`run_arm` now passes `extra` as a 6th positional argument,
  which landed in `_orig` -> `TypeError`); iteration 1 ran on the older gap.py. Any rerun of `gen` on current main would
  have failed at the first worker. Fixed + test.
- `train_distill.py`: `--data` takes several dirs (union, the iteration-1 row sampling for each game); val per dir
  (`src<k>`); DAgger games add on-policy agreement counts to the stats (`gate_agree`, `card_agree`, `cell_agree` over
  all decisions, `teacher_play`, `student_play`, `teacher_exec`); `--cell-kl W` (W x KL(plain init || student) on the
  cell head over the batch's play rows, same mirrored inputs and card, the plain model frozen); `--rehearse NPZ
  --rehearse-frac F` (F of every batch = pro TRAIN rows of `gen_dataset_v32_fv5.npz`). All off = iteration 1's trainer,
  bit for bit (test against commit c66f6af).
- `score_distill.py`: runs `dagger_D1`, `daggerkl_D1`, `iter1_D1` + their pairs; `--pro NAME=eval_gen.json` prints the
  v3val cell NLL against the bar (reference + 0.3, owner).
- `run_distill.sh dagger_smoke | dagger` (header comment has the env). Round k (P_SCHEDULE "0.5 0"): the latest
  student plays D1 on DBLOCKS 3 x 480 fresh games (seeds 750000 + 10000 k: 760000.., 770000..; never the eval seeds or
  iteration 1's 750000..754999), the teacher labels every decision; then train FROM THE PLAIN INIT on iteration 1's
  2,400 teacher games + every round so far (standard DAgger aggregation; also keeps the KL anchor = the init). After the
  last round: the same final union + `--cell-kl 1` -> `dagger_r2_kl.pt`; eval_gen pro VAL for plain, dagger_r2,
  dagger_r2_kl; both students D1 on the 960 pairs; iteration 1's plain_D1 / teacher_D3 / student_D1 are linked, not
  rerun. Per-round D1 win lines of the generation games go to run.log (p 0 round = the previous student's own D1 on
  1,440 unpaired games, free). Finished parts are skipped on a rerun.

### Design choices and where they deviate from the request
1. "Exactly D3" vs "same input row" cannot both hold: D3's `--own-effects` is a look-ahead that changes the model INPUT.
   The label is D3's rules + grafted heads on the student's row; the look-ahead is not applied
   (`meta.own_effects_not_applied`). It only matters within 7.5 s of an own Log / Tornado / Rocket / IW press; the
   share of DAgger rows with an own spell in `past` within 7.5 s (computable from the recorded rows) bounds it. The
   student never sees the look-ahead at D1 anyway.
2. In DAgger games every teacher play label is a PLAY row (`accepted` = label): the teacher's play was mostly not
   executed, so there is no landing to check. Iteration 1 dropped 3,922 refused/unlanded of 111,161 plays (3.5%).
3. Gate base rate (plausible, untested): while the student waits and the teacher wants to play, the teacher says play at
   every 10-tick decision until the state changes, and each becomes a PLAY row (waits stay 1 per 40 ticks). That
   shifts the gate's play/wait mix toward play vs iteration 1 (PLAY rows = 107,239 of 936,813 decisions). The check:
   `teacher_play / dagger_decisions` and `play_rows` in the train logs, plays/game in SUMMARY (iteration 1 student 41.6,
   plain 42.3, teacher 44.5). If the student over-plays, the fix is to sample play labels like waits in DAgger games.
4. One change per experiment: the DAgger loop trains WITHOUT the KL term (DAgger rows = the one change vs iteration 1);
   the KL student is trained on the same final rows (+KL = the one change vs dagger_D1). Rehearsal is a flag only, off.
5. KL weight 1 = the largest weight whose per-state optimum, q = (e_teacher + W p_plain) / (1 + W), still keeps the
   teacher's cell as the argmax. It does NOT guarantee the +0.3 NLL bar: the bound on a training state is plain NLL +
   ln((1 + W) / W) = +0.69 at W 1; a guarantee needs W >= 2.86, where plain's argmax can win back the cells the rules
   chose (Rocket / Log aims) -- an owner trade-off if W 1 fails the bar. Note also: cell NLL is calibration; D1 decodes
   the argmax, so a pure calibration fix (a temperature) would not change D1 play at all. The bar protects the pro
   knowledge; it is not by itself a win-rate lever.

### Expected cost (13-worker pod; estimates from iteration 1's timings unless stated)
- dagger_smoke ~3 min. Per round: 1,440 games; iteration 1's D3 ran 2,400 games in 88.7 min -> ~53 min, plus the
  teacher forward on every learner decision (a third forward per decision; overhead unmeasured, estimate +15-35%):
  ~60-72 min. Two rounds ~2.0-2.4 h.
- Train: iteration 1 = 1.9 min for 2,400 files / 303k rows. Round 1 ~485k rows ~3 min, round 2 ~665k rows ~4 min, KL
  ~6 min (second forward) -- estimates. Pro VAL: 3 x eval_gen (~12 GB RAM each, the whole npz) ~10-15 min, unmeasured.
- Score: iteration 1 = 29 min per 960-game arm -> 2 arms ~1 h. Total ~3.3-3.8 h. Disk ~+170 MB of game files.

### Pod commands (repo root, current main + this dir, LF endings)
    sed -i 's/\r$//' scratchpad/gauntlet/L74/distill/run_distill.sh
    export R=/workspace/results/DISTILL_DAGGER R1=/workspace/results/DISTILL_ADAPT \
      TEACHER=icebow/data/bench/rl_royale/wk_adapt_main/wk_adapt_main_latest_grafted.pt \
      STUDENT=icebow/data/bench/rl_royale/wk_adapt_main/wk_adapt_main_latest.pt \
      OUT=icebow/data/bench/rl_royale/distill/distill_adapt_d3.pt
    sha256sum $TEACHER $STUDENT $OUT          # 4893e67a.. 55c8f49e.. a152cc46.. (iteration 1's ckpts.sha)
    bash scratchpad/gauntlet/L74/distill/run_distill.sh dagger_smoke; tail -2 $R/run.log
    nohup bash scratchpad/gauntlet/L74/distill/run_distill.sh dagger > /dev/null 2>&1 &   # -> $R/SUMMARY.txt, $R/DONE_dagger
If $R1 is gone: upload `pod_backup_weekend/pod1014b_distill/DISTILL_ADAPT/{gen,eval}` to it (150 MB) and
`pod_backup_weekend/pod1014b_distill/icebow/.../distill/distill_adapt_d3.pt` to $OUT; the plain ADAPT ($STUDENT) is in
`pod_backup_weekend/pod3/x_ADAPT/wk_adapt/icebow/data/bench/rl_royale/wk_adapt_main/`. Needs
`icebow/data/pipeline/gen_dataset_v32_fv5.npz` (PRO). gen and score wait on /workspace/cpu.lock like iteration 1.

### Reading the result
- PRIMARY `dagger_D1 - plain_D1` (iteration 1: -8.33). `dagger_D1 - iter1_D1` = what the student-state rows added.
- Covariate shift directly: `gate_agree / dagger_decisions` (student's choice vs the teacher's label on the states the
  rollout reached) against the .94 measured on the teacher's own states. Round 1 (p .5) mixes in the teacher's actions,
  so it understates the shift for the iteration-1 student; round 2 (p 0) is clean on-policy agreement, but for
  dagger_r1. The clean test for the iteration-1 student is a p 0 round with it (`P_SCHEDULE="0 0.5 0"`, +~1 h). Much
  lower than .94 = shift confirmed; about .94 = shift is not the cause and DAgger should not help (then look at the
  value head / SIM-outcome confound, risk 4).
- `daggerkl_D1 - dagger_D1` and the pro VAL lines: the calibration guard's cost or gain at equal rows.

### Tests (17, CPU, ~27 s; same command as above)
New: the 6-argument `run_arm` call; the DAgger command = gap's D1 + exactly D3's extra flags, and the worker strips them
before livecal; the teacher label equals gap's D3 path (search_s0.Runner.round with the teacher, real BoardStates,
the full LIVE flags, 24 decisions incl. a hazard draw) for p 0 / 1 / 0.5, the executed action is the student's (p 0),
the teacher's (p 1) or per the mix, the rule RNG state ends identical, the recorded row is the student's (a no-rules
mutant matches 9 / 24 labels, the real hook 24 / 24); another vocab is refused; the DAgger game file; defaults
bit-identical to c66f6af's trainer; union + per-dir val + agreement stats + KL + rehearsal; the KL formula; the pro bar.
