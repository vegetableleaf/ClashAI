# LSPEED: learner speed tickets A / B / C (+ the A/B's critic_warmup_minibatch)

Labels: (a) measured (number + source), (b) plausible, untested, (c) contradicted. Owner constraints: fp32, TF32 off,
kl_stop_prev 0.02 per update, no KL leash. Inputs: SCALE.md 2 / 6b / 7b / 7e (where a step's time goes), SPEED2.md 4.

## STATUS (keep current; LEARNER-SPEED, account 3, 10-31 ~00:45 UTC)
- Commits: 96fda93 critic_warmup_minibatch (+ this doc); c065306 pod_boot.sh AVX-512 numpy / OpenBLAS paths; bc2470f
  split_attn + trunk_graph (tests, lspeed/ scripts); the results commit carrying this STATUS (sections 4-6).
- Pods:
  - 33903 (CPUs 146-153, shared 4090 <= 6 GB). Trees = hard-link copies of /workspace/speed2/cb with pipeline/ replaced
    (never edit a file in place: rm + cp): cb = origin 7fd5721 pipeline (reference smokes); cbn = + critic_warmup_minibatch;
    cba / cbb = + A (+ B); cbo = cbb + origin c714d63's pilot/loop dir (overlap v3). env /workspace/lspeed/env.sh, smoke
    `/workspace/lspeed/smoke.sh TREE RUN CPUS [k=v]` (log /workspace/lspeed/logs/RUN.log), unit tests `ut.sh TREE LOG tests`.
  - 31892 RTX PRO 6000 (bench pod; the lead stops it when the benches are done). Booted with LOOP-OPS's launcher
    (`RUN=lspeed_boot ENTRY=-c ENTRY_ARGS=pass REQUIRE_ACK=0 loop_pod.sh up 31892 root@81.27.69.178`: venv / code / 84
    artifacts / exact gate; no loop). My bench tree /workspace/lspeed/cb (copy of /workspace/loop/cb + my pipeline files),
    env /workspace/lspeed/env.sh (CPUs 0-5), records /workspace/lspeed/rec/, outputs /workspace/lspeed/out/. GPU timings take
    /workspace/BENCH_LOCK (`/workspace/lspeed/locked.sh TAG CMD`). Block queued: `locked.sh ... bench_block.sh` (section 4).
- Nothing of mine is running. 31892 DONE (results lspeed/out, scripts lspeed/pod31892; copies in
  C:/Users/benpe/pod_backup_weekend/pro6000/). Overlap v3 DONE (section 6; restart: `cd /workspace/lspeed && setsid
  nohup bash ov3_queue.sh "1028 2029" > logs/ov3.out 2>&1 < /dev/null &`, finished runs skipped via ov3/<run>.done).
- Next (proposed): the full ticket B (padded played-row buckets, monitors out of the step) for the remaining ~30% launch
  idle at mb 256 (section 5); dedicated learner cores in the overlap stack (section 6).
- Codex dispatches: none.

## 1. critic_warmup_minibatch (A/B arm L)
Key `critic_warmup_minibatch: m` (int >= 1; absent / null = `minibatch`; hash unchanged when absent). In the critic
warm-up (vf policy False) _ppo_steps uses m rows per minibatch; policy updates keep `minibatch`. Arm L sets
`minibatch: 65536, micro_batch: 1024, critic_warmup_minibatch: 256` so its warm-up is arm S's (256-row steps; micro_batch
is inactive at 256 < 1024).
- Tests (a): pipeline/tests/test_critic_warmup_mb.py (3): warm-up with the key = warm-up at that minibatch, byte-identical
  weights and steps; absent / null byte-identical for warm-up, policy and match_loo updates, and policy updates ignore the
  key; validation + hash. 33903 CPU: with test_learner_fast_accum + test_kl_stop_prev 12 passed; HEAD accum 6 passed.
- Smokes (a; 33903, succ48_x_s101 --smoke, CPU learner; logs /workspace/lspeed/logs/lsp_*.log; both smoke updates are
  critic warm-up updates, so they exercise the key):
  | run | tree | config sha | u0000 batch / weights | u0001 batch / weights | result |
  |---|---|---|---|---|---|
  | lsp_ref_head2 | origin 7fd5721 | b5e2a2bbafef | 6d412f8c / 3e07cff4 | d7353efa / 63a925c3 | SMOKE PASS |
  | lsp_new_absent2 | + key, absent | b5e2a2bbafef | 6d412f8c / 3e07cff4 | d7353efa / 63a925c3 | SMOKE PASS (= ref) |
  | lsp_cwm_armL: critic_warmup_minibatch=256 minibatch=65536 micro_batch=1024 | + key | e46b659e4901 | 6d412f8c / 3e07cff4 | d7353efa / 63a925c3 | SMOKE PASS: arm L's warm-up = arm S's, bit for bit |
  | lsp_cwm_64: critic_warmup_minibatch=64 | + key | aa9fbe7c4302 | 6d412f8c / 3e07cff4 | d7353efa / 42fb94cd | SMOKE PASS (key acts: 162 vs 42 optimizer steps) |
  The batch shas differ from 33920's reference (e816a6a4 ...): 33903 runs another engine lib / tables 16.635.3; the
  absent-key identity is HEAD vs new on the same pod. config sha b5e2a2bbafef = 33920's reference (hash unchanged).
- (Laptop: test_learner_fast_accum.test_one_minibatch_gradient fails at HEAD's own tolerance on the laptop's torch build,
  2.9e-8 abs on a 1e-9 delta; it passes on the pod. Not this change: the key is absent there.)

## 2. Ticket A: split_attn (pipeline/learner_attn.py)
torch's MHA training path copies the packed q/k/v projection into a contiguous [3, L, B, E] buffer and selects from it;
each select's backward zero-fills a full buffer (SCALE 7b). SplitMHA keeps the SAME packed matmul and SDPA call and
splits by views (unbind; backward = one stack). It runs only with grad enabled; every no-grad forward (actors, refs, the
lazy anchor, live) is nn.MultiheadAttention.forward itself. Actors / live never import the file; rl_royale key
`split_attn: true` swaps the classes on the Learner's model before the ref copies (state_dict unchanged).
- Identity (a): pipeline/tests/test_learner_attn.py, 6 tests: forward, input and every parameter gradient BITWISE equal
  (torch.equal) on both encoder shapes with random padding, CPU and the 33903 4090 (deterministic, TF32 off); a real
  minibatch_loss (tiny S1Model, sampler trajectories, value loss, beta 0.1): loss, monitors and every gradient bitwise
  equal; 3 PPO updates (Adam): steps and weights byte-identical; state_dict / deepcopy; validation + hash.
- Speed (a; lspeed/attn_bench.py, out/attn_bench.json; 33903 4090 shared, fp32, deterministic; fwd + bwd wall median):
  | encoder | rows | torch ms | split ms | speedup | kernels torch -> split | bitwise |
  |---|---:|---:|---:|---:|---|---|
  | trunk (d 128, 4 layers, 209 tokens) | 256 | 74.7 | 59.3 | 1.26x | 426 -> 322 | yes |
  | trunk | 1,024 | 258.8 | 202.6 | 1.28x | 474 -> 369 | yes |
  | memory (d 64, 2 layers, 129 tokens) | 256 | 15.7 | 15.1 | 1.04x | 219 -> 167 | yes |
  | memory | 1,024 | 53.8 | 40.6 | 1.33x | 243 -> 191 | yes |
  RTX PRO 6000 (a; 31892, out/attn_bench_pro6000.json): trunk 1.18x / 1.30x / 1.34x at 256 / 1,024 / 4,096 rows
  (22.0 -> 18.6, 92.7 -> 71.5, 363 -> 271 ms); memory encoder 0.95x / 1.23x / 1.28x; bitwise equal everywhere; the unit
  tests pass there too (Blackwell sm_120). The whole-step effect: section 4.
- Smokes (a; 33903, succ48_x_s101 --smoke): absent key with the A + B rl_royale (lsp_ab_absent): config b5e2a2bbafef,
  u0000 6d412f8c / 3e07cff4, u0001 d7353efa / 63a925c3 = origin's reference, SMOKE PASS. GPU learner with
  critic_warmup_updates=1 (u0001 = a policy update): ref (HEAD) e0e02d282f5a PASS; split_attn=true fe6bc3975408 PASS
  ("[rl] split_attn: 4 attention modules"). Their post-u0001 weights differ, but so do their u0000 BATCHES
  (a325f43f vs 28fc7730, before any update): with learner_device=cuda the smoke's rollouts are not run-to-run
  reproducible (the CPU smokes are), so the GPU smoke is a functional PASS only; identity = the tests + section 4.

## 3. Ticket B first cut: trunk_graph (pipeline/learner_graph.py; lead 10-30: make_graphed_callables on the fixed trunk)
Key `trunk_graph: n` (int; absent / null = off, historical hash). rl_royale sets model.trunk_graph AFTER the ref copies;
policy_terms routes GenPolicy.heads_t (encode_gen + heads_gen + the card scatter) through
torch.cuda.make_graphed_callables when grad is on, the rows are CUDA, exactly n rows, and the trunk is trainable (the
critic warm-up and every no-grad forward run eager). Graphs are cached weakly per model and per (input layout,
requires_grad pattern). The played-row cell head, losses, monitors (and their syncs), the lazy anchor, the entropy pair,
clip and Adam stay eager and unchanged; an epoch's tail minibatch (other size) runs eager.
- Capture blocker found and handled (a): tower_refine.tower_features builds two constant rows with sc.new_tensor([...])
  (a host-to-device copy; capture refuses it). During the capture only, learner_graph swaps in the same function with the
  constants pre-built on the device (checked bitwise against the original first). Model code is untouched.
- Bug found by the tests and fixed (a): those constants must outlive the graph; freed, their memory was reused and the
  graph read garbage (tower_refine.card.2.weight gradient off by 57% from the 2nd replay on; zero-initialised weight, so
  the forward and loss stayed bitwise equal). The cache entry now holds them.
- Identity (a; pipeline/tests/test_learner_graph.py, 33903 4090, deterministic, TF32 off; tiny GenModel with both refine
  modules, lazy_refine on, real-sampler rows): loss bitwise equal; 65 / 67 gradient tensors bitwise equal; card_id /
  form_id differ by 1.3e-8 relative = the predicted summation-order effect (they get gradient from inside the graph AND
  from the eager cell head; the graph sums its own part first). ppo_update with kl_stop_prev at 4 limits (stop at
  step 1, at step 4 across the epoch boundary, none in 12 steps with eager tails): identical stops and steps; Adam weights
  after 12 steps differ by <= 3e-4 = 0.1 lr (Adam-eps on near-zero-gradient parameters, as SCALE 3a), 1.2e-9 after 4.
- Bug 2 found by the composition test and fixed (a): the graphed backward hands autograd its parameter gradients as
  views of the graph's STATIC buffers; with p.grad None, AccumulateGrad adopts them as p.grad, and the next replay (the
  next micro-batch of micro_batch) overwrites p.grad in place -> the accumulated gradient was off by 3.2x relative.
  Fix: a post-hook on the graphed node returns one fused torch._foreach_mul(grads, 1.0) (exact) = fresh tensors.
  After: decoupled + micro + split_attn + graph vs the plain eager learner: worst gradient 5.4e-8 relative, kl_stop at
  the same step (3), 6 steps without a stop, weights bitwise equal after both.
- Bug 3 (a, smoke lsp_gpu_graph): the warm-up check read model.unit_in.weight; feature_version >= 3 models wrap unit_in
  (UnitFormInput, no .weight) -> AttributeError. Now next(model.encoder.parameters()).requires_grad.
- Composition (lead 10-30, the overlap stack): ppo_decoupled 2.0 on one-version-stale rows (is_maxdev 4.0) + micro_batch
  (graph rows = the micro-batch) + split_attn + trunk_graph = the plain eager learner (test above).
- Tests on 33903 4090 and the 31892 PRO 6000: test_learner_graph 5 + test_learner_attn 6 OK.
- Smoke (a; 33903, GPU learner, critic_warmup_updates=1 split_attn=true trunk_graph=256): lsp_gpu_graph2 SMOKE PASS
  (config 20057a9f14c1, "[rl] trunk_graph: ..."); the final code (bugs 2 + 3 fixed): lsp_gpu_graph3 SMOKE PASS (same config).
- Speed: section 4.

## 4. Real-row benches (31892 RTX PRO 6000; lspeed/step_bench.py; rows from lspeed/gen_recs.py; outputs lspeed/out/)
Rows (a): rl_royale's own CPU actors on 33903, pilot_noG.yaml (= pilot.yaml minus opponent G), B0, T_gate 0.1:
res_e32g4.pkl 128 matches (sha 5382c1cd...) + res_e96g4_s2.pkl 384 matches, seed 2029 (79f811af...) = 512 matches
(158,713 rows, 14.0% played). Learner as the pilot's: lazy_refine, memory v2 frozen, ability head, mem_row_cache, fp32,
TF32 off, deterministic. A timed step = minibatch_loss + backward + clip + Adam with the lazy anchor prefilled (SCALE 7e).
- Identity on real rows (a): split_attn 138 / 138 gradient tensors bitwise; trunk_graph 136 / 138 (card_id 5.7e-8,
  form_id 7.9e-8 relative), global 1.4e-9; one whole kl_stop update: identical steps (37 / 67) and KLs in all 4 arms.
- Step time, mb 256 (a; quiet pod, both arm orders, 60 steps; q256_*.json; the block's first run overlapped another
  bench's CPU load and is not used):
  | arm | ms / step (order A, order B) | kernels / step | kernel ms / step |
  |---|---|---:|---:|
  | base | 57.4, 63.5 | 3,865 | 40.4-41.3 |
  | split_attn | 61.8, 61.2 | 3,709 | 37.4-37.9 |
  | trunk_graph | 56.4, 56.6 | 4,034 | 40.8-41.8 |
  | both | 52.6, 50.6 (1.16x) | 3,878 | 37.1-38.1 |
  At 256 rows the step is launch-bound (kernel time ~2/3 of wall): split_attn's fewer kernels do not shorten it alone;
  the trunk graph removes the trunk's launches only (+170 kernels: static-input copies + the fresh-grad foreach);
  together 1.16x.
- Step time, mb 1,024 (a; step_mb1024.json): base 169.8 ms (89% kernel-busy), split_attn 144.5 (1.18x), trunk_graph 167.0
  (1.02x), both 142.6 (1.19x). GPU-bound: the graph cannot help; split_attn's kernel time (151.6 -> 127.7 ms) is the gain.
- Whole update, 512 matches, fresh Adam (a; upd_S512 / upd_L512.json; cold MemRowCache, anchor filled inside):
  - S (mb 256, lr 1e-5): 37 steps, stop KL 0.0212; 5.41 s base -> 4.67 s both (1.16x).
  - L (65536 / micro 1024, lr 2e-5): 6 steps, no stop; 83.9 s base -> 73.8 s both (1.14x); peak 10.9 GB.
  - Outside ppo_update in this bench: collate 1.9 s, to_device + gae_batch 20 s (b: the pilot's stored v_old skips most
    of gae_batch's forward).
- Arm-L lr (a; upd_L512_lr*.json = fresh Adam on 512 matches; warm_probe.json = two consecutive updates on 256-match
  halves, Adam carried; KL to the anchor after k steps, gate + card + cell, each on that minibatch's own rows):
  | lr | fresh Adam, 512 matches | update 1, 256 matches | update 2 (warmed Adam), 256 matches |
  |---|---|---|---|
  | 2e-5 | 0.0149, 0.0097, 0.0060, 0.0057, 0.0058 (6 steps, no stop) | 0.0058, 0.0091, 0.0060 | 0.0012, 0.0075, 0.0120 |
  | 3e-5 | 0.0305 -> stop (1.5x) | 0.0126, 0.0212 -> stop | 0.0079, 0.0495 -> stop (one step +0.042) |
  | 4e-5 | 0.0492 -> stop | 0.0215 -> stop | 0.0433 -> stop |
  | 5.5e-5 | 0.0815 -> stop | - | - |
  Decision (lead rule): 2e-5 is the only measured lr with no single step over the cap, fresh or warmed; 3e-5 / 4e-5
  overshoot in steady state too, so no ramp. (b) At 512 matches (6 steps) the warmed update should land near the cap.

## 5. Ticket C: the learning A/B and the learner projection
- A/B (owner 10-30: APPROVED, replaces the pilot; the lead runs it on 33308). Full-stack restart lines (sent 10-31):
  - S = pilot.yaml + mem_row_cache=true split_attn=true trunk_graph=256;
  - L = minibatch=65536 micro_batch=1024 critic_warmup_minibatch=256 lr=2e-5 ppo_epochs=2 mem_row_cache=true
    split_attn=true trunk_graph=1024 (warm-up = S's bit for bit: section 1; lr: section 4);
  - both B0 + ability_head_from_init true; with fastloop --overlap 1: + ppo_decoupled=2.0 (section 6).
  - Score: learning per WALL HOUR = paired 480-game iu40 checks vs CLXIII at matched wall times (pilot/gate/pchk.sh) +
    training win rate per update.
- Learner s/update (a = measured on the PRO 6000; b = projected), learner only:
  | | 512 matches | 1,024 matches |
  |---|---|---|
  | S policy update, base / A+B | 5.4 / 4.7 s (a) | ~5.4 / ~4.7 s (b: steps to the cap do not grow with M, SCALE 6f) |
  | S critic warm-up update (every row x 2 epochs at ~52 ms) | ~64 s (b) | ~128 s (b) |
  | L policy update, base / A+B (6 / ~12 steps) | 84 / 74 s (a) | ~168 / ~148 s (b, rows x 2) |
  | + collate / to_device in this bench | ~2 + <= 20 s (a, upper bound) | ~4 + <= 40 s (b) |
  -> learner-only bound on updates / h: S ~500-750 (any M); L ~45 at 512, ~22 at 1,024 (b). In the synchronous loop the
  rollout wave adds its own time; with overlap the period is max(wave, learner) (section 6).
- What is left (b, from the kernel shares above): at mb 256 the A+B step is still ~30% launch idle (37 ms of kernels in
  52 ms) -> the full ticket B (padded played-row buckets + monitors out of the step, the whole loss as graphs) can give
  <= ~1.4x more; at 1,024+ rows the step is kernel-bound (89%), so only fewer / faster kernels help.

## 6. Overlap A/B v3 (lead 10-30: arm-L learner settings; 33903; lspeed/ov3/)
Setup: = LOOP-ASYNC v2 (OVERLAP.md: ref_pilot_noiw, 128 matches / update, 8 updates, critic warm-up 1, 2 producers x 64,
server eager) with minibatch 32768, micro_batch 256 (exact accumulation, sized for the 6 GB GPU share), lr 2e-5,
critic_warmup_minibatch 256, mem_row_cache, ppo_decoupled 2.0 on BOTH modes; seeds 1028 / 2029; held-out = the other
seed's u0 batch (ab_eval.py). Tables: ov3/TABLE.txt, ov3/eval_s*.json.
- (a) Steps: 4 per policy update in every run; the cap never fires (no steps-to-cap signal at this size).
- (a) Held-out KL from B0 at u8 (gate / card / cell; sum): s1028 m0 .0319 / .0188 / .0077 (.0584), m1 .0188 / .0246 / .0108
  (.0542, 0.93x); s2029 m0 .0148 / .0167 / .0109 (.0424), m1 .0148 / .0296 / .0170 (.0614, 1.45x).
- (a) No saw-tooth: m1's summed KL to B0 rises every update (s1028 .016 .018 .023 .032 .037 .048 .054; s2029 .009 .015
  .027 .032 .039 .049 .061); single-head gate dips of one update occur in both modes.
- (a) Stale rows: is_maxdev_first 0.85-9.8, <= 0.43% truncated at c 2; clip_frac at mode 0's level.
- (b) J: all arms within ~1 se; m1 points above m0 on both seeds (+0.0015 vs +0.0008, +0.0017 vs +0.0005).
- (a) Speed: s1028 m1 21.6 min vs m0 27.4 (1.27x: the ~55 s learner hides under the ~137 s wave); s2029 m1 28.4 vs 26.8
  (0.94x: waves 197-275 s and learner 64-100 s at u2-u5). (b) On 33903 the learner and the producers share the same 8 CPUs,
  so in mode 1 the learner's CPU work (memory-row features, launches) slows the wave. The full stack needs dedicated
  learner cores.
- Verdict: the owner's bar (not worse per update: movement, no saw-tooth) holds at arm-L settings to these metrics'
  resolution.
