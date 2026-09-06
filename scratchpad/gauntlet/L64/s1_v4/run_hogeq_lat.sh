#!/bin/bash
# Lattice label convention (§5cs.70): hogeq S1 on v3 (baseline under the new convention) then on v4, 3 seeds each,
# all evaluated on the v3 val rows. Chained after the naive v4 run (HOGEQ_V4_DONE) so trainings never overlap.
cd /c/Users/benpe/ClashBot
O=scratchpad/gauntlet/L64/s1_v4
until grep -q HOGEQ_V4_DONE $O/run_hogeq_v4.out; do sleep 60; done
echo "start lat $(date -u +%H:%M)"
for s in 0 1 2; do
  ./icebow/.venv/Scripts/python.exe -m pipeline.train_s1 hogeq --seed $s --epochs 20 --data hogeq/data/pipeline/s1_dataset.npz --tag lat --grid lattice --out-dir $O > $O/train_hogeq_lat_s$s.log 2>&1
  tail -1 $O/train_hogeq_lat_s$s.log | cut -c1-300
done
echo "v3-lat done $(date -u +%H:%M)"
./icebow/.venv/Scripts/python.exe -m pipeline.eval_s1 hogeq hogeq/data/pipeline/s1_hogeq_lat_s0.pt hogeq/data/pipeline/s1_hogeq_lat_s1.pt hogeq/data/pipeline/s1_hogeq_lat_s2.pt --data hogeq/data/pipeline/s1_dataset.npz > $O/eval_v3val_hogeq_lat.out 2>&1
echo HOGEQ_V3LAT_DONE
for s in 0 1 2; do
  ./icebow/.venv/Scripts/python.exe -m pipeline.train_s1 hogeq --seed $s --epochs 20 --data hogeq/data/pipeline/s1_dataset_v4.npz --tag v4lat --grid lattice --out-dir $O > $O/train_hogeq_v4lat_s$s.log 2>&1
  tail -1 $O/train_hogeq_v4lat_s$s.log | cut -c1-300
done
./icebow/.venv/Scripts/python.exe -m pipeline.eval_s1 hogeq hogeq/data/pipeline/s1_hogeq_v4lat_s0.pt hogeq/data/pipeline/s1_hogeq_v4lat_s1.pt hogeq/data/pipeline/s1_hogeq_v4lat_s2.pt --data hogeq/data/pipeline/s1_dataset.npz > $O/eval_v3val_hogeq_v4lat.out 2>&1
echo HOGEQ_V4LAT_DONE $(date -u +%H:%M)
