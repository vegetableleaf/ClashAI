#!/bin/bash
cd /c/Users/benpe/ClashBot
for d in icebow hogeq; do for s in 0 1 2; do
  ./icebow/.venv/Scripts/python.exe -m pipeline.train_s1 $d --seed $s --epochs 20 --out-dir scratchpad/gauntlet/L64/s1 > scratchpad/gauntlet/L64/s1/train_${d}_s${s}.log 2>&1
done; done
echo ALL_SEEDS_DONE
