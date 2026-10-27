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

### c3. Projection (b): `project.py results/loop_n2048_c2_t24.json --extra-core-s 0.05`
CPU bound = the measured loop rate (720k/h on 48 threads), linear to the pod's vCPU minus 2, slowed by 0.05 core-s per
match for the observation parts not yet ported (b: 10x the measured Java tok / mask / sc cost of 0.005). GPU bound =
SPEED.md's rows/s on one 4090 (B >= 1,024, CLXIII inputs) x GPUs / 706 rows per match.

| pod | model, GPU path | CPU-bound matches/h | GPU-bound matches/h | **matches/h** | 300k | 1 M |
|---|---|---:|---:|---:|---|---|
| 54 vCPU + 1x 4090 | 1.76 M as today, fp32 | 626,711 | 48,580 | **48,580** | no | no |
| 54 vCPU + 1x 4090 | 1.76 M lazy refine, fp32 | 626,711 | 95,833 | **95,833** | no | no |
| 54 vCPU + 1x 4090 | 1.76 M lazy refine + bf16 | 626,711 | 227,035 | **227,035** | no | no |
| 54 vCPU + 1x 4090 | 10 M as today, fp32 | 626,711 | 22,324 | **22,324** | no | no |
| 54 vCPU + 1x 4090 | 10 M lazy refine + bf16 (b: CLXIII's x4.67) | 626,711 | 104,329 | **104,329** | no | no |
| 128 vCPU + 2x 4090 | 1.76 M as today, fp32 | 1,518,570 | 97,159 | **97,159** | no | no |
| 128 vCPU + 2x 4090 | 1.76 M lazy refine, fp32 | 1,518,570 | 191,667 | **191,667** | no | no |
| 128 vCPU + 2x 4090 | 1.76 M lazy refine + bf16 | 1,518,570 | 454,069 | **454,069** | yes | no |
| 128 vCPU + 2x 4090 | 10 M as today, fp32 | 1,518,570 | 44,648 | **44,648** | no | no |
| 128 vCPU + 2x 4090 | 10 M lazy refine + bf16 (b: CLXIII's x4.67) | 1,518,570 | 208,657 | **208,657** | no | no |

**What reaches 300k and 1 M per pod:**
- **CPU side** (b): 300k needs at most 0.62 core-s per match on 54 vCPU (52 usable) and the loop measured 0.19-0.21
  with the main tensors, so **300k: yes on both pods**. 1 M needs at most 0.19 core-s per match on 54 vCPU (**no**: about
  0.25 after the port) and 0.45 on 128 vCPU (**yes**: 1.5 M projected).
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
