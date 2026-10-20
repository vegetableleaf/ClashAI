# New full step-d pods — 2026-10-20

Ticket: [SETUP_TICKET.md](SETUP_TICKET.md). Mechanical setup only.

| Pod | SSH endpoint | State |
|---|---|---|
| P1 | root@64.247.206.80:48148 | **READY** — verified 10:40 UTC / 06:40 EDT |
| P2 | root@64.247.206.80:40548 | **READY** — verified 10:40 UTC / 06:40 EDT |

Both pods are idle for the lead. Only the explicitly requested smokes ran; no training arm, fine-tune, evaluation chain, waiter, GO file, live change, or pod stop was started.

## Acceptance evidence

| Check | P1 / 48148 | P2 / 40548 |
|---|---|---|
| Existing `ship_stepd.sh HOST PORT` with isolated staging path | `CODE_OK`, exit 0 | `CODE_OK`, exit 0 |
| `RUN=stepd_l16_s74 bash .../l16/pod_smoke.sh` | `SMOKE PASS`, exit 0, 10:39:03 UTC | `SMOKE PASS`, exit 0, 10:39:05 UTC |
| Smoke coverage | Two updates, PPO at update 1; all 11 resume fields true | Same |
| `venvf13/bin/python -c "import torch; print(torch.cuda.is_available())"` | `True` | `True` |
| GPU imitation preflight | Actual IL model loaded on CUDA; pipeline imports pass | Same |
| Final `verify.sh` | `POD_READY`, exit 0 | `POD_READY`, exit 0 |
| Runtime/input integrity | All code/data/checkpoint manifests, 52 dependency pins, and source torch library hashes pass | Same |
| Capacity | 27.2 CPU quota, L40, approximately 25 GB free | Same |
| Final state | No training/eval processes or GO files | Same |

The exact s74 YAML SHA is `601065b3b54a689b2d741b8af405767e3d8e25d165d9adf3e1715b7dd09fc6b1`; persisted smoke configs contain `live_levels: all16`. Only the existing wrapper's `critic_warmup_updates=1` smoke override was used.

Smoke logs, independently copied back and rehashed:

- P1: `3a82c503e0b284b866c7a198361aeed372d1cb97e9862a3148a6bcff90dca2be`
- P2: `2e340ced78b9879c69e6987b5aac63b657cb7d1b8bbefc1ecc60c3864b67aed8`

Remote evidence: `/workspace/stepd/l16_smoke_stepd_l16_s74/{smoke.log,status.log,yaml.sha,SMOKE_OK}`, `/workspace/pods1020_install.log`, `/workspace/stepd/fin13/setup.log`, `/workspace/troops/setup.log`, and `/workspace/in/pods1020/` manifests. Local copies: `.unlazy/pods1020/evidence/<port>/`. Runnable gate fingerprints are recorded in [GATES.md](GATES.md).

After each real smoke passed, its log/YAML receipt was copied into `/workspace/stepd/smoke/` and the legacy `SMOKE_OK` marker established there, satisfying `stepd_chain.sh`'s prerequisite. The installed chain equals committed source; shell syntax and `EVAL_LEVELS` propagation checks pass. No chain was invoked.

## Scope and provenance

- The code snapshot is pinned to `578697f9080710f57885cd7ef7149cfd0806249e`, archived directly from Git. Unrelated working-tree edits are excluded.
- Existing `pod1015/up.sh HOST PORT none` supplies the base bundles, `pod_setup_l74.sh`, and base staging. `none` starts no job.
- Full step-d staging follows `troops/setup_troops.sh`, `stepd/setup_fin13.sh`, and the existing `ship_stepd.sh`, with an isolated laptop staging directory.
- Inputs come from the laptop, `pod_backup_weekend`, and the exact dependency archives used to stage 15617. No existing pod is accessed.
- Added scripts prepare files/environments and verify readiness. The only trainer invocation authorized here is the requested `l16/pod_smoke.sh` using `stepd_l16_s74.yaml`.
- No training arm, evaluation chain, waiter, GO file, live change, deployment, or pod stop is authorized or performed.

## Progress

- 2026-10-20 10:10 UTC: both SSH endpoints verified empty; both report NVIDIA L40, 46,068 MiB GPU memory, 50 GB workspace.
- 10:16 UTC: both base uploads passed `BUNDLE_OK`; base runtime builds started.
- 10:18 UTC: supplemental uploads started. Packaging self-hash defect corrected before upload; independent read-only review found no overlapping code/dependency paths.
- 10:21 UTC: both base stages passed, with `torch 2.11.0+cu128` detecting NVIDIA L40.
- 10:25–10:26 UTC: both supplemental uploads checksum-verified. The local upload wrapper reported an EOF after `UPLOAD_OK` because its file was edited while running; direct remote transport verification independently passed before either install. The current wrapper passes `bash -n`; all later commands use stable script snapshots.
- 10:26 UTC: both installs exited zero with `INSTALL_OK` and `DEPENDENCY PREFLIGHT PASS`. Fin13 and fork36 activated with their frozen manifests; the actual IL checkpoint loaded onto CUDA without training or evaluation.

## Shared inputs

All hashes are SHA-256. The shipped code manifest covers 2,705 files.

| Artifact | SHA-256 |
|---|---|
| Code archive, commit `578697f` | `562e66bb12b41190d113319f451ea8714383a7e35d971b0318529f0a39c7b470` |
| `code.sha` | `fd95ac7502b3c0d08982f4e9fce4271f3879210c72d8c668825039479f8f0d7a` |
| Existing step-d data archive | `487dc042cd86f4f5fd3d1dfbacea3be3e1dc0a229f88c4425943858f53318f92` |
| Added checkpoints/cue/weights archive | `22444b389c2aaf695c2acc9a47affb49aed55169f8a88dc5be8198a1dbc1844f` |
| Fin13 wheel | `969a2ac8de9dccadac72269bff18690e2e702c199eca84de45c7b0e866951878` |
| Fork36 wheel | `db2476f3759ac1ed50b7c6df1de46637d4c060aa7e46e31a92db364ae71afe03` |
| Init `rlarm_succ_levels_u0065.pt` | `05d42da7048daf0e59e5370a6ef1a1c561b538a7ea5822d0fd51cf06b52a53cf` |
| CLIII `rlarm_succ_levels_u0065_grafted.pt` | `edc82ada38e102369f9e99bdd681df16355851185ae44b95027378b404289952` |
| CLX `rlarm_stepd_ctrl_nos2_u0130_grafted.pt` | `5d212358322eb0dd9874448f848a56d633ebb64f8049dd1ac46fe96a374f2492` |
| IL `stepd_il/gen_cuew_s0.pt` | `279b4f30eb415fbda5d6379112b66c81fa16a2dc9d265c09debb08b62d64380d` |
| S2 `s2_all_il_sA_u0130.pt` | `87033dcc360deef5607b7d7d554cfe2ac5cf5362201ad16bc3b56ce237eff531` |

Installed under `/workspace`: base `clashbot`/`venv33`, full `cb_tt`/`venvf36`, `cb_stepd`/`venvf13`, chain in `stepd/bin`, and `KEEP`. Included inputs: all s74 YAML paths, five external opponents, S1/GEN/E4 checkpoints, u250 graft donor, pool split, catalog/config/legacy helper dependencies, v32 imitation dataset and context artifacts, completed cue sidecar, and row weights. Fin13 uses RoyaleSim commit `a697d1f9`; fork36 uses `bc2bf9d`; RoyaleGym is `0.1.23`, torch `2.11.0+cu128`, NumPy `2.5.4`.

The s74 YAML contains no IL/S2 opponent reference, but both checkpoints are installed for the other step-d arms. No model fitting was performed to claim GPU readiness: measured evidence is module/dependency loading and loading the IL model onto CUDA, followed by the explicitly requested RL smoke.

Readiness is measured by the checks above. Full assigned training/fine-tuning and promotion evaluations remain for the lead to launch.
