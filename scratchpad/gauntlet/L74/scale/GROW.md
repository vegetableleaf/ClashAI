# GROW-10M: function-preserving growth of CLXIII / B0 to ~10 M (PLAN Pillar 4a step 3)

Labels: (a) measured (number + source), (b) plausible, untested, (c) contradicted.

## STATUS (restart point)
- DONE on the laptop (CPU only): `grow.py` (the tool), `grow_identity.py` (identity test + latency), this doc. Commits 321088b,
  M2, M3 (`git log -- scratchpad/gauntlet/L74/scale/grow*.py`).
- Grown checkpoints (local only; icebow/data is untracked) in `icebow/data/bench/grow/`, all `--noise 0.01 --seed 0 --place
  interleave` unless named: `b0_grow_d256_l10.pt` (sha256 673dd261...), `b0_grow_d384_l4.pt` (24c43276...),
  `clxiii_grow_d256_l10.pt` (caf475e6...), `b0_grow_d256_l10_noise0.pt` (615da095..., test control only, do NOT train it).
  Same input + same args -> same output; rebuild: `icebow/.venv/Scripts/python.exe -B scratchpad/gauntlet/L74/scale/grow.py
  icebow/data/bench/rl_royale/b0/b0_clxiii_s3aux_grafted.pt icebow/data/bench/grow/b0_grow_d256_l10.pt --d 256 --layers 10`.
- Recorded rows (local, 79 MB): `.foreman/scratch/grow/id/b0_cpu.rows.pt` (+ `b0_cpu.pt` = B0's live replay). Rebuild:
  `... grow_identity.py run icebow/data/bench/rl_royale/b0/b0_clxiii_s3aux_grafted.pt .foreman/scratch/grow/id/b0_cpu.pt --rows` (~3 min).
- OWED: (1) laptop-GPU latency (not run: live CLXIII plays on the laptop GPU, COMMON forbids a second GPU job; command in
  section 4); (2) a real `rl_royale --smoke` on a pod with the grown init (no trainer code changed, but the rule stands for a new
  init shape); (3) the RL comparison itself (section 5). No Codex dispatch was used.

## 1. What the tool does
`grow.py IN OUT --d D --layers L [--place interleave|end] [--noise 0.01] [--seed 0]` (and `IN --count` for the exact size table).
The output is a PLAIN GenModel checkpoint: `args.d` / `args.layers` changed, 4 heads and ffn 4 D as the constructor builds them,
every add-on (cue_in, cell_refine, tower_refine, mem v2 + zero_empty, mem_aux) rebuilt by content. No loader changed.

Widening d -> D = k d, k an integer:
- Every d-space vector is carried as k exact copies: the residual stream, LN outputs, patch / unit / global tokens, cell_emb, the
  cell query (block layout [x, x, ...]); inside attention each of the 4 heads is k copies of the old head's 32 dims.
- **LayerNorm is exact with no change:** LN over D of [x, ..., x] has the mean and the population variance of x, so
  LN'([x, ..., x]) = [LN(x), ..., LN(x)] with gamma / beta copied. That is why D must be a multiple of d (a [x, 0] padding would
  change the statistics; a custom LN over the old dims would need a new module that no loader builds).
- A linear that READS a copied space gets W / k per copy; one that WRITES one has its rows copied. Scales: q by 1/sqrt(k)
  (scores q.k / sqrt(32 k)); the key side of the two dot products divided by sqrt(D) (cell_key: kp / kc; CellRefine.out and
  TowerRefine.cell.out: the refine residuals) by 1/sqrt(k).
- **Symmetry breaking:** each reader's per-copy weights get antisymmetric noise (copies' noise sums to 0 per weight;
  `--noise` x the tensor's std), so W'x' = Wx at init but the copies get different gradients. Without it the copies stay equal
  forever: RL runs the model in eval() (rl_royale: "eval() for rollout AND update"), so dropout never breaks it.
- Every float tensor must match exactly one rule in `RULES`; an unknown module raises.

Deepening: the old layers keep their order at `old_layer_positions` (interleave 4 -> 10: [0, 2, 5, 8]); each new layer is a fresh
init with self_attn.out_proj and linear2 weights AND biases zero, so the layer adds exactly 0 (x + 0 + 0).

Checkpoint meta: everything of the input kept (b0, memory, memory_aux, memory_v2, s3, grafted_heads_from, card_vocab, d_c, gen,
val, ...), `args` d / layers, `n_params`, new key `grow` (base path + sha256, d0 / layers0 / d / layers / k, place, positions,
noise, seed, n_params0, builder). `rl`: `ability_head` widened by the same rules (its input is cat[features 55, g]; `ability.d_g`
= D); `optimizer`, `ability_optimizer`, `kl_ref` (128-wide state) dropped -- a fresh run never reads them (only `_restore`
on --resume of the same run does); everything else kept.

## 2. Size (a, `grow.py B0 --count`, exact, B0 layout incl. memory v2 + aux heads)
| d x layers | params | | d x layers | params |
|---|---|---|---|---|
| 128 x 4 (B0) | 2.23 M | | 384 x 4 | 10.77 M |
| 256 x 8 | 8.77 M | | 384 x 6 | 14.32 M |
| 256 x 10 | **10.35 M** | | 384 x 8 | 17.87 M |
| 256 x 12 | 11.93 M | | 384 x 10 | 21.41 M |
CLXIII (1.76 M) -> 256 x 10 = 9.83 M. Only D = 256 / 384 / 512 are possible (multiples of 128).

## 3. Identity (CPU; recorded rows = test_decide_identity's 4 recorded CLXIII live matches, 1,718 decisions, through this tree's live path)
Model level (`grow_identity.py model BASE GROWN ROWS PREC [STRIDE]`; every head, the cell head for EVERY real hand card of every row):
| grown vs base | prec | rows / cell calls | max abs log-prob diff | argmax (card, wait, value, gate sign, cell) |
|---|---|---|---|---|
| B0 -> 256x10 | fp64 | 1,718 / 6,872 | cell 1.5e-6, card 4.5e-7, gate 3.2e-7, wait 2.3e-7, value 1.8e-7; g 4.6e-8; logits <= 9.9e-7 | all equal |
| B0 -> 256x10 | fp32 | 1,718 / 6,872 | cell 1.9e-5, card 7.6e-6, wait 5.7e-6, value 2.9e-6, gate 2.6e-6; g 1.4e-6 | all equal |
| B0 -> 384x4 (k 3) | fp64 | 430 / 1,720 | cell 1.9e-6, card 1.0e-6, others <= 4.2e-7 | all equal |
| CLXIII -> 256x10 | fp64 | 430 / 1,720 | cell 1.5e-6, card 4.5e-7, others <= 2.6e-7 | all equal |
| B0 -> 256x10 noise 0 | fp64 | 430 / 1,720 | cell 1.5e-6, card 4.4e-7 (same as noise 0.01) | all equal |
- (a) The fp64 residual is the grown model's fp32 WEIGHTS, not the method: noise 0 and noise 0.01 give the same 1.5e-6, so it is
  the rounding of the 1/sqrt(2) scalings (irrational for k = 2, 3; exact only at k = 4) when stored in fp32.
- (a) The fp32 deviation is the base model's own fp32 floor: B0 fp64 vs B0 fp32 = card 1.1e-5, gate 2.7e-6, value 3.4e-6, g 1.2e-6;
  grown fp32 vs B0 fp64 = card 1.4e-5, gate 2.5e-6, value 2.7e-6, g 1.7e-6 (430 rows, `64v32`). The cell head in that mixed
  run differs by 1.34 for B0 against ITSELF (fp64 vs fp32), (b) an input-cast artifact (cell_label rounds x * 36 at lattice
  points), so it says nothing about growth; the same-dtype comparisons above are the ones that count.
- So "within 1e-6": logits yes in fp64 (<= 9.9e-7); log-probs <= 1e-6 for every head but the cell head (1.5e-6 at k 2, 1.9e-6 at k 3).
  For scale: CLXIII CPU vs CLXIII CUDA differ by 6.0e-3 in cell log-prob (pilot/ops/README).

Live path (`grow_identity.py run GROWN OUT` + `cmp BASE GROWN`; this tree's live_play.load_pilot + GenPilot, iw_press head, so the
widened rl ability head is loaded and width-checked by ability_head_live): B0 vs b0_grow_d256_l10, 1,718 decisions, 229 plays,
1,505 cell-head calls: **actions 1718/1718** (decision dicts minus the logged `p_play` float), decision-RNG states 1718/1718;
the 3 "tap" differences are only the logged follow-up `p_play` in the 7th digit; max |log-prob diff| cell 1.7e-5, card 7.6e-6,
gate 2.8e-6, value 2.4e-6, g (each copy) 1.7e-6 (a). Ability head (rl_royale.load_ability_head) on 86 rows: max press-logit
diff 1.9e-6 (a). Loaders: eval_gen.load_model (rl_royale learner) and model_gen.load_model (live, e1_eval) both build d 256 x 10
layers, 10,350,971 params, memory v2 + aux + cell_refine + tower_refine + cue_in (a).

Symmetry (`grow_identity.py sym`, one backward on 16 rows): with noise 0.01 the two copies' gradients differ by 2.7% (norm.weight),
0.9% (layer 0 norm1), 1.9% (layer 0 linear2 bias); with noise 0 by exactly 0 on all of them (a). Head readers (gate_head,
cell_key) differ by 5e-8 at step 0 because their INPUTS are still exact copies; they diverge once the residual copies do after
the first update (b). A larger `--noise` breaks it faster at no identity cost (the fp64 residual did not move with noise) (b).

Check: `grow_identity.py model B0 GROWN ROWS fp64 40` prints `GROW_IDENTITY PASS` and exits 0 (argmax all equal, fp64 <= 1e-5).

## 4. Latency (batch 1, the decide path = encode_gen + heads_gen + the cell head of the 4 hand slots, 200 reps on recorded rows)
| model | params | laptop CPU, 2 threads p50 / p90 / p99 |
|---|---|---|
| B0 | 2.23 M | 67.6 / 80.1 / 128.4 ms |
| B0 -> 256 x 10 | 10.35 M | 148.4 / 161.8 / 188.1 ms |
| B0 -> 384 x 4 | 10.77 M | 152.7 / 164.6 / 174.7 ms |
- (a) CPU: the grown model is 2.2x slower; live plays on the GPU, so this is the fallback / CPU-actor number, measured while
  live CLXIII ran on the same laptop (noisy).
- NOT measured: laptop GPU (RTX 5050). Live CLXIII was on it the whole session; COMMON forbids a second GPU job. Command for a
  quiet window: `icebow/.venv/Scripts/python.exe -B scratchpad/gauntlet/L74/scale/grow_identity.py lat
  icebow/data/bench/grow/b0_grow_d256_l10.pt .foreman/scratch/grow/id/b0_cpu.rows.pt cuda 2` (and the same for B0 / 384x4).
  Expectation (b): GPU batch 1 is launch-bound (ONE_FORWARD 1.3: 497 vs 548 kernels for 1.76 M vs 11.1 M), so 384 x 4 (4 layers,
  same kernel count as B0) should be close to B0's eager time, and 256 x 10 adds ~6 layers of launches; the curve's 11.1 M
  graph replay was 1.9 ms on a 4090. CLXIII-family models still carry refine modules that broke CUDA-graph capture (ONE_FORWARD).

## 5. What rl_royale needs to train it
- Loading: nothing. `init: icebow/data/bench/grow/b0_grow_d256_l10.pt`; the learner (eval_gen.load_model) and actors
  (GenModel(d=args.d, layers=args.layers), rl_royale `base.update(d=..., layers=...)`) read d / layers from args (a for the two
  loaders, b for a real run: the pod smoke is owed). The fresh Adam is built on all params (no init optimizer state is read).
- Which params get gradients: ALL trunk + head params (copied and new). Pilot config keeps the memory encoder frozen as for B0
  (same mem.* names). The rl ability head is separate (g detached) and loop_learner loads it strictly from rl["ability_head"]
  (d_g 256 now). New layers: only their out_proj / linear2 get a nonzero gradient at step 0; in_proj / linear1 / LN from step 1.
- lr (b, untested): Adam moves each element by ~lr regardless of fan-in, and a reader of k copies has k columns doing the old
  column's job, so at the same lr the function moves ~k x faster through those weights early on (muP intuition: hidden lr ~
  1 / fan-in). Proposal: lr 1e-5 / k = 5e-6 for k = 2, OR keep 1e-5 and rely on kl_stop_prev 0.02 (the step-size limit)
  -- measure update-0 KL / early-stop epoch fraction for both before a long run. One change per experiment: the size change IS
  the experiment, so run grown-at-5e-6 vs B0 at its pilot lr, and the lr variant separately.
- Warm-up (b): a short lr warm-up (e.g. linear over the first 5 updates) on top of the pilot's 5 critic warm-up updates, because
  the new zero layers and the copy asymmetry both start at a saddle-like point; the value head itself is intact (V = B0's V).
- grad_clip 0.5 is a GLOBAL norm over ~4.6x more params: monitor the u0 grad norm (b) -- if it clips much more often than B0's,
  the effective step shrinks.
- Learner time scales with size (~42 s / update at 1.76 M, PLAN 4a; the fast loop is learner-bound): the grown model's learner
  time is not measured (b).
- Do not re-base on imitation: the grown model IS B0 at u0 (section 3), which is the point of the method.

## 6. Choice of shape (b)
256 x 10 (10.35 M; depth + width; nearest to the curve's 320 x 7 / 11.1 M aspect) vs 384 x 4 (10.77 M; width only, no new
layers, same depth = fewer GPU launches). Both are identical to B0 at u0 (section 3). The curve (v1) does not separate width
from depth; which one learns faster under RL is untested. Proposal: GPU-latency both in a quiet window, then RL the one that
passes the latency gate (p99 < 100 ms full decide on the RTX 5050), 256 x 10 first if both pass.
