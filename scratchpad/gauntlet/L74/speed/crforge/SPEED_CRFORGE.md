# S3 speed on crforge: engine cost, observation cost, full-loop prototype (plan1026 Pillar 4b)

Labels: **(a) measured** (with n), **(b) plausible but untested**, **(c) contradicted**.
Pod 32657: AMD EPYC 7702, cgroup quota **54 vCPU**, 125 GB container memory, Ubuntu 24.04, OpenJDK 17.0.20.1. Its GPU
and about 2.5 cores belonged to ticket S2 the whole time, so every run here used **48 Java threads at most, CPU only**.
crforge `ad8ef3a532ada8dea732bf1ecdeb01beef0fb4b0` and tables 16.402.22, copied from pod 33920 (tree sha256
`349b4ea9...0df45f`, cache `38fbddd8...a9cbcd9`, identical on both pods). Workload everywhere: the **223 real Ranked deck
pairs** (icebow vs the opponents we met, `census_decks.tsv`, evo / hero slots as played), level 16, a decision every
10 ticks for both seats, a random legal play with probability 0.3 per decision. That gives **28.9 plays per side,
3,530 ticks and 353 decisions per seat per match** (a, every run below).

## Summary

1. **The engine is cheap once the JVM is warm (a).** One long-lived JVM thread costs **0.088-0.093 core-s per match**
   (3 runs, 400 matches each), about 43k matches/h per thread. The pilot's 0.87 core-s (PILOT.md) was mostly start-up:
   the JIT compilers alone burn about **36 core-s in a fresh JVM's first minute** (C2 33, C1 3; a, per-thread CPU sampled every
   10 s). So "crforge ~0.65 core-s per match" (PLAN.md 4b) is **(c) contradicted** for a long-lived actor.
2. **48 threads: 12 JVMs x 4 threads is best (a): 1.51-1.57 M matches/h, 0.105-0.110 core-s per match** (2 runs,
   12,000 matches each). One JVM with 48 threads does only 0.64 M/h (0.80 M with ParallelGC). Engine only, a 54-vCPU pod
   would do about **1.6-1.7 M/h** (b, linear from 48 to 52 threads).
3. **crforge's VectorEnv as shipped costs about 2x more per match (a):** 0.157 core-s per match on 1 thread, and 242k/h on 48 threads
   in one JVM (0.403 core-s per match). Its fog, health-bar tracking, elixir counting and 7,024-int observation plus
   2,307 masks for both seats are the difference. We do not need its observation: our policy reads its own.
4. **Our observation in Java is about 30-90x cheaper than in Python (a, n = 38,400 seat-rows).** Per seat-row (one
   side's decision): Python via JPype field reads **298 us**; Java dump + Python `from_engine` / `to_tokens` **191 us**
   (245 us at CLXIII's feature_version 6); **Java builder 3.3-6.9 us** inside the batch step. The Java builder's
   tok / mask / sc / unit_form equal `obs_contract.from_engine` + `to_tokens` + `to_unit_forms` on **38,400 / 38,400**
   seat-rows.
5. **Full loop, CPU side (a): 720-764k matches/h on 48 threads** (Java engine + our main tensors + legality bits for
   both seats, served by a Python thread, 2 cohorts x 2,048 matches, 0.188-0.204 core-s per match, 150k policy rows/s).
   8,192 matches in flight fit in **20.5 GB** peak RSS (S1 on RoyaleSim needed about 15 MB per match, and 4,096 did not
   fit in 62 GB).
6. **The GPU decides what a pod reaches (b, from SPEED.md's measured rows/s).** A match needs 706 policy rows. One 4090
   serves **49k matches/h** with CLXIII as today, **96k** with lazy refine, **227k** with lazy refine + bf16, and **22k**
   (fp32) to **104k** (b) for a 10 M model. So:

   | per pod | 300k matches/h | 1 M matches/h |
   |---|---|---|
   | 54 vCPU + 1x 4090 | **no** (best 227k: GPU-bound; the CPU side does 720-764k measured, about 630k projected) | **no** |
   | 128 vCPU + 2x 4090 | **yes, only with CLXIII lazy refine + bf16** (454k) | **no** (best 454k) |
   | 10 M model, either pod | **no** (104k / 209k at best, b) | **no** |

   300k on one 4090 needs **at most 534 rows per match** (for example an opponent deciding every 20 ticks: about 530)
   or 32% more GPU rows/s than the best measured. 1 M on 2 GPUs needs **at most 320 rows per match**, or 2.2x the
   best measured rate on each 4090. The CPU side reaches 300k on both pods and 1 M only on the 128-vCPU pod (b, with the rest
   of the observation ported, section c3).

## a. Step 1: steady-state engine cost

### a1. One long-lived JVM, one thread (a)
`CfSpeed core` (`CfSpeed.java`): `Standard1v1Battle` + `PlayerCommands.playCard`, as `LadderEnv.reset` / `apply` do it,
without LadderEnv's observation. CPU = `/proc/self/stat` of the whole JVM (GC and JIT threads included) over a window
that starts after a warm-up.

| run | warm-up | matches | core-s per match | of it: env thread / JIT | matches/h per thread |
|---|---|---:|---:|---|---:|
| `t1x1` | 30 matches | 80 | 0.246 | - | 30,122 |
| `t1x1b` | 100 matches | 100 | 0.175 | 0.084 / - | 41,187 |
| `t1x1w` | 50 s | 400 | **0.093** | 0.078 / 0.011 | 43,898 |
| `g_1x1` | 60 s | 400 | **0.089** | - | 42,103 |
| `o_1x1` | 60 s | 400 | **0.088** | 0.081 / - | 43,085 |

The JIT (C2 compiler thread) in one fresh JVM, sampled every 10 s (`thr_long`): 9, 19, 27, 29, 31, 33, 33, 34 ... 37
core-s at 10 ... 130 s. The env thread ran at 1.0 core throughout. **A JVM must live for minutes** (b: an actor that
starts a JVM per match pays about 30 core-s each time). The tables load in 0.33-0.39 s per JVM (a).

At 0.081 s of env-thread CPU per 3,520-tick match, one thread steps about **43k ticks/s** (a). crforge reports about
104k ticks/s per thread on an Apple M4 Pro with its replay set (`docs/performance.md`). Not reproduced here (a): other
hardware, our L16 census decks with evo / hero forms, and random plays.

### a2. 48 threads: JVMs x threads (a)
`bench.sh` / `grid.sh`: K JVMs at once, each `-XX:ActiveProcessorCount=T`, 16 matches in flight per thread, 60 s warm-up,
then the target matches. matches/h = the sum of the JVMs' own rates.

| JVMs x threads | matches in flight | matches | **matches/h** | core-s per match | peak RSS (sum) | GC s |
|---|---:|---:|---:|---:|---:|---:|
| 1 x 1 | 16 | 400 | 42,103 | 0.089 | 0.45 GB | 0.6 |
| 1 x 8 | 128 | 2,400 | 242,262 | 0.107 | 1.5 GB | 1.6 |
| 1 x 24 | 384 | 7,001 | 563,669 | 0.124 | 4.6 GB | 2.0 |
| 1 x 48 | 768 | 12,002 | 638,552 | 0.195 | 8.1 GB | 4.9 |
| 1 x 48, ParallelGC | 768 | 12,000 | 799,908 | 0.167 | 4.8 GB | 2.4 |
| 1 x 48, **2 matches per thread** | 96 | 6,000 | 217,500 | 0.257 | 1.6 GB | 1.7 |
| 2 x 24 | 2 x 384 | 12,001 | 1,103,549 | 0.125 | 8.8 GB | 4.0 |
| 4 x 12 | 4 x 192 | 12,002 | 1,277,811 | 0.117 | 6.9 GB | 7.4 |
| **12 x 4** | 12 x 64 | 12,000 | **1,573,898** | **0.106** | 14.1 GB | 7.7 |
| 12 x 4 (rerun, `o_12x4`) | 12 x 64 | 12,001 | 1,508,704 | 0.110 | 14.1 GB | 7.6 |
| 12 x 4, ParallelGC | 12 x 64 | 12,002 | 1,498,388 | 0.111 | 19.6 GB | 14.4 |
| 48 x 1 | 48 x 16 | 12,002 | 1,347,821 | 0.141 | 18.5 GB | 27.5 |

- Every step ends at a barrier (all matches of the JVM step one decision, then the next). With 2 matches per thread the
  1 x 48 JVM used about 16.6 of 48 cores (`top`, 10-27 10:53) and did 218k/h. **Keep at least 16 matches per thread.**
- One JVM does not scale past about 24 threads (a): the cost per match rises from 0.089 (1 thread) to 0.195 (48). The
  cause is untested (b: G1's pauses stop all 48 threads at once; shared-heap cache traffic). ParallelGC helps one big
  JVM (0.167) but not 12 small ones.
- 48 x 1 is worse than 12 x 4: 48 JIT compilers compete for the same cores, and after the 60 s warm-up the JIT still
  took 0.037 core-s per match (a, `g_48x1/jvm1.json`).
- Memory is not a limit: 12 x 4 with 768 matches in flight holds 14 GB, most of it heap the JVMs grew into (b: about
  1.2 GB RSS per JVM of which about 0.35 GB is the JVM and tables).

### a3. crforge's VectorEnv as shipped (a)
`CfSpeed env`: `VectorEnv.ladder` with `EnvConfig(decisionTicks, 16, 16, 0)`, autoreset, the same census and play rule
(random open action from the mask, probability 0.3).

| setup | matches | **matches/h** | core-s per match | CPU per env decision |
|---|---:|---:|---:|---:|
| 16 envs, 1 thread, 10-tick decisions | 200 | 26,554 per thread | **0.157** | 439 us |
| 768 envs, 48 threads (1 JVM), 10-tick | 6,000 | **241,510** | 0.403 | 1,092 us |
| 768 envs, 48 threads, 5-tick (its default) | 6,000 | 160,226 | 0.540 | 725 us |

crforge-env's own Python benchmark (JPype, numpy action draws, **its mirror decks**, not ours; best of 3, 10-tick
decisions; `py_bench_t*.out`):

| envs | threads | decisions/s | us per call | spread |
|---:|---:|---:|---:|---:|
| 1 | 1 | 2,078 | 481 | 42% |
| 16 | 1 | 3,369 | 4,750 | 7% |
| 64 | 48 | 16,683 | 3,836 | 58% |
| 768 | 48 | 34,272 | 22,409 | 21% |

At 356 decisions per match (our decks) 34,272 decisions/s would be about 347k matches/h (b: its decks' match length
was not measured). On 1 thread LadderEnv costs **+0.068 core-s per match (+76%)** over the bare core (0.157 vs 0.089).

## b. Step 2: our observation from crforge state (a)

`cf_obs.py`, 16 matches on 1 Java thread, 600 warm-up + 600 timed decisions per match: **38,400 seat-rows** compared,
timed: 19,200 seat-rows for P2, 2,400 for P1, 4,800 P3 calls. Times are thread CPU (`time.thread_time`); a path's p50 is the sum of its parts' p50s.

| path | what it does | **us per seat-row** (p50 / mean) | core-s per match (706 rows) |
|---|---|---|---:|
| P1 | Python reads every entity field through JPype (179 / 196) + `from_engine` fv4 + `to_tokens` + `to_unit_forms` (119 / 128) | **298** / 324 | 0.21 |
| P2 | Java dumps the match into one `int[]` (48 / 53) + Python builds the raw dict (16 / 20) + the same calls at fv4 (127 / 136) | **191** / 209 | 0.135 |
| P2 at fv6 | the same with CLXIII's `feature_version 6` (`body_identity.resolve_board`; 181 / 199) | **245** / 272 | 0.173 |
| P3 via JPype | `CfSpeed.Match.obs` called once per seat from Python (wall) | 21 / 24 | 0.015 |
| **P3 in the batch** | the same builder inside `Rollout.step` (no Python): core-s per match with obs minus without | **3.3** (1 thread: 0.0903 vs 0.0880) to **6.9** (12 x 4: 0.1153 vs 0.1104); 1 x 48: 0.1947 vs 0.1952, within noise | **0.002-0.005** |

**Identity (a): P3 == P2's Python tensors on 38,400 / 38,400 seat-rows** (tok, mask, unit_form for both seats; all of
sc for seat 0, sc except the hand one-hots for seat 1, whose stand-in deck is the engine order). The Java builder follows
`obs_contract.from_engine` (raw path) + `to_tokens` + `to_unit_forms`: bodies with hp > 0 in holder order, then spells,
ranked by |y - 0.5| (stable), side 1 mirrored, ages from a per-match first-seen table, towers in the fixed 6 slots.

Caveats:
- **51 crforge body names have no vocab id** (a, `obs.json` `unmapped_units`): for example Goblin, Minion, Bat,
  Skeleton_EV1, SpearGoblin, RoyalHog, Ram, Wallbreaker, SkeletonWarrior, ElixirGolem1. crforge spells some bodies
  unlike RoyaleSim (Skeleton, Barbarian, IceWizardHero; aliased in `cf_obs.ALIAS` for this probe). Both paths drop the
  unmapped bodies, so the identity holds, but the boards are thinner than they will be. This is EVAL.md's "card names /
  vocab" item (0.5-1 day), not part of this ticket.
- Evolved forms come from the name (`_EV1`, `Hero`); bodies whose evolution does not show in the name read as form 0
  (b, untested which ones). Sub-spawns (golemite vs golem) map to the parent: the Java table has no max_hp split (b).
- The comparison uses `from_engine` at fv4. fv5 / fv6 add `body_identity.resolve_board` (timed above, not compared).
- **What the Java builder does not build yet** (b, all of CLXIII's other inputs): `past`, the deck / hand identity
  arrays, `opp_past`, `opp_cycle`, `projectiles`, `effects`, `own_ability`, `cue` (22 numbers per unit from the unit's
  state), the 24-tick extrapolated view and the pending-play view, the opponent-elixir counter, and a memory model's
  tables. On RoyaleSim the whole Python observation costs 3.2 s per match in one process and 5.3 vCPU-s under 48 workers
  (SPEED.md b). The tok / mask / sc part in Java costs 0.002-0.005 core-s per match.

## c. Step 3: the full loop

### c1. Prototype (a): `CfSpeed.Rollout` + `cf_loop.py`
- **Java side:** `Rollout` holds N matches and a pool of T threads. `step()` applies each seat's action from a direct
  buffer (`[slot or -1, x, y]`), advances 10 ticks, resets finished matches with the next deck pair, and writes for both
  seats tok [64, 14], mask [64], sc [70], unit_form [64] and 4 legality bits (`PlayerCommands.tryCard`) into direct
  buffers. `stepAsync()` / `await_()` run it off the Python thread, so Python never holds the JVM up.
- **Python side (the server):** one process, the JVM inside it (JPype). Each cohort's buffers are numpy views and
  `torch.from_numpy` tensors with no copy. Per cohort in turn: `await_()`, then the policy writes the actions, then
  `stepAsync()`. Here the policy is a numpy stand-in (random legal slot, probability 0.3, random point) because the GPU
  was S2's; the real server puts S1's `forward_batch` + decide in its place.

| cohorts x matches, threads | window | matches | **matches/h** | core-s per match | cores busy | policy rows/s | round | peak RSS / Java heap in use |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| 2 x 512, 24 each | 90 s | 15,810 | 632,303 | 0.197 | 34.6 | 124k | 8 ms | - |
| **2 x 2,048, 24 each** | 90 s | 18,006 | **719,991** | 0.204 | 40.9 | 145k | 28 ms | - |
| 2 x 2,048, 24 each (rerun) | 60 s | 12,736 | 764,135 | 0.188 | 39.8 | 150k | 27 ms | 17.9 GB / 8.0 GB |
| 2 x 4,096, 24 each | 90 s | 18,468 | 737,846 | 0.209 | 42.7 | 160k | 51 ms | - |
| 2 x 4,096, 24 each (rerun) | 60 s | 12,282 | 731,594 | 0.210 | 42.7 | 163k | 50 ms | 20.5 GB / 4.2 GB |
| 1 x 2,048, 48 | 90 s | 16,553 | 661,933 | 0.201 | 37.0 | 130k | 32 ms | - |

- The Python thread costs at most 0.0002 core-s per match and waits 97-98% of the time: the CPU side of the server is
  free.
- Rows per match: 706 (2 seats x 353 decisions; the 726-803 in some window rows are window-edge effects).
- The JVM was started with `-Xmx24g`; the peak RSS is heap that G1 grew into, not need (b: the heap in use was 4-8 GB
  for 4,096-8,192 matches).

### c2. Design for the real loop (b)
1. **Java envs (from `Rollout`):** the trainer's job list goes in (deck pair, seed, levels, opponent id, per-side
   decision interval), finished matches reset from it. The observation builder covers every GenModel input (the list
   in b), each with an identity test against the Python builder in the `cf_obs.py` style. Legality uses our
   `allowed_slots` rule (elixir and cost), not `tryCard`. Per decision, Java writes the policy id of each row and the
   reward / outcome fields PPO records into a ring buffer.
2. **GPU server (S1's server, reused):** per cohort round, rows are grouped by policy id and each group gets ONE
   `forward_batch`. The decide becomes a batched GPU decide (sample gate / card on the GPU; one `cell_logits` call for
   the rows that place). S1's per-row CPU decide cost 0.5 vCPU-s per match (SPEED.md b), which would be 42 cores at
   300k/h. S1's cell-wave protocol is not needed: every row is in one process.
3. **Overlap:** 2 or more cohorts; Java steps one while the GPU serves the other. At 2 x 2,048 a Java round is 27 ms and
   holds 4,096 rows. One 4090 needs 92 ms for 4,096 rows even at the best measured rate (44.5k rows/s). So the **GPU is
   busy and Java waits**, and fewer Java threads, or one cohort's Java work spread over the GPU's time, would do.
4. **Batch size per policy:** S1's league put about 8 policies in each round and got 19-146 rows per forward, which is
   overhead-bound (SPEED.md c). With 8,192 rows per round, 8 policies get about 1,000 rows each, the B >= 1,024 rates
   that SPEED.md's rows/s assume (b: the learner holds about half the rows, the opponents split the rest).
5. **Past 48 threads (128 vCPU):** one in-process JVM scaled worst in a2. Run several JVM processes of 4-12 threads that
   share their buffers with the server through memory-mapped files in `/dev/shm` (Java `MappedByteBuffer`, numpy
   `memmap`), with one byte per round as the signal (b, not built).
6. **Effort (b, engineer-days):** Java port of the remaining observation 4-8; batched GPU decide plus identity tests
   against `DECIDE` 2-3; trainer integration (job lists, records, rewards, opponent groups) 3-5; multi-JVM shared
   memory 1-2; crforge naming adapter 0.5-1 (EVAL.md). About **2-3 weeks**.

### c3. Projection: `project.py results/loop_n2048_c2_t24.json --extra-core-s 0.049` (S3b-4: the extra is measured)
CPU bound = the measured loop rate (720k/h on 48 threads), linear to the pod's vCPU minus 2, slowed by **0.049 core-s
per match: the full Java observation's measured cost in the loop** (S3b-4 below, a: every builder, cue included, the
median process core-s per match with the observation minus without; it was the 0.05 guess of S3, b). Cross-check:
`project.py results/s3b4_all4.json` (the facade loop with every builder, no extra) gives a CPU bound of 648,568 on
54 vCPU and 1,571,731 on 128 vCPU. GPU bound = SPEED.md's rows/s on one 4090 (B >= 1,024, CLXIII inputs) x GPUs / 706
rows per match.

| pod | model, GPU path | CPU-bound matches/h | GPU-bound matches/h | **matches/h** | 300k | 1 M |
|---|---|---:|---:|---:|---|---|
| 54 vCPU + 1x 4090 | 1.76 M as today, fp32 | 629,184 | 48,580 | **48,580** | no | no |
| 54 vCPU + 1x 4090 | 1.76 M lazy refine, fp32 | 629,184 | 95,833 | **95,833** | no | no |
| 54 vCPU + 1x 4090 | 1.76 M lazy refine + bf16 | 629,184 | 227,035 | **227,035** | no | no |
| 54 vCPU + 1x 4090 | 10 M as today, fp32 | 629,184 | 22,324 | **22,324** | no | no |
| 54 vCPU + 1x 4090 | 10 M lazy refine + bf16 (b: CLXIII's x4.67) | 629,184 | 104,329 | **104,329** | no | no |
| 128 vCPU + 2x 4090 | 1.76 M as today, fp32 | 1,524,562 | 97,159 | **97,159** | no | no |
| 128 vCPU + 2x 4090 | 1.76 M lazy refine, fp32 | 1,524,562 | 191,667 | **191,667** | no | no |
| 128 vCPU + 2x 4090 | 1.76 M lazy refine + bf16 | 1,524,562 | 454,069 | **454,069** | yes | no |
| 128 vCPU + 2x 4090 | 10 M as today, fp32 | 1,524,562 | 44,648 | **44,648** | no | no |
| 128 vCPU + 2x 4090 | 10 M lazy refine + bf16 (b: CLXIII's x4.67) | 1,524,562 | 208,657 | **208,657** | no | no |

**What reaches 300k and 1 M per pod:**
- **CPU side** (b): 300k needs at most 0.62 core-s per match on 54 vCPU (52 usable) and the loop measured 0.19-0.21
  with the main tensors, so **300k: yes on both pods**. 1 M needs at most 0.19 core-s per match on 54 vCPU (**no**:
  0.25 projected, 0.27 measured in the facade loop with every builder, S3b-4) and 0.45 on 128 vCPU (**yes**: 1.5 M
  projected; b: linear past 48 threads, which needs several JVMs, c2 point 5).
- **GPU side: 300k only on 2x 4090 with CLXIII lazy refine + bf16** (454k). Lazy refine is SPEED.md's untested refactor
  (b), bf16 changes the stored log-probs (SPEED.md e5). On one 4090 the best is 227k.
- **1 M: no pod here reaches it.** It needs 196k rows/s at 706 rows per match: 4.4 4090s at the best measured CLXIII
  rate, or rows per match cut to 320 on 2 GPUs. A 10 M model reaches neither target on these pods.
- Levers that change the GPU bound, none measured: fewer rows per match (opponents every 20 ticks: about 530 rows, 300k
  on one 4090 with lazy + bf16; both seats every 20 ticks: about 353 rows, 908k on 2 GPUs), a smaller rollout opponent
  than the learner, CUDA graphs or TensorRT for the forward. Each changes training or the policy and is outside this
  ticket.

## Files and commands
- `CfSpeed.java`: `Match` (one match on the core), `Match.obs` (P3 builder), `Dump` (P2), `Rollout` (N matches,
  thread pool, direct buffers, async step), `core` / `env` benchmarks.
- `bench.sh`, `grid.sh` (step 1), `grid3.sh` (P3 inside the grid), `phase2.sh` (VectorEnv as shipped, crforge-env's
  bench, `cf_obs.py`, `cf_loop.py`), `grid4.sh` (loop memory).
- `cf_obs.py` (step 2 + identity), `cf_loop.py` (step 3 prototype), `project.py` (c3; `_demo()` is its self-check),
  `id_probe.py` (entity ids start at 5,000,000: the first `Match.firstSeen` indexed raw ids and ran 768 matches out of an
  8 GB heap; fixed, the 3 runs that hit it were rerun in `grid3.sh`).
- `results/`: every run's JSON and log as written on the pod (`g_*`, `o_*`, `t1x1*` step 1; `v_*`, `py_bench_*` a3;
  `obs.json` step 2; `loop*.json` step 3). `results/g_*_obs` are the out-of-heap runs, superseded by `results/o_*`.
- Pod 32657 `/workspace/cfspeed`: `crforge/`, `crforge_cache/` (the sha-checked copies), `build/`, `src/`, `pylib/`
  (JPype 1.7.1 from PyPI, `pip --target`), `cb/` (`pipeline/` at 1cad2a0 plus the cards / catalog / calibration data
  files), `decks.tsv` (the census, not committed: it comes from the git-ignored battle log), `runs/`.

```
cd /workspace/cfspeed; L=crforge/env/build/install/env/lib; P=/workspace/venvf15/bin/python
javac -d build -cp "$L/*" src/CfSpeed.java
./bench.sh g_12x4 12 4 64 60 1000 10 0.3 0 1500m              # step 1, one grid row
$P -I cf_obs.py --envs 16 --steps 600 --warm-steps 600 --out runs/obs.json
$P -I cf_loop.py --envs 2048 --cohorts 2 --threads 24 --warm 60 --seconds 90 --out runs/loop_n2048_c2_t24.json
python -I project.py results/loop_n2048_c2_t24.json --extra-core-s 0.05   # laptop
```

## S3b-1: crforge body rows -> the ids RoyaleSim's production path gives (`body_map.json`)

- **Method (a).** Every card form of the 223 census pairs (180 jobs: 119 cards, base + the evo / hero slots played) was
  played by side 0 alone, 2,400 ticks, towers attacking, in both engines at level 11 (RoyaleSim's level):
  crforge via `BodyProbe.java` (direct play; in a Ladder match for the 4 forms that need champion slots or a king),
  RoyaleSim fin15 via `rs_probe.py` (`RoyaleSelfPlayEnv.raw()`, the production raw dict). A crforge body matches the
  RoyaleSim body of the same card form with the same max_hp; its id is `vocab.engine_unit_id(rs_name, max_hp)`, what
  `from_engine` computes. **All 204 matches were exact on max_hp** (0 needed the 3% tolerance). `map_bodies.py` joins
  them; its `_check()` asserts three known cases.
- **Result (a).** 188 crforge body names mapped (16 entries carry a max_hp rule: the golem / lava / elixir golem /
  recruits / mother witch sub-spawn splits and the spell bodies). 15 names stay dropped (`_unmatched`): 10 the
  RoyaleSim probe never showed (bomb / bottle death bodies with max_hp -1, Tombstone hero visual dummies at 2,559,997 hp,
  Skeleton Barrel's container) and 5 seen only in matches through kills or curses, with no RoyaleSim evidence
  (SpearGoblin_Dummy, VoodooHog, PhoenixNoRespawn, Wallbreaker_mini, GoblinCurseGoblin).
- **Bodies dropped per match, 223 census matches (a, `cf_drop.py`, random plays, L16; 91.2 bodies per match):
  before 23.3 (193 of 223 matches drop at least one; 61 names), after 1.0 (36 matches; 6 names).**
- **Finding (a): 9 crforge rows need the spawning card, not the name.** RoyaleSim names a body by its parent card, so
  production gives a Witch's skeleton the `witch` id, a Night Witch's bat `night_witch`, a Furnace's spirit `furnace`,
  a Goblin Giant's spear goblin `goblin_giant`. crforge uses one row for each (Skeleton, Bat, SpearGoblin, Goblin_Stab,
  Barbarian, Barbarian_EV1, FireSpirits, Minion, Goblin). **42.5 of the 91.2 bodies per match** carry such a row. The
  facade must pick the entry by the card that spawned the body (`by_name_unique: false`); whether crforge exposes that
  parent for every spawn (Play.units() covers direct units) is untested (b).
- **Forms (b).** RoyaleSim showed status_flags 0 on every probed body, evolved and hero slots included, so `form` comes
  from the crforge row name (_EV1 / Hero) and is not checked against RoyaleSim.

## S3b-3a: byte-identity harness, Java builders vs the production GenModel row (`obsid/`)

- **Harness.** `obsid/run.sh OUT.json [--n 56] [--set k=v]` (pod 32657) compiles CfCore (the work tree's HEAD copy),
  `CfSpeed.java` and `obsid/CfObsBind.java` into `obsid/build`, starts the facade's JVM with them, and runs
  `e1_eval.run_selfplay_batch` (ROYALE_ENGINE=crforge, CLXIII both seats, `search_s0.live_cfg` + delay 26 + fv6, as
  accept_f1 obs). A hook on `Match.gen_row` builds every `BUILDERS` entry on the SAME facade battle and tick and
  compares each GenModel key (dtype, shape, bytes). Keys no builder makes: NOT_PORTED. A port adds one builder.
  The Java builder's opponent-elixir slot (sc[5], the engine truth) is replaced by -1 before comparing, never logged.
- **Result (a), `obsid/results/live.json`: 56 matches, 49,229 seat-rows, Java tick = production tick on all.**
  tok equal 17,842 / 49,229, mask 43,528, unit_form 24,440, sc 0 (sc[5] by construction). 15 keys NOT_PORTED.
  So S3's 38,400 / 38,400 does **not** carry over (c): S3 compared against from_engine **fv4** without the live cfg.
- **Why (a: per-column counts; b: the attribution of shifted rows).** `results/x0.json` = the same with
  `--set extrapolate_ticks=0` (48,451 rows): sc[0..2] then match on all rows, tok's position columns 4 / 5 drop from
  ~28k to 5.5k rows (= the spell rows). What the Java builder does that production fv6 does not:
  1. **26-tick extrapolated view** (`extrapolate`): positions, hp, t (sc[0..2]). Not ported.
  2. **fv>=4 `body_only_board`**: no spell tokens (cols 12 / 13, 5.5-5.7k rows; mask), deploying and age empty
     (cols 8-11, ~31k rows). The builder still writes fv4's.
  3. **My elixir sc[3]** (31-34k rows): the facade reports `getElixir() / 10` milli (CfCore.java:477, truncated),
     the builder `getElixir() / 10000.0`.
  4. **Opponent elixir sc[5]**: production = the public counter estimate; the builder reads the truth (port the counter).
  5. **Identity / form**: the builder's name table (body_map first entry) gives the Hero Ice Wizard body cls 110 form 2,
     production gives cls 7 form 0 (facade status flags 0 -> fv6 `resolve_board`); tok col 0 13.3k rows at x0,
     unit_form 24k. The table must come from production's identity rule (and the 9 by-root names from the root play).

## S3b-3a2: the Java builder at feature version 6 (`CfSpeed.Match.fv6`, `obsid/CfObsBind.FacadeMatch`)

- **Changes.** `CfSpeed.Match.fv6` (default false = S3's fv4 path, unchanged): no spell tokens, deploying / age
  columns 8-11 left 0 (`body_only_board`), my elixir `getElixir() / 10 / 1000.0 / 10.0`. `FacadeMatch` overrides
  `unitCode`: a body is a token as `raw()` + `from_engine` fv6 make it one (alive; a card from the facade's own tables,
  body_map by name and the 9 split names by the root play's card; dead with a known max dropped), and its class / form
  come from production's `body_identity.resolve_board` on that body with the side's tower level factor (key
  "card|body row|max_hp|form|tower", filled from Python on first sight; the Hero Ice Wizard rows read 'IceWizard' as
  `royale_heroiw.public_identity` names them). STATUS_HERO comes from the facade's own method by reflection
  (`heroBody` at 3531b83, `heroCard` at ee7896c, none before), so the bit follows the facade.
- **Elixir: the builder was wrong, the facade is right (a, code).** RoyaleSim's `PlayerState.elixir_milli` is an
  integer and `raw()` reads `elixir_milli / 1000`, so fin16 feeds the model milli. The facade's `getElixir() / 10`
  is that unit, and flooring keeps crforge's own affordability (raw >= 10,000 cost exactly when floor(raw / 10) >=
  1,000 cost). What the live reader feeds was not checked (b).
- **Result (a), 56 matches each, `obsid/results/`, sources pinned by sha256 in each JSON (`facade_src_sha256`):**

  | facade | cfg | seat-rows | tok | mask | sc (all but sc[5]) | unit_form |
  |---|---|---:|---|---|---|---|
  | 3531b83 (F1c-1b, hero bit) | extrapolate 0 (`x0.json`) | 49,816 | **identical** | **identical** | **identical** | **identical** |
  | 3531b83 | live cfg (`live.json`) | 48,751 | 22,513 equal | identical | 0 equal (sc[0..3]) | 42,787 equal |
  | ee7896c (F1c-1, `/workspace/f1c1/build`) | extrapolate 0 (`x0_f1c1.json`) | 49,782 | identical | identical | identical | identical |
  | 087ca4c-era HEAD (no hero bit) | extrapolate 0 (`x0_head.json`) | 48,451 | identical | identical | identical | identical |

  The live-cfg differences are the 26-tick extrapolation, not ported: sc[0..2] (t), sc[3] (31,368 rows: the
  look-ahead's elixir), tok positions 4 / 5 and, through the re-sorted rows, cols 0-2 / 6 and unit_form (b: the
  attribution of shifted rows). sc[5] stays masked (the counter is not ported). S3b-3a's `live.json` / `x0.json`
  (fv4 builder) are in git at 087ca4c.
- Not re-run: S3's `cf_obs.py` on the edited CfSpeed (the fv4 path is a mechanical refactor, b).

## S3b-3e: the look-ahead (extrapolated) view in the Java builder (`CfSpeed.Match` hooks, `FacadeMatch`)

- **What the live cfg runs (a, code + counts).** `search_s0.live_cfg` sets `extrapolate_ticks` 26 and none of
  `own_effects`, `predict_drops`, `pipeline_decisions`. So `extrapolate()` there is: h = 26 from a seat's second
  decision on; each body paired with the seat's previous decision state (entity id, side, card) moves
  x + (x - px) * h / gap, clamped to the board; tick + h; my elixir + `regen_between` (opp_elixir_count's
  REGEN_SCHEDULE) capped at 10. `retrack` needs own_effects, the drop tracker predict_drops, the pending board
  pipeline_decisions: the live cfg runs none of them (rows_own_fx 0, rows_drops 0, rows_pend 0 of 48,751).
  `advance_public_objects` feeds only the projectile / effect keys (fv6: no spell tokens). Ported: the active part.
- **Pending plays (c).** On the facade path no row has a pending play the observation could show: e1's
  `pipeline_decisions` board is off (rows_pend 0), and a seat's own decided play is never pending at its next
  decision (rows_own_pending 0; F1b: a seat decides again only after the engine runs its play). The opponent's
  `SelfPlaySide.pending` was never set at a decision either (rows_opp_pending 0; b: its 6-tick e1 wait ends between
  10-tick decisions). Exercising the pending board needs `--set pipeline_decisions=true`, not the live cfg.
- **Code.** `CfSpeed.Match`: hooks `lookahead` / `ahead` / `regen` / `observed` (S3's default: none). `FacadeMatch`:
  per-seat previous-state snapshot, dead reckoning, the regen schedule, `rewind(seat)` (a rebuild after new names
  must not see itself as the previous state: that bug moved no body on 1% of rows in the first smoke).
- **Result (a), facade 3531b83, sources pinned (`facade_src_sha256`), 56 matches each:**

  | cfg | seat-rows | rows with look-ahead | rows where a body moved | tok | mask | sc (all but sc[5]) | unit_form |
  |---|---:|---:|---:|---|---|---|---|
  | live (`results/live.json`) | 48,751 | 48,639 | 26,238 (88,092 bodies) | **identical** | **identical** | **identical** | **identical** |
  | extrapolate 0 (`results/x0.json`, regression) | 49,816 | 0 | 0 | identical | identical | identical | identical |

  S3b-3a2's live / x0 JSONs are in git at 4a8075f.

## S3b-3b: past plays and the hand / deck identity arrays in Java (`obsid/CfIdent.java`)

- **Keys.** `past`, `hand_slot`, `hand_card`, `hand_form`, `next_card`, `next_form`, `deck_card`, `deck_form`,
  `slot_card`, `slot_form` (int64 / float32 as `GenPolicy.slot_ident` + `GenPolicy.row` + `dataset._past` give them).
- **Inputs (a, code).** From the facade: the deck's catalogue card ids and forms by deal index (`St.deckIds`,
  `St.forms`), the hand and queue, the tick. From the loop: the deal index -> deck slot map (as `CfObsBind.bind`
  takes), a catalogue id -> checkpoint card id table (filled once per deck from the policy's gid; JPype boxes a
  Python int key as a Long, hence `putGid`), and the plays the facade GAVE: `played(seat, facade tick at the act,
  slot, decided cell)`, logged by a hook on `e1_eval.Match._land`. x / y come from the cell in Java
  (`model_v3.cell_xy`, lattice or floor); dt from the view tick. The facade keeps no play log of tick / position
  (CfCore.play records only the play name -> card), and its x / y are the request // 18 (lossy), so the loop that
  decides the cell is the log's source.
- **Extrapolation (c: the ticket expected none).** `past` (and production's `opp_past`) take dt = view tick - play
  tick, and the view tick is tick + h (`Match.prepare`: `_past(..., tick + h)`; `public.features(match._view_tick)`).
  At the live cfg 35,900 of 48,751 rows have a past play and h = 26, i.e. every such row's dt is 1.3 s larger than
  at h = 0. `CfIdent` applies the same rule as `FacadeMatch.lookahead` (h = extrapolate_ticks from a seat's second
  decision); the identity arrays do not depend on h.
- **Result (a), facade 3531b83, sources pinned (`facade_src_sha256`), 56 matches each, all 10 keys identical:**

  | code | cfg | seat-rows | 10 keys |
  |---|---|---:|---|
  | S3b-3e (fa3b8ee) + S3b-3b (`results/ident_live.json`) | live | 48,751 | **identical** |
  | S3b-3e (fa3b8ee) + S3b-3b (`results/ident_x0.json`) | extrapolate 0 | 49,816 | **identical** |
  | 4a8075f + S3b-3b (before the rebase onto S3b-3e; JSONs not kept) | live / extrapolate 0 | 48,751 / 49,816 | identical |

- **`opp_past` not ported (c: the ticket's source is not production's).** At feature version >= 4 production's
  `opp_past` is `PublicObserver.features`: plays DETECTED from the public board at the seat's decision frames
  (`PlayDetector` bodies + spell sightings, the first-sighting tick and the body / spell position), not the
  delivered plays. Measured on the same rows (a, `opp_past_delivered`): `opponent_past(env.public_plays)` (the
  delivered log) equals production on 12,757 of 48,751 live rows (12,920 rows are empty in production), card /
  form columns on 35,026. A delivered-play builder would therefore change the feature, and a byte-identical one
  needs `PlayDetector` + `public_frame` (sim source) + the spell dedup + the native card-id / card_db tables in Java.
  Owner / foreman call; not done.

## S3b-3c: the PUBLIC opponent-elixir estimate (sc[5]) and opp_past in Java (`obsid/CfOppElixir.java`)

- **What production does (a, code at 8ecde05).** fv >= 4: `e1_eval.Match.prepare` runs `PublicObserver.update(state,
  source='sim')` at each of the seat's own decisions and sets `opp_elixir = public.estimate_at(tick + h)`;
  `gen_row`'s `opp_past` is `opponent_past(public.plays, view tick, side, gid)`. Bodies go through
  `opp_elixir_count.PlayDetector`, spells through the board's spell objects (`sim_objects` -> `public_frame`, cards.yaml
  kind 'spell'), the counter is `OppElixirCounter` on the env's schedule (crforge: `REGEN_SCHEDULE`). The delivered-play
  path (`opp_estimate`) is fv < 4 only and is not used.
- **Port.** `CfOppElixir` (one per seat, held by `FacadeMatch.opp`, reset with the battle) builds the public frame from
  the facade battle (state()'s bodies: alive, not a tower, a card from the identity tables, hp > 0 or max_hp <= 0; the
  opponent's only), runs PlayDetector + PublicObserver + the counter, and answers `estimateAt(tick + h)` (CfSpeed's new
  `oppElixir` hook, which writes sc[5]) and `past()` (opp_past, dt from that same view tick). Python fills two tables on
  first sight: "card|body row|form" -> (detector key, catalog form) by running production's `public_frame` on that
  body's own raw() entity, then `_catalog_names` -> `vocab.engine_key` (so the Hero Ice Wizard's public id and every
  form rule are production's, not re-derived); card id -> key when `public_frame` keeps that card's objects as a spell.
  Per key: `card_cost` (None -> NaN, no charge), the swarm window, the policy gid. No elixir, hand or deck of either
  side is read; the harness no longer masks sc[5] (nothing holds the truth).
- **Edge cases matched (a: each fired in the identity runs; counts live / x0, `opp_counter_edges`).**
  1. Swarm join: a new group of a key within its window (100 ticks; Graveyard 200) of that key's last charged play is
     the same cast (164 / 148).
  2. Spawn by parent: a same-key body with a higher max_hp on the board or gone <= 60 ticks (counted from the first
     decision frame WITHOUT it), or an unreadable (max_hp <= 0) one when the group is weaker than the key's strongest
     charged max_hp (290 / 279). Spawn by death: a weaker same-key body gone <= 60 ticks within 1,500 units (28 / 30);
     with no readable max_hp in the group every gone positive-max_hp body counts (Python's `inf`).
  3. A body play is dropped when a same-key spell was seen <= 100 ticks earlier (101 / 102); a still-visible spell is
     not recounted while consecutive sightings are <= 100 ticks apart (2,101 / 2,248 sightings).
  4. Same-tick plays are charged in key-STRING order (`sorted(candidates)`): it fixes the re-base and the float
     order (41 / 29 re-bases). A spell sighting replaces a same-tick body candidate (form 0, the objects' centroid).
  5. `estimate_at(t)` counts plays seen strictly before t: at h = 0 a play seen at this decision is not in its own sc[5].
  6. Shots count by their firer's card (tower -1, unknown -2, as state() writes them) only when raw() carries
     projectiles (env feature_version >= 4); an area with no card (`areaCard` null) is not on the board.
  7. A key with no cards.yaml cost (1 live play): it is dated, enters opp_past, charges nothing.
- **Step 1 (a): bodies only (`--opp-spells 0`) on the 3 census pairs whose opponent deck has no spell card (88, 166,
  209; 4 seeds each, live cfg, `results/s3b3c_step1_bodies.json`): sc on those rows (`sc@nospell_opp`) identical
  5,129 / 5,129 (927 body plays, 62 spawn groups, 27 swarm joins); the other 5,117 rows (icebow's Log / Rocket / Tornado as the
  opponent) differ only at sc[5] (2,597 rows), as expected without spells.**
- **Result (a), facade 3531b83 (`CfCore.java` 1fa04dc2), sources pinned (`facade_src_sha256`: production pipeline,
  CfSpeed / CfObsBind / CfOppElixir / obs_id.py), 56 matches each, `results/s3b3c_{live,x0}.json`:**

  | cfg | seat-rows | sc (incl. sc[5]) | opp_past | tok / mask / unit_form | S3b-3b's 10 keys | plays / spawn tallies |
  |---|---:|---|---|---|---|---|
  | live | 48,751 | **identical** | **identical** (35,831 rows hold a play) | identical | identical | identical |
  | extrapolate 0 | 49,816 | **identical** | **identical** (36,491 rows hold a play) | identical | identical | identical |

  Plays detected: 4,219 live (3,481 by bodies, 738 by spells), 3,997 at x0. Not ported: `opp_cycle` (the same play
  list; b: a few lines on top of it), `own_ability`, `projectiles` / `effects`, `cue`.
- Pod 32657 `/workspace/s3b3c`: `rl/` (pipeline at fa3b8ee, data links to `/workspace/f1/rl`), `head/` (CfCore.java at
  fa3b8ee), `crforge/` (these sources), `out/`. Command: `OBSID_RL=/workspace/s3b3c/rl
  OBSID_CFCORE=/workspace/s3b3c/head/scratchpad/gauntlet/L74/crforge/facade/CfCore.java OBSID_BUILD=... crforge/obsid/run.sh
  OUT.json --n 56 [--set extrapolate_ticks=0] [--opp-spells 0 --pairs 88,166,209,...]`.

## S3b-3d: the remaining public-observer keys in Java (`obsid/CfPubObj.java`): projectiles, effects, own_ability, opp_cycle

- **What production computes (a, code: e1_eval.Match.prepare / gen_row / sim_v3_features at the live cfg, fv 6).**
  CLXIII's `gen_row_keys` = 20 keys; before this ticket NOT_PORTED: `projectiles`, `effects`, `own_ability`,
  `opp_cycle`, `cue` (`opp_past` done in S3b-3c). The four public keys are `PublicObserver.features(tick + h, gid,
  objects_override=_public_object_view)`; `PublicObserver.update(self.state, 'sim')` runs at every prepare (the seat's
  decision ticks only), BEFORE extrapolation.
  - `projectiles` [64, 8] / `effects` [32, 6]: raw() `sim_objects` (shots: firer's card, -1 tower, -2 none; spell rows
    motion 0-2 -> projectiles, 3-4 -> effects, remaining = delay x 50 only for PULSING) -> `projectile_observation.objects`
    (key = base card key, tower / unknown dropped, area-timer mask, ceil to 50 ms) -> `ProjectileMotion(catalog_fallback)`
    (catalog TTI every frame; else a unique (card, side, target) track's closing speed over <= 20 ticks) -> the
    COMPRESSED snapshot history (unchanged frames not stored: `previous_objects` / gap = the last two DIFFERENT snapshots).
    **Depends on h:** h > 0 -> `extrapolate.advance_public_objects` on that history (catalog / known TTI: land or move
    along the aim, TTI - 50h; unknown TTI: the unique track's velocity x h / gap if 0 < gap <= 20, clamped; area clocks
    - 50h, expired dropped); h = 0 -> the stored snapshot. Then `tokens_from_objects` (gid, my-frame position, sort, cap).
  - `own_ability` [8, 7]: `own_ability.observe` on the UN-extrapolated board (own alive bodies, form 2 or a champion
    key; hp > 0) + `tokens(rows, gid, own_events, tick + h)`: `own_events` = env.public_plays (tick = act + 20 on the
    facade) + env.own_ability_events (tick = the press) of my side, counted when < tick + h; spec = `catalog('off')`.
    **h:** only through the view tick (which events count, the cooldown).
  - `opp_cycle` [8, 4]: `opponent_cycle(PublicObserver.plays, tick + h)` = the DETECTED plays (S3b-3c's detector):
    built on `CfOppElixir`'s play arrays (no second detector). **h:** which plays count and the age column.
  - Own effects: `own_effects` is not set by `search_s0.live_cfg` -> `own_fx` None (rows_own_fx 0 below); not ported.
  - `cue`: `sim_cue_rows` (CLXIII has a cue layer), not a public-observer key: S3b-3f's (CfCue). Still NOT_PORTED here.
- **Code.** `CfPubObj` (one per facade core, per-seat state, reset on a new battle): `update(seat)` reads the facade
  like `CfCore.state()` (bomb spell row, spell projectiles, shots with `cardOf`'s firer, areas via `areaCard`; own bodies
  with state()'s status bits 8 / 16), `build(seat, ...)` writes the four keys. Action log: `act(side, act tick, card id)`
  / `press(side, tick, button)` (card = the button's champion slot), fed in the harness by a hook on
  `royale_env._Core.act`. Tables from production functions (`JavaPub.tables` / `resolve`: `objects`,
  `constant_projectile_speeds`, `unavailable_area_timers`, `own_ability.observe` / `catalog`, `card_key`, gid).
  `math.hypot` -> `sqrt(dx*dx + dy*dy)`: every hypot input is integer-valued (crforge units), so the sum is exact and the
  sqrt correctly rounded (b: equal to CPython's here; the identity below found no difference).
- **Fix to an earlier builder (c -> fixed).** At facade 0446ab3 `unit_form` was DIFF (smoke, 2 matches: 1,533 / 1,893
  rows equal; prod form 1, Java 0): state() now ORs STATUS_EVOLVED (8, `CfCore.evolvedBit`, an `_EV` body row) and
  `FacadeMatch.unitCode` did not. `CfObsBind.evolved(w)` (reflection, 0 on an older facade) added; identical below.
- **Result (a), pod 30408 `/workspace/s3b3d` (crforge lib / tables / decks / CLXIII sha-equal to 32657's), facade =
  0446ab3's CfCore.java, pipeline at ca2930a, sources pinned in each JSON (`facade_src_sha256`), 56 matches each, 0
  skipped, tick_mismatch 0; ALL 19 ported keys IDENTICAL (tok, mask, sc incl. sc[5], unit_form, opp_past, past + the 9
  identity keys, projectiles, effects, own_ability, opp_cycle); `cue` NOT_PORTED:**

  | cfg | JSON | seat-rows | rows w/ projectiles / effects / own_ability / opp_cycle | motion TTI / landed / expired |
  |---|---|---:|---|---|
  | live | `results/s3b3d_live.json` | 50,046 | 13,447 / 3,078 / 16,191 / 37,131 | 4,216 / 14,037 / 347 |
  | extrapolate 0 | `results/s3b3d_x0.json` | 49,917 | 12,905 / 2,961 / 14,461 / 36,596 | 4,520 / 0 / 0 |

  Also 0 view-tick mismatches and 0 own-event-count mismatches (Java log vs `PublicObserver.own_events`) on every row.
  **The press branch (a), `--hero-abilities` (RoyaleSelfPlayEnv hero_abilities, the generic press rule):** the harness
  env above presses NO button (0 presses in 56 matches: `hero_abilities` defaults off), so those runs never showed a
  controller after a press. With presses on, at 93e718f (S3b-3f's CfCue in the harness too), 56 matches each, every
  GenModel key (all 20, `cue` included) IDENTICAL:

  | cfg | JSON | seat-rows | presses | own_ability rows: known / not ready / no charge left / cooldown > 0 |
  |---|---|---:|---:|---|
  | live | `results/s3b3d_live_press.json` | 50,939 | 580 | 16,518 / 9,488 / 9,488 / 0 |
  | extrapolate 0 | `results/s3b3d_x0_press.json` | 50,527 | 538 | 15,573 / 10,028 / 8,913 / 1,255 |

  0 view-tick, own-event-count and press-tick mismatches. Cooldown > 0 is only the deploy window (born + 1,000 ms; no
  hero / champion here has an ability cooldown): the body shows from born = act + 20 on, so at h = 26 the view tick is
  always past born + 20 (0 rows), at h = 0 it is not (1,255 rows).
- Command (pod 30408): `OBSID_RL=/workspace/s3b3d/rl OBSID_CLXIII=/workspace/f1c/models/succ48_o_s91_u0075_grafted.pt
  OBSID_BUILD=/workspace/s3b3d/build_live rl/scratchpad/gauntlet/L74/speed/crforge/obsid/run.sh out/s3b3d_live.json
  --n 56 [--set extrapolate_ticks=0]`.

## S3b-3f: the cue rows in Java (`obsid/CfCue.java`)

- **What production computes (a, code at 0446ab3; sources pinned in each JSON).** CLXIII has a cue layer
  (`model.cue_in`), so `e1_eval.gen_row_keys` lists `cue` and `Match.gen_row` sets `row["cue"] = sim_cue_rows(match)`:
  [64, 22] float32 = `model_gen.cue_vector` (cue_known, state one-hot 7, charging, Tesla hidden, has target, target is a
  tower, phase one-hot 3, attack frac, frozen / slowed / raged / invisible / shielded, slow frac). `fast_obs.sim_cue_rows`
  (S1b) gives the same rows when installed; the harness runs the original. Its sources:
  1. `sim_unit_state.extract(core._battle, match._cue_memo, hit_window_ms=100)`. On the facade `save()` =
     `CfCore.cueSave()` (attack timer, `phase()`, river jump / dash from the view state, kind, base speed, `hide()`,
     the charge flag) and `state_json()` = `CfCore.state()` (uid = entity id, team, x / y, deploy ticks, `stunTicks()`,
     shield, target = `acquired()`, status flags = body_map flags | underground / invisible / hidden | hero | charged |
     `abilityBits()` | evolved, buffs by name at their longest remaining ms, FOREVER = 999999, the idle buff left out).
     Units = alive bodies but the Mighty Miner bomb, named by crforge body row (`unit_types_json`). Hit speed,
     `hides_when_not_attacking`, the idle buff, each buff's status words (`_statuses`) and table totals come from the
     royalesim module's 10-19 card table looked up by those crforge names. Flag bits read: underground 1, invisible 2,
     ability_windup 64 (`royalesim.STATUS_BITS`).
  2. Per unit: state (tunnelling > deploying > jumping > casting > engaged > moving > idle), phase (idle; hit while
     progress mod hit speed < 100 ms; else windup), frac = round(progress mod hs / hs, 3).
  3. **Memo (time-dependent).** One dict per seat per match (`Match._cue_memo`), updated at every decision of that seat
     for every unit (towers too): total(uid, buff) = max(ms now, the earlier total, the table total); a buff's frac =
     round(ms / total, 3). So a frac depends on which earlier decisions of that seat saw the buff.
  4. **Matching (extrapolation-dependent).** The unit tokens (mask, col 13 = 0, a side flag) of the prepared `tok`,
     which is the look-ahead view (tick + 26 at the live cfg), are matched to the bodies of the battle NOW (not
     extrapolated; towers out; by uid) on the same side, distance hypot(dx * 18, dy * 32) tiles, pairs taken globally
     nearest-first (`np.argmin` order), within 3 tiles; unmatched rows stay 0.
  Not read: the opponent's hand or elixir; extract's projectiles / areas (built, unused by the cue).
- **Port.** `CfCue.build(core, seat, Tables, Seat, tok, mask, out)` reads the same crforge values through CfCore's own
  helpers (same package), the card-table facts by name from `CfCue.Tables` (filled by `obs_id.JavaCue.fill` from
  `_tbl` / `_statuses` on first sight; a build with an unknown name writes nothing and asks for them), the memo per seat;
  tok / mask are JavaMain's buffers for the row. Python `round(x, 3)` = `BigDecimal` HALF_EVEN; a body's x / y =
  `a / 1000` (= `round(a * 18 / 18000, 3)`, checked for a in -100..40,000); `np.hypot` = `Math.hypot` (no difference
  seen).
- **Result (a), facade 0446ab3 (`CfCore.java` sha256 57e3755b...), 56 matches each, `cue` byte-identical on every row.**
  `cue_live` / `cue_x0` = the harness as committed at 93e718f (S3b-3c + S3b-3d + this; `builder/obs_id.py` sha256
  f9e23afc... pinned in the JSON): **all 20 GenModel keys IDENTICAL** at both cfgs. The pre-merge runs (harness at
  0446ab3 + this builder only) gave the same seat-rows, rows / tokens with a cue and per-column counts, cue identical.

  | cfg | JSON | seat-rows | rows with a cue | tokens with a cue | cue |
  |---|---|---:|---:|---:|---|
  | live | `results/cue_live.json` | 49,822 | 31,297 | 177,603 | **identical** |
  | extrapolate 0 | `results/cue_x0.json` | 50,353 | 31,312 | 181,374 | **identical** |
  | live, census pairs 74 92 112 141 149 152 158 195 211 217 50 55 76 0 (Miner / Goblin Drill / hero Knight / Monk / Mighty Miner; pre-merge harness via a pod wrapper over `census`) | `results/cue_cover.json` | 11,454 | 8,221 | 45,435 | identical |

  Tokens with each column set (live; `diag.cue_colNN`): every column but state=tunnelling (col 6) and state=casting
  (col 7) is set on 150+ tokens. Tunnelling: 0 live, 126 in the coverage run (identical). **Casting: 0 tokens in all
  runs (b: untested)**; it is the same flag test as tunnelling, on `abilityBits` bit 64. Measuring it needs a match
  where a casting champion / hero body (hero Knight, Monk, Mighty Miner) is pressed and stands within 3 tiles of its token.
- **Cost per seat-row (a, in-process on the same rows; the merged runs, two at once on a pod under load ~10):**

  | path | live | extrapolate 0 |
  |---|---:|---:|
  | production `e1_eval.sim_cue_rows` | 805 us | 794 us |
  | `fast_obs.sim_cue_rows` (S1b; timed on a copy of the memo) | 400 us | 383 us |
  | `CfCue.build` inside the JVM | 15.3 us | 14.5 us |
  | the same call from Python (JPype) | 24.8 us | 24.3 us |

  The Java path takes tok / mask as built; the first-sight table fills are left out of its time.

## S3b-4: the full Java observation inside the loop (`obsid/CfLoop.java`, `obsid/cf_loop_obs.py`)

- **What runs (a, code).** `CfLoop` = S3's `Rollout` on the F1 facade: C cohorts of N `CfCore` matches (the facade's
  identity tables copied from one `CrforgeCore`), T Java threads per cohort, async step, direct buffers. Per 10-tick
  decision each seat acts by Rollout's Java stand-in rule (a random hand slot with p 0.3 if `CfCore.check` allows it,
  a random point and cell; an ability press with p 0.05 when the side has a button), the match steps, and both seats'
  rows are built at the live cfg (fv6, extrapolate 26, the public counter) by EVERY ported builder, in
  `Match.prepare`'s order: `CfOppElixir.update` -> `FacadeMatch.obs` (tok / mask / sc / unit_form) -> `CfCue.build`
  (cue) -> `CfOppElixir.past` -> `CfIdent.build` (past + 9 identity keys) -> `CfPubObj.update` + `build` (projectiles,
  effects, own_ability, opp_cycle): all 20 GenModel keys of CLXIII. Decks: the 56 census pairs of the harness (Icebow
  on side i % 2; `CfCore.reset` arguments captured from `RoyaleSelfPlayEnv.reset`), levels 16.
- **Measured:** process CPU (`getrusage`: engine, obs, GC, JIT, the Python thread), and the pool threads' CPU
  (`ThreadMXBean`) split into engine (acts + 10 ticks + resets) and obs (both seats' rows). Tables are per cohort,
  filled from production code between that cohort's rounds; a decision that meets a missing key skips that builder
  (counted). Window 120 s after 90 s warm-up, 2 cohorts x 2,048 matches x 24 threads (S3's best loop shape), pod 30408
  (54 vCPU quota; its GPU trainer took ~1.1 cores throughout; the cgroup was throttled in about a third of its 100 ms
  periods during each run, `results/s3b4_throttle.txt`: the wall rate is low, core-s per match is the robust number).
- **Result (a), `results/s3b4_*.json`, sources pinned (`src_sha256`), runs in time order:**

  | run | builders | matches | **process core-s / match** | engine thread core-s / match | **obs thread core-s / match** | **obs us / seat-row** | matches/h (48 threads) |
  |---|---|---:|---:|---:|---:|---:|---:|
  | `all` | all 20 keys | 14,888 | 0.363 | 0.237 | 0.0633 | 90.8 | 446,230 |
  | `noobs` | none | 23,151 | 0.231 | 0.191 | - | - | 694,164 |
  | `all2` | all 20 keys (1 engine crash; cue skipped on 2,772 rows) | 19,413 | 0.266 | 0.179 | 0.0388 | 55.6 | 582,115 |
  | `nocue` | all but cue | 21,973 | 0.246 | 0.172 | 0.0287 | 40.8 | 658,986 |
  | `noobs2` | none | 25,178 | 0.212 | 0.177 | - | - | 755,318 |
  | `noobs3` | none | 25,053 | 0.219 | 0.174 | - | - | 751,385 |
  | `all3` | all 20 keys (cue skipped on 5,220 rows) | 19,622 | 0.273 | 0.185 | 0.0421 | 60.5 | 588,525 |
  | `nocue2` | all but cue | 22,852 | 0.250 | 0.168 | 0.0285 | 40.9 | 685,389 |
  | `all4` | all 20 keys (0 misses, 0 crashes) | 19,961 | 0.275 | 0.187 | 0.0391 | 56.4 | 598,755 |
  | `noobs4` | none | 23,681 | 0.235 | 0.185 | - | - | 709,605 |

  Seat-rows per match 697-704; 0 rows missed a detector or CfPubObj key in any window.
- **The numbers (a; medians of the runs above, `all` an outlier kept in the table):**
  - **Java observation, all 20 keys: 0.039 core-s per match of pool-thread CPU, 56-61 us per seat-row** (all2-4;
    0.063 / 91 us in `all`). Without cue: 0.029 core-s per match, 41 us per seat-row, so cue costs about 0.011 core-s
    per match (about 16 us per seat-row).
  - **Process cost of the observation** (with it minus without, all GC / allocation included): median 0.274 - 0.225 =
    **0.049 core-s per match** (range 0.03-0.15 over the pairings; `all` vs `noobs` gives 0.13). This is the value c3
    now uses in place of S3's guessed 0.05.
  - **Engine (facade) core-s per match: 0.17-0.19 of pool-thread CPU, 0.21-0.235 process** without the observation
    (S3's raw-crforge loop measured 0.19-0.21 WITH tok / mask / sc, on pod 32657).
  - A small run (1 cohort x 64 matches x 4 threads, `results/s3b4_smoke.json`) gave 26 us per seat-row and 0.10
    engine thread core-s per match: per-unit costs at 48 threads are about 2x those at 4 (b: SMT / cache sharing on a
    shared host, not separated).
- **Engine crash (a, new):** with random ability presses crforge itself threw on 1 match of `all2` and killed the
  first `nocue` run (`results/s3b4_nocue_crash.log`): `UnsupportedOperationException:
  EliteArcherHero_Ability_Triple_Shot_Projectile is shot by proj_..., which has no root, so the shooter would be its
  root, not modelled` (the hero Musketeer's ability shot). `CfLoop` now drops such a match (counted as
  `engine_crashes`) instead of stopping the loop. A real loop needs this decision too (F1 / crforge, not this ticket).
- **Not in this cost (b):** the GPU forward / decide (c2), the server's Python, the memory model's tables, and real
  table misses (here tables fill in warm-up; 109-136 keys were still filled in each window, about 1 per second).
- Threading changes to make the builders safe on a pool: the `missing` sets of `CfOppElixir.Keys`, `CfPubObj.Tables`
  and `CfCue.Tables` are concurrent sets (were LinkedHashSet; the harness only reads them between builds). `CfPubObj.build`
  takes buffer offsets.
- Command (pod 30408, `/workspace/s3b3d`): `OBSID_RL=/workspace/s3b3d/rl
  OBSID_CLXIII=/workspace/f1c/models/succ48_o_s91_u0075_grafted.pt OBSID_BUILD=/workspace/s3b3d/build_loop
  rl/scratchpad/gauntlet/L74/speed/crforge/obsid/run_loop.sh out/s3b4_all4.json --envs 2048 --cohorts 2 --threads 24
  --warm 90 --seconds 120 [--no-cue | --no-obs]` (`s3b4_chain*.sh` ran them in the order above).

## LOOP-MEM: memory v2 (e1_eval.Match._memory) in Java (`obsid/CfMem.java`, harness `JavaMem` in `obs_id.py`)

- **STATUS (updated each step).** Done: production trace (below), `CfMem.java` (observe / features / table + the CPython
  sum / hypot arithmetic), `JavaMem` builder + table / learner-rebuild checks in `obs_id.py`, `mem_arith.py` (arithmetic
  self-check), `mem_par.sh` / `mem_merge.py` (the harness over 14 processes). Measured so far: `mem_arith.py` (400k
  draws each: hypot 0, sum 0, round 0 bit differences; sigmoid float64 16,206 differ, float32 0); 2-match smoke
  (`/workspace/loopmem/out/smoke.json`): all 26 keys IDENTICAL on 1,804 seat-rows, 4 / 4 tables identical, learner rebuild
  1,804 / 1,804. Running (started 14:17Z): 56 matches live + 56 with presses. Pod 32657 `/workspace/loopmem` (rl = HEAD pipeline + links to /workspace/f1/rl; B0 =
  models/mem_best_ze.pt sha 3d75a25d).
  Restart: `OBSID_RL=/workspace/loopmem/rl OBSID_CLXIII=/workspace/loopmem/models/mem_best_ze.pt
  OBSID_BUILD=/workspace/loopmem/build /workspace/loopmem/rl/scratchpad/gauntlet/L74/speed/crforge/obsid/run.sh
  /workspace/loopmem/out/mem_live.json --n 56`; parallel: `MEM_CPU0=0 obsid/mem_par.sh /workspace/loopmem/out/live 56 14
  [--hero-abilities]` (same env), results in OUTDIR/merged.json.
- **What production computes (a, code at 70193b9).** B0 = `mem_best_ze.pt` (CLXIII + the S3-aux encoder, memory v2,
  zero_empty, coupling zero). `gen_row_keys` = the 20 keys + MEM_KEYS; `Match.gen_row` -> `_memory(policy, deck_card)`:
  `sample_sim(self.state, side)` (UN-extrapolated raw at the decision tick: `tower_reads_engine` on crown towers, own
  `elixir_exact`, `public_frame(source='sim')` bodies of both sides keyed `engine_key(catalog_card_form(card_id)[0])`),
  tick = `_cur[0]`; `MatchMemory.observe(..., plays = PublicObserver.plays + own_events)` (own_events = env.public_plays
  (act + 20, form, x, y) + own_ability_events of my side); `features(tick, gid, deck, 'v2')` = events(t) -> encode
  (newest 128, [128, 46]) + summary (54) + `_s1c` on `table(gid)` (60: priors, cycle, opp elixir, slots, king, margins,
  lock head). Record: `result()['memory'] = mem.table(gid)` -> rl_royale collate `mem_tab_*` (pack) + `mem_row_tab` /
  `mem_row_t`; the learner rebuilds rows by `rows_features` (vectorised, np.cumsum).
- **Arithmetic traps (a, code).** Python 3.12 (pods) `sum()` of floats is Neumaier-compensated (`_lost`, `_mean`, the
  Rocket sum): CfMem.pySum mirrors CPython; `math.hypot` = CPython vector_norm (pyHypot); the vectorised learner path
  uses plain cumsum, so rollout row == learner row is itself checked (`memory.stats.rebuild_*`).
- **API for LOOP-INT (`CfMem`, default package beside CfCore).** Shared: `CfMem.Tables` (fill once per JVM from Python,
  as `obs_id.JavaMem` does: `slugs` -> `cidSlug`, `fill_det` -> `detSlug`, `resolve` on `Tables.missing`, `unit`, the
  v2 LUT / lock head / regen arrays). Per facade core: `CfMem.Log(core, tables)`; the loop calls
  `log.play(side, actTick, cid, CfMem.Log.playForm(core, side, cid) /* read BEFORE giving the play */, x, y)` for every
  ACCEPTED play (x, y = the act's engine millitiles) and `log.press(side, tick, button)` for every accepted press. Per seat
  per match: `CfMem(core, tables, log, seat)` (`reset()` when the battle restarts in place); at each of the seat's
  decisions, AFTER that seat's `CfOppElixir.update()`: `while (!mem.observe(opp)) fill tables`, then
  `mem.features(deckCard /* the row's 8 gid ids */, buf, off)` writes the MEM_KEYS row at `off` (layout `CfMem.OFF_*`,
  `BYTES` = 26,192, native order). At the match end: `mem.table()` = the event table (TABLE_KEYS dtypes; `obs_id.JavaMem.
  java_table` converts) -> rl_royale's `result["memory"]`; each recorded row's `mem_t` = its decision tick.
  Bodies are kept only while an open outcome window can read them (a play arriving later than its tick's previous
  decision would throw: none in SIM, `late` counts them).
- **Result (a), pod 32657 `/workspace/loopmem`, pipeline at 70193b9, facade = HEAD CfCore.java on the cfspeed lib, B0
  both seats, sources pinned (`facade_src_sha256` in each JSON), 56 matches each (14 processes, `mem_par.sh`):**

  | cfg | JSON | seat-rows | MEM_KEYS (6) | other 20 keys | tables (both seats) | learner rebuild | plays / presses |
  |---|---|---:|---|---|---|---:|---|
  | live | `results/mem_live.json` | 51,396 | **identical** | identical | **112 / 112 identical** (12,340 events) | 51,396 / 51,396 | 3,968 / 0 |
  | live + `--hero-abilities` | `results/mem_press.json` | 53,782 | **identical** | identical | **112 / 112 identical** (11,861 events) | 53,782 / 53,782 | 3,531 / 479 |

  0 tick mismatches, 0 own-log mismatches, 0 play-form mismatches (CfMem.Log.playForm vs public_plays), 0 late plays.
  Coverage (`diag.memev_colNN` = tokens with column NN set, live): tower falls 1,298, X-Bow reach / done / locked
  85,765 / 63,560 / 26,901, answers 93,506, Rocket aimed / done 1,545 / 2,018; ability rows 74,646 (press run).
  **Never exercised (b): `rk_combo` (col 45 and summary 13: 0 in both runs; CLXIII made no Rocket within -24..+40 ticks
  of its own Tornado here).** The cost columns of these runs are NOT the cost (28 processes on shared cores: the cue's
  Java time read 494 us / row vs S3b-3f's 15.3); the clean cost run is separate (below).
