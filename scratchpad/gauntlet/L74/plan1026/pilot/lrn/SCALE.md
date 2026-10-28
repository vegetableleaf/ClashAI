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
