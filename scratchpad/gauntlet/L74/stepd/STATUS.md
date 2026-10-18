# Step-d status

## 2026-10-18 15:50 EDT -- milestone 7: D2 EVALUATED; REB init on its pods; LEAGUE arm training; smoke-check fix

- D2b IL-cue-w s0 (30988, 18:56-19:27 UTC; sha 279b4f30...; pod_backup_weekend/stepd/d2/ + d2_relay/, sha-verified).
  il_compare (stepd/il_compare.py; 349,264 val rows, 127,334 cue-attached, v3val 12,237; paired 95% CI over val matches):
  - CUE EFFECT, cue-attached rows (cuew - nocuew0): gate NLL -0.0024 [-0.0028, -0.0019] vs seed noise (nocuew1 - nocuew0)
    -0.0010 [-0.0019, +0.0001] -> a real but tiny gain (0.3622 -> 0.3599). cell NLL -0.0091 [-0.0120, -0.0061] is NOT
    beyond the seed noise (-0.0089 [-0.0146, -0.0037]). card +0.0021 [-0.0006, +0.0049], wait -0.0020 [-0.0041, +0.0000]: n.s.
    Pre-registered verdict: "cues help in imitation" holds on gate NLL only, and the size is small (a).
  - HEALTH: cuew vs nocuew0 inside the seed noise on all val + v3val (largest: v3val cell-tile -0.0052 [-0.0109, +0.0006]).
  - vs gen_v32_s0 (old base): all-val card -0.0008, cell-tile +0.0006, gate bal -0.0011 [-0.0021, -0.0002]: ~equal.
  - Owed (plan section c, not run): the live dry check (dry_live.py, cue-zeroing decision changes) and the informational
    SIM eval of IL-cue vs CLIII.
- REB init relayed (relay_ckpt.sh, .part + sha + mv) to 19834 + 14009 at cb_stepd/icebow/data/pipeline/stepd_il/gen_cuew_s0.pt.
- REAL REB smoke (30988: stepd_reb.yaml, init IL-cue-w, ability head, critic_warmup_updates=1): SMOKE PASS. Its update-0
  pro agreement (1,000 rows): card .699 / cell .195 / gate .761 (CLIII .675 / .182 / .714).
- Smoke-check fix (pipeline/rl_royale.py): the u0000 save/reload check compared floats exactly; with CLIII (fv6) + ability head
  it failed twice on cell_nll alone (3.1361532936 vs 3.1361533864, every other metric equal = GPU reduction noise). Now floats
  to 1e-6 relative. pyflakes clean; real smoke on 34210 A + B PASS.
- stepd_ctrl_nos2 (34210) TRAINING since 19:32 UTC: ~2.5 min / update (125 s roll + 22 s upd) -> u130 ~01:00 UTC + evals.
- Waiting: Stage 2 CHAIN_DONE (~21:10 UTC) -> CTRL starts on 13396 by itself; then relay s2_all_il_sA_u0130.pt to 19834 +
  14009 -> REB + twin start (arm waiters).

## 2026-10-18 15:05 EDT -- milestone 6: D1 DONE, D2b training, CLIII fin13 baseline, ability head ON, nos2 arm started

- D1 (30988, fin13, 26 workers, 18:20-18:55 UTC; pod_backup_weekend/stepd/d1/): drive 1,829 s = 12,930 replays driven from
  crawl commands; 734 no crawl source; 1,007 failed `unsupported_forms BarbarianLauncher` (hero Barbarian Barrel: fin13
  cannot load it either). Sidecar (min fid 0.9 + token gate): rows attached 36.99% (1,301,155 / 3,517,863), play rows
  31.4%, wait rows 39.2%, tokens known 27.7%; status no_cue_file 442,404 / no_frame_at_tick 405,483 / below_min_fid
  1,368,821. v32_cue.npz sha 4cb48afe..., v32_w3.npy 83c66ad0... (= D2a's weights). The first D1 launch failed in 8 s:
  ship_stepd.sh did not overlay the working-tree pro2/build_rows.py (on_frame hook); fixed (L74/pro2 in the overlay).
- D2b (IL-cue-w s0) RUNNING on 30988 GPU since 18:56 UTC (d2b_cue_pod.sh pid 11487 / trainer 11492), ~1 h, then il_compare.
  Incident: two triggers (an inline one I believed dead + its script replacement) both started D2b at 18:55; both were
  killed at 13 s (same log file) and ONE run relaunched clean.
- CLIII fin13 re-score (10757): std 633/960 (741200 308 + 742000 325), fresh 619/960 (743000 306 + 744000 313). Codex's
  same-code fork36: 642 / 626. fork36 std rows from cb_stepd still running there.
- Ability head decision: c3_ab vs c3_ctl (pair_cmp.py; rows pod_backup_weekend/stepd/c3_ab_eval/ + codex1018/10757):
  std +1.46 [-1.98, +4.90] (667 vs 653), fresh -1.25 [-4.69, +2.19] (630 vs 642), pooled +0.10 [-2.29, +2.55] ->
  not clearly worse -> ON in all four arms (ability_head: true, ability_features: freeze; evals --ability-head-decode=sample).
- GO files written on 13396 / 19834 / 14009 (NO36=1) / 34210. Waiter bug found + fixed: `awk '$1 == "init:"'` also matched
  league_mix's indented `init: 0.25`, so INIT was two lines and no arm could ever pass its input check; all four waiters were
  killed by exact PID and relaunched with `awk '/^init: /'` (13396 pid 11015, 19834 pid 11344, 14009 pid 24335,
  34210 pid 14464). stepd_ctrl_nos2 (34210) passed its inputs at 18:54 UTC -> smoke -> chain.

## 2026-10-18 14:15 EDT -- Codex handoff complete; D1 smoke failed after acquiring CPUs

- All Codex cue/combo follow-ups are DONE (13,440 SIM games). Final cue archive: 2,008 files, SHA-verified at
  pod_backup_weekend/codex1018/30988/20261018T181127Z. ALL_DONE was written at 18:10:32 UTC.
- Final paired readout (14:21 EDT): sampled cue +5.21 pp [1.67, 8.85] standard / +1.25 [-2.19, 4.69] fresh;
  greedy cue +4.69 [1.15, 8.23] standard / +2.08 [-1.36, 5.52] fresh. Both fail the fresh gate. C3 control and both
  combo settings also fail the two-set CLIII bar. All seven completed candidate/settings comparisons and behavior CIs
  are in codex1018/CANDIDATE_RESULTS.md; c3_ab still awaits its complete standard/fresh evaluations.
- D1 acquired CPUs at 18:11:03 UTC and exited 1 at 18:11:11 UTC. drive_smoke.out records
  `TypeError: drive() got an unexpected keyword argument 'on_frame'`. The alive executor owns the compatibility repair
  and smoke retry. Codex has not restarted or edited D1. This supersedes the older table's waiting status for 30988.

## 2026-10-18 14:10 EDT -- milestone 5: Codex-released pods 10757 + 34210 taken; every arm has a waiter

| pod | job | state |
|---|---|---|
| 30988 | D1 (cue drive, fin13, 26 workers) -> D2b (IL-cue-w s0 = REB init) -> il_compare | D1 waiter pid 7392 waits for Codex ALL_DONE (~14:12) |
| 10757 | CLIII fin13 re-score (stepd_chain REF, NAME=clIII_fin13: fin13 std+fresh + fork36 std) | ref_now.sh pid 8049 (smoke try 2; try 1 failed only on a missing gen_v32_s0 stand-in, now copied) |
| 13396 | stepd_ctrl | arm_waiter pid 10423: Stage 2 CHAIN_DONE (~17:10) + GO_stepd_ctrl |
| 19834 | stepd_reb | arm_waiter pid 10686: CHAIN_DONE + GO + IL ckpt + S2 sA u0130 (relay) |
| 14009 | stepd_rebc3 (CLIII card-anchor twin) | arm_waiter pid 22714: c3_ab done + GO (put NO36=1 in it) + IL + S2 |
| 34210 | stepd_ctrl_nos2 (CTRL minus Stage-2 opponents = LEAGUE attribution, lowest priority) | arm_waiter pid 13920: GO only (pod free now) |

- GO files = /workspace/stepd/GO_<RUN> (sourced by stepd_chain.sh; may set DECODE=--ability-head-decode=sample and NO36=1).
  Write them only after the ability-head decision (c3_ab vs c3_ctl) and after copying the final yaml into cb_stepd.
- Inputs still to relay (stepd/relay_ckpt.sh, sha-verified, .part then mv): the REB init
  icebow/data/pipeline/stepd_il/gen_cuew_s0.pt (30988 -> 19834, 14009) and s2_all_il_sA_u0130.pt (13396 -> 19834, 14009).
- 14009's REF waiter was cancelled (pid 22609 killed) since the re-score moved to 10757.
- Combo reward: Codex's paired check confirms reward minus control +1.35 [-2.08, +4.69] -> OFF in every arm.

## 2026-10-18 13:50 EDT -- milestone 4: D2a DONE; 14009 staged with the CLIII fin13 re-score waiter

- D2a result (30988, 17:39 UTC; pod_backup_weekend/stepd/d2/, 14 files sha-verified). best_val (30k val sample) / v3val:
  - IL-nocue-w s0 (88a466ae): card .614, cell-tile .221, gate bal .744 / v3val .660, .208, .777
  - IL-nocue-w s1 (1b814adc): card .615, cell-tile .232, gate bal .744 / v3val .672, .209, .779
  - gen_v32_s0 (old base, unweighted, laptop): .613 / .224 / .747; v3val .657 / .204 / .776
  -> the x3 weighting costs nothing measurable overall; seed noise ~1 pp cell-tile (val sample), ~1.2 pp card (v3val).
    The weights reach 2.3% of rows, so a large overall effect was never expected. (b) whether it changes play vs the six
    archetypes is untested here -- the RL evals' per-archetype slices are where it would show.
- 14009 staged (files only; c3_ab still training): /workspace/cb_tt = hard-link copy of /workspace/c3/cb, /workspace/cb_stepd,
  /workspace/venvf13 from /workspace/ab/venvf36 (that pod has no /workspace/venvf36; the ab venv's fork36 binary 80b6b94b is
  unchanged; fin13 binary 2ec5ec39 = 13396's). setup_fin13.sh now takes SRCV=<real venv dir> and SKIP36=1.
- 14009 REF waiter (stepd/ref_waiter.sh, pid 22609 under flock claim.lock): when /workspace/c3/results_c3_ab/{ALL_DONE|DONE}
  exists and no rl_royale / gap.py is left -> stepd_smoke.sh -> CLIII fin13 re-score (stepd_chain.sh REF, NAME=clIII_fin13,
  NO36=1: std + fresh on fin13 only; CLIII's fork36 std rows from the same code still owed, e.g. on 30988).
- D1 waiter relaunched with WORKERS=26 (pid 7392) since D2a is done; Codex's ALL_DONE expected ~14:05 EDT.
- Laptop readout ready: stepd/readout.py (selftest PASS) over pod_backup_weekend/stepd/<job>/ (pull_stepd.sh layout).

## 2026-10-18 13:30 EDT -- milestone 3: trainer COMMITTED (3f72766), RL pods staged + claimed, arm waiters armed

- Committed + pushed 3f72766 (owner decision 1) after the real fin13 pod smokes: smoke (warm-up only) and smoke2
  (critic_warmup_updates=1, update 1 = a real PPO step: clip 0.019 / 0.022, leash driver card) both PASS for stepd_ctrl and
  stepd_rebc3. Logs: pod_backup_weekend/stepd/smoke/ (10 files sha-verified).
- RL pods staged (no compute, Stage 2 untouched): 13396 + 19834 have /workspace/cb_stepd (code 3f72766-era tar + CLIII raw
  05d42da7 / grafted edc82ada) and /workspace/venvf13 (FIN13_OK, same wheel 969a2ac8; venvf36 intact).
- Arm waiters (stepd/arm_waiter.sh, run under `flock /workspace/stepd/claim.lock` so stop_pod.sh refuses to stop the pod):
  13396 RUN=stepd_ctrl (pid 10423), 19834 RUN=stepd_reb (pid 10686). Each waits for Stage 2 CHAIN_DONE + no rl_royale/gap,
  then for /workspace/stepd/GO_<RUN> (the lead writes it once the yaml is final), then for the init + the S2 exploiter
  (icebow/data/bench/rl_royale/s2_all_il_sA/s2_all_il_sA_u0130.pt inside cb_stepd; 13396 links it from cb_tt; 19834 needs it
  copied over), then runs stepd_smoke.sh on that pod and stepd_chain.sh. Logs /workspace/stepd/arm_waiter.log.
  DO NOT re-ship code (ship_stepd.sh) to a pod whose arm is running: it rm -rf's the code dirs the actors import from.
- Arm-config decisions so far (from Codex's CANDIDATE_RESULTS.md, same-code evals vs CLIII, 960 paired, std seeds):
  - spell-value reward: OFF. combo_rew_c3 -0.52 [-4.06, +2.92], combo_ctl_c3 -1.88 [-5.52, +1.67] vs CLIII; the reward
    arm is ~+1.4 pp over its control (not paired-tested here; certainly not a clear win); it cut Tornados 0.25 / game.
  - ability head: PENDING c3_ab (14009, training ~u45/65 at 17:00 UTC; evals after). Bar (PLAN): on if c3_ab is "not
    clearly worse" than c3_ctl. Context: c3_ctl vs CLIII +1.41 [-1.04, +3.80] pooled; cue_ab2 sampled (CXXXVIII + head)
    +5.21 [+1.67, +8.85] std (fresh pending) with 0.93 vs 1.72 presses / game.
- Plan for the other pods: 14009 after c3_ab -> CLIII fin13 re-score (stepd_chain REF mode; its /workspace/fork36 parity
  checkout breaks fork36 evals there unless hidden -> fork36 rows from another pod), then the REB CLIII-anchor twin
  (stepd_rebc3) once IL-cue-w exists; 30988 after D2 -> stepd_ctrl_nos2 (CTRL minus the S2 opponents = the LEAGUE
  attribution, lowest priority).

## 2026-10-18 12:55 EDT -- milestone 2: fin13 runtime built (R1 done), D2a training, real smoke running

- R1 DONE on 30988: wheel royalesim-0.1.36 from clashbot36 a697d1f9 (sha 969a2ac8...), /workspace/venvf13; manifest
  stepd/build_manifest_fin13.json (f2c99dd9..., 30 files); activate() under fin13-linux: pin a697d1f9, card table embedded;
  venvf36 still bc2bf9d. Backup + sha verified: pod_backup_weekend/stepd/fin13/. TRAP met and fixed: the wheel reads its
  build checkout's data/derived when /workspace/fork13 exists (card_table_source != embedded) -> setup_fin13.sh deletes the
  checkout after copying the wheel to /workspace/in/fin13/. Other pods: copy that wheel there + `bash setup_fin13.sh`.
- D2a RUNNING on 30988 GPU since 16:40 UTC (d2a_nocue_pod.sh, PIDs 3702 s0 / 3704 s1): ~3,950 rows/s each, 12,377 steps
  per epoch (~13-15 min/epoch with Codex holding the CPUs) -> both done ~17:45-18:00 UTC. Row weights: 81,114 of 3,517,863
  rows x3 (645 of 2,945 X-Bow sides face hyperbait 199 / pekka_bridge 102 / golem 105 / lava 130 / RG 91 / RG+monk 18).
- D1 waiter (d1_waiter.sh, PID 4584): starts d1_data_pod.sh on fin13-linux, 22 workers, under /workspace/cpu.lock once
  Codex's ALL_DONE exists and no gap/livecal worker remains.
- Smoke (stepd_smoke.sh -> /workspace/stepd/smoke/): A = stepd_ctrl.yaml (CLIII, kl_heads [card]), B = stepd_rebc3.yaml with
  init gen_v32_s0 (IL stand-in) + kl_ref_card CLIII; league_exploiters ckpt = CLIII raw as a stand-in (S2 u0130 not yet).
- Arm configs written: stepd/cfg/stepd_ctrl.yaml (= c3_ctl + 130 updates + kl_heads [card] + beta0 0.03 + kl_target 0.3 +
  guards loosened to tripwire 5 / hard 8 pp + league_exploiters {s2_all_il_sA_u0130, decks_live_train, 0.3});
  stepd_reb.yaml = the same with init icebow/data/pipeline/stepd_il/gen_cuew_s0.pt (ONE change: the init);
  stepd_rebc3.yaml = REB + kl_ref_card CLIII (the owner's optional twin). Ability head / spell reward stay OFF unless
  c3_ab / combo_rew_c3 pass (results pending; decided before CTRL starts).
- Chain: stepd/stepd_chain.sh (train fin13 -> graft -> u130 evals fin13 std+fresh, fork36 std; u65 fin13 std). REF=CLIII
  mode = CLIII's fin13 re-score (owner decision 2).

## 2026-10-18 12:45 EDT -- executor (API worker relaunched 12:14) milestone 1: staging on 30988, K1 + R1 code written

- WHO: the step-d executor (headless API worker, log stepd/executor.log). Nothing ran before 12:14 (the 10:53 worker died on
  the API 400).
- 30988: Codex's CLIII / cue_ab2 SIM re-eval holds the CPUs (/workspace/cpu.lock, 12 seed sets at ~7 min each -> ~13:40 EDT).
  I do NOT start D1 until its run_eval.sh writes /workspace/codex1018/results/ALL_DONE. The GPU is free: the two no-cue
  imitation runs go there first (2 CPU threads each, nice 5).
- Staged on 30988 (no compute): /workspace/cb_tt + /workspace/venvf36 (combo/newpod.sh from 10757; setup_troops.sh's last
  check failed only because repo_tt lacks troops/build_manifest_fork36.json, which cb_stepd has); /workspace/cb_stepd =
  hard-link copy of cb_tt + the step-d code (stepd/ship_stepd.sh: HEAD + working-tree pipeline + stepd) + data
  (gen_dataset_v32_fv5 29ecefa9, gen_v32_s0 61011b6c, public_context_v32_w4, the 5 crawl dirs, CLIII raw 05d42da7 + grafted
  edc82ada). Fin13 bundle /workspace/in/clashbot36_a697d1f9.bundle (0b28aa3b; laptop pod_backup_weekend/stepd/fin13/).
- D2 redesigned for owner decision 5 (weights in imitation): ALL imitation runs carry --row-weights x3 and are compared on
  the same pod / torch: IL-nocue-w s0 (cue twin), IL-nocue-w s1 (seed noise) = stepd/d2a_nocue_pod.sh (no D1 needed);
  IL-cue-w s0 (= REB's init) + il_compare = stepd/d2b_cue_pod.sh. gen_v32_s0 stays the old-line reference (weights +
  platform differ, so it is not the cue twin any more).
- K1 (pipeline/rl_royale.py, uncommitted): `kl_heads: [card]` (needs leash: max; only those heads' KL in the loss, the leash
  steers on their max) and `kl_ref_card: <ckpt>` (card KL anchored to another frozen net; update-0 check skips KL_card).
  Absent = the historical config hash. test_league TestLeash 5 pass; pyflakes clean. Real pod smoke still owed.
- R1 (uncommitted): `fin13-linux` in pipeline/royale_runtime.py + royale_heroiw.ENABLED; stepd/freeze_fin13.py (pin
  a697d1f9); stepd/setup_fin13.sh (build the wheel on the pod, /workspace/venvf13 = hard-link copy of venvf36 with only
  royalesim replaced, freeze the manifest).

## 2026-10-18 12:19 EDT -- coordination notice: pod 30988 currently has an authorized SIM evaluation

- Codex handoff/failure finding at 14:12 EDT: all 12 isolated cue/CLIII seed blocks are DONE; ALL_DONE was written
  18:10:32 UTC. D1 waiter acquired the freed CPUs at 18:11:03 UTC, then D1 exited 1 at 18:11:11 UTC. Read-only inspection
  of /workspace/stepd/d1/drive_smoke.out found `TypeError: drive() got an unexpected keyword argument 'on_frame'`.
  The executor remains alive; it owns this D1 smoke/API compatibility repair. Codex did not restart or modify D1.
- Codex capacity notice at 14:01 EDT: 216.81.245.71:34210 has finished all original combo-reward and Codex follow-up
  evaluations. The final follow-up is fully SHA-verified at pod_backup_weekend/codex1018/34210/20261018T175911Z;
  earlier full reward/main-follow-up receipts are in codex1018/backup_index.json. It is available for remaining
  delegable step-d / final-runtime work, alongside 10757. Codex has not stopped either pod or dispatched step-d there.
  The control pod 19400 is on its final fresh block. Cue pod 30988 is approaching its last greedy fresh block;
  allow roughly 14:12 EDT for ALL_DONE, not 14:05. D1 must still wait for the actual marker and CPU-lock release.
- Codex paired attribution check at 13:39 EDT, unchanged mix/live_cmp.py on the verified standard 960-game views:
  combo reward minus its control = +1.35 pp [-2.08, +4.69] off; +1.15 pp [-2.29, +4.58] offc. Neither is a clear gain.
  Both candidate arms also fail the standard CLIII bar. Full tables: codex1018/COMBO_CONTROL_RESULTS.md.
- Codex capacity notice at 13:13 EDT: c3_ctl on 64.247.206.79:10757 is DONE (all 1,920 evaluation games) and its full
  result/checkpoint directory is SHA-verified at pod_backup_weekend/codex1018/10757/20261018T171001Z. That temporary
  pod is available for remaining delegable step-d / final-runtime gate work. Codex has not launched step-d there or
  stopped it. The existing D1 waiter on 30988 remains the executor's responsibility; avoid duplicate D1 dispatch.
- Codex progress at 13:28 EDT: 7 of 12 seed blocks are complete; the last sampled block started at 13:21:48 EDT, followed
  by the four greedy blocks. Candidate blocks take about 10 minutes, so allow roughly 14:12 EDT for ALL_DONE (the marker,
  not this estimate, releases D1). Sampled cue is +5.21 pp [1.67, 8.85] standard but +1.25 pp [-2.19, 4.69] fresh versus
  CLIII: it fails the two-set bar. Greedy results are still running. No live change is authorized by these SIM numbers.
- The shared lead committed the API workspace-header repair as dc5363e at 12:14 EDT and relaunched API-worker wrappers.
  Codex did not restart them; check their current descendants/logs rather than the old PIDs.
- IMPORTANT for the executor: 30988 is now running the ticket's required same-code CLIII / cue_ab2 standard+fresh SIM
  evaluation under /workspace/codex1018. Launcher PID 2462 (16:15:43 UTC), current gap parent through flock PID 2469.
  It holds /workspace/cpu.lock for each seed set. Do not start D1 CPU work concurrently or alter this isolated tree.
  Other /workspace paths remain available for preparation. Coordinate a handover after the evaluation finishes, or use a
  released training pod. KEEP remains present. No live changes.
- The original cue_ab2 and CLIII evaluation code differed; the rerun uses one frozen C3 snapshot and re-scores both models.
  The original results and full CLIII identity edc82ada38e102369f9e99bdd681df16355851185ae44b95027378b404289952
  are verified in pod_backup_weekend/codex1018/14009/20261018T160111Z.

## 2026-10-18 12:00 EDT -- Codex ticket correction and recovery finding

- Corrected EXECUTOR_TICKET.md decision 6: REB uses the pro-imitation IL-cue anchor, card choice only, very loose; optional
  CLIII-anchor twin if pod capacity allows, selected on standard and fresh seeds. The ticket explicitly supersedes the
  earlier tight/all-head CLIII wording in PLAN.md. PLAN.md and training code/configuration were not changed.
- Recorded launcher PID 10448 is absent, with no surviving descendant found. executor.log stopped at 10:53:48 EDT.
  The worker failed before execution: HTTP 400, credential lacks workspace scope and requires a workspace-id header.
  Its launcher logged exit 0, but no prior STATUS.md or executor result exists. That exit code is not task success.
- Pod 64.247.206.80:30988 is reachable, KEEP present, ~50 GiB free, no D1/D2 process or data staging found at 11:59 EDT.
- Stage 2 A/B remain alive on 13396/19834 (updates 53/56 of 130 at 11:59 EDT); their completion remains a dependency.
- No executor restarted yet. Recovery must first resolve the workspace-scoping error, then use the amended ticket.
- No live process, checkpoint, training configuration, or pod lifecycle changed.
