#!/bin/bash
# L67d (option B), SEQUENTIAL relaunch. Measured this loop: one train_s1 process on the 622,923-row
# augmented set holds ~2.3 GB, and three in parallel drove free RAM to 160 MB (guardrail: check RAM before
# launching). Seeds 1 and 2 were killed at epoch 0 (nothing lost); seed 0 was left running and this script
# picks up after it, then runs 1 and 2 one at a time.
cd /c/Users/benpe/ClashBot
set -e
O=scratchpad/gauntlet/L67/s1_v6aug
PY=./icebow/.venv/Scripts/python.exe

# wait out the seed-0 process that is already running
while ps -ef | grep -q "[t]rain_s1 icebow --seed 0 --epochs 20 --data icebow/data/pipeline/s1_dataset_v6aug.npz"; do sleep 60; done
tail -1 $O/train_icebow_v6aug_s0.log | cut -c1-260

for s in 1 2; do
  $PY -m pipeline.train_s1 icebow --seed $s --epochs 20 --data icebow/data/pipeline/s1_dataset_v6aug.npz \
      --tag v6aug --grid lattice --out-dir $O > $O/train_icebow_v6aug_s$s.log 2>&1
  tail -1 $O/train_icebow_v6aug_s$s.log | cut -c1-260
done

C="icebow/data/pipeline/s1_icebow_v6aug_s0.pt icebow/data/pipeline/s1_icebow_v6aug_s1.pt icebow/data/pipeline/s1_icebow_v6aug_s2.pt"
$PY -m pipeline.eval_s1 icebow $C --data icebow/data/pipeline/s1_dataset.npz > $O/eval_v3val_icebow_v6aug.out 2>&1
tail -3 $O/eval_v3val_icebow_v6aug.out | cut -c1-260
$PY -m pipeline.eval_s1 icebow $C --data scratchpad/gauntlet/L67/s1_dataset_v3_degraded_s0.npz > $O/eval_v3degraded_icebow_v6aug.out 2>&1
tail -3 $O/eval_v3degraded_icebow_v6aug.out | cut -c1-260
echo "ICEBOW_V6AUG_DONE $(date -u +%H:%M)"
