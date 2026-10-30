# LSPEED: learner speed tickets A / B / C (+ the A/B's critic_warmup_minibatch)

Labels: (a) measured (number + source), (b) plausible, untested, (c) contradicted. Owner constraints: fp32, TF32 off,
kl_stop_prev 0.02 per update, no KL leash. Inputs: SCALE.md 2 / 6b / 7b / 7e (where a step's time goes), SPEED2.md 4.

## STATUS (keep current; LEARNER-SPEED, account 3, 10-30 ~22:40 UTC)
- Commits: 96fda93 critic_warmup_minibatch (+ this doc); c065306 pod_boot.sh AVX-512 numpy / OpenBLAS paths; A + B: the
  commit that carries this STATUS (split_attn, trunk_graph, tests, lspeed/ scripts).
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
- RUNNING (33903): overlap A/B v3 (section 6): `cd /workspace/lspeed && setsid nohup bash ov3_queue.sh "1028 2029" >
  logs/ov3.out 2>&1 < /dev/null &` (resumable: finished runs have ov3/<run>.done); outputs /workspace/lspeed/ov3/.
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

## 4. Real-row benches (31892 RTX PRO 6000; lspeed/step_bench.py; rows from lspeed/gen_recs.py)
Rows (a): rl_royale's own CPU actors on 33903, pilot_noG.yaml (= pilot.yaml minus opponent G), B0, T_gate 0.1:
res_e32g4.pkl 128 matches (sha 5382c1cd...) + res_e96g4_s2.pkl 384 matches, seed 2029 (79f811af...) = 512 matches.

## 5. Ticket C: the learning A/B (owner 10-30: APPROVED, replaces the pilot; the lead launches it on 33308)
- Arms (both B0 + ability_head_from_init true + mem_row_cache true, pilot.yaml otherwise, 512 matches / update, same
  opponents, side by side on 33308 = one 4090 + 54 CPUs + ~55 GB each):
  - S = pilot.yaml (minibatch 256, lr 1e-5);
  - L = minibatch 65536, micro_batch 1024, critic_warmup_minibatch 256 (warm-up = S's, bit for bit: section 1), lr 2.0e-5,
    ppo_epochs 2. lr evidence: SCALE 3b (1.6e-4 = KL 0.638 in one fresh-Adam step, 32x the cap), SCALE 5 (65k at
    <= 2e-5: 4 steps, cap never fired, KL <= 0.008, T 0.3). Unmeasured (b): fixed lr at T_gate 0.1 -> the lead reads L's
    first policy update's per-step KL and lowers lr if the first step exceeds ~0.03.
- Score: learning per WALL HOUR = paired 480-game iu40 checks vs CLXIII at matched wall times (pilot/gate/pchk.sh), plus
  training win rate per update; L pays ~4-6 min of learner per update (section 4), S ~3-15 s.
