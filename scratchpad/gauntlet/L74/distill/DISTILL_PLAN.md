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
