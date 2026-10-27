# S1 speed: live decide profile, training per-match cost, batched rollout prototype (plan1026 Pillar 4a / 4b)

Labels: **(a) measured** (with n), **(b) plausible but untested**, **(c) contradicted**.
Pod 30408 = 1x RTX 4090, AMD EPYC 7702, cgroup quota **54 vCPU** (not 128: every pod number below is on 54 vCPU / 1 GPU).
Model = CLXIII NOLEAK (GenModel fv6, d 128 x 4 layers, cue_in + cell_refine + tower_refine, **1,759,432 params**).
Training recipe = `stepd/cfg/succ48_x_s101.yaml` (CLXIII's own recipe: league + W7 exploiters + opp_style on + ability
head + tau_phase + habit/crown tracking), fin15-linux, update 0 job lists built by the real trainer (`harness.py`).

## Summary

1. **Live decide (a).** The 10-26 laptop logs say p50 77 / p90 88 / p99 110 ms (27 sampled CLXIII logs, 10,552
   decisions). Replayed on the pod with the same code, model and options, a decide is **p50 19-21 ms on the 4090** and
   38 ms on CPU. **85% of it is two full forwards**: every decision that plays a card runs the whole trunk a SECOND
   time to get the cell logits (`live_gen.decide`: `self.model(b)` then `self.model(b, card=...)`). The
   observation (`row`) is 1.4-2.4 ms at p50 and the decode rules about 1 ms. The plan's guess "mostly Python and decode
   rules" is **(c) contradicted**: it is forward latency.
2. **Laptop vs pod (a + b).** The same CLXIII code logged **p50 40-41 ms** on 10-26 between 14:20 and 15:10 and 73-85 ms
   in every other sampled log. The code did not change, so about half of the typical 77 ms is the laptop's state, not
   the decide (b: the cause is untested; candidates are GPU sharing with the reader/emulator and power or clock state).
3. **Training per match (a).** One actor costs **11.7 s per match**: the CPU forward is 7.9 s (68%), the observation
   3.2 s (27%), and the engine 0.33 s (3%). Inside the observation, `sim_cue_rows` (a `Battle.save()` + JSON parse at
   every learner decision) costs about 1.9 s per match by itself, **6x the engine**.
4. **Batched rollout (a).** `pipeline/batched_rollout.py`, on 48 workers and 1 GPU (54 vCPU):
   **6,070 matches/h at N = 256, 9,611 at N = 1,024 and 11,869 at N = 2,048**, in fp32 and with **identical
   decisions** (d). **N = 4,096 did not fit**: this pod's container has a 62 GB memory limit, the run reached it and a
   worker died (EOFError). It needs about 15 MB per match in flight (b), so it needs a bigger pod or N split over two
   servers.
   The bottleneck after batching is shown in section c.
5. **What reaches 200-300k/h (b, from measured rates).** Two things together:
   - the observation must drop from about 5.3 to about 1.8 vCPU-s per match (128 vCPU);
   - the GPU must do about 25k rows/s per 4090. CLXIII does 9.5k in fp32 today; it would do 18.8k in fp32 and 44.5k in
     bf16 if the `cell_refine` / `tower_refine` features were computed only for the rows that place a card.

   Each of these is a separate change outside this ticket's write set (section e).

## a. Live decide profile

### a1. Logged decide_ms (laptop, RTX 5050, `--device cuda`, torch 4 threads)

| set | logs | decisions | p50 | p90 | p99 |
|---|---|---|---|---|---|
| 10-26, every 10th log, CLXIII | 27 | 10,552 | **77** | 88 | 110 |
| 10-26, CLXIV memory (1 log in the sample) | 1 | 377 | 84 | 103 | 126 |
| 10-26 14:20 (`live_play_20261026_142027`) | 1 | 310 | **40** | 54 | 70 |
| 10-26 14:31 (`..._143116`) | 1 | 332 | 41 | - | 72 |
| 10-26 13:04 (`..._130453`) | 1 | 328 | 73 | 84 | 107 |

Per-log medians across the sample: 73-85 ms, except 41 (14:31) and 62 (15:09). Tool: an inline scan of the `decision`
events (decide_ms = `pilot.decide(f)` wall, live_play.py:1433).

### a2. Replay of logged decisions (pod: EPYC 7702 + 4090), `live_profile.py`

The replay uses the real `live_gen_v2.GenPilot`, set up like `live_play.load_pilot` from the log's own start event:
decision_options, afford_ticks 23, identity_ext, LiveCues, tau / tau_phase, extrapolate 24, own_effects, hero spec
supplement, 4 threads. Every frame is observed, every 2nd frame after tick 150 is decided, and 300 decisions are taken
per run (ms; cuda timings are synchronized at each forward).

| run | decide p50 / p90 / p99 | row p50 / p99 | forward p50 (calls / decision) | rest p50 / p99 |
|---|---|---|---|---|
| 142027, cuda | **21.1** / 23.7 / 84.0 | 2.37 / 37.1 | **17.6** (2) | 1.05 / 13.1 |
| 130453, cuda | **18.8** / 21.9 / 96.0 | 1.36 / 32.3 | **16.0** (2) | 0.88 / 31.7 |
| 142027, cpu (4 threads) | **38.3** / 39.8 / 95.9 | 2.19 / 36.1 | **34.3** (2) | 0.97 / 4.8 |

- **forwards per decision: p50 2** (mean 1.98 / 1.88).
- The forward alone at batch 1 is 7.6-7.7 ms on cuda and 15.1 ms on CPU (4 threads).
- The p99 tail comes from rare `row` spikes of 32-37 ms (1% of decisions) and, in 130453, rare decode spikes.
- **One-forward decide (b, untested): cuda p50 about 21 -> 12 ms, CPU about 38 -> 21 ms.** It means computing
  `cell_logits_gen(enc, card, form)` from the first call's `enc` instead of a second `self.model(b, card=...)`. The
  outputs are the same by construction, but this needs an identity test. It is ticket B's decide()
  (`live_gen.py:454-464`, `live_gen_v2.py` decide path).

### a3. Forward cost vs model size

The table uses random weights except CLXIII itself, CLXIII's inputs (one real live batch), and the refine modules at
each width. Batch 1: cpu 4 threads / cuda (4090). Batch 1,024: rows/s on cuda.

| d x layers (heads) | params | cpu b1 ms | cuda b1 ms | cuda B 256 rows/s | cuda B 1,024 rows/s | cuda B 4,096 rows/s |
|---|---|---|---|---|---|---|
| **128 x 4 (4) = CLXIII** | 1,759,432 | 15.0 | 7.7 | 9,723 | **11,050** | 11,243 |
| 192 x 6 (6) | 3,972,616 | 21.0 | 7.6 | 7,194 | 7,927 | 7,934 |
| 256 x 6 (8) | 6,545,480 | 25.0 | 7.6 | 5,593 | 6,025 | OOM |
| 288 x 8 (9) | 10,069,672 | 35.6 | 9.4 | 4,124 | **4,378** | 4,336 |
| 320 x 8 (10) | 12,223,240 | 47.1 | 8.2 | 3,268 | 3,389 | OOM |

(a), `model_scale.py`, one 4090, fp32. There is no 15 M row: 15 M is about 2.7k rows/s by extrapolation (b). The
OOMs are allocator fragmentation in the sweep, not the model (288 x 8 fits at 4,096). The B = 1,024 rate of CLXIII is
11.0k here and 9.5k in `refine_cost.py`: two timing loops on the same model.

Batch 1 on cuda is **latency-bound** (about 6-8 ms whatever the width). The extra cost comes with more layers (more
kernel launches), not with a larger d (a: 128x4 -> 256x6 adds 0.6 ms). So for the live p99 gate, **prefer a wider
network over a deeper one**.

**RTX 5050 estimate (b).** No 5050 measurement exists. The laptop's own logs bound it. On a quiet laptop (p50 40) the
current decide is about 2 forwards x about 17 ms + about 6 ms. With the one-forward decide a 10 M 8-layer net costs
about 1 forward x 25-35 ms + about 6 = **31-41 ms at p50**. Under the typical load (p50 77, so about 35 ms per forward)
it is about 55-75 ms. The p99 adds the 30-40 ms `row` spikes. So **p99 < 100 ms at 5-15 M is plausible only with the
one-forward decide**, and with the two-forward decide it fails at about 10 M. The check owed is to run
`model_scale.py` on the PC (about 2 min of GPU) when live is not running. It must not run on the laptop while it plays.

## b. Training per-match cost (one rl_royale actor, CPU forward, 1 thread)

`harness.py --mode ref --timing` builds the update-0 job list with the real trainer, runs `rl_royale.actor_main`
in-process and calls `e1_eval.run_selfplay_batch` with in_flight 8. **n = 32 matches, 22,556 policy rows (705 per
match: learner 364 + opponent 341), 375 s = 11.7 s per match** (cProfile run: 13.6 s per match).

| phase | s per match | share | what |
|---|---|---|---|
| policy forward (CPU, about 4 rows per call) | **7.94** | 68% | `GenPolicy.forward_batch`, 5,611 calls, about 11 ms per row |
| observation: `gen_row` | **2.38** | 20% | of which `sim_cue_rows` about 81% (cProfile): **`royalesim.Battle.save` 3.4 ms + JSON parse at every learner decision** |
| observation: `prepare` | **0.81** | 7% | live_view about 40% (`mine_classes` about 24%: CORRECTED in S1b, section f -- three one-off CardDB loads per process, already cached, not a per-call cost), `ability_commands` about 30%, public observer about 21%, from_engine about 14% (cProfile shares) |
| engine (advance + raw + reset) | **0.36** | 3% | matches REPORT_engine's 0.3-0.4 core-s |
| decide (sample + styled, incl. 2,138 cell calls) | about 0.25 | 2% | per-row styled decode for every opponent |
| apply / pre / result | 0.04 | <1% | |

So the "~13 actor-s per match" is (a) confirmed: 11.7 s here, 13.6 s under the profiler. Without the forward the CPU
work is **3.8 s per match** in one quiet process. Under 48 parallel workers on this pod it measured **5.3 vCPU-s**
(N = 1,024: due 0.47 + prepare/row 4.14 + decide 0.50 + reset/apply 0.15), about 1.4x slower per process (a; the cause
is untested, b: SMT siblings and boost clocks on a shared host).

## c. Batched rollout prototype (`pipeline/batched_rollout.py`)

**Design.**
- W forked CPU workers each own their matches (`SelfPlayMatch` on any `make_env`; nothing reads the engine, so
  crforge's facade plugs into the same seam).
- Per round each worker runs `due()`, `prepare()` and `gen_row()` for every deciding side and sends the rows.
- The server (main process, GPU) runs **one `forward_batch` per policy group over all of the cohort's workers**. It
  returns gate, card, p, hand and g. The `enc` tensors stay on the GPU.
- Workers run the unchanged decide functions (`DECIDE` = run_selfplay_batch's per-group rule) on CPU with their own
  RNGs. Each decide runs in a thread, and its only device call (`cell_logits`) goes through a stub. All parked calls of
  a worker go out as ONE request per wave, and the server answers every worker's requests with one cell call per
  policy. Styled opponents decode per row (styled_decisions is per-row by construction), and their calls still share
  one wave.
- Workers are split into 2 cohorts served in turn, so one cohort's CPU work overlaps the other cohort's forward.
- Swapping in ticket B's unified decide() means replacing `DECIDE` (same arguments).

**Measured (a), CLXIII recipe, update-0 specs, W = 48 workers on 54 vCPU, 1x 4090, fp32, all N matches in flight**
(matches/h = N / wall, including the batch tail as an update sees it):

| N | cohorts | wall s | **matches/h** | server forward s / calls / rows per call | server waiting s | worker CPU s (mean) | worker waiting s |
|---|---|---|---|---|---|---|---|
| 256 | 1 | 187 | 4,925 | 94.5 / 4,597 / 38 | 82.8 | 37 | 138 |
| 256 | 2 | 152 | **6,070** | 101.1 / 9,051 / 19 | 39.9 | 38 | 104 |
| 1,024 | 2 | 384 | **9,611** | 201.3 / 9,304 / 74 | 156.4 | 112 | 257 |
| 2,048 | 2 | 621 | **11,869** | 297.7 / 9,354 / 146 | 286.1 | 204 | 388 |
| 4,096 | 2 | - | **did not fit** (62 GB container limit reached, a worker died) | | | | |
| 1,024 **bf16** (not identical) | 2 | 490 | 7,531 | 307.7 / 9,296 / 74 | 153.6 | 111 | 363 |
| ref: 1 actor, in_flight 8 | - | 375 (32 matches) | 307 | CPU, 4 rows per call | - | - | - |
| today's trainer (48 actors) | - | about 117-140 per 256 | about 4,600 per pod (DISTRIB.md) | | | | |

**Bottleneck after batching (a).**
- The server forward costs 11 / 22 / 32 ms per call at 19 / 74 / 146 rows per call (the batch-1 latency is
  6-8 ms). The league puts about 8 distinct policies in every round: the learner, league snapshots, W7
  exploiters and externals. So **a round costs about 8 forwards, and rows per forward stay small**: at N = 1,024 the
  server runs at 3.4k rows/s against the 9.5k rows/s the same model does at batch 1,024.
- The second limit is the **observation CPU**: 5.3 vCPU-s per match caps 54 vCPU at about 36k matches/h and 128 vCPU at
  about 87k matches/h. That holds even with a perfect GPU. At N = 2,048 the measured worker CPU is 4.8 vCPU-s per
  match.
- **Both sides idle about half the time** (N = 2,048: server waits 46% of the wall, workers 62%). One cohort's CPU
  round (about 340 ms) is longer than the other cohort's forward (about 250 ms), so 3+ cohorts or an asynchronous queue
  (b) would push GPU use up.
- **bf16 autocast made it slower** (N = 1,024: 7,531 vs 9,611 matches/h; forward 308 vs 201 s). At 74 rows per call
  the cast overhead outweighs the math, which confirms the server is overhead-bound, not FLOP-bound (a). Only 96 / 1,024
  matches kept the fp32 actions.

**GPU budget (a, B = 1,024 rows/s on one 4090, CLXIII inputs; `refine_cost.py`):**

| CLXIII forward | fp32 | bf16 autocast |
|---|---|---|
| as today (cell_refine + tower_refine features for EVERY row) | **9,527** | 16,091 |
| without cell_refine features | 14,470 | 27,428 |
| without tower_refine | 11,274 | 20,313 |
| without both (as if computed only for the rows that place) | **18,794** | **44,524** |

Both refine modules feed only `cell_logits_gen` (`model_gen.py:417-427`; `cell_feat` / `tower_cell_feat`), and only
about 3% of rows (the playing ones) ask for cell logits. So **computing them lazily in `cell_logits` is a pure
refactor** (b: identity untested), and it doubles fp32 throughput. CLXIII itself was trained with `amp: bf16`.

**What 250k/h needs (b, arithmetic on the measured rates).** 250k/h is 69.4 matches/s, which is **49k policy
rows/s** at 705 rows per match.
- **GPU:** 2x 4090 must do 24.5k rows/s each. CLXIII fp32 today does 9.5k (2 GPUs give about 97k matches/h). Lazy
  refine in fp32 does 18.8k (192k/h). **Lazy refine + bf16 does 44.5k (454k/h)**, or lazy refine + fp32 + opponents
  deciding every 20 ticks instead of 10 (about 0.75x the rows, about 256k/h).
- **CPU:** 128 vCPU at 250k/h means **1.84 vCPU-s per match** against 5.3 measured. Rough gains:
  - `sim_cue_rows` via an engine accessor instead of `Battle.save()` + JSON: -2.5 vCPU-s;
  - (`mine_classes` is already cached: 0, see section f);
  - `ability_commands`: -0.3.

  Together these give about 2.2 vCPU-s per match (about 210k/h on 128 vCPU). **300k/h needs about 1.5 vCPU-s per
  match**, which means a vectorized or native observation builder.
- **Server protocol:** the per-round forward count must not grow with the opponent pool. That needs either larger N per policy (memory: about 15 MB per match in flight)
  per cohort, CUDA graphs for the 8 small forwards, or concurrent streams. A double pod is 2 servers (1 per GPU), each
  with about 60 workers.

**Model size vs the 4b budget (c).** "A ~10 M learner + a ~10-20 M opponent roughly fill two 4090s" at 250k/h is
contradicted by the forward rates: one 4090 does 4.4k rows/s at 10 M (fp32, B 1,024), so 49k rows/s
needs about **11 4090s** in fp32. Even if lazy refine and bf16 gave a 10 M net the same 4.7x they give CLXIII
(untested), that is still about 2.4 GPUs for the learner alone, before any 10-20 M opponent. At 250k/h on 2 GPUs the
budget fits about a 2-4 M policy (lazy refine + bf16). The alternative is fewer rows per match (opponents deciding
every 20 ticks), or a rollout opponent much smaller than the learner.

## d. Identity check (batched decide == e1_eval sample_decide_batch / styled path, row for row)

The fixed seed set is the update-0 job list of `succ48_x_s101` (seed 101): E = 8 x G = 4 = 32 matches, both sides,
with the same `rollout_jobs` seeds. The reference is `--mode ref` (the real actor path, CPU forward, in_flight 8).
`compare.py` matches the two runs by (tag, k, side) and compares sha256 over every recorded traj array.

| candidate | matches obs-identical | matches action-identical | rows action-identical | max abs delta log-prob (gate / card / cell) | outcomes |
|---|---|---|---|---|---|
| batched, server cpu, W 4, 1 cohort | **32 / 32** | **32 / 32** | **11,657 / 11,657** | 4.7e-6 / 2.7e-6 / 1.0e-5 | 32 / 32 |
| batched, server **cuda** (4090 fp32), W 4, 2 cohorts | **32 / 32** | **32 / 32** | **11,657 / 11,657** | 7.1e-6 / 8.4e-6 / 1.0e-5 | 32 / 32 |
| (earlier) E 2 x G 2, server cpu, W 2 | 4 / 4 | 4 / 4 | 1,425 / 1,425 | 3.5e-7 / 0 / 0 | 4 / 4 |

- The log-prob deltas are float noise from a different batch composition (and device), the same kind DISTRIB.md saw
  between N = 24 and N = 48. The stored `lp_*` bits therefore differ, as they already do between actor counts.
- **"Identical update-0 rows" in the bit sense (batch_sha) holds only up to that noise (c for bit identity, a for
  action / observation identity).** A bit-identical batch would need the same row grouping as the actor, or fp64.
- Engine-free unit test: `pipeline/tests/test_batched_rollout.py` (3 tests). It checks that the threaded wave decide
  equals `sample_decide_batch` (a group) and `styled_decisions` (per row) exactly, that all of a round's cell calls go
  out in ONE wave, and that a task's exception reaches the caller.

## e. Next changes, in order of gain (each outside this ticket's write set; owners as noted)

1. **One-forward live decide** (ticket B): live p50 about -45% (a2).
2. **Lazy refine features** (model_gen `encode_gen` -> `cell_logits_gen`): GPU rows/s x2 fp32, x4.7 with bf16; needs an
   identity test.
3. **`sim_cue_rows` without `Battle.save()` + JSON** (an engine-side unit-state accessor; for crforge it is part of the
   facade): about -45% of rollout CPU per match.
4. **Fewer forwards per round:** a larger N per server (memory permitting), CUDA graphs and 3+ cohorts. bf16 only pays at large batches (measured slower at 74 rows per call). Rows over shared memory instead of pickled
   pipes only if the server shows pickle time.
5. A bf16 rollout server only with a PPO-ratio check (the learner recomputes in fp32 or bf16; the stored log-probs then
   differ).

## Files and commands

- `pipeline/batched_rollout.py`: the prototype (`run(make_env, learner, opponents, jobs, cfg, on_result, ..., workers,
  in_flight, device, cohorts, amp)`).
- `pipeline/tests/test_batched_rollout.py`: engine-free identity tests.
- `speed/harness.py`: builds the trainer's update-0 jobs and runs `actor_main` in-process, in ref or batched mode.
- `speed/timing.py`: per-phase wall clock.
- `speed/compare.py`: the identity check.
- `speed/live_profile.py`: (a2).
- `speed/model_scale.py`, `speed/fwd_ops.py`, `speed/refine_cost.py`: (a3, c).
- `speed/setup_pod.sh`: builds venvf15 on a fresh pod from PyPI plus the royalesim / royalegym packages copied from
  pod 32657.
- Pod 30408 `/workspace/speed/` holds every run directory: meta.json, batched_stats.json, results.jsonl, timing.json,
  live/*.json, prof_e2g2/prof.pstats.

```
cd /workspace/cb; export ROYALE_RUNTIME=fin15-linux PYTHONPATH=/workspace/cb; P=/workspace/venvf15/bin/python
$P scratchpad/gauntlet/L74/speed/harness.py --cfg scratchpad/gauntlet/L74/stepd/cfg/succ48_x_s101.yaml --E 8 --G 4 --mode ref --timing --out /workspace/speed/ref_e8g4
$P scratchpad/gauntlet/L74/speed/harness.py --cfg ... --E 8 --G 4 --mode batched --workers 4 --device cuda --out /workspace/speed/id_e8g4_cuda
$P scratchpad/gauntlet/L74/speed/compare.py /workspace/speed/ref_e8g4/results.jsonl /workspace/speed/id_e8g4_cuda/results.jsonl
$P scratchpad/gauntlet/L74/speed/harness.py --cfg ... --E 256 --G 4 --mode batched --workers 48 --cohorts 2 --device cuda --out /workspace/speed/b_n1024_w48_c2
```

## f. S1b: fast paths, one at a time, each with the identity check (10-27)

**Setup.**
- Identity: E8 x G4 = 32 matches against `ref_e8g4` (the actor path). Pass = observations and actions identical and
  log-probs within 1e-5.
- Throughput: N = 2,048 on pod 30408 (54 vCPU, 1x 4090, W 48, 2 cohorts, fp32).
- vCPU-s per match = the workers' CPU work (due + prepare_row + decide + apply + reset), not their waiting
  (`summ.py`).
- Each step is added on top of the previous one.

| step | identity (32 matches) | matches/h | worker vCPU-s / match | server forward s (stack / device) | cell s | server waiting s |
|---|---|---|---|---|---|---|
| baseline (S1) | (S1 d: pass) | 11,869 | 4.78 | 297.7 | 12.5 | 286.1 |
| + (1) refine: `LazyRefine` | **pass** (32/32, 11,657 rows, max delta 1.0e-5) | 11,812 | 4.84 | 298.4 (41.2 / 253.7) | 12.7 | 288.7 |
| + (2) cue: `fast_obs.sim_cue_rows` | **pass** (the obs sha covers the cue arrays) | 11,788 | **4.39** | 309.1 (43.6 / 261.8) | 8.4 | 272.9 |
| + (3) merge: same-architecture opponents in one vmapped call | **pass** | **12,445** | 4.29 | 287.7 (28.7 / 202.5); 3,466 single + 1,180 merged calls (was 9,354 calls) | 8.1 | 262.7 |
| + (4) bf16 autocast (on top of 1-3) | **FAIL**: 6 / 32 matches identical; first divergence **0.45% per decision** (E8 x G4), **0.59%** at N = 2,048 (197 / 2,048 matches identical) | 10,190 (slower) | 4.36 | 417.7 (28.3 / 331.4) | 10.4 | 259.3 |
| extra: workers at os.nice 10 (1-3) | pass | 12,273 (no gain) | 4.44 | 281.6 | 7.9 | 280.8 |
| extra: 3 cohorts (1-3) | - | 11,513 (worse than 2) | 4.65 | 294.6 (28.2 / 200.4); 5,199 + 1,765 merged | 11.2 | 303.0 |

**What each step did (a unless labelled).**
1. **refine: no gain in training (a), and the reason was missed in S1.**
   - The training learner (`rlarm_succ48_o_s91_u0075.pt`, 1,546,536 params) and every league opponent have **no
     cell_refine / tower_refine**. Only the grafted deployed CLXIII (1,759,432) carries them.
   - So S1's 9.5k -> 18.8k rows/s figure applies to the deployed model (live, and evaluation of grafted checkpoints),
     not to training rollouts. `league_mix.py`: 7 opponent files; each is fv5 or fv6, d 128 x 4, no refine, and only
     the learner's own init has a cue layer.
   - `LazyRefine` is kept: it is correct on CLXIII (`test_lazy_refine_equals_genpolicy`: heads within 1e-6, cell
     logits within 1e-5, identical argmax).
2. **cue: -9% worker CPU (4.78 -> 4.39 vCPU-s per match), matches/h flat** because the run is server-bound.
   - The saving comes from skipping `Battle.save()` when no unit token can take a cue, with the buff memo still
     updated from `state_json` (`test_memo_update_equals_extract_memo`), and from not decoding the projectiles /
     areas / catalogue that the cue rows never read (`test_extract_units_equals_extract`).
   - Most decisions do have a unit token, so `save()` (3.0 ms, 36 KB) still runs there. No Battle method exposes
     attack_ms / jumping / dash_state / speed without `save()` (`probe_battle.py`). The remaining fix is an
     engine-side unit-state call (fin16 or the crforge facade), outside this write set.
   - `mine_classes` correction: it is already cached per deck config. Its cProfile share was 3 one-off CardDB loads
     (0.66 s each, per process), not a per-call cost; S1's "-0.3 s per match" for it is withdrawn.
3. **merge: +4.9% matches/h.**
   - The 5 league externals share one architecture, so their 5 forwards per round become 1 vmapped call
     (`batched_rollout.Merged`: `stack_module_state` + `vmap(functional_call)`). Server stack + device time fell
     305 -> 231 s.
   - `test_merged_forward_equals_separate`: heads within 1e-5, cell logits within 1e-4.
   - The isolated probe (`merge_probe.py`, 5 x 146 rows) gave 64.5 -> 57.2 ms. Same-architecture forwards are close
     to compute-bound already, so merging cannot do much more.
4. **bf16: rejected.** Decisions diverge at 0.45-0.59% per decision, and it is slower at the batch sizes the server
   sees (cast overhead). It is not usable for identical rows.

**The bottleneck after steps 1-3 is the server loop itself (a).**
- The server waits on cohorts about 44% of the wall and workers wait about 62%.
- A real server forward of 146 rows takes 12.8 ms alone (`server_prof.py`: stack 1.8, H2D 0.6, heads_t 10.4 ms;
  321 kernel launches) but 27-31 ms inside the rollout. The 2x slowdown under load is measured; its cause is untested
  (b). os.nice on the workers did not help (a), and CFS throttling is negligible (30408: 147 throttled periods in
  87k).
- The next protocol change is an asynchronous server (b, not built): it forwards whatever rows are queued instead of
  a lockstep cohort.

## g. Double pod 33308 (measured, not projected): 108.8-core quota, 2x 4090, 125 GB container limit

Fast paths refine + cue (merge was still being identity-checked when this chain started; GPU 1 was shared with ticket S2, see below), fp32, 2 cohorts per server.
Memory is about **19.5 MB per match in flight + 0.41 GB per worker** (a: from the two 1-GPU runs).

| config | N in flight | wall s | **matches/h** | worker vCPU-s / match | server forward s (stack / device) | server waiting s | container max memory |
|---|---|---|---|---|---|---|---|
| 1 server (GPU 0), W 100 | 2,048 | 529 | **13,942** | 4.89 | 294.3 (39.6 / 251.1) | 183.0 | 81 GB |
| 1 server (GPU 0), W 100 | 4,096 | 927 | **15,907** | 4.63 | 498.7 (102.1 / 386.8) | 343.7 | **121 of 125 GB** |
| 2 servers (GPU 0 + 1), W 50 each, 1,024 each | 2,048 | 387 / 742 | 9,517 + 4,967; **9,936 aggregate** (2,048 in 742 s) | 4.92 / - | GPU1: 555.5 (**292.6** / 210.1) | | |
| 2 servers, W 50 each, 2,048 each | 4,096 | 665 / 973 | 11,087 + 7,581; **15,155 aggregate** (4,096 in 973 s) | 4.64 / 4.75 | GPU1: 660.0 (**291.5** / 313.8) | | 121 GB (high-water mark) |
| 1 server on GPU 1 alone, seed 202, W 50 | 1,024 | 709 | 5,202 | 4.81 | 545.2 (**289.0** / 204.2) | 87.3 | |
| 1 server on GPU 0 alone, seed 202, W 50 (control) | 1,024 | 361 | **10,204** | - | 205.9 (23.5 / 179.3) | 128.2 | |

- **The 2-GPU numbers are contaminated: GPU 1 was in use by ticket S2 (a).** `nvidia-smi` shows pid 605397
  (`pipeline.train_gen --data /workspace/scale/...`, running 1 h 10 min, 92% util, 20 GB) on GPU 1. The control
  separates the cause: the same seed-202 job list ran normally on GPU 0 (10,204/h, stack 23.5 s) and slowly on
  GPU 1 (5,202/h, stack + H2D 289 s, cell 54.5 s). It is GPU sharing, not the seed and not the PCIe link (pinned H2D
  16-20 GB/s on both GPUs; both on NUMA node 0).
- **So the clean 2-GPU measurement is still owed.** It needs both GPUs free of S2. The one valid point is the GPU 0
  half of each 2-server run: 9,517/h (1,024 matches, W 50) and 11,087/h (2,048, W 50). Two free servers would
  therefore give about 19-22k/h (b: 2 x the GPU 0 half; the cores are not the limit, workers wait 66-70%).
- **At 108.8 cores the prototype is server-bound at about 14-16k matches/h** (workers wait 70% of the time). The CPU
  ceiling at the measured 4.3-4.9 vCPU-s per match is 80-91k/h, and the isolated GPU rate (11-15k rows/s per 4090 at
  146-600 rows) is about 55-75k/h per GPU.
- N = 4,096 fits on this pod only with a single server (121 of 125 GB).

## h. Laptop RTX 5050, batch-1 forward (a): live idle

The supervisor log ended 05:20 and the last live log was 04:29; MuMu was open but not playing. One run, 61 s,
`model_scale.py --b1-cuda-only`, CLXIII inputs, refine modules at each width:

| model | params | cuda batch-1 ms |
|---|---|---|
| CLXIII 128 x 4 | 1,759,432 | **45.9** |
| 224 x 6 | 5,179,176 | 44.8 |
| 288 x 8 | 10,069,672 | 46.5 |
| 320 x 10 | 14,689,160 | 45.0 |

- **Flat at about 45 ms from 1.8 to 14.7 M (a).** On the laptop the forward is bound by launch / driver overhead,
  not by compute. The 4090 pod does the same forward in 7.7 ms.
- So on the PC the model size (up to 15 M) costs about nothing at batch 1, while each extra forward costs about
  45 ms. The live decide runs 2 per decision, which is the logged p50 77 ms.
- The one-forward decide (ticket B) is about -45 ms per playing decision (b).
- CUDA graphs or a CPU forward (on the pod, CPU 4 threads: 15 ms at 1.76 M, 47 ms at 12 M) could cut it further;
  both are untested on the laptop (b).
- Implication for 4a (b): the p99 < 100 ms gate depends on the number of forwards per decision and the per-launch
  overhead, not on 5 vs 15 M.

## i. Projection for 128 vCPU / 2 GPUs (b, from sections f-g)

- **With this lockstep prototype: about 16k matches/h on one server, measured (a: 15.9k at N = 4,096 on 108.8
  cores), and about 19-22k/h with two free GPUs (b: 2 x the GPU 0 half; the GPU 1 runs shared their GPU with S2).**
  The servers are the limit, not the cores.
- With an asynchronous server (not built) the limit moves to the workers. 4.3 vCPU-s per match on 128 vCPU is about
  **107k/h**; the 2 GPUs give about 110-150k/h at the isolated rates.
- **200-300k/h still needs the observation CPU cut to 1.5-2.3 vCPU-s per match.** The `Battle.save()` cue path is the
  largest single item, and it needs an engine accessor (fin16 / crforge facade).

## j. S4: async GPU decide server, rows/s per model size and precision, the slowdown explained (pod 30408, 1x 4090)

Rows are CLXIII feature-version-6 shapes: the live row fixture `results/live_batch1.pt`, jittered and tiled. Models:
- **1.76M = the real CLXIII weights**, behind `LazyRefine`, so the forward cost equals the training models (no refine);
- 5 / 10 / 15M = the same architecture wider and deeper, with random weights: 224 x 6, 288 x 8, 320 x 10;
  5,179,176 / 10,069,672 / 14,689,160 params.

Script: `s4_bench.py` (parts forward / server / slow / precision) and `shape_probe.py`. Results:
`results/s4/*.json`.

### j1. The server (`pipeline/policy_server.py`): no barrier, measured

**What it does.**
- Producers `submit` row blocks whenever they have them.
- One thread takes whatever is queued, up to `max_batch` rows (it waits at most 1 ms for a fuller batch). It runs one
  stack into pinned buffers, one H2D and one forward.
- Then it runs **the P1 decide** (`decision_options.decide`, decode 'sample', each row with its own rng). The cell
  logits come from the same forward's encodings.
- Forward modes: eager, CUDA graphs (padded buckets of 64-8,192), and torch.compile.

**Identity (a), fp32: `tests/test_policy_server.py`.**
- 4 blocks of 5 / 7 / 3 / 9 rows were merged into ONE batch. play / slot / cell / why equal the same decide run block
  by block, and log-probs are within 1e-5.
- On CUDA, graphs and compile match eager heads (atol 1e-4 on logits, 1e-5 on p).
- On the fixed 2,048-row obs set, fp32 decisions are bit-stable run to run (change rate 0.0, `precision` part below).

**End to end, 1.76M, eager, max_batch 2,048 (a).**

| producers x block | decide | rows/s | mean batch | server time split |
|---|---|---|---|---|
| 16 x 256 | off (forward only) | **19,968** | 2,048 | forward 97%, stack 3.6%, idle 0% |
| 64 x 64 | off | 19,353 | 2,048 | forward 94%, stack 6% |
| 16 x 256 | **on, in the server thread** | **14,336** | 2,048 | forward 70%, decide 28% (about 20 us per row) |
| 64 x 64 | on | 13,721 | 2,048 | |
| 16 x 256 | on, decide in a 2nd thread | 12,275 (slower) | 1,792 | the GIL; and the refine swap raced a concurrent cell call (72 AttributeErrors) -> now refused for refine policies and off by default |

- **Without a barrier the GPU runs at its plateau (20.0k rows/s vs 21.0k in the bare loop).**
- The decide costs about 20 us per row of Python. At 21k rows/s that is 0.42 core, so it must run outside the
  server's process (b): in the producers (crforge's Java side, or Python producer processes), with only the cell call
  coming back to the GPU. Not built.

### j2. Forward rows/s, one 4090, fp32 (a): `forward` part

| model | B 256 | 512 | 1,024 | 2,048 | 4,096 | 8,192 | CUDA graphs B 256 / 1,024 / 2,048 |
|---|---|---|---|---|---|---|---|
| 1.76M | 15,824 | 18,389 | 20,012 | **21,038** | 20,958 | 20,418 | 20,094 / 20,950 / 21,221 |
| 5M | 7,695 | 8,206 | 8,437 | **8,638** | 8,602 | OOM | 8,416 / 8,554 / 8,639 |
| 10M | 4,357 | 4,489 | **4,606** | 4,543 | 4,539 | OOM | 4,571 / 4,636 / 4,541 |
| 15M | 2,770 | 2,834 | **2,849** | 2,796 | OOM | OOM | 2,859 / 2,862 / OOM |

- **CUDA graphs help only at small batches** (1.76M at B 256: +27%). At B >= 1,024 the forward is device-bound.
- **torch.compile** (max-autotune, no cudagraphs) gave 19,864 / 21,090 at B 256 / 512 for 1.76M, the same as graphs.
  It spends minutes autotuning each shape, so the run was stopped and it is not used (a).
- The OOMs at large B come from the graph pools and caching of earlier buckets in the same process (the server
  bounds max_batch).

### j3. Precision on the plateau (B 1,024 / 2,048 best), achieved TFLOPS, decision change vs fp32 (a)

FLOPs per row are counted by `torch.utils.flop_counter` on the unfused fp32 forward. The decision-change rate is
over 2,048 fixed jittered rows, the same per-row rng seeds, with a quarter of the rows forced to play.

| model | GFLOP / row | fp32 rows/s (TFLOPS) | TF32 rows/s (TFLOPS), change | bf16 rows/s (TFLOPS), change |
|---|---|---|---|---|
| 1.76M (real CLXIII) | 0.425 | 20,925 (8.9) | 28,399 (12.1), **0.20%** | 47,072 (20.0), **0.34%** |
| 5M | 1.759 | 8,686 (15.3) | 10,325 (18.2), 0.39% | 19,085 (33.6), 8.8% |
| 10M | 3.751 | 4,615 (17.3) | 5,574 (20.9), 0.64% | 11,000 (41.3), 6.0% |
| 15M | 5.719 | 2,845 (16.3) | 4,370 (25.0), 0.54% | 7,974 (45.6), 5.2% |

- TF32 is +19-54%. bf16 is x2.2-2.8.
- The 4090's vendor peaks (b, spec sheet, not measured here) are fp32 82.6, TF32 tensor 82.6 and bf16 tensor 165
  TFLOPS dense. So **fp32 reaches 11-21% of peak and bf16 12-28%**. The forward is not purely matmul-bound: it also has
  attention softmax, layer norms, GELU, embeddings and global features.
- **The 5-15M change rates come from random weights** (near-flat logits flip on small perturbations). Only the 1.76M
  row (real weights: 0.20% TF32, 0.34% bf16) speaks for a trained model (b).
- **fp32 is the only identical path (a), and it runs on CUDA cores.** For hardware (b):
  - a GPU wins on the identical path only through fp32 non-tensor throughput (and memory bandwidth);
  - tensor-core datacenter parts help only if TF32 / bf16 decisions are accepted (a 0.2-0.34% per-decision change on
    CLXIII);
  - **the A100's fp32 non-tensor peak (19.5 TFLOPS) is below the 4090's 82.6**, so A100s would be slower than 4090s
    for the identical path.
- `gpu_bench/` measures this grid on the candidate card rather than projecting it.

### j4. Max matches/h per 4090 (b: plateau rows/s x 3,600 / rows per match; the GPU alone)

| model | fp32 (identical) 706 / 534 / 320 rows | TF32 706 / 534 / 320 | bf16 706 / 534 / 320 |
|---|---|---|---|
| 1.76M | **107k / 142k / 237k** | 145k / 191k / 319k | 240k / 317k / 530k |
| 5M | 44k / 59k / 98k | 53k / 70k / 116k | 97k / 129k / 215k |
| 10M | 24k / 31k / 52k | 28k / 38k / 63k | 56k / 74k / 124k |
| 15M | 15k / 19k / 32k | 22k / 29k / 49k | 41k / 54k / 90k |

- **(c) S3's "227k/h on one 4090 at 1.76M" needs bf16 (+ lazy refine).** On the identical fp32 path it is 107k at 706
  rows per match.
- 300k/h on one 4090 at 1.76M fp32 needs about 250 rows per match.
- These ceilings assume the decide runs off the server (j1). With the decide in the server thread they are about
  x0.68.

### j5. The 12.8 -> 27-31 ms forward slowdown inside S1's rollouts: first sight of each batch shape (a)

`slow` part + `shape_probe.py`, 1.76M, eager:

| condition | ms per 146 rows |
|---|---|
| constant B 146 | 11.4 (15.1 in the probe run) |
| 8 different models alternating, B 146 | 11.5 |
| 48 CPU-burner processes, B 146 | 11.9 |
| a new batch size every call (19-700), first pass | **92.5** (232 ms per call) |
| the same 200 sizes, second pass | **8.45** |
| 20 sizes after each was seen once | 8.52 |
| new sizes padded to the next power-of-two bucket | 11.7 |

- **The cause is the first use of each batch shape: about 210 ms each** (kernel and algorithm selection / caches).
- It is **not CPU contention** (48 burners: +4%), **not the model switching**, and **not the allocator** (39 device
  allocations, 0 retries, 0 frees).
- S1's server saw an unbounded variety of row counts (19-700), so many calls paid first-sight costs. The 27-31 ms was
  an average over those.
- **Fix: pad to a few fixed buckets** (`policy_server.bucket`; the graphs / compile modes already do), or warm every
  bucket at start.

### j6. GPU bench bundle for the candidate card (`gpu_bench/`)

`make_bundle.sh` builds `gpu_bench.tgz`: pipeline/ at HEAD plus the S4 scripts, the fixture and the CLXIII checkpoint.
The tarball is a build artifact and is never committed (icebow/data).

`bench_gpu.sh`:
- records GPU / driver / torch / CUDA / cuDNN;
- makes a venv that sees the image's torch (`FRESH=1` installs torch cu128 instead);
- runs the j3 grid (precision part: 4 sizes x fp32 / TF32 / bf16, B 1,024 / 2,048, FLOPs, change rate) and the j2
  grid (eager + graphs, B 256-8,192);
- writes `/workspace/out/gpu_bench.json` + `bench.log` and prints DONE.

torch.compile is left out (no gain, minutes per shape).

Dry run on 30408 (4090, `FRESH=1`, so torch 2.11.0+cu128 was installed from scratch), measured:
- **381 s wall**: setup 113 s (venv + torch + deps), precision grid 100 s, forward grid 166 s. All 12 precision rows and 48 forward rows were written, and DONE was the last line.
- The numbers reproduce j2 / j3 within 1.5% (1.76M fp32 21,091 / TF32 28,193 / bf16 47,175 rows/s; same change rates).
- On a card with more memory the OOM cells will run, so the time grows. It stays far under 40 min (b).
- Usage: `tar xzf gpu_bench.tgz -C /workspace && bash /workspace/gpu_bench/bench_gpu.sh` (`GRID=quick`: 1.76M only).

## k. RTX PRO 6000 Blackwell (Server Edition, 96 GB) vs RTX 4090 -- 10-27, gpu_bench bundle, results/gpu_bench_pro6000/
Same bundle as the 4090 dry run (torch 2.8.0+cu128). Wall 210 s. Pod cgroup = 27.2 cores (cpu.max), not 32.
Plateau rows/s (B 2048), PRO 6000 / 4090 (ratio):

| model | fp32 | TF32 | bf16 | bf16 decision change (PRO 6000) |
|---|---|---|---|---|
| 1.76M (CLXIII) | 41.1k / 21.0k (1.96x) | 45.2k / 28.4k (1.59x) | 68.8k / 47.1k (1.46x) | 0.49% |
| 5M  | 13.8k / 8.7k (1.59x) | 17.6k / 10.3k (1.71x) | 27.8k / 19.1k (1.46x) | 9.2% (random weights) |
| 10M | 7.4k / 4.6k (1.61x) | 9.8k / 5.6k (1.75x) | 15.6k / 11.0k (1.42x) | 6.0% (random weights) |
| 15M | 5.05k / 2.85k (1.77x) | 7.2k / 4.4k (1.64x) | 11.5k / 8.0k (1.44x) | 5.2% (random weights) |

Per dollar (listed $2.49 vs $0.89, i.e. 2.8x the price): the 4090 gives 1.4-1.9x more rows per dollar in every cell.
Achieved fp32 only 17-29 TFLOPS on the PRO 6000: the forward is far from peak on both cards, so kernel work is cheaper
than hardware. The PRO 6000 wins only where many GPUs in ONE machine are needed (learner + rollouts), or 96 GB.
