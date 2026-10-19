# L16 status

## 2026-10-19 - ticket accepted

Owner authorizes two all16 training arms and two all16 fin13 reference chains; no live changes, deploys, or pod stops. Reading current stepd status, overnight log and ship/arm/chain scripts completed. Code checks and exact committed shipping precede launches. Expected training duration about 5.5 hours plus evaluations.

## 2026-10-19 18:29:33 -04:00 - preflight

All four pods reached over SSH and no training/eval/chain/waiter processes found. 13396 and 14009 have cb_stepd + fin13; 19899 has cb_tt + fork36; 15617 has w_cue/cb and needs layout/runtime staging. Existing GO confirms DECODE=--ability-head-decode=sample and NO36=1 on 14009. Trainer and gap implementation delegated with disjoint file ownership. Unrelated working-tree changes excluded from ticket commit and exact shipping archive.


## 2026-10-19 18:33:47 -04:00 - checks and candidate smoke staging

Requested legacy suites: 71 passed, 4 skipped (existing conditional tests); new trainer tests 5 passed, gap tests 19 passed, related livecal tests 12 passed. Changed Python files pyflakes empty. Chain and pod_smoke shell syntax pass. Default gap commands compared to HEAD across 24 variants: identical. Candidate archive 95a90252443197025a875b81d8640f02adf7ab66495333fe949db5bf12f23336 is HEAD plus only 8 explicit L16 code/config/helper files; preparing real pod smoke before commit. Mechanical preflight issues corrected: PowerShell SSH quoting and gate Windows executable separators. No behavioral test failures.


## 2026-10-19 18:36:06 -04:00 - integration checks passed

Combined requested suites plus new trainer/gap and existing livecal tests passed (exit 0; output fingerprint a27663d06f48dd592ee4baa690bf9c7572efb852ac207373f64be9cebc384cc5). Config comparison confirms ONLY live_levels and seed differ from base. YAML SHA256: s74=601065b3b54a689b2d741b8af405767e3d8e25d165d9adf3e1715b7dd09fc6b1; s75=55b8ad0141d4ff0ffbedd1e58b32dfec05e5badbffc2b995cd4fe28747b214f6.


## 2026-10-19 18:36:34 -04:00 - real pod smokes launched

Candidate manifest verified CODE_OK on both arms. Real all16 --smoke with critic_warmup_updates=1 (exercises PPO) launched under claim.lock and cpu.lock: 13396 seed 74 wrapper 1299; 14009 seed 75 wrapper 778. Training config hashes as above. Nine explicit paths staged; no unrelated changes staged. Awaiting SMOKE PASS before commit/push.

## 2026-10-19 18:40:22 -04:00 - smoke progress

Both real pod smokes saved u0000 and passed save/reload pro-agreement round trip. Persisted smoke configs explicitly contain live_levels: all16. Training update/resume checks still running. Reference staging on15617 is installing exact torch2.11.0+cu128 plus source dependency pins directly to avoid slow laptop relay; required runtime hash verification remains unchanged.


## 2026-10-19 18:43:04 -04:00 - reference runtime staged

15617 now has exact source torch2.11.0+cu128 with matching torch/lib SHA256 hashes and all source dependency pins. Replaced slow relay with direct pinned install; fixed temporary duplicate-disk ENOSPC within task-owned environment only. Data and prerequisite manifests verified there. REF candidate-code smokes authorized in parallel with n_actors=8 for preflight throughput; final committed-code verification still required before eval launch. No pods stopped.


## 2026-10-19 18:48:17 -04:00 - real all16 SMOKE PASS

13396 and 14009 both printed SMOKE PASS: two updates including a PPO update (critic_warmup_updates=1), checkpoint reload and all eleven resume checks true. Persisted configs contain live_levels: all16. Wrapper PIDs were 1299/778, trainers 1311/790. 19899 also passed its eight-actor reference preflight at 22:47:51 UTC. 15617 is mechanically filling missing base-tree companions from 13396 (public catalog/config files); prior failed preflights preserved. Committing nine explicit paths after all code gates passed.

## 2026-10-19 18:49:07 -04:00 - code committed and pushed

Code commit: db84ac95834f9373092c72a11ec984cad9442756 (main pushed). Exactly nine explicit paths staged/committed; staged diff check passed. Candidate all16 smoke logs saved locally under .unlazy/l16/evidence: 13396 SHA2564d724c963acb1f6d469bfcbdae2520256b2a521db132c194b8be249b29b88634; 14009 SHA256bebb2177b16a8dec1736eeef46bde7957f709129f8dbf50ac85e786a30a2b04e. Building final archive directly from this commit, with no working-tree overlays.


## 2026-10-19 18:51:27 -04:00 - training arms launched from committed code

Final archive SHA256 39547f71cf86623c5121dd34467f58faaf55f6a2c7cb434143382d9c91d2f1b8; code.sha file SHA256 dfc5e0f6248ad5fb70f34f7a88e41ca7933e7a85845007cf699b570c62e3fd12. Compared against smoked candidate: 2642 files identical, only STATUS.md added. Both arms re-shipped via ship_stepd.sh and CODE_OK; own fresh all16 smoke and exact YAML SHA checked before chain launch.

- 13396 stepd_l16_s74 launched 22:50:40 UTC / 18:50:40 EDT: claim PID 1756, chain 1759, trainer 1764. GO EVAL_LEVELS=all16, DECODE=--ability-head-decode=sample. Persisted config seed 74 and all16 verified.
- 14009 stepd_l16_s75 launched 22:50:49 UTC / 18:50:49 EDT: claim PID 1066, chain 1069, trainer 1074. Same GO plus NO36=1. Persisted config seed 75 and all16 verified after startup wrote config.yaml.
- 19899 CLIII REF chain launched 22:50:54 UTC, claim PID 25139 / chain 25143; awaiting first evaluated rows for final verification.
- 15617 repairing missing base-tree companions using source-verified bytes; real smoke retry active. No design changes or pod stops.

Training ETA: about 00:20 EDT Oct 20 (~5.5 hours after launch), then evaluations roughly 1-1.5 hours (14009 skips fork36). Estimates, not a completion claim.


## 2026-10-19 18:54:32 -04:00 - three jobs verified; remaining base-tree repairs

19899 independently verified REF_RUNNING with 125 worker-chunk rows at ~22:53 UTC: every row had exactly eight learner cards and eight opponent cards at16, towers16/16; active gap PID25153 with --levels all16, claim25139, chain25143. Actual CLIII checkpoint SHA256 edc82ada38e102369f9e99bdd681df16355851185ae44b95027378b404289952; final archive and all code manifest entries pass. REF ETA about30-45minutes from22:50:54UTC (~19:20-19:35EDT).

15617 minimal w_cue tree lacks dynamically loaded legacy helpers outside ship_stepd's code directories. Copied exact source pool split, public catalog/config companions, IceWizard helper+model (hashes only; no internals printed); now staging L70/abilities and auditing remaining external dependencies before another retry. All failures so far are missing-file/module mechanical staging failures; evidence preserved. Training arms remain active.


## 2026-10-19 18:56:40 -04:00 - 15617 dependency preflight passed

Independent audit plus no-match dependency-loading preflight passed for all active dynamic helpers/models and public card/config/calibration data. Exact source companions staged and SHA-verified. 15617 now has final committed archive 39547f71... and CODE_OK; real eight-actor all16 smoke_ref7 launched 22:56:25 UTC, wrapper PID3484. This run uses commit db84ac9 directly. Awaiting its SMOKE PASS before CLX REF launch.

## 2026-10-19 19:00:08 -04:00 - all four pods verified running; ticket complete

Code commit **db84ac95834f9373092c72a11ec984cad9442756** is pushed to main. All four pods run the exact committed archive, SHA256 `39547f71cf86623c5121dd34467f58faaf55f6a2c7cb434143382d9c91d2f1b8`; every code manifest entry passed. Optional all16 training/evaluation is implemented; omitted settings preserve existing behavior. Requested regressions, new level/hash/default tests, pyflakes and shell syntax passed; four existing conditional tests skipped on the laptop. All real pod smokes printed **SMOKE PASS**.

| Pod | Job | Launch (EDT Oct 19) | Claim / chain / trainer PID | Final observed state |
|---|---|---|---|---|
| 13396 | `stepd_l16_s74` | 18:50:40 | 1756 / 1759 / 1764 | Training active; u0000 complete; seed 74 and all16 persisted |
| 14009 | `stepd_l16_s75` | 18:50:49 | 1066 / 1069 / 1074 | Training active; u0000 complete; seed 75 and all16 persisted; NO36=1 |
| 15617 | REF `clx_l16` | 18:59:29 | 3781 / 3786 / n/a | Eval active; gap PID 3795; 13 first worker rows independently verified at about 19:00 |
| 19899 | REF `cliii_l16` | 18:50:54 | 25139 / 25143 / n/a | Eval active; gap PID 25153; 323 merged rows independently verified at about 19:00 |

Both arms use `EVAL_LEVELS=all16` and CLX `DECODE=--ability-head-decode=sample`; 14009 also uses `NO36=1`. Their production YAML differs from `stepd_ctrl_nos2.yaml` only in `live_levels: all16` and seed. SHA256:

- `stepd_l16_s74.yaml`: `601065b3b54a689b2d741b8af405767e3d8e25d165d9adf3e1715b7dd09fc6b1`
- `stepd_l16_s75.yaml`: `55b8ad0141d4ff0ffbedd1e58b32dfec05e5badbffc2b995cd4fe28747b214f6`

Both REF chains use fin13 standard seeds 741200/742000 and fresh seeds 743000/744000, `EVAL_LEVELS=all16 NO36=1`. CLX uses the same sample decode as the CLX chain; CLIII has no ability head. Each checked row has eight learner cards and eight opponent cards at 16, with both towers at 16. Checkpoint bytes independently rehashed:

- CLX `rlarm_stepd_ctrl_nos2_u0130_grafted.pt`: `5d212358322eb0dd9874448f848a56d633ebb64f8049dd1ac46fe96a374f2492`
- CLIII `rlarm_succ_levels_u0065_grafted.pt`: `edc82ada38e102369f9e99bdd681df16355851185ae44b95027378b404289952`

REF evaluation has no training YAML. Both REF preflight smokes used the seed 74 YAML SHA above with smoke-only `critic_warmup_updates=1 n_actors=8`; those overrides do not affect production arms. 15617 final-code smoke passed at 18:59:04 EDT, including both updates and every resume field. Missing base-tree companions/runtime staging were fixed mechanically using exact source bytes. No unresolved design or test failure remains.

Estimated completion: both training phases about **00:20 EDT Oct 20** (~5.5 hours), followed by about **1-1.5 hours of evaluations**. CLIII REF about **19:20-19:40 EDT Oct 19**; CLX REF about **19:30-19:50 EDT Oct 19**. These are estimates; full training/evaluation outcomes are pending.

Pod logs: `/workspace/stepd/rl_<job>/chain.log`; arms also have `train.log`; REF rows are under `eval/<name>_<seed>_fin13/D3/`. Additional runtime, smoke and launch receipts: [ref_receipts.md](ref_receipts.md). All four jobs are left running. No pod stops, live changes or deploys. Unrelated working-tree edits were excluded from commits and shipping.

- 2026-10-19T19:06:55-04:00 follow-on poll: 13396: stepd_l16_s74 active u=3 rows=0 pids=1764 smoke=PASS | 14009: stepd_l16_s75 active u=3 rows=0 pids=1074 smoke=PASS | 15617: clx_l16 active u=None rows=310 pids=- smoke=pending | 19899: cliii_l16 active u=None rows=791 pids=- smoke=pending

- 2026-10-19T19:07:07-04:00 follow-on poll: 13396: stepd_l16_s74 active u=3 rows=0 pids=1764 smoke=PASS | 14009: stepd_l16_s75 active u=3 rows=0 pids=1074 smoke=PASS | 15617: clx_l16 active u=None rows=310 pids=- smoke=pending | 19899: cliii_l16 active u=None rows=791 pids=- smoke=pending

## 2026-10-19T19:07:29.9609713-04:00 - follow-on accepted

Monitoring four authorized pods every 4 minutes (maximum requested 9). Initial poll at 19:04 EDT found all original chains active; 19:06 poll confirms s74/s75 at u3, CLX 310 rows and CLIII 791 rows. New s76-s79 YAML files differ from s74 ONLY in seed. Readout extension and safe successor staging helpers are being prepared independently. Prior code db84ac9 and original chain scripts remain unchanged. No deployment, live changes, pod stops, or messages to external channels. Final exit requires s74/s75 scored and required successors verified through SMOKE PASS and u1.

- 2026-10-19T19:09:54.6540916-04:00 preparation verified: readout.py adds s74-s79 with exclusive all16 reference routing and std/fresh/pooled CIs; --selftest passed independently, offline pyflakes clean, prior legacy output byte-identical. Four successor YAML files verified seed-only. Preparing explicit six-path commit before any successor staging.
