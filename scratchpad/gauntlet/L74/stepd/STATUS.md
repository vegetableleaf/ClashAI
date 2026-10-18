# Step-d status

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

- Codex capacity notice at 13:13 EDT: c3_ctl on 64.247.206.79:10757 is DONE (all 1,920 evaluation games) and its full
  result/checkpoint directory is SHA-verified at pod_backup_weekend/codex1018/10757/20261018T171001Z. That temporary
  pod is available for remaining delegable step-d / final-runtime gate work. Codex has not launched step-d there or
  stopped it. The existing D1 waiter on 30988 remains the executor's responsibility; avoid duplicate D1 dispatch.
- Codex progress at 12:44 EDT: 3 of 12 seed blocks are complete; the fourth started at 12:42:49 EDT. Observed throughput
  is about 9 minutes per block, so allow roughly 14:05 EDT for ALL_DONE (the marker, not this estimate, releases D1).
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
