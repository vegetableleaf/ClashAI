# LEARNER-SCALE: making the learner ~100x faster (fp32, KL cap 0.02) on the 8x RTX PRO 6000 box

Labels: (a) measured (number + source), (b) plausible, untested, (c) contradicted. Owner mandate 10-28: learning progress
per wall-clock hour x50-100+, fp32 only (TF32 off), kl_stop_prev 0.02. Rent only on a measured >= ~50x projection.

## STATUS (keep current; LEARNER-SCALE2, 10-28 ~23:45 EDT)
- Previous seat's commits: 335f151, 3866761, e09c4cd, e8da717. This seat: kl_lr_target + T 0.1 records + section 6
  (this commit).
- Opt-in keys landed (absent = byte-identical, hash unchanged):
  - `micro_batch`, `mem_row_cache` (previous seat).
  - `kl_lr_target` (this seat): the KL-adaptive lr, section 6a. Smoke ls2_smoke_off on 33920 with this code: config
    b5e2a2bbafef, u0000 e816a6a4 / 3e07cff4, u0001 f060b678 / 5c61ac04 = the reference. SMOKE PASS.
- Records (a): 6 x 512 B0 matches at T_gate 0.1 (pilot.yaml at HEAD e8222884), each with LOOP-REC byte-identity PASS.
  - Engine: 33920's crforge lib d2/stage, NOT the pilot's fe364ceb lib (b: the engine difference is not measured).
  - Location: 33920:/dev/shm/lscale/t01_s{2101..2106}/keep, ~2.5 GB each, in RAM: a pod restart loses them.
  - Rebuild: /workspace/lrn/cap_t01.sh (Codex LEARNER-SCALE_3), and chain_ls2.sh for 2105 / 2106.
- RUNNING on 33920: /workspace/lrn/chain_ls2.sh (log /workspace/lrn/logs/chain_ls2.log). Steps, in order:
  1. capture 2105 and 2106;
  2. lr_sweep at equal KL (log sweep2.log, out /workspace/lrn/sweep2/sweep_t01.json);
  3. the noise scale on 1,024 T 0.1 matches (noise2.log, /workspace/lrn/noise2/ns_t01_1024.json).
  Restart: `cd /workspace/lrn && setsid nohup bash chain_ls2.sh > logs/chain_ls2.log 2>&1 &`. It skips the captures
  already done; the sweep and the noise run start over.
- Codex dispatches:
  - Previous seat: LEARNER-SCALE_1 (profiler) DONE; _2 BLOCKED; _2b (2-GPU probe) DONE.
  - This seat: LEARNER-SCALE_3 (low), the T 0.1 capture (4 x 512): DONE in 27 min, 4/4 PASS. I checked its numbers
    against the log.
- NEXT: read the sweep and the noise results into section 6, then the projection (section 6d).

Previous seat's STATUS (10-29 ~00:30, superseded): `git show e8da717:scratchpad/gauntlet/L74/plan1026/pilot/lrn/SCALE.md`.

## 1. Gradient noise scale (noise_scale.py)
Method: B_simple = tr(Sigma) / |G|^2. The loss is split into components: gate / card / cell = -sum w A lp_head (the L_pg
gradient at ratio 1), value = vf_coef x the clipped value loss. The sum of the components is checked against
minibatch_loss's gradient: rel diff 1.2e-6 (a).
- MATCH unit h_m = M sum_{i in m} g_i. tr(Sigma_m) is its sample variance. The unbiased true-gradient norm is
  |G|^2_U = |h_bar|^2 - tr / M, which corrects for the batch's own sampling noise.
- ROW unit: random b-row minibatches of the batch give E|G_b - G_fin|^2 = tr(Sigma_row) / b x FPC.
- CI: delete-one-group jackknife over 32 groups of 16 matches. The lo / hi bounds are tr / (|G|^2 +- 2 se).

Run 1 (a): id1/keep, 512 matches, 159,070 rows (311 train rows / match), T_gate 0.3 (on-policy: ratio_maxdev 5.7e-6),
B0 with its own critic (no warm-up; explained var 0.92 with tower_phat). Result file
`33920:/workspace/lrn/noise/ns_raw_t03.json` (copy: lrn/noise/ns_raw_t03.json).

| component | tr(Sigma_match) | unbiased G^2 (+- se) | B_match (matches) | B_row via 256-row mbs | note |
|---|---:|---:|---|---|---|
| policy | 30.3 +- 2.3 | -0.0067 +- 0.041 | >= 405 (2 sigma), no upper bound | tr_row 7,451 +- 987 -> >= ~100k rows | G_fin^2 0.052 = noise alone (tr/M 0.059) |
| gate | 22.9 +- 1.7 | -0.0072 +- 0.033 | >= 386 | - | most of the noise |
| card | 4.3 +- 0.6 | -0.0017 +- 0.0038 | >= 737 | - | |
| cell | 3.8 +- 0.6 | +0.0021 +- 0.0020 | 1,826 [630, inf] | 392k rows | the only head with ~1 sigma of signal |
| value | 0.083 +- 0.004 | 0.0029 +- 0.0010 | 29 [17, 95] (~9k rows) | 328 rows | design effect 28 (rows in a match correlated) |
| total | 30.4 | -0.0017 +- 0.047 | >= 327 | - | |

Also (a): the 256-row gradient norm is 8.5-9.1 against grad_clip 0.5, so every step is clipped ~17x. Adam is
scale-invariant, so the clip acts as a per-step reweight, not a step-size change.

Reading:
- (a) Over 512 matches, the policy gradient's signal is below what the noise can resolve. The critical batch is at
  least ~400 matches / ~100k rows, with no upper bound found.
- (b) Today's update (145 x 256 = 37k rows) is therefore noise-dominated: under Adam plus the KL cap, most of the policy
  movement is a random walk. Large batches up to >= 100k rows cut the number of steps about linearly, which is what lets
  many GPUs share one step. Thousands of matches per update are needed before the update gradient carries more signal
  than noise.
- Caveats: B0 at its init critic; T_gate 0.3 records (the pilot samples at 0.1). The warm-critic and T_gate-0.1 reruns
  are owed.

### 1b. Reruns (a)
| run | records | policy trS | policy G^2_U | B_match policy (2 sigma lo) | cell B_match | value B_match | file |
|---|---|---:|---:|---|---|---|---|
| raw critic | id1 512, T 0.3 | 30.3 | -0.0067 +- 0.041 | >= 405 | 1,826 [630, inf] | 29 [17, 95] | noise/ns_raw_t03.json |
| critic warmed 3 updates on disjoint id0 | id1 512, T 0.3 | 28.8 | -0.0049 +- 0.031 | >= 513 | 1,249 [513, inf] | 16 [11, 35] | noise/ns_warm3_t03.json |
| T_gate 0.1 pilot records (lint_pa3 u0-2, abilities + barrel_decoy_sim, fe364ceb + 16.635.3) | 96 matches, T 0.1 | 106.7 | -0.31 +- 1.0 | >= 60 | >= 520 | 89 [18, inf] | noise/ns_pa3_t01.json |

- T 0.1, gate: the gate log-prob scales with 1 / T_gate, so its noise trace is 103.6 vs 22.9 at T 0.3 (x4.5). The
  256-row gradient norm is 23.5 vs 8.5.
- T 0.1, n = 96 matches: this can only bound B_match from below at ~60 matches. It says nothing beyond "no policy signal
  resolved". The 512-match T 0.3 runs are the informative ones until a few hundred T 0.1 matches exist.
- Both 512-match runs agree (a): the policy signal over 512 matches is below what the noise resolves. B_match >= ~400-500
  matches (>= ~125-160k rows at 311 rows/match), with no upper bound.

## 2. Learner step profile (prof_step.py; Codex LEARNER-SCALE_1; table lrn/prof/PROF_TABLE.md)
Setup (a): 33920 4090, pilot.yaml, T_gate 0.3, 128 matches of id1 records. One PPO step = minibatch_loss + backward +
clip + Adam, with the lazy anchor filled outside the timer. Timers are CUDA-synchronised medians over 12 steps; one
torch.profiler pass covers 3 steps.

| mb | total ms | gen_batch (CPU mem features) | fwd (rest) | bwd | clip + Adam | rows/s | peak MB | kernels / step | TFLOP/s (mm + conv) |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 64 | 102 | 13.1 | 36.3 | 46.6 | 5.3 | 625 | 1,300 | 5,190 | 1.00 |
| 256 | 170 | 42.3 (25%) | 59.8 | 62.5 | 6.5 | 1,510 | 2,790 | 5,260 | 2.26 |
| 1,024 | 441 | 166 (38%) | 102 | 166 | 7.0 | 2,320 | 8,790 | 5,710 | 3.25 |

- (a) det 0 (no deterministic algorithms, cudnn.benchmark on) gives the same times within 1-7%. Determinism costs
  nothing, so it stays.
- (a) gen_batch scales linearly with rows: the CPU match_memory.rows_features rebuild runs again for every minibatch.
  This is the first lever. The features are a deterministic function of the row, so they can be built once per update
  and kept on the GPU, exactly (b: identity to be checked).
- (a) ~5,200-5,700 kernels per step, about 3,160 of them fill_ (zero-init) kernels. Achieved 2-3 TFLOP/s on mm + conv
  against the 4090's ~82 TFLOP/s fp32 peak: 3-4% of peak. At 1,024 rows the GPU part (fwd + bwd excluding gen_batch) is
  ~270 ms = 0.26 ms/row. Launch overhead plus small kernels dominate at 256 rows.
- (a) The main kernels are the fused fp32 SDPA (cutlass mem-efficient attention; SDPA is already fused) and the
  CellRefine conv backward.
- (b) Peak memory is ~8.6 MB/row at 1,024, so a 96 GB PRO 6000 fits ~8-10k-row micro-batches.

## 3a. micro_batch: exact large minibatch on one GPU (gradient accumulation; lead 10-28 priority 2)
Key `micro_batch: m` (int >= 1; absent / null = off; the config hash is unchanged when absent). Any minibatch larger
than m rows is computed in m-row micro-batches. Each micro-batch's loss is scaled by |j| / |minibatch| (n_total x
|j| / |mb|) and backpropagated at once, so the summed gradient IS the minibatch gradient (fp32 order aside). Clip,
Adam step and the kl_stop_prev check then see the whole minibatch, as before.
- Monitors are merged per minibatch: sums for the scaled losses, max for the max-deviations, and row-weighted means
  with minibatch_loss's own masks (gate-sampled rows for gate KL / entropy, played rows for card / cell, rows for
  ratio / clip_frac). cf_credit and F6' rows are refused.
- vf_grad_share's monitor minibatch is capped at m rows.
- Use: `minibatch: 32768-131072`, `micro_batch: 1024` on a 4090 (8.8 GB at 1,024 rows), ~8192 on a PRO 6000 (b).
- lr / clip rule:
  - lr x sqrt(minibatch / 256): Adam's square-root scaling rule (Malladi et al. 2022), valid while the minibatch is
    under the noise scale, which section 1 puts at >= ~100k rows. The KL cap 0.02 stays the real step limit (it stops
    the epoch).
  - grad_clip stays 0.5. Adam is scale-invariant, so the clip only rescales a step. From section 1's tr(Sigma_row), the
    gradient norm falls from ~9 at 256 rows to ~0.4-0.6 at 32k-65k rows (b), so the clip mostly stops binding.
  - The lr is the A/B's free parameter (step 5), not a settled rule.
- Tests (a): pipeline/tests/test_learner_fast_accum.py, 5 tests:
  - off / null / >= minibatch: weights and monitors byte-identical.
  - micro 1 / 3 / 4 vs whole minibatch (16 and 64 rows, with and without the value loss), SGD: weights within 1e-5
    rel / 1e-6 abs, monitors within 1e-5.
  - one-minibatch gradient within 1e-5 rel.
  - kl_stop fires at the same (epoch, minibatch, steps).
  - config validation and hash.
  - Adam note: on the tiny test model Adam turns ~1e-9 gradients of truly-zero-gradient parameters into steps of
    ~0.1 lr (eps 1e-8), so Adam weights there differ by O(lr) although every gradient agrees to 1e-7. Hence the SGD
    identity test.
  - Pod 33920 (a): 79 passed (new + test_kl_stop_prev, test_lazy_refine, test_ent_pair, test_rl_gen, test_rl_royale);
    pyflakes clean.

## 3b. accum_gate on real records (a; 33920, id1, T 0.3, u5 from a fresh B0 learner; accum/gate.json)
| arm | lr | steps | stop KL | rows used | PPO s | note |
|---|---:|---:|---:|---:|---:|---|
| base mb 256 | 1e-5 | 145 | 0.0208 | 37,120 | 38.6 | today |
| mb 256, micro 64 | 1e-5 | 145 | 0.0208 | 37,120 | 95.7 | identity: monitors <= 3.6e-5 rel, weights max 1.09e-5 |
| mb 32,768, micro 1,024 | 1.13e-4 (sqrt rule) | 1 | 0.106 | 32,768 | 59.9 | one step = 5x the cap |
| mb 65,536, micro 1,024 | 1.6e-4 (sqrt rule) | 1 | 0.638 | 65,536 | 115.1 | one step = 32x the cap |

- Identity rule (lead 10-28, accepted): gradients agree <= 1e-7 rel, monitors <= 1e-4 rel. Weights may differ at ~lr
  scale through Adam's eps on parameters with zero true gradient. Here 1.09e-5 = 1.1 lr after 145 steps; lazy_refine's
  accepted gate was the same mechanism.
- The square-root lr rule is CONTRADICTED under the per-update cap (c). From a fresh Adam the first step is a sign step
  of exactly lr per parameter. A clean large-batch gradient makes the signs coherent, so one step's KL is large: x6 from
  32k to 65k rows at x1.41 lr.
- The large-batch lr is set by the KL budget per step: KL ~ lr^2 (b) gives ~2.5e-5 at 32k and ~1.4e-5 at 65k for
  ~0.005 per step (~4 steps per update). lr_sweep.py measures this with a warmed Adam (running).
- Cost (a): ~0.88 ms per row-step at 1,024-row micro-batches, including the lazy anchor and gen_batch (115 s for 2 x
  65k). The minibatch that trips the cap pays a full forward + backward only to read its KL.
  - Fix (ii): a no-grad KL pass first. It costs 1/3 of a step on every minibatch and saves 2/3 on the tripping one,
    so it pays only when an update has <= 2 steps.

## 4. Learning speed under the FIXED per-update cap (owner: kl_stop_prev 0.02; lead 10-28 framing)
progress / h = U x I. U = updates / h = 3600 / (T_roll + T_learn) in the synchronous loop. I = the real improvement per
update (the cap fixes its KL at ~0.02).
- I depends on how much of the KL-0.02 move is signal. A crude model (b): with fixed KL the move D has a fixed size, and
  E[D . G] ~ |D| |G| / sqrt(1 + B_row / R), where R = rows used per update (capped by the rows of the update's matches;
  beyond that the floor is tr_m / M).
  - Today R = 37k. With B_row >= ~125k (section 1): I_today / I_max <= 0.48.
  - All rows of 1,024 matches (318k): I / I_max >= 0.85 at B = 125k.
  - So the per-update gain from large clean steps is <= sqrt(R_L / R_S): <= 1.7-2.9x at 1,024 matches and
    <= ~5.9x at 4,096 matches (all rows). It is bounded; it is not the 100x.
- To measure I: lr_sweep.py's held-out surrogate J (unbiased first-order improvement over B0 on a never-trained
  256-match batch). Section 1 implies J's per-update change is near the resolution of 256 held-out matches (b), so the
  SIM A/B over many updates stays the real test.
- U: the synchronous loop's U is bounded by the wall time of one rollout WAVE. A wave lasts as long as its longest
  match: 1,024 matches took 170 s on 4 producers (a, PROJECTION.md), ~6-9 s projected on the box (b).
  - T_learn today: 40-58 s for 512-1,024 matches (a).
  - Fresh on-policy data per update means matches / h = U x M <= the box's rollout capacity (~400-580k / h, b,
    PROJECTION.md).
  - At M = 1,024: U <= ~400-570 / h.
- Implication (b, from the terms above): the multiple vs today's learner (~80 updates / h at R 37k) is about
  (U_new / 80) x (I_new / I_today).
  - At M = 1,024: <= (400-570 / 80) x (1.7-2.9) = ~8-21x, and only if T_learn falls to <= ~6-9 s (i.e. ~20 row-steps / ms
    on the box, vs ~1.1 / ms on a 4090 today: ~15-20x per-row work).
  - ~50-100x needs BOTH that learner speed and U past the synchronous wave limit, i.e. rollouts overlapped with the
    update (behaviour policy one version stale; PPO's ratio uses the stored lp_old, so the maths holds). That is a
    lead / owner decision (PROJECTION.md way 1).
- Not measured yet: I_new / I_today (lr_sweep, then the SIM A/B), T_learn on the box (per-row fixes + DDP: next steps),
  and the overlap.

## 5. Warmed-Adam lr sweep, mem_row_cache, 2-GPU probe (a; 10-28 night)
lr_sweep.py (33920, T 0.3). Each arm: 3 consecutive updates with a persistent Adam on disjoint 256-match batches.
J = held-out surrogate gain over B0 on a never-trained 256-match batch, cumulative after u7; file sweep/sweep.json.

| arm | steps per update (u5/u6/u7) | cap fired | rows used per update | PPO s per update | J after u7 (+- se) |
|---|---|---|---|---|---|
| base mb 256, lr 1e-5 | 103 / 16 / 14 | yes | 26k / 4k / 3.6k | 28 / 4.4 / 3.8 | +0.00090 +- 0.00046 |
| 32k, lr 1.5e-5 | 6 / 6 / 6 | no | 197k | ~110 | +0.00044 +- 0.00035 |
| 32k, lr 2.5e-5 | 6 / 6 / 6 | no | 197k | ~104 | +0.00059 +- 0.00048 |
| 32k, lr 4e-5 | 1 / 2 / 3 | yes (stop KL 0.025 / 0.046 / 0.020) | 33-98k | 58-83 | +0.00015 +- 0.00051 |
| 65k, lr 1e-5 / 1.4e-5 / 2e-5 | 4 / 4 / 4 | no (KL <= 0.008) | 262k | ~113 | +0.00028 / +0.00039 / +0.00047 (se ~0.00025) |

- (a) With a persistent Adam, today's learner hits the cap after ~15 steps (~4k rows) from the 2nd update on: ~4 s of
  PPO per update.
- (a) No large-minibatch arm beats base on J after 3 updates (all within ~1-2 se), and base is ~25x cheaper per update
  on one GPU.
- (a) The large-batch lr window is narrow: 32k at 2.5e-5 never reaches the cap; at 4e-5 one step overshoots to
  0.025-0.046.
- (b) The thesis "large clean steps make the KL budget signal" is NOT supported at this scale. Per update, J is
  unresolved at 256 held-out matches. Per hour on one GPU, base wins clearly.
- Owed before any conclusion on I: a larger held-out set (lead: scale it via Codex) and the SIM A/B.

mem_row_cache (opt-in `mem_row_cache: true`; MemRowCache / gen_rows in rl_royale): each row's MEM_KEYS features are built
once per update, then served from the cache.
- (a) Unit test pipeline/tests/test_learner_fast_cache.py (3): bytes = gen_batch for any request order / overlap;
  absent = gen_batch; row_subset drops the cache; another memory version falls back to gen_batch.
- (a) Pod 33920: 102 passed (+ match_memory, accum, kl_stop_prev, lazy_refine, ent_pair, rl_gen, rl_royale); pyflakes
  clean.
- (a) Absent-key smoke with this code: b5e2a2bbafef, e816a6a4 / 3e07cff4, f060b678 / 5c61ac04 = reference.
- (a) accum_gate (accum/cache_gate.json), u5 on 512 matches: weights max |diff| vs base = 0.0 (bit-identical), same 145
  steps; PPO 41.2 -> 31.4 s (-24%).

2-GPU probe (Codex LEARNER-SCALE_2b; ddp/DDP_PROBE.md, 33308 2x4090):
- (a) NCCL all-reduce of the 2.0M fp32 gradient: p50 0.85 ms, deterministic.
- (a) Both GPUs stepping at once vs alone: rows/s ratio 0.98-1.01 at mb 256 / 1024 / 2048. No CPU / PCIe contention at 2
  GPUs.
- (b) DDP is compute-bound: all-reduce is <= 0.2% of a 1,024-row step.
- But DDP only helps if each update has enough rows to split. Today's steady-state update is ~15 steps x 256 rows,
  i.e. too few rows to share across GPUs (64 rows / GPU at 4-way: 1.6 ms/row vs 0.66 ms/row at 256).

## 6. LEARNER-SCALE2 (10-28 night)

### 6a. kl_lr_target: the KL-adaptive lr (opt-in, lead-approved)
Key `kl_lr_target: x` (a finite float > 0; absent / null = off; the hash is unchanged when absent).
- What it does: on policy steps only (a no-op in the critic warm-up), before each step the lr is multiplied by
  clamp(sqrt(x / dKL), 0.5, 2).
  - dKL = this minibatch's KL to the anchor minus the previous minibatch's: the KL the last step added. The rule
    assumes KL ~ lr^2.
  - The lr is bounded to [lr / 16, 16 lr] of the config lr.
  - It lives in opt.param_groups, so it carries across updates and checkpoints.
  - The update record gets `lr_end`.
- Use: x ~ kl_stop_prev / 4 (0.005) with large minibatches, so the cap is reached in ~4 steps instead of one overshooting
  step (3b: one 32k step at 1.13e-4 = 5x the cap).
- Known ceiling: dKL comes from two different minibatches, so it is noisy. This matters at mb 256, not at 8k+ rows.
  A negative dKL reads as a tiny step and doubles the lr.
- Tests (a): pipeline/tests/test_learner_fast_kllr.py, 4/4 on 33920:
  - off / null are byte-identical (with and without the value loss);
  - the warm-up leaves the weights and lr untouched;
  - the lr sequence equals the rule replayed from the measured KLs, for 3 targets;
  - the bounds hold;
  - config validation and hash.
  With test_learner_fast_accum and test_kl_stop_prev: 7 passed. pyflakes clean.
- The no-grad KL check before the backward is NOT built. 3b's cost model says it pays only at <= 2 steps per update, and
  kl_lr_target aims at ~4. Build it if the sweep shows 1-2 step updates.

### 6b. Where a step's GPU time goes now (prof_mod.py; 33920 4090; pilot.yaml + mem_row_cache; id1 T 0.3; prof2/)
| mb | fwd ms | bwd ms | clip + Adam ms | total ms | ms / row | kernels / step |
|---:|---:|---:|---:|---:|---:|---:|
| 256 | 48.2 | 57.2 | 4.9 | 110.6 | 0.43 | 5,329 |
| 1,024 | 108.2 | 164.1 | 5.9 | 278.5 | 0.27 | 5,786 |

(a) With mem_row_cache, gen_batch is off the step: at 256 rows the step is 110.6 ms, vs 170 ms in section 2.

(a) Kernel time per step at 1,024 rows (prof_mod_kern_mb1024.txt / _stack_):
- Memory-movement ops: fill_ 31 ms (2,126 calls), clone 30 ms (221), copy_ 29 ms (380), index_put_ 16 ms (25), zeros
  10 ms (65). Together ~117 ms, ~42% of the step.
- The rest: attention backward (cutlass mem-efficient, fp32), conv backward (CellRefine), mm / addmm, Adam ~4.5 ms.
- The kernel count barely depends on rows (5,329 -> 5,786).

(a) Module forward split: the trunk encoder and the memory encoder take ~10 ms each of the 256-row forward. Most of the
rest is glue outside nn.Module forwards: indexing, masks, cat, loss terms, and the lazy refine features (a method).

### 6c. torch.compile probe (compile_probe.py; fp32, TF32 off; prof2/compile_enc.json)
| target | mb | eager ms | compiled ms | speedup | loss rel | grad max diff / global max grad |
|---|---:|---:|---:|---:|---:|---:|
| whole minibatch_loss, dynamic=True | - | - | - | - | - | InductorError (inductor assert on a dynamic size, torch 2.11) |
| trunk encoder + memory encoder only | 256 | 107.1 | 78.3 | 1.37x | 2.5e-6 | 2.6e-6 |
| trunk encoder + memory encoder only | 1,024 | 264.4 | 209.1 | 1.26x | 1.5e-6 | 4.9e-5 |

- (a) The compiled encoders are NOT inside the identity bar: gradients agree to ~5e-5 of the largest gradient, against
  the bar of 1e-7 rel. The worst single tensor is tower_refine.cell.out.bias, whose gradient is ~0 (rel 2-4): the
  Adam-eps case.
- (b) Compile + removing the fill / clone / copy glue (~42%) could reach ~1.5-2x per row. That is not the 15-20x
  target.
- Why not more:
  - The model is small: 2.0M parameters, d 128, so each kernel does little work.
  - FLOPs per row are low (section 2: ~1.4 GFLOP per row in mm + conv), so per-kernel work is memory-bound, not
    compute-bound.
  - Even a perfect fusion is bounded by the attention and conv kernels, ~35-40% of the step.
- CUDA graphs: they need static shapes. The played-row subsets and the token counts change per minibatch, so they need
  padding to fixed buckets first. Not built.
