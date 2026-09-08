#!/bin/bash
# L67d confirmation: a DISJOINT slice for the gate finding -- a third recorded session the first read never
# touched, and the other two seeds. One session + one checkpoint is a screen, not a result.
cd /c/Users/benpe/ClashBot
P=./icebow/.venv/Scripts/python.exe
L=scratchpad/gauntlet/L67

$P $L/student_dryrun.py icebow/data/sessions/20260804_173304 --ckpt icebow/data/pipeline/s1_icebow_v6lat_s0.pt \
   --out $L/dryrun_20260804_173304.jsonl --every 12 --limit 400 >> $L/confirm_wave.out 2>&1

for S in 1 2; do
  $P $L/student_dryrun.py icebow/data/sessions/20260815_222309 --ckpt icebow/data/pipeline/s1_icebow_v6lat_s$S.pt \
     --out $L/dryrun_s${S}_20260815_222309.jsonl --every 12 --limit 400 >> $L/confirm_wave.out 2>&1
done

# gate distributions, elixir-matched, for each seed on its own live frames
$P $L/gate_dist.py --ckpt icebow/data/pipeline/s1_icebow_v6lat_s0.pt --clean icebow/data/pipeline/s1_dataset.npz \
   --degraded $L/s1_dataset_v3_degraded_s0.npz --live $L/dryrun_20260804_173304.jsonl --elixir-min 5 \
   --out $L/gate_dist_s0_session3_e5.json >> $L/confirm_wave.out 2>&1
for S in 1 2; do
  $P $L/gate_dist.py --ckpt icebow/data/pipeline/s1_icebow_v6lat_s$S.pt --clean icebow/data/pipeline/s1_dataset.npz \
     --degraded $L/s1_dataset_v3_degraded_s0.npz --live $L/dryrun_s${S}_20260815_222309.jsonl --elixir-min 5 \
     --out $L/gate_dist_s${S}_e5.json >> $L/confirm_wave.out 2>&1
done
echo CONFIRM_WAVE_DONE >> $L/confirm_wave.out
