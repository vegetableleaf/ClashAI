# LOOP-ASYNC: overlapped rollouts for the fast loop (owner decision 10-28 ~20:30)

Labels: (a) measured, (b) plausible / untested, (c) contradicted.

## STATUS (10-28, LOOP-ASYNC)
- BUILT (laptop): `fastloop.py --overlap 1|0` + `producer.run(..., ver=)`; tests `pipeline/tests/test_loop_overlap.py`
  8/8 OK (laptop icebow/.venv, unittest).
- COMMITTED 5b91944 (fastloop.py + producer.py together, tests, this file).
- Identity lint, overlap ABSENT (a; 33308; old tree /workspace/async/old = the pre-overlap fastloop/producer, new tree
  /workspace/async/cb; ref_pilot_noiw + E 8 G 4, 3 updates, critic warm-up 1, stored_values false (in-process forwards),
  same seed; logs /workspace/loop/logs/async_id_{old,cb}.log):
  - outcomes 32/32 at u0000-u0002;
  - 47 of 51 W16 batch keys identical at every update; only lp_card / lp_cell / lp_gate / lp_old differ;
  - weights_sha identical at u0000 (e7323eda) and u0001 (b606e6f8); u0002 differs (4baf4c74 vs 0aeda3ed) via lp_old.
  - Noise floor (a): the old tree against ITSELF (async_id_old2) shows the same pattern: the same 4 lp keys differ at
    every update, outcomes 32/32, weights equal at u0/u1, and u0002 differs again (a473cf05). VERDICT: overlap-absent
    = the old code up to the existing run-to-run in-process lp float noise.
- A/B v1 DONE (a). Setup: 33308 GPU0; ref_pilot_noiw + E 32 x G 4 = 128 matches / update, 8 updates, critic warm-up 1,
  2 producers x 64, serve.py eager. Tables: .foreman/scratch/a2/async/ab_v1/TABLE.md (Codex). Held-out = the other
  seed's B0 u0 batch (128 matches, ~40k rows); eval_s{1028,2029}.json on the pod.
  | | s1028 m0 | s1028 m1 | s2029 m0 | s2029 m1 |
  |---|---|---|---|---|
  | update period s (median, u>=2) | 161.4 | 135.9 | 160.2 | 139.1 |
  | updates/h, matches/h | 22.3, 2,854 | 26.5, 3,390 | 22.5, 2,876 | 25.9, 3,313 |
  | speedup m1/m0 | | **1.19x** | | **1.15x** |
  | wave s / learner s per update (u>=2) | 127-140 / 12-30 | 122-149 hidden / 4-6 | 135-146 / 14-29 | 124-142 hidden / 4-5 |
  | PPO steps before kl_stop (u2-u7) | 40-100 | **9-16** | 42-90 | **10-12** |
  | first-minibatch max abs(ratio-1) (u2-u7) | ~1e-5 | **0.83-2.5** | ~1e-5 | **0.83-4.1** |
  | clip_frac (u2-u7) | 0.034-0.040 | 0.050-0.083 | 0.029-0.039 | 0.046-0.096 |
  | held-out J at u8 (+- se) | +0.0020 +- 0.0111 | +0.0010 +- 0.0029 | +0.0008 +- 0.0022 | -0.0002 +- 0.0014 |
  | held KL(B0 to theta) cell at u8 | 0.0157 | **0.0064** | 0.0186 | **0.0079** |
  | held KL gate u2..u8 | .010 .040 .074 .083 .101 .150 .200 | .013 .006 .030 .006 .031 .009 .034 | .009 .029 .060 .105 .057 .028 .023 | .010 .009 .012 .010 .019 .013 .029 |
  | prefetch_miss / staleness | 0 / 0 | 0 / 1 (u>=1) | 0 / 0 | 0 / 1 |
  - Mechanics (a): every mode-1 row was trained at staleness exactly 1, and there were 0 prefetch misses. At u1,
    mode 1 has the same outcomes and rows as mode 0 (W1 = W0 in policy after the critic warm-up).
  - Speed (a): mode 1's period is the wave, and the learner time is hidden. At this size, T_roll (~130 s) >> T_learn,
    so the gain is only 1.15-1.19x. The ceiling is 2x at T_roll = T_learn.
  - Per-update progress (owner bar: "not worse"):
    - J cannot tell the arms apart (b): every arm is within ~1 se of 0 at 128 held matches. SCALE.md predicted this
      resolution limit.
    - The steps and the movement are measured (a). Mode 1 stops after ~1/5 of the steps, and after 7 policy updates
      its cell policy is ~0.4x as far from B0 as mode 0's.
    - Its gate KL to B0 SAW-TOOTHS on s1028 (.013 .006 .030 .006 .031 .009 .034): one update moves the gate, the next
      undoes it.
    - So the bar is NOT met (c, for "not worse" on movement per update).
  - Diagnosis (b, consistent with the table): the ratio pi_theta / pi_behaviour starts far from 1 (max abs(r-1) up to
    4 at step 0). For A < 0 rows the clipped objective min(rA, clip(r)A) does not bound r A, so a few stale rows with
    large r drive the gradient. The policy then hits the 0.02 KL-to-update-start cap after ~10 steps, mostly along
    directions that correct the previous update.
  - Proposed fix (NOT built; it changes rl_royale's PPO loss: lead / owner decision; opt-in key, absent = today):
    decoupled PPO (Hilton et al. 2021, "batch size-invariance for policy optimization").
    - Clip on pi_theta / pi_prox with pi_prox = the update-start policy W_u. LazyRef already computes W_u's lps on
      every minibatch row for the KL stop.
    - Multiply by the importance weight pi_prox / pi_behaviour (from the stored lp_old), truncated at c (e.g. 1-2).
    - With overlap absent, pi_prox = pi_behaviour, so the loss is exactly today's.
    - The KL stop is unchanged (it is already to W_u).
    - Then rerun the A/B (same queue, tag v2).
- DECOUPLED PPO BUILT (lead-approved 10-28): rl_royale key `ppo_decoupled: c` (absent / null = today's loss).
  - Loss: pg = -min(pi_prox / pi_behaviour, c) x min(r A, clip(r) A), with r = pi_theta / pi_prox.
  - pi_prox = the KL anchor = the update-start policy. Its taken-action lp (`prox_lp`) is rebuilt from the anchor terms
    LazyRef / ref_terms already compute: no extra forward.
  - pi_behaviour = the stored lp_old. Truncation constant **c = 2.0** (v1 saw step-0 ratios up to ~5).
  - The u0 on-policy assert also checks `is_maxdev` = max abs(pi_prox / pi_behaviour - 1), i.e. stored vs recompute.
  - Monitors (train_log `decoupled`): `is_maxdev_first`, `is_trunc_frac_ep0`. The KL stop is unchanged.
  - Requires kl_ref_refresh_every 1 and no kl_ref_gate / kl_ref_card / kl_ref_gate_max_elixir. The posture / ability
    terms keep their behaviour ratios.
  - Landed on origin inside LEARNER-SCALE2's daaecbf: a sweep of my uncommitted hunks, content = what I tested.
  - Verification (a):
    - `pipeline/tests/test_loop_overlap_decoupled.py` 6/6:
      - absent / null: byte-identical;
      - on-policy rows: today's loss bitwise, weights + monitors, at c 1 and 2;
      - prox_lp == policy_terms bit for bit;
      - stale formula + truncation;
      - micro_batch merge;
      - validation + hash.
    - On 33308: 19/19 with test_loop_overlap + test_learner_fast_accum. On the laptop, accum's
      test_one_minibatch_gradient fails identically with the pre-edit code (pre-existing, not this key).
    - pyflakes clean.
    - Historical hashes unchanged (succ48_x_s101 32192ba00a43, ref_pilot_noiw f692d08823da).
    - rl_royale --smoke on 33308 (`async/smoke_dc.sh`): key absent PASS (b5e2a2bbafef); key on PASS (is_maxdev_first
      3.0e-6 / 3.7e-6).
- A/B v2 DONE (a; 33308 GPU0, 10-29 01:12-03:02). Same setup as v1 + `ppo_decoupled=2.0` on BOTH modes.
  - Results on the laptop: .foreman/scratch/a2/async/ab_v2/ (eval json, logs, throughput, train logs).
  - Summary: `cd /workspace/async && python cb/.../loop/async/ab_summary.py v1 v2`.
  - m0 with the key (on-policy) = v1 m0 without it at u0-u2: same W/L, steps 322 / 29 / 97, KL to 4 decimals. That is
    the live check that the key is today's loss on-policy. From u3 on the runs drift apart through the server-mode lp
    noise (sampled actions); the J spread between v1 m0 and v2 m0 at u8 (+0.0020 vs -0.0062, s1028) shows that
    run-to-run noise.
  | (u2-u7 unless noted) | s1028 m0 | s1028 m1 | s2029 m0 | s2029 m1 | v1 m1 (for reference) |
  |---|---|---|---|---|---|
  | updates/h | 22.62 | 26.03 (**1.15x**) | 22.05 | 25.47 (**1.16x**) | 26.5 / 25.9 |
  | PPO steps | 97 78 45 49 59 93 | 52 78 18 81 23 85 | 52 90 54 57 68 145 | 48 71 35 70 81 101 | 9-16 |
  | mean steps (m1 / m0) | 70.2 | 56.2 (0.80x) | 77.7 | 67.7 (0.87x) | ~0.15x |
  | first max abs(r-1) / clip_frac | 0 / .030-.038 | 0 / .031-.045 | 0 / .034-.044 | 0 / .030-.042 | 0.8-4.1 / .046-.096 |
  | max abs(pi_prox / pi_beh - 1) at step 0; rows truncated at c 2 | 0; 0 | 0.56-6.5; 0.1-0.7% | 0; 0 | 0.67-2.2; 0.2-0.5% | - |
  | held KL cell from B0 at u8 | 0.0285 | 0.0212 (0.74x) | 0.0208 | 0.0290 (1.39x) | 0.4x |
  | held KL gate u2..u8 | .010 .040 .039 .083 .048 .098 .123 | .013 .027 .033 .034 .045 .095 .128 | .009 .029 .059 .103 .125 .091 .062 | .010 .028 .011 .019 .054 .066 .058 | saw-tooth |
  | held J at u8 +- se | -.0062 +- .0087 | -.0016 +- .0088 | -.0025 +- .0029 | -.0034 +- .0022 | |
  - VERDICT v2:
    - (a) The v1 pathologies are gone. Steps per update recovered from ~0.15x to 0.80-0.87x of mode 0, the clip
      fraction is mode 0's, and the gate KL no longer saw-tooths on s1028 (monotone .013 -> .128).
    - (a) After 7 policy updates, the distance moved from B0 is within mode 0's own range: cell 0.74x / 1.39x, gate
      1.04x / 0.94x.
    - (b) J cannot resolve real improvement: all four arms are within ~1 se of each other and of 0, and the
      run-to-run J spread (v1 m0 vs v2 m0) is larger than any arm difference.
    - So "per-update progress not worse" holds to the resolution of these metrics. The real test is the SIM A/B over
      many updates at pilot scale.
    - (a) Speed is unchanged by the key: 1.15-1.16x at this size (T_roll ~130 s >> T_learn 5-30 s, hidden). The
      ceiling is 2x at T_roll = T_learn.
- A/B v1 restart: `cd /workspace/async && setsid nohup bash ab_queue.sh v1 "1028 2029" > ab_v1.out 2>&1 < /dev/null &`
  (finished runs skipped via ab_v1/RUN.done).
- Codex dispatches: LOOP-ASYNC_1 (medium; .foreman/scratch/a2/codex/LOOP-ASYNC_1.md): ran + watched the queue, built
  TABLE.md / table.json. Outcome: BLOCKED on my eval bug (B0's init file lacks the cell_refine.cfg buffer). Fixed:
  ab_eval uses the run's u0000 checkpoint, max diff 0.0 vs the init. I reran the eval myself and checked Table A / B
  against the train logs.
- Nothing of mine is running on 33308.

## What it does
- Absent: today's alternating loop. `FastPool.run` = `collect(submit(update, sd, jobs, ver=update))` (same messages,
  same push version, same results; the only new code is a check that raises when a row's wver differs from the
  version that was sent, which the producer already refuses).
- `--overlap 1`: `Learner.rollout(u)` is production's code with its rng swapped for `match_rng(seed, u)` during the
  call. Right after it returns (the league ratings already updated by u's results), update u+1's matchups are drawn
  (production's `sample_matchups` call, from `match_rng(seed, u+1)`) and its wave is submitted with the CURRENT
  weights = version u. It plays while `one_update(u)` trains. `rollout(u+1)`'s own `actors.run` collects that wave
  when its jobs equal the ones production asks for. Otherwise the wave is drained and dropped, the asked jobs are
  played fresh, and `prefetch_miss` counts it (e.g. a league snapshot taken by update u changes the pool).
- `--overlap 0`: the same matchup stream, synchronous (each wave played with its own update's weights). This is the
  A/B control: it differs from mode 1 only in the staleness.
- Staleness: u0 is on-policy (version 0). From u1 on, every row is exactly 1 version stale. A wave at another version
  cannot be trained on: collect raises on any row whose wver != the version sent, and the producer raises when the
  server's version is not the one asked for. The throughput line carries `behaviour_ver`, `staleness`, `wait_s`,
  `wave_s` and `prefetch_miss`.
- PPO maths: the ratio uses the stored behaviour `lp_old`; GAE and the value clip use the stored `v_old` (stored_values,
  required by mode 1). `kl_stop_prev` measures the KL to `self.ref` = the update-start model, kl_ref_refresh_every 1
  (also required). The KL is estimated on states sampled by the previous version (b: a small bias). The u0 on-policy
  assert still holds (u0 is on-policy). Precision is unchanged (fp32, TF32 off).
- Server: weights are pushed only between waves (no producer is mid-share), so every wave sees one version.
  policy_server's push also flips its copies atomically.
- Deterministic given seeds: the matchups (per (seed, u)), the job seeds (production's rollout_jobs) and the learner
  (deterministic kernels) are deterministic. Not deterministic: the server-mode lp bits (fp32 batch composition, as
  today: lead bar 5e-5).
- Crash recovery: FastPool's restart + share replay also runs inside `collect`, for the wave's own version.
- Not covered:
  - `--resume`: the wave that was in flight is lost and the first rollout after a resume is on-policy.
  - STOP / max_updates: no prefetch.
  - The wave tail: producers idle until the wave's longest match ends. Filling that time needs two weight versions
    served at once (next lever, not built). Wave u+1 only needs W_u, which exists as soon as update u-1 ends, so it
    could start in the slots freed by wave u's finished matches while wave u's tail still plays. Needs: the server
    serving W_{u-1} and W_u at once (it holds 2 copies today but flips one active copy), the producer tagging each
    match with its own version, and the staleness bound unchanged (each row is still exactly 1 version behind its
    learner update). Gain (b): removes the tail term, so the period approaches max(mean wave work, T_learn).
- Ceiling (b): the update period becomes max(T_roll, T_learn) instead of their sum, so overlap alone gives at most 2x.
  Its value grows with a fast learner (LEARNER-SCALE): the period is then the rollout wave alone.

## Restart / commands
- Tests: `icebow/.venv/Scripts/python.exe -m unittest pipeline.tests.test_loop_overlap -v`
- A pod arm: `FAST_ARGS="... --server eager --overlap 1" run.sh fast RUN CPUS k=v ...` (run.sh passes FAST_ARGS through).
