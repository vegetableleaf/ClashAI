# LEARNER-SCALE: making the learner ~100x faster (fp32, KL cap 0.02) on the 8x RTX PRO 6000 box

Labels: (a) measured (number + source), (b) plausible, untested, (c) contradicted. Owner mandate 10-28: learning progress
per wall-clock hour x50-100+, fp32 only (TF32 off), kl_stop_prev 0.02. Rent only on a measured >= ~50x projection.

## STATUS (keep current; LEARNER-SCALE3, 10-29 ~13:30 UTC; ALL STEPS DONE)
- Task list = the LEARNER-SCALE2 handover below, steps 1-6. Results are in section 7.
- LEAD DECISIONS (10-29 ~03:35 UTC):
  1. kl_lr_target is PARKED: the key stays but is unused, and the pilot keeps base small steps.
  2. Tickets A (split-projection attention) and B (static-shape minibatch_loss + CUDA graphs) are APPROVED as
     learner-only opt-in work after the A/B. The lead dispatches them. The live / actor inference path must stay
     byte-identical, with identity tests on recorded live decisions.
  3. Finish the A/B into 7f / 7g: DONE.
- Commits:
  - ab133d4: gate_baseline key, tests, glue_probe, 7a-7b.
  - 0e266d2: 7c, 7d, abm/.
  - d4cfc7c: 7e, 7g.
  - 792e868: the MC at 3,000 draws.
  - The STATUS commit: lead decisions.
  - This commit: 7f.
- Results:
  - 7a: gate_baseline is unbiased (MC at 3,000 draws: z 1.50; the planted leak is caught at 33.5). Smokes PASS.
  - 7c: kl_lr_target v2 overshoots the cap up to 6.3x (now parked).
  - 7d: gate baseline = -3% of the policy noise per match. Not adopted.
  - 7e: CUDA-graph bound <= 2x at mb 256; glue ~25% of kernel time.
  - 7f: SIM A/B, M 1,024 - M 128 = +0.6 +- 1.0 pp after 7 updates (both arms +1.0 / +1.7 pp vs B0, unresolved).
  - 7g: verdict ~10-30x, no rent case.
- Finding for the lead (7f): the memory v2 artifacts differ between pods. 33553 /workspace/loop/cb: priors 178955c2,
  lock_head ca144009. 33920 /workspace/lrn/cb: 4312a8ad / 15065623.
- Nothing of mine is running. Leftovers (RAM, safe to drop):
  - 33920: /dev/shm/cbg (test tree), /dev/shm/abm (the dropped eval tree), /dev/shm/lrn_ckpt_moved (726 MB of
    moved scratch checkpoints).
  - 33553: /workspace/abm. On disk there: the A/B checkpoints, ~21 GB free before the run.
- Codex: LEARNER-SCALE3_1 (medium). Dispatches 1, 1b and 1c were BLOCKED correctly (each fixed by me); 1d ran the A/B
  to completion. 1d stopped one run at the 45 GB bar and reran it at 2 x 64, as the ticket said. Its numbers were
  checked against the raw logs (abm/ab_tab.py).

## STATUS of LEARNER-SCALE2 (10-29 ~01:35 EDT; superseded, kept for the handover list)
- Commits this seat:
  - 9bdc04f: kl_lr_target v1, prof_mod, compile probe.
  - daaecbf: kl_lr_target v2 + sweep v1.
    - CAUTION: daaecbf also carried LOOP-ASYNC's uncommitted ppo_decoupled hunks in pipeline/rl_royale.py (my whole
      working file). The lead says they equal what LOOP-ASYNC tested. From now on: hunk-only commits of shared files.
  - This commit: noise scale T 0.1, steady-state cadence, projection (6e-6g).
- Opt-in keys (absent = byte-identical, hash unchanged, smokes PASS):
  - micro_batch, mem_row_cache (previous seat);
  - kl_lr_target v2 (6a).
- Records: 6 x 512 B0 matches at T_gate 0.1 in 33920:/dev/shm/lscale/t01_s{2101..2106}/keep. They are RAM-only: a pod
  restart loses them. Rebuild: /workspace/lrn/cap_t01.sh, plus chain_ls2.sh for 2105 / 2106.
- RUNNING on 33920: chain_ls2b.sh, the equal-KL sweep with kl_lr_target v2.
  - Arms: base, 8k, 32k; started 01:27; ~45-60 min.
  - Log: /workspace/lrn/logs/sweep2v2.log; out: /workspace/lrn/sweep2/sweep_t01_v2.json. Tabulate: `python3
    /workspace/lrn/tab.py /workspace/lrn/logs/sweep2v2.log`.
  - Restart: the last command in /workspace/lrn/chain_ls2b.sh.
- Codex: LEARNER-SCALE_3 (low), the T 0.1 capture: DONE, 4/4 PASS, checked against the log. No other dispatch.
- HANDOVER (10-29 ~01:35; this seat's context is exhausted). Lead's overnight ticket (BUILD + MEASURE; nothing goes into
  pilot.yaml), for a fresh seat, in order:
  1. Gate-head variance reduction, as an opt-in key. It must be UNBIASED.
     - Where: the gate term is in policy_terms (rl_royale.py ~2460: lp_gate = logsigmoid(+-x) on gate_sampled rows) and
       minibatch_loss (joint ratio on lp_gate + lp_card + lp_cell, ~2807).
     - Form (a), the expected value over the two gate outcomes: needs Q(s, play) and Q(s, wait). The records hold only
       the sampled outcome, so this needs counterfactual returns (the R_fork / cf SIM forks give them at fork rows
       only). Not buildable from today's records.
     - Form (b), a gate-specific state baseline: A_gate = A - b(s) on gate rows only. b(s) is a detached regression of
       A on the trunk's g. CROSS-FIT it by match halves, so a row's own A never enters its baseline; otherwise the bias
       comes back. Unbiased because b does not depend on the gate action.
     - Proof: on test_rl_royale's tiny model, compare the mean gradient over many sampled trajectories (MC), on vs off,
       equal within MC error. Plus: absent = byte-identical, hash unchanged, a real smoke.
     - Then: noise_scale.py on s2101 + s2102 with the key on; compare against 6e (gate tr 85.7; policy B_match ~1,200).
  2. SIM win-rate A/B: 128 vs 1,024 matches per update, >= 2 seeds, at equal updates. ASK THE LEAD before using 33308.
     Use LOOP-ASYNC's ab_queue.sh pattern (fastloop + ab_eval) with E/G set per arm.
  3. CUDA graphs on fixed row buckets (pad the minibatch to 256 rows; played-row subsets padded to fixed buckets) +
     removing the glue (6b: fill / clone / copy / index_put ~42%). Identity: gradients <= 1e-7 rel, monitors <= 1e-4.
     Measure with prof_mod.py.
  Then update 6g with what got measured.
- NEXT (older):
  1. Read the v2 sweep into 6d. The question: does any arm reach the cap without overshoot, and with what paired dJ?
  2. Lead / owner decision on 6g lever 1 (gate-gradient variance reduction; it changes the loss).
  3. SIM A/B for M 128 vs 1,024 per update at equal updates; it needs producers (LOOP-INT / ASYNC tooling).
  4. Per-step latency: CUDA graphs on fixed 256-row buckets + glue removal (6b), identity-tested.

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
Key `kl_lr_target: x` (finite > 0; absent / null = off; the hash is unchanged when absent).
- When it acts: on policy steps only (a no-op in the critic warm-up), once per step, before the step.
- The rule, v2 (current): lr x clamp(sqrt(t / dKL), 0.5, 1.25), with
  - dKL = this minibatch's KL to the anchor minus the previous minibatch's (the KL the last step added; KL ~ lr^2);
  - t = min(x, max(kl_stop_prev - KL, x / 10)), so a step is never aimed past the cap.
  - Bounds: [lr / 16, 16 lr] of the config lr.
  - The lr lives in opt.param_groups, so it carries across updates and checkpoints. The update record gets `lr_end`.
- v1 (x [0.5, 2] per step, aimed at x only) OVERSHOT on real records (6d): the lr ramped x2 per step, then one step
  landed at 2-5x the cap.
  - 8k rows: stop KL 0.076 / 0.077.
  - 32k: 0.043 / 0.052.
  - 65k: 0.094 / 0.093.
- Use: x ~ kl_stop_prev / 4 (0.005) with large minibatches.
- Known ceiling: dKL comes from two different minibatches, so it is noisy at mb 256, not at 8k+ rows. A negative dKL
  reads as a tiny step (growth x1.25).
- Tests (a): pipeline/tests/test_learner_fast_kllr.py, 5 tests:
  - off / null byte-identical, with and without the value loss;
  - the warm-up leaves the weights and the lr untouched;
  - the lr sequence equals the rule replayed from the measured KLs, for 3 targets, and with a binding cap;
  - the bounds;
  - config validation and hash.
  With test_learner_fast_accum + test_kl_stop_prev: 13 passed on 33920. pyflakes clean.
- Smoke with v2 (ls2_smoke_v2, 33920, absent key): b5e2a2bbafef, e816a6a4 / 3e07cff4, f060b678 / 5c61ac04 = the
  reference. SMOKE PASS.
- The no-grad KL check before the backward is NOT built. By 3b's cost model it pays only at <= 2 steps per update.

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

### 6d. Equal-KL lr sweep at T_gate 0.1, v1 rule (a; 33920; lr_sweep.py; sweep2/sweep_t01.json)
Records: 4 consecutive warmed updates (u5-u8) on 4 disjoint 512-match T 0.1 batches (s2101, s2102, s2105, s2106).
Held-out: 1,024 never-trained matches (s2103 + s2104). ppo_epochs 4 for every arm. dJ is paired vs base on the same
held-out matches.

| arm | steps u5-u8 | stop KL u5-u8 | PPO s per update | lr_end | dJ vs base after u8 (+- se) |
|---|---|---|---|---|---|
| base mb 256, lr 1e-5 | 59 / 15 / 43 / 12 | 0.023 / 0.020 / 0.022 / 0.024 | 16.8 / 4.3 / 11.7 / 3.5 | 1e-5 | 0 (J +0.00016 +- 0.00028) |
| 8k, kl_lr_target 0.005 (v1) | 7 / 2 / 1 / 2 | 0.076 / 0.077 / 0.028 / 0.026 | 65 / 24 / 17 / 24 | 1.1e-4 | -0.0001 +- 0.0007 |
| 32k, v1 | 6 / 3 / 5 / 4 | 0.043 / 0.052 / 0.024 / 0.029 | 169 / 106 / 147 / 139 | 9.5e-5 | +0.00003 +- 0.0004 |
| 65k, v1 | 9 / 2 / 2 / 2 | 0.094 / 0.093 / 0.027 / 0.042 | 314 / 139 / 135 / 140 | 4.1e-5 | +0.00004 +- 0.0008 |

- (a) At T 0.1 the pilot's learner stops after 12-59 steps (3-15k of ~160k rows) and pays 3.5-17 s of PPO per update.
- (a) v1 overshoots the cap 2-5x in the first two updates; fixed in v2 (6a).
- (a) After 4 updates, no arm is resolvably better than base. The mid-run dJ at u6-u7 (+0.0010 +- 0.0007-0.0008 for 8k /
  65k, ~1.3 se) is gone at u8.
- (a) The large arms cost 5-40x the PPO seconds of base per update.
- (b) Per-update policy improvement is below what 1,024 held-out matches resolve, even paired: the paired se (0.0004-0.0008)
  is set by the larger-moving arm's own variance.
- Comparing learner settings therefore needs the SIM A/B (win rate over many updates), not J.
- Consistent with section 1: no policy-gradient signal resolved over 512 matches.

### 6e. Noise scale at T_gate 0.1 on 1,024 matches (a; noise_scale.py; noise/ns_t01_1024.json)
Setup:
- Records: s2101 + s2102, 1,024 matches.
- The critic was warmed 3 updates on s2105 first (explained variance 0.92).
- Sanity: rel diff 8.3e-6, ratio maxdev 2.0e-5.
- The 256-row gradient norm is 17.6, against grad_clip 0.5 (~35x clipped).

| component | tr(Sigma_match) | G^2_U (+- se) | B_match: point [2 sigma lo, hi] | B_row via 256-row mbs |
|---|---:|---:|---|---:|
| gate | 85.7 | 0.040 +- 0.13 | 2,158 [279, inf] | 782k |
| card | 4.6 | 0.0007 +- 0.0024 | 6,554 [835, inf] | 1.38M |
| cell | 3.1 | -0.0002 +- 0.0004 | - [4,714, inf] | - |
| value | 0.069 | 0.0052 +- 0.0010 | 13.2 [9.6, 20.9] (~4.2k rows) | 138 |
| policy | 92.0 | 0.077 +- 0.16 | 1,202 [234, inf] (~380k rows) | 418k |

- (a) The gate head carries 93% of the policy gradient noise at T 0.1. It is 85.7 here vs 22.9 at T 0.3 (1b): its
  log-prob scales with 1 / T_gate.
- (a) Policy critical batch: >= ~230 matches (2 sigma), point estimate ~1,200 matches (~380-420k rows), no upper bound.
  The critic's is ~13 matches.
- (b) Today's update uses 3-15k rows. That is ~1-4% of B_row, so each update's KL-0.02 move is mostly noise. With the
  crude model of section 4, the signal fraction is sqrt(R / (R + B_row)) ~ 0.08-0.19.

### 6f. Steady-state learner time per update (a; lr_sweep base arm, mem_row_cache on, T 0.1; sweep2/cad_m*.json)
| matches per update | steps per update (warmed Adam) | rows used | PPO s | whole update s |
|---:|---|---|---|---|
| 128 (u5-u12) | 54 / 29 / 14 / 36 / 38 / 35 / 13 / 24 | 3.3-13.8k | 2.9-12.6 | 3.3-13.9 (mean 7.0) |
| 512 (u5-u8) | 59 / 15 / 43 / 12 | 3.1-15.1k | 2.8-13.2 | 3.7-14.7 (mean 8.2) |

- (a) Under the cap, one update's learner time is set by the steps until the cap (12-59 x ~0.2 s). It hardly depends on
  matches per update (128 vs 512: 7.0 vs 8.2 s mean).
- (a) mem_row_cache at M 512: 3.7-14.7 s per update, vs 5.3-18.4 s without (6d base). Same steps.

### 6g. Projection for the 8x RTX PRO 6000 (b unless marked; learning per hour vs today)
progress / h = U (updates / h) x I (improvement per update).

Today: the synchronous pilot.
- M 1,024 per update.
- One 4090 producer: 48.9k matches/h (a, LOOP-INT) -> ~75 s per wave.
- Learner ~8-10 s.
- So U_today ~ 3600 / 85 ~ 42 updates/h.

Box inputs:
- Rollouts ~400-580k matches/h (PROJECTION.md, b).
- Rollouts overlapped with the update (LOOP-ASYNC, approved; its A/B is running).
- A PRO 6000 at ~1.7x a 4090 (untested).
- Encoder compile 1.3x (6c; not exact, so not adoptable as is).

| option | U on the box | I vs today | learning / h vs today |
|---|---|---|---|
| A. M 1,024, base learner | wave 6-9 s binds: ~390-560 / h | 1 (same rows used) | ~9-13x |
| B. M 128, base learner | learner binds: 7 s / 1.7 = ~4 s: ~900 / h (~1,200 with compile) | ~1 if M 128 keeps the 3-15k rows' signal (untested: fewer matches, more correlated rows) | ~21-29x |
| C. M 1,024, all 318k rows in ~5-10 large steps (kl_lr_target v2), DDP on 7 GPUs | ~14 s per update: ~250 / h | sqrt(318 / 736) / sqrt(8 / 426) ~ 4.8 by the section 4 model (NOT resolved by the 6d sweep, which neither confirms nor contradicts it) | ~28x |

- HONEST VERDICT: ~10-30x, short of the ~50x rent bar.
  - Option C's I gain is a model estimate that the held-out J could not resolve.
  - Option B's I is untested.
  - The per-row work cannot give the 15-20x the mandate assumed: 6b-6c measured ~1.3x for compile, with ~1.5-2x
    plausible including glue removal.
- What could close the gap (b, ranked):
  1. Gate-gradient variance reduction. The gate is 93% of the policy noise (6e).
     - Options: a Rao-Blackwellised gate term (the expectation over the gate's two outcomes instead of the sampled one,
       where the counterfactual advantage is available), or a gate-specific baseline.
     - Effect: cutting the policy's B_row ~5-10x raises I per update for every option, up to ~2-3x at today's R.
     - It changes the loss: a lead / owner decision.
  2. Per-step latency for options B / C: CUDA graphs on fixed row buckets + glue removal (42% of a step, 6b), ~1.5-2x.
  3. Measure, don't assume: the SIM A/B of M 128 vs 1,024 (option B's I), and LOOP-ASYNC's staleness result.
- No rent case yet on these numbers.

## 7. LEARNER-SCALE3 (10-29 night)

### 7a. gate_baseline: an unbiased gate-row baseline (opt-in; built + measured, NOT adopted: the owner decides)
Key `gate_baseline: {weight: score | plain, ridge: 1e-3, fit_rows: null | int}`. Absent / null = off, and the config hash
is the historical one.
- What it does. Once per policy update (never in the critic warm-up):
  - `gate_baseline_fit` takes the update-start model's trunk output g on the gate-sampled rows (no grad; at most
    fit_rows per match half).
  - It fits a weighted ridge regression of A on [g, 1], one fit per half h = match % 2.
  - W[h] is fitted on the OTHER half's rows, so a row's own A, and its match's, never enters its own baseline.
  - In minibatch_loss, A becomes A - b(s) on gate-sampled rows, with b = [g detached, 1] . W[match % 2]. This goes
    into the joint PPO-clip term (lp_gate + lp_card + lp_cell share one A).
  - The value, posture and ability terms keep A.
  - b depends on the state only, so E[b(s) grad log pi(a | s)] = 0 over the joint action: unbiased.
- Weights.
  - score (default): (d lp_gate / d x)^2, i.e. (1 - p)^2 on played rows and p^2 on waited rows. This is the
    variance-optimal baseline for the gate's own score function, up to the state factor |grad x|^2. With the critic
    already in A (GAE), E[A | s] is ~0, so the plain fit has little to remove (b, untested). The optimal b* =
    (1 - p) A_play + p A_wait is not zero.
  - plain: 1.
- b uses the CURRENT model's g during the epochs. That is still a state-only function, so it stays unbiased. It costs
  no extra forward per minibatch. The fit forward runs once per update.
- Monitors: the update record gets `gate_baseline` {fit_rows per half, oof_r2 (out-of-fold weighted R^2 of A)}.
- Refused with cf_credit rows. Cross-fit caveat (b): A is normalised over the whole batch, so a row's A carries O(1/N)
  of every row. Negligible at N ~ 1e5.
- Tests (a): pipeline/tests/test_learner_fast_gate.py, 4 tests. 33920: 26 passed together with accum, kllr, cache,
  kl_stop_prev and loop_overlap_decoupled.
  - off / null: weights and monitors byte-identical, with and without the value loss. On: it runs, fit_rows is
    respected, and the critic warm-up is untouched.
  - Monte Carlo unbiasedness on the tiny model.
    - Setup: 102 fixed gate-sampled states. Each draw samples a fresh joint action (gate, then card and cell if
      played) from the model's own policy. A = c(s) + 1[played] + 0.5 noise, with c linear in g. The baseline is
      refitted on every draw.
    - Gradient: L_pg at ratio 1, checked on draw 1 against minibatch_loss(gate_bl=) itself (rel < 1e-4).
    - Statistic: paired differences on - off, projected on the mean gradient and 8 random directions.
    - 300 draws: max |z| on = 0.44 (bar < 4.5).
    - Planted in-sample variant (W flipped, so each half sees its own A): max |z| = 18.5 (bar > 6). The test does
      detect a baseline that leaks the row's own A.
    - Variance: tr(Sigma) 3.02 -> 0.61 (x0.20). Expected, because c(s) is linear in g by construction.
    - 100 draws: on 1.85, in-sample 11.3.
    - 3,000 draws, default ridge 1e-3 (logs/gate_mc3000_r.log): on 1.50, in-sample 33.5, variance x0.225. PASS.
    - 3,000 draws at ridge 0 (logs/gate_mc3000.log): z fine (on 1.66, in-sample 36.2), but the variance went UP
      x1.74. Cause (b): rare near-singular score-weighted fits on ~50 rows per half. The test (and the key's default)
      use ridge 1e-3.
- Smokes (a; 33920, tree /dev/shm/cbg, ls3_smoke_off / ls3_smoke_gbl2):
  - Absent: PASS; b5e2a2bbafef, e816a6a4 / 3e07cff4, f060b678 / 5c61ac04 = the reference.
  - On, with critic_warmup_updates=1 (config sha 774e54ed1590): PASS.
    - u0 (warm-up) = the reference shas, as it must be.
    - u1 was a policy update with the key (KL g/c/x 0.0043 / 0.0018 / 0.0030).
  - The update-record log line for the monitors was added after the smokes. It is key-on only; pyflakes clean.
- Restart of the test tree: `git archive origin/main pipeline tools scratchpad/gauntlet/L74/plan1026/pilot/{lrn,ops}`
  into a copy of /workspace/lrn/cb under /dev/shm (NOT /workspace: the disk is full). Then run tests with
  `CB=/dev/shm/cbg PYTHONPATH=/dev/shm/cbg:/workspace/lrn/d2/stage/pylib`.

### 7b. Where the backward's memory-movement kernels come from (glue_probe.py; a; CPU graph walk, 1,024 rows, pilot.yaml)
One pilot minibatch_loss built under autograd anomaly mode, so each backward node carries its forward line. 828 nodes.
Ranked by the zero-filled gradient buffer each node's backward allocates:
- SelectBackward0 x12 inside nn.TransformerEncoder (model_v3.py:139, the trunk): 986M elements per step.
  - These are the packed in_proj q / k / v selects of nn.MultiheadAttention. Each select's backward zero-fills the
    whole [3, L, B, E] buffer and copies one slice into it.
  - The same pattern appears x6 in the memory encoder (model_gen.py:158): 152M.
- IndexBackward0 x3 on the played-row subset (rl_royale.py policy_terms: enc[pi] for cell_of): 27M.
- The ViewBackward / UnsafeView / Squeeze entries at the top are views: no copy.
- Reading:
  - (b) Most of the fill_ / copy_ volume is PyTorch's own MHA training path, not our glue.
  - (b) Removing it means replacing nn.TransformerEncoder (model_v3 / model_gen) with a split-projection attention of the
    same maths.
  - That is a model-code change outside this seat's write set (rl_royale learner hunks), and it moves fp32 rounding:
    it must pass the 1e-7 gradient bar.
- Correction to 6b (c): "~42% of a 1,024-row step" divided PROFILED kernel time by the UNPROFILED wall step.
  - prof_mod.json has gpu_busy_ms_per_step = 473 ms vs a 278 ms wall step (busy_share 1.70): the profiled window also
    held the lazy-anchor fill (Rz.fill inside step()).
  - So the glue is 117 / 473 = ~25% of the kernel time, not 42% of the step.
  - prof_mod.py now has `--prefill`, which fills the anchor for all rows before profiling, so the profiled window is
    the PPO step only. Rerun owed: GPU, after the noise runs.

### 7c. Equal-KL sweep with kl_lr_target v2 (a; 33920; lr_sweep.py; sweep2/sweep_t01_v2.json; log logs/sweep2v2.log)
Same setup as 6d: u5-u8 on s2101 / s2102 / s2105 / s2106, held-out s2103 + s2104 (1,024 matches), ppo_epochs 4,
mem_row_cache on. The first attempt crashed at 01:38 (disk full, my fault, see STATUS). This is the 01:53 restart.
| arm | steps u5-u8 | stop KL u5-u8 | PPO s per update | lr_end u5-u8 | dJ vs base after u8 (+- se) |
|---|---|---|---|---|---|
| base mb 256, lr 1e-5 | 59 / 15 / 43 / 12 | 0.023 / 0.020 / 0.022 / 0.024 | 13.1 / 3.5 / 9.1 / 2.9 | 1e-5 | 0 (J +0.00016 +- 0.00028) |
| 8k, kl_lr_target 0.005 (v2) | 17 / 1 / 2 / 2 | 0.039 / 0.022 / 0.030 / 0.040 | 87 / 9.8 / 14.4 / 14.2 | 1.4e-4 / 1.4e-4 / 7.0e-5 / 3.6e-5 | +0.0007 +- 0.0007 |
| 32k, v2 | 17 / 2 / 1 / 2 | 0.053 / 0.041 / **0.126** / 0.029 | 201 / 57 / 39 / 58 | 1.2e-4 / 1.5e-4 / 1.5e-4 / 7.5e-5 | +0.0032 +- 0.0026 |
- (a) The base arm reproduces 6d's base exactly: same steps and the same stop KLs (deterministic learner).
- (c) "v2 fixes the overshoot" (6a) is contradicted.
  - The applied policy movement still lands at 1.5-2.6x the cap in most updates, and at 6.3x once (32k u7: one step
    of 32k rows at lr 1.5e-4 = KL 0.126).
  - stop KL is the KL of the refused minibatch, so it measures the steps already TAKEN.
- (b) Why:
  - The lr is carried across updates, and each update's first step has no dKL to steer by, so it runs at the
    previous update's end lr.
  - Within an update the KL of coherent steps grows like (k x step)^2, so the next increment is ~(2k + 1) / (2k - 1)
    times the last; the rule sizes the next step from the last increment.
  - Fixes to test (lead): reset the lr to the config value at each update start; or the no-grad KL check before the
    step (6a, not built); or predict the increment as dKL_last x g^2 x (k + 1) / k.
- (a) No large arm is resolvably better than base: 8k +1.1 se, 32k +1.2 se after u8.
  - The large arms also moved 1.5-6x more KL than base, so a positive J is expected and is NOT an equal-KL comparison.
- (a) Cost: the large arms pay 3-15x base's PPO seconds per update.
- Answer to the STATUS question "does any arm reach the cap without overshoot, and with what paired dJ?": no arm does;
  the dJ are within 1.2 se of 0.

### 7d. Noise scale with the gate baseline on (a; noise_scale.py --gate-baseline; the 6e setup; noise3/)
Same records, the same 3-update critic warm-up (deterministic: explained variance 0.92, as in 6e), the same 1,024
matches. W is fitted once on all 321k gate rows (fit_rows null) and held fixed. sanity rel diff vs minibatch_loss(gate_bl=W):
8.1e-6 / 7.9e-6.
| run | fit oof R^2 | fit s | tr(Sigma_match) gate / card / cell / policy | tr(Sigma_row, 256-row mbs) policy | G2_U policy (+- se) | B_match policy: point [2 sigma lo] |
|---|---:|---:|---|---:|---|---|
| off (6e) | - | - | 85.7 / 4.65 / 3.07 / 92.0 | 31,952 | 0.077 +- 0.158 | 1,202 [234] |
| score | 0.040 | 66 | 83.5 / 4.34 / 2.92 / 89.2 | 29,562 | 0.113 +- 0.165 | 792 [202] |
| plain | 0.033 | 70 | 82.9 / 4.44 / 2.94 / 88.8 | 29,603 | 0.104 +- 0.164 | 852 [205] |
- (a) The baseline cuts the policy gradient noise by only 3-3.5% per match and 7.5% per 256-row minibatch.
  - The gate head is still 93-94% of the policy trace.
  - score and plain weights are indistinguishable.
- (a) G2_U (the signal) is unresolved in all three runs: every value is within 0.3 se of the others, as it must be
  for an unbiased baseline. The B_match points move only through that noisy G2_U.
- (b) Why so little: A is a GAE advantage over a critic with explained variance 0.92, so E[A | s] is already ~0. The
  out-of-fold R^2 of A on g is 0.03-0.04. What remains is A's within-state outcome noise, and no state baseline can
  remove that.
- (c) 6g lever 1 as a state baseline ("cut the policy B_row ~5-10x") is contradicted: the measured factor is 1.03-1.08.
- (b) What is left of lever 1:
  - Form (a), the expectation over the gate's two outcomes. It needs Q(s, play) and Q(s, wait), which only the cf /
    R_fork SIM forks provide, and only at fork rows.
  - Fewer, longer-horizon gate decisions. That changes the decision process: an owner / lead topic.
- Cost (a): the fit's forward over all gate rows of 1,024 matches takes 66-70 s on a 4090, against a 3-15 s learner
  update.
  - So even this small gain would need fit_rows (e.g. 16k per half: ~3 s). How fit_rows changes R^2 is untested.
- Not adopted. The owner decides; the numbers above do not make a case for it.

### 7e. How much CUDA graphs + glue removal can give, measured from the kernel timeline (a; prof_mod.py --prefill; prof3/)
prof_mod's busy_share was wrong in 6b / 7b: `prof.events()` with device_type CUDA also returns the user ranges
("forward", "backward", "mod:*"), which the profiler mirrors onto the GPU timeline. So busy double-counted (busy_share
1.5-1.7 > 1). Fixed: kernels only. Also --prefill now fills the lazy anchor (chunked) BEFORE profiling, so the window
holds the PPO step only. 33920 4090, pilot.yaml + mem_row_cache, T 0.1 records s2101 (128 matches).
| mb | wall ms / step (unprofiled median) | GPU kernel ms / step | kernel share of wall | kernels / step | ms / row |
|---:|---:|---:|---:|---:|---:|
| 256 | 128.1 | 63.5 | 0.50 | 3,875 | 0.50 |
| 1,024 | 278.7 | 236.6 | 0.85 | 4,324 | 0.27 |
- (a) At the pilot's minibatch of 256, half the step is GPU idle: launch and CPU overhead across ~3,900 kernels.
- (a) At 1,024 rows the step is 85% kernel time.
- Memory-movement kernels at 1,024 rows: copy_ ~27 ms + fill_ ~26 ms per step, plus clone / index_put_ / zeros. That
  is ~25% of the kernel time, not 6b's 42% (wrong denominator, 7b). 7b traces the bulk to nn.MultiheadAttention's packed
  in_proj selects (trunk + memory encoder).
- Upper bounds (b, from the measured shares; the speed of a real implementation is untested):
  - CUDA graphs remove at most the idle share: <= 2.0x at mb 256, <= 1.18x at mb 1,024.
  - Glue removal: <= 1.3x of the kernel time.
  - Both together: <= ~2.6x per step at mb 256, <= ~1.5x at 1,024.
- Why NOT built this seat (needs a lead decision; NEEDS_CONTEXT):
  - (i) Graph capture needs a static-shape, sync-free minibatch_loss. Today the loss has data-dependent shapes:
    `played.nonzero()` and the played-row cell / lazy-refine forwards, `gs.any()` branches, the boolean-mask KL /
    entropy monitors, `float()` monitor syncs, and gen_rows' CPU-side memory features.
    - Making it static means padding the played subset to fixed buckets with masks and moving the monitors out of
      the step. That is a parallel loss path that must equal minibatch_loss to 1e-7 on gradients.
  - (ii) The glue sits in model code (model_v3 / model_gen nn.TransformerEncoder), outside this seat's write set.
  - Proposed split, two tickets:
    - A: a split-projection attention module with the same maths. Identity bar: the forward to 1e-6, gradients
      <= 1e-7 rel.
    - B: `minibatch_loss_static` for padded buckets (256 rows, played <= 64 / 128 / 256) + torch.cuda.graphs capture
      per bucket, with the same identity bar vs minibatch_loss and a kl_stop equality test.
    - Expected (b): ~1.5-2.5x on the learner step at mb 256.

### 7g. Projection update (replaces the "what could close the gap" list of 6g; b unless marked)
| 6g lever | before | measured now | effect on learning / h |
|---|---|---|---|
| 1. gate variance reduction (state baseline) | B_row / 5-10 hoped | policy noise -3% per match / -7.5% per row (7d, a) | ~1.0x: drop it as a state baseline. Form (a) (both gate outcomes) needs cf-fork Q values: untested, a design topic |
| 2. per-step latency (CUDA graphs + glue) | ~1.5-2x | bounds <= 2.6x at mb 256, <= 1.5x at 1,024 (7e, a: the shares); not built | option B's learner ~4 s -> ~1.6-2.7 s on the box; U then likely wave-bound (~6-9 s per wave, PROJECTION.md, b) unless the rollouts overlap |
| kl_lr_target v2 for option C | assumed to reach the cap cleanly | overshoots 1.5-6.3x (7c, a) | option C's ~14 s update and its I estimate are not usable until the lr rule is fixed |
| 3. SIM A/B M 128 vs 1,024 | not measured | no resolvable difference, M 1,024 - M 128 = +0.6 +- 1.0 pp after 7 updates (7f, a) | option B's I is not shown to be worse; M 128 used 1/8 of the matches |
- Verdict (b): unchanged. ~10-30x, short of the ~50x rent bar.
  - Option B (M 128, learner-bound, with rollouts overlapped) is the only path above ~30x.
  - It needs BOTH the A/B to show I(M 128) ~ I(M 1,024) per update, AND the per-step work (7e tickets A + B).
- No rent case on these numbers.

### 7f. SIM A/B: 128 vs 1,024 matches per update at equal updates (a; 33553; abm/ab_m.sh, ab_tab.py; logs .foreman/scratch/a2/abm/out)
Setup:
- ref_pilot_noiw (the pilot without the hero ability), B0 init, critic warm-up 1, then 7 policy updates (8 updates).
- 2 training seeds (1028, 2029) x M 128 (E 32) / M 1,024 (E 256), G 4.
- Eval = each u0008 checkpoint (and B0) as init, playing 1,024 matches per eval seed (7001, 7002 = common matchups) vs
  the training pool, read from the critic-only u0000 rollouts.
- Caveat (b): in an eval run the pool's "init" opponent is the checkpoint itself, ~1/8 of the matches. It biases every
  arm the same way.
Training: on-policy win rate per update vs the pool (n 128 or 1,024 per update), PPO steps until kl_stop 0.02:
| run | win rate u0 -> u7 | mean u4-u7 | steps per update u1-u7 | wall |
|---|---|---|---|---|
| s1028 M 1,024 | .717 .715 .719 .749 .745 .711 .751 .720 | .732 | 36-111 | 70 min (4 x 128 in flight) |
| s2029 M 1,024 | .721 .736 .750 .725 .730 .719 .715 .729 | .723 | 47-145 | ~2.5 h (rerun at 2 x 64 after a 45 GB memory stop at u6) |
| s1028 M 128 | .719 .750 .781 .656 .742 .789 .797 .711 | .760 | 10-83 | 21 min |
| s2029 M 128 | .773 .742 .836 .727 .727 .695 .828 .750 | .750 | 36-158 | 24 min |
Eval (2,048 matches per checkpoint; binomial se; arm differences are unpaired):
| checkpoint | win rate | vs B0 |
|---|---|---|
| B0 | 0.7231 +- 0.0099 | - |
| s1028 M 128 | 0.7427 +- 0.0097 | +1.95 pp +- 1.38 |
| s2029 M 128 | 0.7246 +- 0.0099 | +0.15 pp +- 1.40 |
| s1028 M 1,024 | 0.7427 +- 0.0097 | +1.95 pp +- 1.38 |
| s2029 M 1,024 | 0.7368 +- 0.0097 | +1.37 pp +- 1.39 |
| pooled M 128 (4,096) | 0.7337 +- 0.0069 | +1.05 pp +- 1.2 |
| pooled M 1,024 (4,096) | 0.7398 +- 0.0069 | +1.66 pp +- 1.2 |
- (a) Over 7 policy updates, neither arm is resolvably better than B0, or than the other.
  - M 1,024 minus M 128 = +0.6 pp +- 1.0.
  - Both point estimates are positive (+1.0 / +1.7 pp).
- (a) Steps until the cap are similar for both arms (10-158 vs 33-145), as 6f found offline.
- (a) At equal updates, M 128 used 1/8 of the matches: 1,024 vs 8,192 per seed. Its updates were ~3x cheaper in wall
  time here (wave-bound: 128 matches ~2.7 min per update vs 1,024 matches ~7.5-9 min per update).
- (b) Reading for option B (7g): no evidence that I(M 128) per update is below I(M 1,024), but the A/B can exclude
  only a large gap. The 2 sigma bound on the difference is ~2 pp over 7 updates. Resolving ~0.5 pp per update would
  need ~10x the eval matches or many more updates.
- Infrastructure findings:
  - (a) The 45 GB bar on 33553 is tight for M 1,024: rss + shmem peaked at 44 GB with 4 x 128 in flight. One run
    crossed it at u6 and was rerun at 2 x 64, 2.5x slower per wave (1,034 s vs 416 s per 1,024 matches).
  - (a) The memory v2 artifacts DIFFER between pods. 33553's tree (via /workspace/loop/cb): counter_priors 178955c2,
    lock_head ca144009. 33920's /workspace/lrn/cb: 4312a8ad / 15065623.
    - The arms' checkpoints refuse to load on 33920 (model_gen.check_memory_meta), so the parallel evals I started on
      33920 were dropped. Only 33553 numbers are used above.
    - The lead should check which pair the pilot uses: runs on different pods may feed different memory features.
- 7g update from 7f: the A/B line now reads "M 128 vs 1,024 per update: no resolvable difference at +-1 pp over 7
  updates (M 1,024 - M 128 = +0.6 +- 1.0 pp)". Option B stays the only path above ~30x. Its I is not shown to be worse.
  Its per-step work is approved (tickets A / B, learner-only).
