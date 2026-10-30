# SPEED2: faster, cheaper pilot training (rollout server wait, producer memory, multi-GPU learner, learner per-row)

Labels: (a) measured (number + source), (b) plausible, untested, (c) contradicted.
Input numbers from the lead (a, the 6x RTX PRO 6000 box, pilot_box1, 2,048 matches / update): 16 x 128 = 16.4k
matches/h, 32 x 64 = 27.4k/h, 128 x 16 = 49.9k/h (CPU ~45 of 163, GPUs 16-39%); per producer forward_wait 114 s of a
141 s rollout, decide_py 19 s, java 7 s; learner ~380 s / update in the critic warm-up (u0-u4) on one GPU; 64
producers OOM on 33308 (125 GB cgroup).

## STATUS (keep current; SPEED-DECIDE, 10-30)
- Seat: SPEED-DECIDE (account 2 lead's ticket). Pod 33903 only (CPUs 218-225, its shared 4090; tree /workspace/speed2/cb =
  hard-link copy of /workspace/opp/cb + git HEAD de0f05e pipeline/ + pilot/loop + obsid + facade; env /workspace/speed2/env.sh).
  33308 and the box are NOT touched.
- Step 1 (forward_wait): mechanism MEASURED (section 1). Fix candidates measured: graphs mode, bigger blocks; two server
  processes per GPU running.
- Step 2 (producer memory): probe written (speed2/mem_probe.py); needs a pilot actor message (speed2/dump.sh) -- next.
- Step 3 (multi-GPU learner): not started.
- Step 4 (learner per-row): not started.
- Restart: `ssh -p 33903 ...; cd /workspace/speed2/cb && . ../env.sh && taskset -c $CPUS $PY -u ../srvshape.py --out
  ../out/X.json --configs 16x21 --mode eager|graphs --seconds 20` (copy speed2/srvshape.py to /workspace/speed2/ first;
  the row fixture scratchpad/gauntlet/L74/speed/results/live_batch1.pt is untracked: scp it from the laptop).
- Codex dispatches: none.

## 1. Why producers wait on serve.py (forward_wait)

### 1a. The mechanism, reproduced at the box's per-server shape (a; speed2/srvshape.py; 33903 4090)
srvshape.py = one PolicyServer (serve.py's class and threads) + P spawned producer processes. Each round a producer
sends one block per model, runs the production P1 decide on each block (its cell calls go to the server), then sleeps
20 ms for the JVM step. The models are the pilot pool: learner B0 + init (B0) + 5 externals + E4 + w14opp_I = 9 server
models (G u0160 is a timing head: the producers forward it themselves, so it is not on the server). The box at 128 x 16
has ~21 producers per server (128 / 6), each round ~16 learner rows and ~2 rows per opponent: config "16x21".
GPU state: "clean" rows = 33903's 4090 idle before the run (nvidia-smi 0 %, 4 MiB; res/gpu_before.txt); "shared" rows = another
agent's job on the same GPU at 39-72 % utilisation (GPU-side times inflated; CPU-side thread seconds are not).
Files: speed2/res/one_eager.json, one_graphs.json (clean), t0_shared_eager.json, t1_shared_graphs.json (shared);
rows by `python speed2/tab.py FILE...`.

| config (K x producers), mode, GPU | rows/s per server | round ms | fwd wait ms | cell wait ms (9 calls) | rest of decide ms | server CPU / wall | fwd CPU per batch ms | cell CPU per call ms | batches/s | mean batch learner / opp |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| 16x21 eager, clean (= box 128 x 16) | 1,876 | 358 | 202 | 120 | 17 | 0.95 | 19.9 | 3.9 | 30 | 164 / 37 |
| 64x5 eager, clean (= box 32 x 64) | 2,025 | 316 | 193 | 89 | 15 | 0.92 | 19.3 | 4.3 | 32 | 161 / 40 |
| 128x3 eager, clean (~ box 16 x 128) | 2,506 | 307 | 186 | 80 | 21 | 0.93 | 18.5 | 5.1 | 33 | 192 / 48 |
| 16x21 graphs, clean | 3,088 | 217 | 62 | 122 | 13 | 1.01 | 4.8 | 3.3 | 77 | 132 / 18 |
| 16x21 eager, shared | 1,222 | 550 | 307 | 189 | 33 | 0.99 | 29.2 | 7.1 | 20 | 160 / 37 |
| 16x21 graphs, shared | 3,076 | 218 | 63 | 120 | 15 | 0.96 | 5.0 | 3.3 | 68 | 146 / 20 |
| 64x5 graphs, shared | 4,082 | 157 | 50 | 72 | 15 | 0.96 | 5.1 | 3.9 | 72 | 160 / 25 |

(64x5 / 128x3 graphs on the clean GPU: OOM -- another agent's rl_royale smoke took 9 GB of the 24 GB mid-sweep, and
srvshape keeps each config's graph pools; a 96 GB PRO 6000 does not have this limit.)

Box check (a vs a): the box at 128 x 16 made 49.9k matches/h x ~700 rows/match / 6 servers = ~1.6k rows/s per server;
the bench gives 1.9k (clean) at the same shape, with the same split (forward wait > half the round).

Reading (a unless marked):
- The server process is GIL-bound: its threads' CPU sums to 0.92-0.99 of one core over the window, while the GPU is
  mostly idle. The forward thread spends ~29 ms of CPU per eager forward (Python dispatch of a few thousand kernels),
  whatever the rows (mean batch 37-190 rows): ~19-20 ms on the clean GPU, 29 ms shared.
- Every server cycle runs one forward per model with rows queued: 9 models -> 9 small forwards (opponent batches of
  ~40 rows), then 9 cell calls. A producer's round waits for its model blocks to come round in that queue, so
  forward_wait ~= one server cycle (~200 ms at 16x21 eager, clean).
- So forward_wait is NOT GPU time and NOT request round-trip latency; it is the server's single Python thread doing
  9 x ~20 ms of kernel dispatch per cycle, plus 9 cell calls (~4 ms CPU each) competing for the same GIL.
- CUDA graphs (serve.py --mode graphs, already built and lp-checked in LOOP-SRV: max lp_cell 7.6e-6, identical
  actions) cut the forward CPU ~20 -> 5 ms per batch: 1.65x rows/s per server on the clean GPU (2.5x shared), forward
  wait 202 -> 62 ms. After that the
  cell calls are the bottleneck (cell thread 48% of the server's core; 120 ms cell wait per round = 9 sequential round
  trips, one per model group).
- (b) The box ran serve.py eager (pilot_box1 launch, c134375). Graphs alone should give ~1.6-2.5x on the box at 128 x 16.

### 1b. Fix candidates (measured where marked)
- F1 graphs mode: a flag (`--server graphs`), no code. (a) 1.65x at 16x21 (clean), 2.5x (shared GPU).
- F0 fewer, bigger blocks per producer (more matches per producer): (a) eager 1,876 -> 2,025 -> 2,506 rows/s per
  server at 16x21 -> 64x5 -> 128x3; small, because the per-batch CPU cost is per MODEL batch, and there are 9 models
  per cycle whatever the producer count. On the box it went the other way (16 x 128 = 16.4k/h < 128 x 16 = 49.9k/h)
  because fewer producers also means fewer JVM threads stepping: the server is not the only limit there.
- F2 more server processes per GPU, each serving ALL models: (c) contradicted as a big lever. Zero code (fastloop
  starts one serve.py per `--devices` entry and maps producer k to entry k % len, so `cuda:0,cuda:0,...` = 2 per GPU),
  but measured (a; speed2/sweep2.sh, max_batch 512, 33903 GPU otherwise idle except a 0.5 GB process; res/s2/):

  | servers x (K x producers), eager | rows/s total (per server) | round ms | fwd wait ms | cell wait ms | server CPU / wall |
  |---|---|---|---|---|---|
  | 1 x 16x22 | 1,751 | 402 | 236 | 128 | 1.09 |
  | 2 x 16x11 | 2,127 (1,079 + 1,048) = 1.21x | 326 / 336 | 195 / 199 | 97 / 102 | 0.91 / 0.96 |
  | 3 x 16x7 | 1,994 (675 + 657 + 662) = 1.14x | 332-341 | 200-217 | 90-102 | 0.94-1.16 |

  Why: each server still runs ~32 forward batches/s at ~19 ms CPU each = one full core, and a server cycle is 9 model
  forwards + 9 cell calls whatever the rows. A producer's round = one cycle, so splitting the producers over more
  servers halves each server's rows per cycle without shortening the cycle. Rows/s scale with ROWS PER CYCLE (rows in
  flight per server) and with 1 / cycle time, not with server count. (Caveat: all 8 of my CPUs carried 22 producers +
  3 servers; on the box CPU is plentiful, but the cycle argument does not depend on that.)
- F2' (b) model-sharded servers: server j serves only a subset of the 9 models (e.g. learner | 4 opponents | 4
  opponents), a producer sends its blocks to all of them at once; the 9 forwards then run in parallel processes and the
  cycle shrinks ~k-fold. Code: producer with one Client per server + a model -> server map, serve.py --models subset.
  Not built.
- F4 (b) more rows in flight per server: the box spreads 2,048 matches over 6 servers (~680 rows per server cycle);
  LOOP-SRV reached 95% of a 4090's rate only at ~12k rows in flight. Fewer inference GPUs at the same rows/s is the
  cheap direction (one server with all 128 producers: ~6x rows per cycle for a ~1.3x longer cycle, b).
- F5 the server's GIL switch interval (sys.setswitchinterval 5 ms default -> 0.5 / 0.2 ms; a thread-scheduling knob, no
  math change): (c) no effect (a; speed2/sweep3.sh, res/s3/; 16x21, max_batch 512): eager 1,633 / 1,670 / 1,730 rows/s,
  graphs 2,985 / 2,979 / 2,912 (another agent's rl_royale held 9.7-13 GB of the GPU during these runs).
- With graphs on, the CELL calls are the largest part of a producer's round (a): 129 of 225 ms (graphs_sw5), 9
  sequential round trips per round (one per model group: _fast_group / loop_opp.decide call cell_fn synchronously),
  each ~14 ms of queueing behind the server's other threads; the cell work itself is ~3.5 ms CPU per call.
- F3 (b, the next lever after graphs) one cell request per producer round instead of one per model group (round trips
  9 -> 1): expected cell wait ~129 -> ~35-40 ms (one trip + the server's 9 cell_logits of ~3.5 ms), round ~225 -> ~130
  ms, ~1.7x on top of graphs. Code: a multi-block cell message in policy_server ("cells": [(bid, ids, slots)...]) and
  the producer's group decides run so that every group's cell request is collected before one send (production's
  loop_opp.decide calls cell_fn synchronously, so either one thread per group with a collector barrier, or a two-phase
  split of _fast_group plus threads for the styled groups only); identity = compare.py --server (16/16 identical,
  lp bar 5e-5). Not built in this ticket.

## 3. Multi-GPU learner (design; NOT prototyped -- see the verdict)
Where the learner's time goes in the pilot (a unless marked):
- Steady state (after the critic warm-up): 3-15 s per update, set by the ~12-59 steps until kl_stop_prev fires, almost
  independent of matches per update (SCALE.md 6f: 7.0 s mean at M 128, 8.2 s at M 512). Against a ~141 s rollout at
  2,048 matches on the box, that is <= ~10% of an update.
- Critic warm-up (u0-u4): ~380 s per update on the box (lead's number). (b, arithmetic) It is every row x 2 epochs:
  2,048 matches x ~330 train rows = ~675k rows -> ~2,640 minibatches of 256 x 2 epochs = ~5,280 steps x ~72 ms. The
  KL stop never fires (the policy is frozen), so every step runs. 5 such updates = ~32 min per run.
- One 256-row step is launch-bound, not FLOP-bound (SCALE.md 2: 5,200-5,700 kernels per step, 3-4% of the 4090's
  fp32 peak; 64 rows take 102 ms vs 170 ms for 256).

Design (b): DDP as `micro_batch` across GPUs. `accum_backward` already computes one minibatch's loss in micro-batches
with the right share of every mean (kl_w) and merges the monitors; a DDP mode = the same split with micro-batch j on
rank j (one process per GPU, identical B / rng / perm on every rank), grads all-reduced (SUM) instead of accumulated
locally, the merged monitors all-gathered so every rank takes the same kl_stop decision. Exactness = micro_batch's
(fp32 summation order only), and absent key = today's code path. NCCL all-reduce of the 2.0M-param gradient: 0.85 ms
p50, deterministic; two learners on two 4090s at once: 0.98-1.01x of one alone (SCALE.md 5, ddp/DDP_PROBE.md, a).

Verdict (b, from the measured step times): at the pilot's minibatch 256, k GPUs give each rank 256/k rows, and a step
at 64 rows costs 60% of a step at 256 (102 vs 170 ms): 4 GPUs -> ~1.7x per step, 6 -> ~1.8x. That saves ~2-6 s of a
steady-state update (<5% of an update) and ~2.5 min of each warm-up update. DDP pays off only with much larger
minibatches (compute-bound: 2,048 rows = 810 ms on one 4090), and the large-minibatch arms showed no learning gain per
update (SCALE.md 5 / 6d / 7f: unresolved or base better). So not prototyped: I have no multi-GPU pod in this ticket
(33903 has one 4090; 33308 and the box are off limits), so exactness on >= 2 GPUs could not be tested, and the
measured numbers say the rollout, not the learner, bounds the pilot. The warm-up is better cut by section 4.

## 4. Exact per-row learner speedups not enabled in pilot.yaml
- mem_row_cache (built, opt-in, OFF in pilot.yaml): (a, SCALE.md 5 accum_gate) weights bit-identical to the key off,
  same 145 steps, PPO 41.2 -> 31.4 s (-24%) on a 512-match update; (a, 6f) steady state 3.7-14.7 s vs 5.3-18.4 s.
  Cost (b, arithmetic): the cache holds every touched row's MEM_KEYS on the CPU: E_MAX 128 x F 46 float32 + mask /
  card / form + summary = ~26 KB per row -> ~17.6 GB of learner RAM in a 2,048-match warm-up update (every row is
  touched), ~2 GB in a steady-state update (~12% of rows used). That RAM competes with the producers (section 2).
  Recommendation: ON for the box (RAM permitting) -- an exact -24% on every learner step, most of it in the warm-up.
- Critic warm-up trunk cache (NOT built; b): in u0-u4 only value_head trains and the policy / trunk / anchor / init are
  all frozen, so per update each row needs ONE trunk forward instead of ~3.1 (2 epochs of policy_terms + R.fill's
  anchor forward + 1/8 ent_ref), and every one of the ~5,280 steps reduces to value_head(g[idx]) plus monitors from
  cached per-row terms. Expected ~3x on a warm-up update (~380 -> ~130 s; ~20 min per run). Exactness premise MEASURED (a;
  speed2/rowinv.py, res/rowinv.json; B0, 33903 4090, fp32, TF32 off, deterministic algorithms): at a FIXED batch
  shape a row's g, gate logit and value are bitwise independent of its batch companions and of its position (128 / 128
  rows bit-equal between two different 256-row batches); at another shape (128 or 192 rows vs 256) they differ by
  1-3e-6 (fp32 kernel choice). So a cache computed at the minibatch shape (256, plus each epoch's tail minibatch at its
  own size) can be BIT-IDENTICAL to today's warm-up, not just within micro_batch's bar. (The card logits compare as NaN
  because of the -inf masked slots; not a difference.)
