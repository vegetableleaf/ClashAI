# LOOP-SRV: the fast loop's GPU policy server (pipeline/policy_server.py `PolicyServer`)

Labels: (a) measured, (b) untested / projected, (c) contradicted.

## STATUS (2026-10-28)
- **DONE**: code, identity tests (6/6), lp check on 4,096 B0 rows, bare + mix benches, projection. Commits d783df0 + the follow-up.
- **Pods**:
  - 30408 `/workspace/loopsrv`: the sweep, the lp check and the tests;
  - 33920 `/workspace/loopsrv`: the bare bench and the first mix.
  - Both trees = git HEAD pipeline + this ticket's files + the pool checkpoints at their /workspace/cb_arm and /workspace/exploit paths.
- **Restart**:
  - `cd /workspace/loopsrv && nohup bash sweep.sh > sweep.log 2>&1 &` (resumable: configs with a json are skipped);
  - `python lp_check.py --out lp_check.json`;
  - `python srv_bench.py --part bare --out bare.json`.
- **STOP 10-28 (account switch)**: nothing of mine is running; the last runs were stopped by exact PID.
  - Last commit: b03fdb7 (value head, `v_old` per row).
  - Owed: the throughput cost of the value head, on a FREE 4090. Both were held by other agents' jobs at the stop. Command: `cd /workspace/loopsrv && OMP_NUM_THREADS=2 /workspace/venvf15/bin/python srv_bench.py --part mix --mode graphs --configs 512x24 --out mix_value_512x24.json`; compare with `results/mix_graphs_512x24_f7_fp32.json` (15,388 rows/s).
- **NEXT** (not this ticket):
  - rerun the mix with OPP's final row shares;
  - measure on the RTX PRO 6000 (the projection below is b);
  - LOOP-INT wires the real producers.

## Interface (LOOP-INT)
- **Server, one per GPU:**
  ```
  PolicyServer(models, listen="/dev/shm/loop/srv{g}.sock", device="cuda", mode="graphs").start(warm={name: rows})
  ```
  - `models` = `[{name, policy (GenPolicy), spec=row_spec(rows, gen_row_keys(model)), cfg, block_max, swap, watch}]`;
  - pass `warm` (a few real rows per model): every bucket's first-use cost (~210 ms) and every graph capture happen at start, not mid-run.
- **Producer:** `cl = connect(address)`.
  - `fs = cl.forward([(name, rows, n), ...])` takes at most one block per model and sends them all at once.
  - Each `Fwd` has `.heads` (every heads_t head, numpy), `.p` and `.ver`.
  - `cl.cells(f, ids, slots)` and `cl.ability(f, ids, feat)` are answered from the SAME batch (its encodings and its weight copy).
  - `cl.done(fs)` releases the batches.
  - `cl.decide_fwd(f, allowed, stalled, rngs)` = the S4b P1 sample decide, with every dict tagged `wver`.
  - **Value (lead-approved 10-28)**: `f.heads["value"]` = the 7 critic logits, value_head(g) of the same batch and version. `decide_fwd` stores `v_old` = `rl_royale.value_scalar(...)` (float64) per row, next to `lp_*`, under the same `wver`; a producer with its own decide does the same.
    - Parity vs the CPU fp32 critic, 4,096 B0 rows: max abs 4.9e-7 (a, results/lp_check.json). The tests check `v_old` < 1e-5 before and after a push.
    - Throughput cost not measured: both 4090s were busy with other agents' jobs. Arithmetic (b): about 1.8 kFLOP per row vs 0.425 GFLOP for the forward, plus one small kernel per batch.
    - **CtxHead caveat**: the pilot has no `critic_ctx`, so the stored V is the plain critic. A `critic_ctx` recipe (V = value_scalar(value_head(g) + CtxHead(ctx, g))) would need the CtxHead tensors in the push message (as `__ability__.` is) and `ctx` as a row input.
- **Weight versions** (contract with LOOP-LRN), DIR = /dev/shm/loop/weights:
  - the learner writes `DIR/learner.v{V:08d}.pt` = `{"version": V, "state_dict": actor_bytes dict}`, then `DIR/learner.latest`, each by a .tmp file plus os.replace;
  - a `watch=DIR` model serves nothing until V=0 arrives;
  - `__ability__.` tensors load into an AbilityHead per weight copy;
  - the learner deletes v{V-3} (servers never delete);
  - the learner drops a match with min(wver) < u-1.
- **PFSP learner snapshots** (up to 13): one entry each, with the learner's spec and `swap=True`; refresh with `push(name, V, sd)` or `watch`.
- **Multi-GPU design (8 GPUs):**
  - GPU 0 = learner;
  - GPUs 1..k = one PolicyServer process each, serving ALL models (8 models x 2 copies fit: 12.7 GB peak on the 4090), listening on `/dev/shm/loop/srv{g}.sock`;
  - producer p connects to server 1 + p % k;
  - every server watches the same DIR.
  - The GPU is in exclusive-process compute mode on these pods, so one process per GPU.
- `ProcServer(policy, spec, n, block_max, cfg)` = S4b's one-model form, same API.

## Identity (a)
- `pipeline/tests/test_policy_server.py`: **6 passed** on 30408 and 33920 (4090).
  - S4b's 3 tests.
  - Two architectures (CLXIII; CLXIV with memory v2 inputs) x 2 producer processes x 2 rounds, with weight version 1 (new weights + an ability head) pushed between rounds:
    - actions equal the block-by-block CPU decide of the tagged version;
    - log-probs < 1e-5, ability z < 1e-5;
    - wver 0 -> 1 for the learner and 0 for the opponent.
  - The same on CUDA, eager-padded and graphs, against the CPU reference.
- **lp check (`lp_check.py`, results/lp_check.json)**: B0 (mem_best_ze_grafted.pt), 4,096 rows, 1,392 plays, against the CPU fp32 reference:

| server numerics | max lp_gate | max lp_card | max lp_cell | rows with an lp >= 1e-5 | action diffs |
|---|---|---|---|---|---|
| torch defaults (cuDNN TF32 ON in cell_refine's convs) | 6.3e-6 | 9.5e-9 | **2.53** | 1,297 | 1 |
| fp32 = `configure()` (TF32 off in matmul + cuDNN), eager | 6.3e-6 | 9.5e-9 | **7.6e-6** | 0 | 0 |
| fp32, CUDA graphs | 6.3e-6 | 9.5e-9 | 7.6e-6 | 0 | 0 |

- S4b's CUDA path ran the cell_refine convs in TF32: torch's `cudnn.allow_tf32` defaults to True. LOOP-LRN found the same on the learner (1.46e-3 -> 1.5e-5). The lead ruled both flags off.

## Bare forward, 4090 fp32, rows/s (a, results/bare.json; padded buckets)

| model | B 64 eager / graphs | 128 | 256 | 512 | 1,024 eager | 2,048 eager |
|---|---|---|---|---|---|---|
| B0 learner (2.23M, memory + cue + refine) | 6,160 / **15,002** | 9,856 / 16,558 | 13,784 / 17,573 | 16,449 / 17,608 | 17,517 | 17,525 |
| wk_adapt_exp1 (1.55M, fv6) | 9,025 / 18,116 | 12,945 / 19,923 | 16,569 / 21,007 | 19,034 / 21,121 | 20,648 | 21,252 |
| w14opp_I (1.52M, fv5) | 9,256 / 18,409 | 13,191 / 20,264 | 16,783 / 21,328 | 19,325 / 21,470 | 20,945 | 21,826 |
| E4 (1.76M, refine) | 8,941 / 17,822 | 12,944 / 19,752 | 16,476 / 20,808 | 19,028 / 21,035 | 20,584 | 21,327 |

CUDA graphs reach the plateau from B 64 (2.0-2.4x eager at B 64, +27% at B 256). B0 is 17% slower than the 1.55M opponents per row (the memory encoder).

## Production mix, end to end with synthetic producers (a; 30408 unless noted; 30 s window, a push every 6 s)
- **Mix**: per round, a learner block of K rows plus opponent blocks of K x share:
  - init (a B0 copy) and 5 externals at 0.117 each;
  - w14opp_I at 0.15;
  - 8 models in all; opponent rows = 0.85 x the learner's.
- Every 7th row is forced to play (25% play) unless "natural" (12%).
- Producer = a spawned process running the P1 decide.

| config | precision | producers x learner block | rows/s, all models | learner rows/s | mean batch: learner / an opponent | producer CPU us/row | push ms | GPU mem |
|---|---|---|---|---|---|---|---|---|
| graphs | fp32 | 16 x 256 | 13,101 | 7,075 | 1,247 / 238 | 95 | 239 | 8.0 GB |
| graphs | fp32 | 32 x 256 | 14,578 | 7,873 | 1,823 / 491 | 104 | 486 | 9.8 |
| graphs | fp32 | 24 x 512 | 15,388 (15,334 rerun) | 8,302 | 1,988 / 911 | 82 | 637 (282) | 10.8 |
| graphs | fp32 | **40 x 512** | **16,102 (16,219)** | **8,687** | 2,037 / 1,683 | 81 | 3,437 (1,667) | 12.7 |
| eager | fp32 | 32 x 256 | 14,101 | 7,616 | 2,030 / 651 | 105 | 297 | 6.7 |
| eager | fp32 | 24 x 512 | 14,727 | 7,945 | 2,031 / 1,001 | 82 | 182 | 8.1 |
| graphs | **tf32** | 32 x 256 | 16,941 | 9,149 | 1,666 / 449 | 105 | 393 | 9.8 |
| graphs | **tf32** | 24 x 512 | 17,696 | 9,547 | 1,986 / 820 | 79 | 209 | 10.9 |
| graphs, natural play | fp32 | 32 x 256 | 15,816 | 8,542 | 1,940 / 590 | 72 | 599 | 9.7 |
| graphs, natural play | fp32 | 24 x 512 | 17,012 | 9,178 | 2,022 / 1,106 | 54 | 6,908 (2 pushes) | 10.6 |

(Rerun) = after the foreach weight load. 16 x 256 on 33920: 13,611.

- **The TF32 cost (one number for the lead): TF32 off costs the server 13-14%.** That is 14,578 vs 16,941 rows/s (32 x 256) and 15,388 vs 17,696 (24 x 512): TF32 on is +15-16%. LOOP-LRN measured no cost on the learner.
- **Graphs vs eager at this mix: +3.4-4.5%**. Eager batches come out larger (an opponent batch of 651-1,001 vs 491-911), so the small-batch gain of graphs shows less here than in the bare table.
- **Rows in flight**: about 12k per server (24 x 512) gives 95% of the 40 x 512 rate.
- **Vs the bare forward**: the bare ceiling of this mix is 19.0k rows/s (b, weighted from the bare table at B 2,048). The server reaches 85% (25% play) to 89% (12% play). The rest is cell calls: B0 has refine layers, 24-29 s of cell work per 30 s window on the cell stream, overlapping forwards (S4b k1 found the same on CLXIII).
- **Push latency**:
  - before the fix, a per-tensor `load_state_dict` under the GIL load of the server threads took up to 3.4-6.9 s;
  - the copies' wait for in-flight batches is 0 s (a);
  - after one `torch._foreach_copy_` per model copy: 282 ms (24 producers), 1.67 s (40 producers).
  - Rows stay tagged, so a lag is visible and harmless under the learner's u-1 rule (b).
- **Producer CPU**: 54-105 us per row for the decide, i.e. 1.3-2.5 cores per 4090 at these rates.

## Matches/h and the 8x RTX PRO 6000 projection
- **Rows per match** (LOOP-OPP interim, a, 21 crforge matches): learner 329 + opponents 0.84 x 329 = **605 rows/match**.
- **Per 4090, fp32 identical path**:
  - 16.1k rows/s -> **96k matches/h** (25% play);
  - 17.0k -> 101k (12% play);
  - TF32 would give 105k.
- **Per RTX PRO 6000 (b)**:
  - x1.96: the bare fp32 1.76M ratio of SPEED.md section k; B0 and the cell path are not measured on that card;
  - -> about 31.5-33k rows/s -> **about 190k matches/h per inference GPU**, provided about 2x the rows in flight (about 24k per server).
- **8 GPUs = 1 learner + 7 servers (b)**: about 1.3M matches/h GPU-side.
  - **300k/h needs 50.4k rows/s = 2 PRO 6000 servers** (1.6 at 31.5k).
  - The remaining GPUs can go to learner DDP.
- **CPU per server GPU (b)**:
  - decide about 2-3 cores;
  - the server is ONE Python process with GIL-bound threads, so run one per GPU;
  - the envs (0.27 core-s/match) dominate: about 22.5 cores for 300k/h.
- **(c)** "the GPU is the bottleneck for 300k/h on 8 PRO 6000s": contradicted by the above; CPU and JVM obs are the limit.

## Files
- `srv_bench.py` (parts bare / mix), `sweep.sh`, `lp_check.py`, `results/*.json`.
