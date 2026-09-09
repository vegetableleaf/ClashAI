#!/bin/bash
# L67d (option B), relaunch after the merge fix: 3 seeds IN PARALLEL (the per-row token padding in
# train_s1.Rows.batch is Python-side, so one process leaves the GPU mostly idle; 622,923 rows would take
# ~200 min/seed sequentially = 10 h). Dataset build + merge are already done and are NOT redone.
cd /c/Users/benpe/ClashBot
set -e
O=scratchpad/gauntlet/L67/s1_v6aug
PY=./icebow/.venv/Scripts/python.exe
ls icebow/data/pipeline/ | grep -q s1_icebow_v6aug && { echo "REFUSING: s1_icebow_v6aug_* already exists"; exit 3; }
test -f icebow/data/pipeline/s1_dataset_v6aug.npz || { echo "REFUSING: augmented dataset missing"; exit 3; }

for s in 0 1 2; do
  $PY -m pipeline.train_s1 icebow --seed $s --epochs 20 --data icebow/data/pipeline/s1_dataset_v6aug.npz \
      --tag v6aug --grid lattice --out-dir $O > $O/train_icebow_v6aug_s$s.log 2>&1 &
done
wait
for s in 0 1 2; do tail -1 $O/train_icebow_v6aug_s$s.log | cut -c1-260; done

C="icebow/data/pipeline/s1_icebow_v6aug_s0.pt icebow/data/pipeline/s1_icebow_v6aug_s1.pt icebow/data/pipeline/s1_icebow_v6aug_s2.pt"
$PY -m pipeline.eval_s1 icebow $C --data icebow/data/pipeline/s1_dataset.npz > $O/eval_v3val_icebow_v6aug.out 2>&1
tail -3 $O/eval_v3val_icebow_v6aug.out | cut -c1-260
$PY -m pipeline.eval_s1 icebow $C --data scratchpad/gauntlet/L67/s1_dataset_v3_degraded_s0.npz > $O/eval_v3degraded_icebow_v6aug.out 2>&1
tail -3 $O/eval_v3degraded_icebow_v6aug.out | cut -c1-260
echo "ICEBOW_V6AUG_DONE $(date -u +%H:%M)"
