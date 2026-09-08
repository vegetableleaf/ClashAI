#!/bin/bash
# L67d (option B): degrade() as TRAINING AUGMENTATION. Base corpus held at v6 (same as v6lat) so augmentation is
# the only variable. Val rows stay clean -> same checkpoint rule as v6lat. Graded on clean v3 VAL AND the degraded twin.
cd /c/Users/benpe/ClashBot
set -e
O=scratchpad/gauntlet/L67/s1_v6aug
mkdir -p $O
ls icebow/data/pipeline/ | grep -q s1_icebow_v6aug && { echo "REFUSING: s1_icebow_v6aug_* already exists"; exit 3; }
PY=./icebow/.venv/Scripts/python.exe

$PY scratchpad/gauntlet/L67/build_degraded.py icebow --corpus scratchpad/gauntlet/ext/corpus_v6/icebow \
    --out scratchpad/gauntlet/L67/s1_dataset_v6_degraded_s0.npz --seed 0 > $O/build_degraded_v6.out 2>&1
tail -n 1 $O/build_degraded_v6.out | cut -c1-260
$PY scratchpad/gauntlet/L67/merge_aug.py --clean icebow/data/pipeline/s1_dataset_v6.npz \
    --degraded scratchpad/gauntlet/L67/s1_dataset_v6_degraded_s0.npz \
    --out icebow/data/pipeline/s1_dataset_v6aug.npz > $O/merge_aug.out 2>&1
tail -n 1 $O/merge_aug.out | cut -c1-300
for s in 0 1 2; do
  $PY -m pipeline.train_s1 icebow --seed $s --epochs 20 --data icebow/data/pipeline/s1_dataset_v6aug.npz --tag v6aug --grid lattice --out-dir $O > $O/train_icebow_v6aug_s$s.log 2>&1
  tail -1 $O/train_icebow_v6aug_s$s.log | cut -c1-260
done
C="icebow/data/pipeline/s1_icebow_v6aug_s0.pt icebow/data/pipeline/s1_icebow_v6aug_s1.pt icebow/data/pipeline/s1_icebow_v6aug_s2.pt"
$PY -m pipeline.eval_s1 icebow $C --data icebow/data/pipeline/s1_dataset.npz > $O/eval_v3val_icebow_v6aug.out 2>&1
tail -3 $O/eval_v3val_icebow_v6aug.out | cut -c1-260
$PY -m pipeline.eval_s1 icebow $C --data scratchpad/gauntlet/L67/s1_dataset_v3_degraded_s0.npz > $O/eval_v3degraded_icebow_v6aug.out 2>&1
tail -3 $O/eval_v3degraded_icebow_v6aug.out | cut -c1-260
echo "ICEBOW_V6AUG_DONE $(date -u +%H:%M)"
