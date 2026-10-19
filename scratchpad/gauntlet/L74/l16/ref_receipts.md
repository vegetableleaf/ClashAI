# L16 reference pod receipts

## 2026-10-19 22:31:11 UTC - initial inventory and staging

- 15617: existing `/workspace/w_cue/cb` hardlinked as `/workspace/cb_tt`; existing `/workspace/vfork` retained. Dedicated `/workspace/venvl16` created for this task only.
- 19899: existing `/workspace/cb_tt` and real `/workspace/venvf36` reused; source versions torch 2.11.0+cu128, numpy 2.5.4, royalegym 0.1.23.
- Both: reusable 673,024,000-byte stepd data archive and explicit 201,041,920-byte prerequisites archive transferring. Prerequisites copied from 13396's working stepd tree with SHA256 manifest; include GEN/E4 evaluation dependencies.
- Exact fin13 wheel confirmed SHA256 `969a2ac8de9dccadac72269bff18690e2e702c199eca84de45c7b0e866951878`.
- Waiting for root's committed immutable code archive before shipping code or launching. No pod stops or live changes.

## 2026-10-19 22:39:46 UTC - mechanical environment staging changes

- A task-only CPU2.11 environment was installed successfully but never used for smoke/evaluation; replaced to match source CUDA build exactly.
- Exact CUDA environment relay from19899 proved slow; only owned source tar/gzip PIDs22639/22641 terminated. Destination tar exited on EOF.
- Parent authorized direct cloud installation with exact torch2.11.0+cu128, source nvidia/triton pins and source torch/lib SHA256 verification.
- First cloud fetch completed in32s; copy-mode installation hit temporary ENOSPC from duplicate extracted files. Only task-owned `/workspace/venvl16` recreated; no existing environments/data/shared caches removed. Retried with no-cache hardlinks to avoid duplication.

Last staging update: 2026-10-19 22:41:26 UTC

## 2026-10-19 22:45:44 UTC - candidate preflight

- Both pods: candidate archive SHA256 `95a90252443197025a875b81d8640f02adf7ab66495333fe949db5bf12f23336` shipped through ship_stepd.sh; CODE_OK. DATA_OK and DEPS_OK from their manifests.
- 15617 at22:41:04UTC: exact CUDA2.11 environment installed; torch/lib file hashes match19899. Source ancillary package pins subsequently aligned, including cuda-bindings12.9.7 and cuda-pathfinder1.6.0; 1.6GB free. FIN13_OK at22:44:18UTC, fin13 binary/runtime and royalegym manifest verified by activate().
- REF preflight uses real `python -m pipeline.rl_royale --smoke` with the unmodified all16 seed74 YAML, overrides `critic_warmup_updates=1 n_actors=8` (parallelizes fixed smoke set). Eval configurations remain unchanged.
- 19899: preflight launcher24071 / trainer24197 started22:44UTC.
- 15617: initial smoke found missing ghost-pool split companion; copied from13396, SHA256 `83323b38a99515e196f0af4dcbe8003be849d86ac38692681f6b137a5aa8ba5f`. Failure log preserved as `smoke_missing_split.log`. Retry first refused existing run directory; used new run name `smoke_stepd_l16_s74_ref2` to preserve prior evidence. Current launcher2094 started22:45:28UTC.
- No reference chain launched yet. Final committed archive verification remains required.
## 2026-10-19 22:49:19 UTC - first real smoke passed

- 19899: full SMOKE PASS confirmed22:47:51UTC in `/workspace/stepd/l16_smoke_stepd_l16_s74/smoke.log`. Both requested updates completed and resume check passed every recorded field. Global stepd/smoke/SMOKE_OK was set only after this genuine success.
- 15617: missing public cards.yaml repaired using exact13396 bytes SHA256 `820b1035f1af6189b2faae7ea072d5ed3538844b06f1ba768f445fb564e47e0e`; source public card-stats/mechanics/calibration and complete derived catalog copied only when missing, then SHA-checked. 19899 matches the same public config manifest.
- 15617 current smoke run `smoke_stepd_l16_s74_ref4`, launcher2571 / trainer2693. Prior missing-catalog/cardsyaml failure logs retained; each retry had a new run directory.
- Code commit reported by root: `db84ac95834f9373092c72a11ec984cad9442756`, pushed. Final archive still pending at this entry; no REF launched yet.
## 2026-10-19 22:55:37 UTC - CLIII reference verified; CLX base dependency closure

- Code commit `db84ac95834f9373092c72a11ec984cad9442756`; final archive SHA256 `39547f71cf86623c5121dd34467f58faaf55f6a2c7cb434143382d9c91d2f1b8`; code.sha file SHA256 `dfc5e0f6248ad5fb70f34f7a88e41ca7933e7a85845007cf699b570c62e3fd12`.
- 19899 CLIII REF launched22:50:54UTC: claimPID25139, chainPID25143; checkpoint full SHA256 `edc82ada38e102369f9e99bdd681df16355851185ae44b95027378b404289952`. `NAME=cliii_l16 EVAL_LEVELS=all16 NO36=1`, fin13 standard741200/742000 and fresh743000/744000 seeds.
- Tightened verification passed with168 first worker rows at22:53UTC, checking active process command, noDONE marker, exact final archive/all manifest files, actual checkpoint bytes, and both eight-card arrays/towers16 on every row. Mean match wall22.9s; estimated reference completion23:20-23:40UTC (30-50min after start; approximate).
- 15617 minimal base needed additional exact helper data outside ship_stepd.sh code dirs. Copied source ability helper plus model companion (hash-only audit, no contents printed), complete L70/abilities directory, unit_values.json and public native live_card_catalog.json. All source manifests verified. Source public pipeline dependency audit underway before retry; prior failure logs and distinct run directories retained.
- Final archive shipping to15617 now that no smoke process remains active. No production reference chain on15617 yet.
## 2026-10-19 22:56:57 UTC - CLX dependency preflight complete; final-code smoke active

- 15617 complete dependency preflight PASS using final committed code and fin13 runtime. It loads all required dynamic helper/model, catalog/card/calibration dependencies without running matches or printing their contents. Script: `.unlazy/l16/refs/dependency_preflight.py` (remote `/tmp/l16_dependency_preflight.py`).
- Final archive and code.sha file hashes match the committed receipt above; CODE_OK after shipment.
- New genuine final-code smoke `smoke_stepd_l16_s74_ref7` started22:56:25UTC, launcher3484, unchanged all16 seed74 YAML and documented smoke-only overrides. No missing paths remain in the independently audited active loader set.
## 2026-10-19 23:01:33 UTC - FINAL: both reference chains verified running

Code commit: `db84ac95834f9373092c72a11ec984cad9442756` (pushed). Both pods verify final archive SHA256 `39547f71cf86623c5121dd34467f58faaf55f6a2c7cb434143382d9c91d2f1b8` and every code.sha entry. Both use fin13-linux with the exact wheel969a2ac8, source torch2.11.0+cu128, and source public runtime dependencies.

| Pod | Reference | Start UTC | Active PIDs | Checkpoint SHA256 | Verified first rows | Approximate completion UTC |
|---|---|---|---|---|---|---|
| 15617 | clx_l16 | 2026-10-19 22:59:29 | claim3781, chain3786, CPUflock3794, gap3795 | 5d212358322eb0dd9874448f848a56d633ebb64f8049dd1ac46fe96a374f2492 | 13 worker rows at23:00 | 23:30-23:50 |
| 19899 | cliii_l16 | 2026-10-19 22:50:54 | claim25139, chain25143, CPUflock25152 | edc82ada38e102369f9e99bdd681df16355851185ae44b95027378b404289952 | 323 merged rows at23:00 | 23:20-23:40 |

- Each reference runs fin13 standard seeds741200/742000 then fresh743000/744000, 480matches perseed; explicit `EVAL_LEVELS=all16 NO36=1`. CLX additionally uses `DECODE=--ability-head-decode=sample`; CLIII has no ability head.
- Root independently checked both real processes and first rows at23:00UTC. Every inspected row has exactly eight learner cards and eight opponent cards at16, plus both towers16. Actual checkpoint bytes were rehashed; both chains had noDONE marker. First CLX row artifact: `/workspace/stepd/rl_clx_l16/eval/clx_l16_741200_fin13/D3/`; CLIII artifact: `/workspace/stepd/rl_cliii_l16/eval/cliii_l16_741200_fin13/D3/`.
- Both genuine all16 smokes completed two updates and passed the complete resume check: 19899 at22:46:54UTC; 15617 at22:59:04UTC. Smoke log on each: `/workspace/stepd/l16_smoke_stepd_l16_s74/smoke.log`. Unmodified seed74 all16 smoke YAML SHA256 on both: `601065b3b54a689b2d741b8af405767e3d8e25d165d9adf3e1715b7dd09fc6b1`. Documented smoke-only overrides: `critic_warmup_updates=1 n_actors=8`.
- `.unlazy/l16/refs/GATES.md`: 2met,0unmet,0abandoned. Both runnable verifier processes exited0 and matched REF_VERIFIED, with shell/CWD/output fingerprints recorded. Verifier paths: `.unlazy/l16/refs/verify.ps1` and `verify_remote.py` (remote `/tmp/l16_verify.py`).
- ETAs are estimates from initial observed match times; this ticket exits with all reference jobs running. No pod stops, live changes or deployments occurred. Mechanical missing-dependency failures and preserved logs are documented above; no unresolved design or nonmechanical failure remains.