#!/bin/bash
# Extra GPU job while no candidate is ready: CellRefine v2 (1 epoch) on gen_v32_s0; holds gpu.lock so cand.sh waits.
HERE="$(cd "$(dirname "$0")" && pwd)"; cd "$HERE/../../../.."
touch "$HERE/gpu.lock"
D=/c/Users/benpe/ClashBot/icebow/data/pipeline
/c/Users/benpe/ClashBot/icebow/.venv/Scripts/python.exe -m pipeline.train_cell_refine --base $D/gen_v32_s0/gen_s0.pt \
    --data $D/gen_dataset_v32_fv5.npz --epochs 1 --channels 48 --layers 5 --out $D/gen_v32_s0/gen_s0_cellref5.pt \
    > "$HERE/train_s0_v2.out" 2> "$HERE/train_s0_v2.err"
rm -f "$HERE/gpu.lock"
