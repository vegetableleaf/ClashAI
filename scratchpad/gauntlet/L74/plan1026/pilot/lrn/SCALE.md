# LEARNER-SCALE: making the learner ~100x faster (fp32, KL cap 0.02) on the 8x RTX PRO 6000 box

Labels: (a) measured (number + source), (b) plausible, untested, (c) contradicted. Owner mandate 10-28: learning progress
per wall-clock hour x50-100+, fp32 only (TF32 off), kl_stop_prev 0.02. Rent only on a measured >= ~50x projection.

## STATUS (keep current; 10-28 ~21:45 EDT)
- DONE (a) 335f151: step 1 noise scale, T 0.3 records, raw critic (section 1).
- DONE (a) 3866761: `micro_batch` (section 3a): tests, absent-key smoke, step profile (section 2).
- DONE (a), this commit:
  - warm-critic noise scale, T 0.1 noise scale (96 matches; section 1b);
  - accum_gate (section 3b: identity, and the sqrt-lr rule CONTRADICTED);
  - micro_batch=32 smoke PASS: config 27c4dc830ce9, u0000 e816a6a4 / 3e07cff4 (bit-equal to off), u0001 f060b678 /
    f46b1818 (fp32 order);
  - the cap-fixed learning-speed model (section 4).
- RUNNING (33920 GPU): `lr_sweep.py`: warmed-Adam large-minibatch lr sweep with the held-out surrogate gain per update.
  - Command: `/workspace/lrn/sweep/run.sh`; log sweep.log; done marker `done`; ~1 h.
  - Restart: `cd /workspace/lrn/sweep && setsid nohup bash run.sh &`.
- Pilot (owner 10-28): postponed until opponent v1 is usable; no arm S / L run tonight.
- 33308 tree (mine): /workspace/lscale/cb (setup_ls.sh: copies of pipeline + my lrn scripts, symlinks into LOOP-INT2's
  /workspace/loop/cb; env_ls.sh). GPU1 + <= 30 GB RSS (lead).
- Codex dispatches: LEARNER-SCALE_1 (low): profiler runs + PROF_TABLE.md. DONE in 779 s; I checked the numbers against
  the JSONs.
- NEXT (lead order): lr sweep result -> final arm L lr (and the opt-in KL fixes if one step still overshoots) ->
  per-row fp32 fixes (gen_batch features once per update, kernel count) -> DDP on 33308's 2 GPUs -> projection.

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
