# GROW-10M: function-preserving growth of CLXIII / B0 to ~10 M (PLAN Pillar 4a step 3)

Labels: (a) measured (number + source), (b) plausible, untested, (c) contradicted.

## STATUS (restart point)
- M1 done (321088b): `grow.py` + draft `grow_identity.py`; grown checkpoints (local, icebow/data is untracked) in
  `icebow/data/bench/grow/`: `b0_grow_d256_l10.pt` (sha 673dd261...), `b0_grow_d384_l4.pt` (24c43276...),
  `clxiii_grow_d256_l10.pt` (caf475e6...), all `--noise 0.01 --seed 0 --place interleave`.
- M2 running: CPU live replay of B0 with row capture -> `.foreman/scratch/grow/id/b0_cpu.pt` + `.rows.pt`.
  Restart: `icebow/.venv/Scripts/python.exe -B scratchpad/gauntlet/L74/scale/grow_identity.py run icebow/data/bench/rl_royale/b0/b0_clxiii_s3aux_grafted.pt .foreman/scratch/grow/id/b0_cpu.pt --rows`
- M2 done: rows captured (1,718 decisions, 79 MB, local only). Model-level b0_grow_d256_l10 vs B0: fp64 all heads <= 1.5e-6
  log-prob, all argmax equal; fp32 at the base model's own fp32 floor. Running: live-path replay of the grown model + k=3 /
  CLXIII variants + symmetry check (`grow_identity.py run|cmp|model|sym`, commands in the file header).
