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
  - This is the pattern LOOP_INT.md records for the in-process lp float noise. Old-vs-old noise floor: OWED (a repeat
    of the old tree; GPU0 on hold for LEARNER-SCALE).
- A/B (modes 0 / 1 x seeds 1028, 2029; `async/ab_queue.sh v1`, eval `async/ab_eval.py`): queued, not started (GPU0 hold).
- Codex dispatches: LOOP-ASYNC_1 (written, .foreman/scratch/a2/codex/LOOP-ASYNC_1.md: run + watch the A/B queue,
  tables). Not dispatched yet.

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
