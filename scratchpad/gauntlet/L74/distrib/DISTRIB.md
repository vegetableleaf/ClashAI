# W16 -- distributed rollouts (one RL run, several pods)

Owner 10-21: thousands of PPO updates in < 1 day by renting extra pods while a run is active. Code: `pipeline/remote_actors.py`
(+ a 4-line `shares` argument on `ActorPool.run`, the `remote_actors` / `kl_ref_refresh_every` keys in `pipeline/rl_royale.py`).
Tests: `pipeline/tests/test_w16_distrib.py`. Labels: **(a)** measured, **(b)** plausible but untested, **(c)** contradicted.

## Measured (2026-10-21, pods 13396 + 14009, tn_base_s74.yaml, fin13 runtime, seed 74)

### Rows: identical to a single pod (a)

| Run | Setup | Result |
|---|---|---|
| idD_single vs idD_dist | `RL_DETERMINISTIC=1`, E=16 G=4, league snapshot every update; 8 actors on one pod vs 4 local + 4 remote | **batch_sha and weights_sha identical on all 3 updates**: u0 `4e3ae6ca88fd4ced`, u1 `3f128c2ce333a2e2`, u2 `27b1b193f0c9fe38`. Both league snapshots were shipped on demand (6.0 MB each) |
| idF_single | same as idD_single, rerun on the other pod | same u0 and u1 hashes (reproducible across pods) |
| S1 vs S2 u0 | N = 24 vs N = 48, normal mode | same matches, actions, observations, outcomes and rewards (69,520 rows, W/L 149/107). Only the stored log-prob bits differ (`lp_*`, `ab_lp`): the shared forward's float noise with 10 vs 5 envs per batch |

Two things the identity check needs (both measured):
- **The GPU learner is not deterministic.** With identical u0 batches, the u1 weights differ between runs (`4d191e64` vs `c58e7e11`). So a comparison across updates needs `RL_DETERMINISTIC=1` (the env-only switch: `torch.use_deterministic_algorithms` plus `CUBLAS_WORKSPACE_CONFIG`). It ran without errors and cost no visible learner time.
- The ability head's warm start trains on the GPU, so without that switch `ab_lp` differs from update 0 on.

### Failover (a)

Killing the remote server mid-update 1 (idE, and again idF with a same-pod server):
- logged `[dist] REMOTE ... DROPPED: EOFError` and then `FAILOVER u1 selfplay: re-running ... 32 jobs (4 shares)`;
- the update completed with 64/64 rows, and the next update ran local-only (N 8 -> 4, logged).

**But the rerun rows were not identical.** 8 of the 64 matches changed, all from one share (slot 5 of 8), with the same hash in both trials (`e5b2c2da35660ee6`). The other three re-run shares matched.

Probes ruled out what that actor process had run before:
- history_probe.py v1–v3: the same share gives the same matches after any earlier share of the same or a different update, including a fresh league snapshot;
- v4 (with the trainer's warm start and screens): SAME as well (8/8 matches).

The cause is open (c-type caveat): **after a failover, the update's rows are valid samples of the same policy but not bit-equal to the no-failure run.**

### Speed (a), full E=64 G=4 (256 games), 24 actors per pod, screens off

| Setup | rollout s (u0/u1/u2) | learner s | total s/update | updates/h |
|---|---|---|---|---|
| 1 pod (S1, 14009) | 117 / 140 / 132 | 41 / 43 / 41 | 162 / 188 / 178 = **176** | 20.5 |
| 1 + 1 pods (S2, 13396 + 14009) | 72 / 82 / 95 | 41 / 43 / 41 | 118 / 131 / 142 = **130** | 27.7 |

- Speedup with 1 + 1: **1.35x** (176 -> 130 s).
- Per update per remote: weights 6.0 MB sent in < 0.1 s; rows back 537–577 MB read in 1.5–1.8 s. The network is not the bottleneck.

**Why not 2x.** An actor holds up to `in_flight` = 8 matches at once and steps them in turn, so a rollout lasts as long as its slowest actor's longest match.
- Doubling the actors halves the jobs per actor, but each wave is still bounded by the longest match.
- Single-pod runs at smaller E stand in for more pods (same jobs per actor):

| jobs per actor | stands for | rollout s |
|---|---|---|
| 10.7 | 1 pod (S1) | 130 |
| 5.3 | 1 + 1 (S2, measured) | 83 |
| 3.5 | 1 + 2 = 72 actors (S3e, E=21) | 53 / 56 / 51 |
| 1.3 | ~8 pods = 192 actors (S4e, E=8) | 29 / 28 / 27 |

The 1.3-per-actor run plays only 32 matches, so its "longest match" tail is shorter than for 256. The real floor is a little higher (b).

### Projections (b, from the rows above; plus ~5 s collate/monitor overhead; screens excluded, they also spread over N)

| Setup | s/update | 1,000 updates | 2,000 updates |
|---|---|---|---|
| 1 pod (measured 176) | 176 | 49 h | 98 h |
| 1 + 1 (measured 130) | 130 | 36 h | 72 h |
| 1 + 2 | ~55 + 47 = ~102 | ~28 h | ~57 h |
| 1 + 4 (or one 5xL40 pod, ~120–130 actors) | ~38 + 47 = ~85 | ~24 h | ~47 h |
| unlimited actors | ~30 + 47 = ~77 | ~21 h | ~43 h |

**More actors alone cannot reach "1,000 updates in < 1 day."** The learner step (~42 s + ~5 s overhead) is the floor.

## Design

- **Server, one per extra pod** (`python -m pipeline.remote_actors --port 5601 --workers 24`): a plain `ActorPool` of
  `actor_main` processes -- the exact local actor code. Per update it receives `(kind, update, weights bytes, shares)` and
  returns `(rows, skipped, stats)` exactly as the local pool does. The pool is built at the learner's hello and kept across
  reconnects (same `base` + env = instant).
- **Learner side** (`DistPool`): wraps the local ActorPool; same `run / close / pids / n` interface, so the trainer is
  unchanged except one `if` in `start_actors`.
- **Sharding = ActorPool's own deal over N global slots.** N = local `n_actors` + every remote's workers (endpoint file
  order); slot `a` gets `jobs[a::N]`; slots 0..L-1 are local, then each remote's block. Every share runs as ONE actor
  message (same `run_batch` / `run_selfplay_batch`, same in-flight batch), and per-job seeds are per (entry, g, update)
  (`rollout_jobs`), so the rows equal a single-pod run with `n_actors = N`. The batch is sorted by `row_key` (the old
  ActorPool sort) after merging. **Identity target: a distributed run with L local + W remote actors == a single-pod run
  with `n_actors = L + W`** (not with `n_actors = L`: the in-flight batch composition changes float noise in the shared
  forward, e1_eval.run_batch docstring). Raw match records carry `slot` (the actor's local index) -- metadata only, not in
  the collated batch.
- **What travels.** Weights bytes per update per pod (pickled), the job specs, and back the rows. Self-play opponents that
  the remote lacks or holds with a different sha256 (league snapshots are written on the learner pod during the run) are
  shipped once on demand (`files?` -> `files`, only files the learner offered, repo-relative paths only, written via
  temp + `os.replace` so a hard-linked repo copy is never written through). The learner's `ROYALE*` environment
  (`ROYALE_RUNTIME`, `ROYALE_HEROIW_PRESS` -- which `load_config` sets from `heroiw_press` --, `ROYALE_HEROIW_FORM`, ...) is
  sent in the hello and set on the server before its actors spawn (verifier finding: without it a remote presses the
  Hero IW with the generic rule, the 10-18 mismatch). The server refuses a learner whose `pipeline/**/*.py` hashes differ;
  `actor_main` still checks the RoyaleSim runtime (`require_same`).
- **Transport / security.** `multiprocessing.connection` with the shared-token HMAC handshake. Token: env
  `RL_REMOTE_TOKEN` or the gitignored `icebow/data/remote_actors.token` (>= 16 chars; never logged). The server binds
  127.0.0.1 by default: reach it through an SSH tunnel from the learner pod (`tunnel.sh` -- a per-learner ed25519 key made on
  the learner pod and authorised on the remote; the laptop key never leaves the laptop). After the handshake the channel
  is pickle: anyone with the token can run code on the other end, so keep the token secret and the port on loopback.
- **Config hash.** `remote_actors` never enters `config_sha` (where the games run is infrastructure; a resume on a new pod
  set keeps its hash). N is logged (`[dist] N actor slots: ...`) whenever it changes -- the rows follow N, not the hash.

## Failure behaviour

| Event | What happens |
|---|---|
| remote unreachable at connect / hello refused (code differs) / not ready in 300 s | skipped for this update (its slots do not exist, N smaller, logged), retried every 5 runs |
| remote dies, errors, or gives no answer in `2 x actor_timeout_s + 300` s mid-update | `[dist] REMOTE ... DROPPED` + `[dist] FAILOVER`: its shares re-run on the local actors, one share per actor; the update completes with every row (measured), but one of the four re-run shares came out different from the no-failure run (see Failover above, cause open); retried every 5 runs |
| rows + skipped != jobs after merging | RuntimeError (the update crashes into the trainer's crash save; never a silent partial update) |
| learner dies | servers see EOF, keep their pool, wait for the next learner |
| endpoints file edited mid-run | re-read every `run`: added pods join at the next update, removed ones are closed (N changes, logged) |

Known cost: a server that accepts TCP but hangs in the handshake costs up to 360 s per retry (every 5 runs).

## Launch (exact commands; laptop Git-Bash, worktree with the change committed)

```bash
D=scratchpad/gauntlet/L74/distrib
bash $D/ship.sh 13396 && bash $D/ship.sh 14009            # code -> /workspace/cb_w16 on each pod (+ token), hash printed
ssh -i ~/.ssh/runpod_clashbot -p 14009 root@64.247.206.76 'LOCK=1 WORKERS=24 bash /workspace/cb_w16/'$D'/serve.sh'
bash $D/tunnel.sh 13396 14009 5611                         # on 13396: 127.0.0.1:5611 -> 14009's server
ssh ... -p 13396 ... 'printf "127.0.0.1:5611\n" > /workspace/cb_w16/icebow/data/w16_ep.txt'
# learner (any rl_royale command line) + one key, from /workspace/cb_w16 with the chain's env (ROYALE_RUNTIME=fin13-linux,
# ROYALE_HEROIW_FORM=hero, OMP/MKL_NUM_THREADS=1, PYTHONPATH) and `ulimit -n 65536`:
#   python -m pipeline.rl_royale --config <yaml> --run <run> remote_actors=icebow/data/w16_ep.txt
# the test runs above: bash $D/run_learner.sh NAME N_LOCAL icebow/data/w16_ep.txt [key=value ...]
#   (env RL_BATCH_SHA=1 always: batch/weights/per-match hashes; RL_PROFILE=1 phase timings; RL_DETERMINISTIC=1 identity)
```

Pod data the remote needs: `cb_w16` is a hard-link copy of the pod's `/workspace/cb_stepd` (init, league externals,
exploiter, decks, runtime wheels), so a remote must be a staged step-d pod (pods1020 setup) or get those files copied.
League snapshots written during the run are shipped automatically.

Endpoint file: one `host:port` per line, `#` comments; order = slot order. `serve.sh` with `LOCK=1` takes the pod's
`/workspace/cpu.lock` (waits for running chains, blocks new ones while it serves); stop it by exact PID
(`/workspace/w16/server.pid` is the flock wrapper; its child is the server: `pgrep -P $(cat ...)`).

## Learner step: profile, and how to cut it

### Measured (a)

Profile from `RL_PROFILE=1` (each phase timed after `cuda.synchronize`), S1 and S2 at ~70–74k rows. py-spy could not attach on these pods (no ptrace).

| phase | s |
|---|---|
| to_device | 0.1 |
| ref_terms (frozen-ref forward) | 4.8–5.1 |
| gae_batch + vf_grad_share + head prep | 4.4–4.9 |
| ppo_update | 31–34 (544–582 minibatch steps of 256 rows, **57 ms per step**) |
| **total** | **41–43** |

Matches the production run's 45 s median (tn_base_s76, 130 updates).

**GPU-bound, not CPU or transfer-bound:**
- nvidia-smi (250 ms samples) during the learner window: **71–72% mean utilisation**, more than 50% for 87–90% of samples; peak memory 4.0 of 46 GB.
- During rollouts the GPU sits at 0% (the actors run on CPU).
- Minibatch 1024 (S1b): **193 ms per step**, ppo_update 26–27 s (-16% only). The step time grows almost linearly with rows: about 12 ms fixed + 0.177 ms per row. So the cost is the model's compute per row (the transformer over each row's tokens), not kernel launches or syncs.
- Model: 1.55 M parameters (d 128, 4 layers), 6.0 MB of weights.

### Options (one change at a time; none implemented: each changes the training run)

1. **Overlap rollouts with the learner step** (IMPALA-style; the policy acting is one update stale). While the learner trains on batch u, the actors already play batch u+1 with the weights from before update u.
   - Effect: s/update = max(rollout, learner) + ~5 s instead of their sum. 1 + 2 pods: ~102 -> ~60 s (about 17 h per 1,000 updates). 1 + 4: ~85 -> ~52 s (about 14 h per 1,000).
   - Trade-off: each batch is one update off-policy. PPO's ratio is already pi_new / pi_behaviour, so the importance correction is built in. The clip and the KL leash then bound two updates of drift instead of one. With lr 1e-5 and KL around 0.005 per update the lag is small (b), but the on-policy checks (the first-minibatch ratio around 1) no longer hold after update 0.
   - Code cost: medium-high.
     - The matchups for u+1 must be drawn from `self.rng` before the minibatch permutation of u, so the RNG order differs from the synchronous trainer (a separate run, not a resume of one).
     - League snapshots and PFSP ratings lag one update.
     - Screens must not overlap (they use the same actors).
     - A crash loses the in-flight rollout (resume replays it).
   - Not "simple and safe", so not built. This is the biggest remaining lever and would be its own experiment.
2. **Multi-GPU data parallel (DDP) learner.** The step is compute-bound by rows, so splitting each 256-row minibatch over K GPUs helps.
   - From the linear fit: K=4 gives ~6 s (rows) + ~7 s (fixed) + ~1–2 s (gradient all-reduce of 6 MB over PCIe; the L40 has no NVLink) = ~15 s for ppo_update. The no-grad ref/GAE passes split too (10 -> ~3 s). So the learner goes ~42 -> ~18–20 s (b).
   - Code cost: high.
     - One process per GPU.
     - The same permutation on every rank.
     - The heads with their own optimisers (critic context, posture, ability, branch) each need wrapping.
     - All loss normalisations must be global (`n_total` already is).
     - Rank-0 checkpoints and logging.
     - Estimate 1–2 days plus verification on a 4.6k-line trainer. Not simple or safe for tonight; not built.
   - Only worth it together with option 1: without overlap, ~5 pods + DDP gives ~38 + 25 = ~63 s per update.
3. **Cheaper per-row compute** (each an opt-in experiment, behaviour-changing):
   - bf16 autocast in the learner: probably 1.5–2x on the transformer on an L40 (b);
   - `ppo_epochs` 2 -> 1: ppo_update halves;
   - a bigger minibatch: only -16% time measured, and fewer gradient steps.

### Owner question: one N x L40 pod or N separate 1 x L40 pods?

- **Rollouts.** What matters is the CPU count. Our 1xL40 pods have a 27.2–30.6 vCPU cgroup quota and a 286 GB memory limit (`/sys/fs/cgroup/cpu.max`, `memory.max`); the host shows 256 cores.
  - A 5xL40 pod most likely gets about 5x that in one box (b). RunPod's pricing pages do not list multi-GPU vCPU counts and conflict even for 1 x L40, so check `cpu.max` on the pod.
  - That would be ~120–130 local actors and the 1 + 4 row above (~85 s per update) with **zero networking, no tunnels and no failover cases**.
  - Measured per-actor cost: ~740 MB RSS (in_flight 8), so 130 actors is ~96 GB.
  - File descriptors: the learner holds ~9 per actor (80 at 8 actors), so 130 actors pass the 1,024 soft limit. `run_learner.sh` / `serve.sh` now set `ulimit -n 65536` (the hard limit is 524,288).
  - Not measured above 48 actors in one learner (b): the spawn start-up and the learner's single result queue should be checked at 130.
- **GPUs.** One learner uses one GPU, so in both shapes 4 of 5 GPUs sit idle until DDP (option 2) exists. Remote actor servers do not need a GPU at all (`actor_device: cpu`).
- **Recommendation:**
  1. Tonight: one big pod if RunPod gives it ~5x the vCPUs (simplest, no networking). Otherwise the learner pod plus remote actor servers on extra pods (this code, measured).
  2. Cheaper and equivalent for rollouts: CPU-only pods for the remote servers, if RunPod has them with enough cores (b; they need the fin13 runtime + venv setup).
  3. Next, for "thousands of updates < 1 day": overlap (option 1) first, then DDP or bf16. Expected about 11–14 h per 1,000 updates with 1 + 4 pods (b).

## Moving KL anchor (`kl_ref_refresh_every: N`, owner-approved long-run knob)

Absent / null = the frozen init (hash unchanged, test). On: after every N-th completed update (never after a crashed one)
`self.ref` becomes a frozen copy of the current policy, so the KL leash (and `kl_cell_stop` / `kl_gate_stop`) bound the
drift per window, not the total drift from the init. Saved in checkpoints as `rl["kl_ref"]`, restored on resume (laptop
smoke with `kl_ref_refresh_every=1`: SMOKE PASS, the saved `kl_ref` equals the saved model at u2). `kl_ref_gate` /
`kl_ref_card` anchors are separate nets and do not move. The **entropy floor stays the INIT's** (one extra no-grad
`ref_terms` pass with the init net once the anchor has moved) -- otherwise the 0.5 floor would ratchet down 2x per refresh
(verifier finding). The init-screen rebuild on resume also uses the init. Trade-off (b): a moving anchor lets the policy
walk arbitrarily far from the imitation prior over 1,000+ updates; the plays/min and screen guards are the remaining
brakes.
