# LEARNER-SCALE: making the learner ~100x faster (fp32, KL cap 0.02) on the 8x RTX PRO 6000 box

Labels: (a) measured (number + source), (b) plausible, untested, (c) contradicted. Owner mandate 10-28: learning progress
per wall-clock hour x50-100+, fp32 only (TF32 off), kl_stop_prev 0.02. Rent only on a measured >= ~50x projection.

## STATUS (keep current)
- Step 1 noise scale, T_gate 0.3 records, raw B0 critic: DONE (a), see section 1. Warm-critic run (3 critic warm-up
  updates on disjoint id0 records): running on 33920 (`/workspace/lrn/noise/chain.sh`, log ns_warm3_t03.log, done
  marker chain.done). T_gate-0.1 records: waiting on LOOP-INT2's path (the lead relays it).
- Step 2 profile: Codex LEARNER-SCALE_1 (low) dispatched; it waits for chain.done, then runs prof_step.py det 1 / det 0.
  Outputs go to lrn/prof/ (PROF_TABLE.md).
- Steps 3-6: not started.
- Restart: `ssh -p 33920 ...; cd /workspace/lrn/cb && source scratchpad/gauntlet/L74/plan1026/pilot/lrn/env.sh &&
  $PY -u scratchpad/gauntlet/L74/plan1026/pilot/lrn/noise_scale.py --config scratchpad/gauntlet/L74/plan1026/pilot/ops/pilot.yaml
  --keep /workspace/lrn/id1/keep --T-gate 0.3 [--warm /workspace/lrn/id0_freshhead/keep --warm-updates 3] --out X.json`
  (~12 min on the 4090: 7 min for the per-match gradients, then the row minibatches).
- Codex dispatches: LEARNER-SCALE_1 (low): profiler runs + table (outcome pending).

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
