# LSPEED: learner speed tickets A / B / C (+ the A/B's critic_warmup_minibatch)

Labels: (a) measured (number + source), (b) plausible, untested, (c) contradicted. Owner constraints: fp32, TF32 off,
kl_stop_prev 0.02 per update, no KL leash. Inputs: SCALE.md 2 / 6b / 7b / 7e (where a step's time goes), SPEED2.md 4.

## STATUS (keep current; LEARNER-SPEED, account 3, 10-30)
- Pod: 33903 only (CPUs 146-153, shared 4090 <= 6 GB). Trees (hard-link copies of /workspace/speed2/cb, pipeline/ replaced,
  never edit a file in place: rm + cp):
  - /workspace/lspeed/cb = origin HEAD 7fd5721 pipeline/ (reference smokes);
  - /workspace/lspeed/cbn = cb + critic_warmup_minibatch rl_royale (smokes of that key);
  - /workspace/lspeed/cba = cb + split_attn work (learner_attn.py, tests, lspeed/ scripts).
  - env /workspace/lspeed/env.sh (CPUS 146-153, facade build /workspace/speed2/jbuild read-only), smoke
    `/workspace/lspeed/smoke.sh TREE RUN CPUS [k=v]` (succ48_x_s101 --smoke, CPU, log /workspace/lspeed/logs/RUN.log),
    unit tests `/workspace/lspeed/ut.sh TREE LOG tests...`.
- critic_warmup_minibatch (lead 10-30, A/B option i): BUILT, tests pass; smokes running (see section 1).
- Ticket A (split_attn): BUILT + bitwise identity on CPU and GPU (section 2); not committed yet; smoke owed.
- Ticket B (trunk CUDA graph): design in section 3, not built.
- Ticket C: not started.
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
  The whole-step effect is owed (the encoders are part of a step; needs real rows: section 4).

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
- Speed: owed on real rows (section 4).

## 4. Owed
- Real pilot records on 33903 for the whole-step identity + speed numbers (33920 and its records are gone).
