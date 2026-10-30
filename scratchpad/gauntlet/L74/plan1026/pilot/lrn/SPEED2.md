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
CAVEAT: 33903's 4090 is shared with another job at 39-72% utilisation during these runs, so GPU-side times are inflated;
the CPU-side numbers (thread CPU seconds) are not.

| config (K x producers), mode | rows/s per server | round ms | fwd wait ms | cell wait ms (9 calls) | server CPU / wall | fwd thread CPU per batch | batches/s |
|---|---:|---:|---:|---:|---:|---:|---:|
| 16x21 eager (= box 128 x 16) | 1,222 | 550 | 307 | 189 | 0.99 | 29 ms | 20 |
| 16x21 graphs | 3,076 | 218 | 63 | 120 | 0.96 | 5 ms | 68 |
| 64x5 eager (= box 32 x 64; overlapped with another of my runs: recheck owed) | 1,955 | 327 | 200 | 90 | 0.92 | 20 ms | 31 |

Box check (a vs a): the box at 128 x 16 made 49.9k matches/h x ~700 rows/match / 6 servers = ~1.6k rows/s per server;
the bench gives 1.2k at the same shape. Same order, same split (forward wait dominates).

Reading (a unless marked):
- The server process is GIL-bound: its threads' CPU sums to 0.92-0.99 of one core over the window, while the GPU is
  mostly idle. The forward thread spends ~29 ms of CPU per eager forward (Python dispatch of a few thousand kernels),
  whatever the rows (mean batch 37-160 rows).
- Every server cycle runs one forward per model with rows queued: 9 models -> 9 small forwards (opponent batches of
  ~40 rows), then 9 cell calls. A producer's round waits for its model blocks to come round in that queue, so
  forward_wait ~= one server cycle (~300 ms at 16x21 eager).
- So forward_wait is NOT GPU time and NOT request round-trip latency; it is the server's single Python thread doing
  9 x 29 ms of kernel dispatch per cycle, plus 9 cell calls (eager, ~7 ms CPU each) competing for the same GIL.
- CUDA graphs (serve.py --mode graphs, already built and lp-checked in LOOP-SRV: max lp_cell 7.6e-6, identical
  actions) cut the forward CPU 29 -> 5 ms per batch: 2.5x rows/s per server, forward wait 307 -> 63 ms. After that the
  cell calls are the bottleneck (cell thread 48% of the server's core; 120 ms cell wait per round = 9 sequential round
  trips, one per model group).
- (b) The box ran serve.py eager (pilot_box1 launch, c134375). Graphs alone should give ~2-2.5x on the box at 128 x 16.

### 1b. Fix candidates (measured where marked)
- F1 graphs mode: a flag (`--server graphs`), no code. (a) 2.5x at 16x21.
- F2 more server processes per GPU (the GIL limit is per process): running (two_srv.sh). Needs the GPU NOT in
  exclusive-process compute mode (33903 is not: four processes share its GPU; the box: unknown, check
  `nvidia-smi -q | grep "Compute Mode"`).
- F3 one cell request per producer round instead of one per model group (round trips 9 -> 1): code (producer decide in
  two phases + a multi-block cell message); not built.
