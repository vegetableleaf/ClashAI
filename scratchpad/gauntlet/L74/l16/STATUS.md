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
