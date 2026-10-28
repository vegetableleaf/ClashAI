# 8x RTX PRO 6000 projection for the pilot fast loop (LOOP-INT, 2026-10-28)

Labels: (a) measured (number + source), (b) plausible, untested (how to measure), (c) contradicted.
Status: DRAFT. The learner-alongside bench on 33553 did not complete (container memory cap, below), so every overall
matches/h number here is (b), built from measured parts. Not ready to rent yet: see "Blocks" at the end.

## Measured inputs
| what | number | source |
|---|---|---|
| rollout, ref_v0 (CLXIII-class, no memory), 1x 4090, 4 producers x 256 x 4 thr + server | 48.9k matches/h, 0.70 core-s/match all-in, GPU 57% | (a) LOOP_INT.md, 33553 b/srv_k4_m256_t4.json |
| rollout, B0 + memory v2 on BOTH seats (ref_bench), fe364ceb + 16.635.3, same shape | **21.7k matches/h** (1,024 matches in 169.8 s), 686 rows/match, 9.6 cores busy = 1.59 core-s/match all-in, GPU util 33% | (a) 33553 bench2_k4_m256_eager, throughput.jsonl + samples (Codex LOOP-INT_2) |
| same run, per producer stage split | java 28 s, table fills 3 s, decide incl. forward wait 101 s of 170 s; JVM engine 0.30, obs 0.084 core-s/match | (a) same |
| producer memory at M 256, CRFORGE_XMX 5g | 7-9.8 GB RSS each | (a) same, .rss |
| main process (learner) memory | grows with the update's records (~4.5-5 MB per match, held 2-3x during transfer + collate): the 62 GB container cap was hit at 1,024 matches / update with 4 producers + 8 actors | (a) peak 61.98 GB; per-match size (a) LRN.md |
| learner, stored_values, 4090, TF32 off | 512 matches 48 s, 1,024 matches 58 s (PPO-step bound; kl_stop_prev binds at ~145-170 steps) | (a) LRN.md |
| PRO 6000 vs 4090 forward | 1.4-2.0x | (a) SPEED.md k |
| end-to-end fastloop --server + stored_values (tiny: 32 matches / update, 33308) | 3 updates, u0001 kl_stop fired (KL .0289 at e1 mb24), learner 13-23 s / update | (a) 33308 lint_ms1 |

Reading of the B0 row (a): neither CPU (9.6 of 54 cores) nor GPU (33%) is saturated at 4 producers: each producer is a
serial loop (Java step -> server forward -> Python decide), so rollout throughput scales with the number of producers
until the GPU or CPU saturates (b; 1 -> 4 producers gave 18.8k -> 48.9k on ref_v0 (a)). Memory makes a row about 2x as
expensive end to end (48.9k -> 21.7k at the same shape): the memory model's forward + 26 KB of MEM_KEYS per row through
the server (b: split not measured; LOOP-SRV can time the forward alone).

## Projection (b)
The loop is SYNCHRONOUS (production rl_royale: rollout, then update, then rollout): matches/h = N / (T_roll(N) +
T_learn(N)), N = matches per update (E x G).
- Rollout capacity on the box (all 8 GPUs serve during the rollout; GPU 0 also learns between rollouts):
  GPU-bound ~65k/h per 4090 for B0 + memory (33% util at 21.7k, linear) x 1.4-2.0 = ~90-130k/h per PRO 6000, 0.7-1.0M/h
  for 8; CPU-bound 256 cores / 1.59 core-s = ~580k/h. -> rollout ~400-580k/h, needing ~64-96 producers.
- Learner (one GPU; rl_royale is single-process): T_learn ~ (48 s + ~10 s per extra 512 matches) / (1.4-2.0).

| N / update | T_roll (at 400-580k/h) | T_learn (PRO 6000) | matches/h | updates/h |
|---:|---:|---:|---:|---:|
| 512 (pilot.yaml today) | 3-5 s (+ match-length tail, see below) | 24-34 s | 50-70k | 100-130 |
| 4,096 | 25-37 s | 54-77 s | **130-180k** | 32-45 |
| 8,192 | 51-74 s | 94-134 s | **140-200k** | 17-25 |

Tail: one wave of N matches lasts at least as long as its longest match in rounds (u0000 above: 1,024 matches in 170 s
on 4 producers); at small N per producer the tail dominates T_roll (b: measure T_roll at the chosen K x M).
**300k/h is NOT reachable with the synchronous loop at kl_stop_prev 0.02** (b, from the table): the learner is the
bound. Ways past it, each a decision, none built: (1) overlap the next rollout with the update (rollouts one weight
version stale; PPO's ratio uses the stored lp_old, so the math holds, but it is no longer production rl_royale's
schedule -> lead / owner); matches/h = N / max(T_roll, T_learn) -> ~190-310k at N 4,096-8,192; (2) multi-GPU learner
(LOOP-LRN: DDP <= 2.2x on the PPO steps at 4 GPUs); (3) larger N (each match teaches less while kl_stop binds).

## Recommended start (b) and ENTRY_ARGS for LOOP-OPS' launcher
- matches per update: N = 4,096 (pilot.yaml E 1024, G 4) as the start, with LOOP-LRN (owner: a tuning value). The
  launcher's config keeps E x G; fastloop reads the loop shape from its own flags (the `fastloop:` block is stripped).
- `ENTRY_ARGS="--producers 32 --matches 128 --threads 4 --devices cuda:0,cuda:1,cuda:2,cuda:3,cuda:4,cuda:5,cuda:6,cuda:7 --server eager"`
  (32 x 128 = one wave of 4,096; 4 producers per GPU; 128 Java threads + 32 Python + 8 servers on 256 cores). Raise to
  64 producers x 64 if the first updates show GPU util < 60% and idle cores (b).
- Env: CRFORGE_XMX=4g (b: 5g measured fine; heap need at M 128 unmeasured).
- RAM requirement (b, from the measured sizes): 32 producers x 7-10 GB + the learner's ~3 x 5 MB x 4,096 = ~60 GB +
  servers -> **>= 400 GB container RAM**. Ask for the pod's RAM before renting; 33553's 62 GB cap is why the bench
  stopped.

## Boot gate (exact maths on AVX512)
- Fact (a): our pods are AMD EPYC 7702 (Zen 2, no AVX512): numpy finds X86_V3 only, numpy float64 exp == glibc
  (200,000 / 200,000) and numpy (1,14)@(14,) == the sequential sum (88,000 / 88,000) there (LOOP-IW fp/).
- An 8x PRO 6000 node is likely Zen 4/5 or Sapphire/Emerald Rapids: AVX512 present (b). Then numpy's X86_V4 dispatch
  may use its own float64 exp (not glibc) and OpenBLAS a SkylakeX / Zen4 kernel for the dot -> LOOP-OPS' exact_gate.py
  FAILS and the loop must not start (CfAbil computes exp through glibc by FFI; production Python would use numpy's).
- Proposal (b, untestable on our pods): pod_boot exports, BEFORE the gate and for every loop process,
  `NPY_DISABLE_CPU_FEATURES="X86_V4 AVX512_ICL AVX512_SPR"` (numpy back to the X86_V3 paths our pods use),
  `OPENBLAS_CORETYPE=ZEN` (the kernels our pods run), `ATEN_CPU_CAPABILITY=avx2` (torch's CPU softmax / exp in the
  producers' decide = the pods'), plus the JVM flags (--add-modules=jdk.incubator.foreign --enable-native-access=ALL-UNNAMED).
  The gate then decides: EXACT_GATE PASS or no rollout. pod_boot.sh is LOOP-OPS' file: not edited here.

## Blocks (READY_TO_RENT = no)
1. pilot.yaml does not run on the fast loop yet: hero ability presses + the ability head (CfAbil, B6 head, the
   128-match rule warm start that rl_royale sends through ActorPool 'selfplay') are not wired (NotImplementedError).
2. The learner-alongside bench (updates/h measured, not projected) needs a pod with more RAM than 33553's 62 GB, or a
   smaller grid (K 3 x M 256, n_actors 2).
3. Lead decisions: lp_cell 1.14e-5 > 1e-5 in server mode (LOOP_INT.md); the GB-DECOY SIM gap; the synchronous loop's
   ~130-200k/h ceiling vs the 300k/h goal (overlap / DDP / N); pilot.yaml's `fastloop.decode: live` (production
   rl_royale has no live decode, so the fast loop does not do it).
