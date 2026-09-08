#!/bin/bash
# L67d (option B), final schedule. Measured: one epoch on the 622,923-row augmented set is ~16 min, so three
# seeds end to end sequentially would run past noon. RAM measured at 2.3 GB per train_s1 process and 3 in
# parallel exhausted the box (160 MB free), but TWO fit (~2.4 GB free with both up). So: seed 1 joins the
# already-running seed 0, seed 2 follows them, and each eval runs on whatever seeds exist at that point --
# the 2-seed read is a SCREEN, and the 3-seed read is the result.
cd /c/Users/benpe/ClashBot
O=scratchpad/gauntlet/L67/s1_v6aug
PY=./icebow/.venv/Scripts/python.exe
D=icebow/data/pipeline/s1_dataset_v6aug.npz

$PY -m pipeline.train_s1 icebow --seed 1 --epochs 20 --data $D --tag v6aug --grid lattice --out-dir $O \
    > $O/train_icebow_v6aug_s1.log 2>&1 &
S1=$!
while ps -ef | grep -q "[t]rain_s1 icebow --seed 0 --epochs 20 --data $D"; do sleep 120; done
echo "seed 0 done $(date -u +%H:%M): $(tail -1 $O/train_icebow_v6aug_s0.log | cut -c1-200)"
wait $S1
echo "seed 1 done $(date -u +%H:%M): $(tail -1 $O/train_icebow_v6aug_s1.log | cut -c1-200)"

# 2-seed SCREEN on both VALs while seed 2 trains
C2="icebow/data/pipeline/s1_icebow_v6aug_s0.pt icebow/data/pipeline/s1_icebow_v6aug_s1.pt"
$PY -m pipeline.train_s1 icebow --seed 2 --epochs 20 --data $D --tag v6aug --grid lattice --out-dir $O \
    > $O/train_icebow_v6aug_s2.log 2>&1 &
S2=$!
$PY -m pipeline.eval_s1 icebow $C2 --data icebow/data/pipeline/s1_dataset.npz > $O/eval2_v3val.out 2>&1
$PY -m pipeline.eval_s1 icebow $C2 --data scratchpad/gauntlet/L67/s1_dataset_v3_degraded_s0.npz > $O/eval2_v3degraded.out 2>&1
echo "SCREEN_2SEED_DONE $(date -u +%H:%M)"
wait $S2
echo "seed 2 done $(date -u +%H:%M): $(tail -1 $O/train_icebow_v6aug_s2.log | cut -c1-200)"

C3="$C2 icebow/data/pipeline/s1_icebow_v6aug_s2.pt"
$PY -m pipeline.eval_s1 icebow $C3 --data icebow/data/pipeline/s1_dataset.npz > $O/eval_v3val_icebow_v6aug.out 2>&1
tail -3 $O/eval_v3val_icebow_v6aug.out | cut -c1-260
$PY -m pipeline.eval_s1 icebow $C3 --data scratchpad/gauntlet/L67/s1_dataset_v3_degraded_s0.npz > $O/eval_v3degraded_icebow_v6aug.out 2>&1
tail -3 $O/eval_v3degraded_icebow_v6aug.out | cut -c1-260
echo "ICEBOW_V6AUG_DONE $(date -u +%H:%M)"
