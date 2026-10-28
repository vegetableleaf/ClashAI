# LOOP-SRV: the fast loop's GPU policy server (pipeline/policy_server.py `PolicyServer`)

## STATUS (2026-10-28)
- DONE: the code, the identity tests (6/6 pass on pod 33920, 4090), and the bare-forward bench (results/bare.json).
- RUNNING: the mix bench on 33920, `/workspace/loopsrv` (tree = git HEAD pipeline + this ticket's two files).
  Restart:
  `cd /workspace/loopsrv && OMP_NUM_THREADS=2 /workspace/venvf15/bin/python srv_bench.py --part mix --mode graphs --out mix_graphs.json`
  (`--mode eager` for the comparison).
- NEXT: the 8-GPU projection (below) from the mix numbers.

## Interface (LOOP-INT)
- Server, one per GPU:
  ```
  srv = PolicyServer(models, listen="/dev/shm/loop/srv{g}.sock", device="cuda", mode="graphs").start(warm={name: rows})
  ```
  `models` = `[{name, policy, spec=row_spec(rows, gen_row_keys(model)), cfg, block_max, swap, watch}]`.
- Producer: `cl = connect(address)`.
  - `fs = cl.forward([(name, rows, n), ...])` takes at most one block per model and sends them all at once.
  - Each `Fwd` carries `.heads` (every heads_t head, numpy), `.p` and `.ver`.
  - `cl.cells(f, ids, slots)` and `cl.ability(f, ids, feat)` are computed from the SAME batch (its encodings and weight copy).
  - `cl.done(fs)` releases the batches.
  - `cl.decide_fwd(f, allowed, stalled, rngs)` = the S4b P1 sample decide, with every dict tagged `wver`.
- Weight versions (agreed with LOOP-LRN), DIR = /dev/shm/loop/weights:
  - the learner writes `DIR/learner.v{V:08d}.pt` = `{"version": V, "state_dict": actor_bytes dict}`, then `DIR/learner.latest`, each by a .tmp file plus os.replace;
  - a `watch=DIR` model serves nothing until V=0 arrives;
  - `__ability__.` tensors load into an AbilityHead per copy;
  - the learner deletes v{V-3} (servers never delete).
- Learner snapshots as opponents (PFSP, up to 13): one model entry each, with the learner's spec and `swap=True`; refresh one with `push(name, V, sd)` (or `watch` under its own name). Each row's `wver` says which version answered.
- `ProcServer(policy, spec, n, block_max, cfg)` = S4b's one-model form, unchanged API.

## Guarantees and their evidence (a)
- `pipeline/tests/test_policy_server.py`, 6 passed on 33920:
  - S4b's 3 tests;
  - two models (CLXIII; CLXIV with memory v2 inputs) x 2 producer processes x 2 rounds, with weight version 1 (new weights + an ability head) pushed between rounds: actions equal the block-by-block CPU decide with the tagged version's weights, log-probs < 1e-5, ability z < 1e-5, wver 0 -> 1 for the learner and 0 for the opponent;
  - the same on CUDA, eager-padded and graphs, against the CPU reference.
- fp32 default = TF32 off in matmuls AND in cuDNN convs (torch's default cudnn.allow_tf32=True affected cell_refine's convs in S4b).
