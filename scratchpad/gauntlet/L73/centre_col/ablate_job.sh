#!/bin/bash
# Lead ablation: R3 u0050 + barrel + CellRefine v2 for 2 EPOCHS (vs the 1-epoch run), then v2-benchmark SIM.
# Holds gpu.lock so cand.sh waits.
HERE="$(cd "$(dirname "$0")" && pwd)"; cd "$HERE/../../../.."
touch "$HERE/gpu.lock"
R=/c/Users/benpe/ClashBot/icebow/data/bench/rl_royale/rseries_r3
/c/Users/benpe/ClashBot/icebow/.venv/Scripts/python.exe -m pipeline.train_cell_refine --base $R/rseries_r3_u0050_barrel.pt \
    --data /c/Users/benpe/ClashBot/icebow/data/pipeline/gen_dataset_v32_fv5.npz --epochs 2 --channels 48 --layers 5 \
    --out $R/rseries_r3_u0050_barrel_cellref5e2.pt > "$HERE/train_r3_barrel_e2.out" 2> "$HERE/train_r3_barrel_e2.err"
rm -f "$HERE/gpu.lock"
scp -i ~/.ssh/clashbot_gcp $R/rseries_r3_u0050_barrel_cellref5e2.pt clashbot-gauntlet@34.148.91.90:ClashBot/icebow/data/bench/rl_royale/rseries_r3/
ssh -i ~/.ssh/clashbot_gcp clashbot-gauntlet@34.148.91.90 "cd ~/ClashBot && export SIM_EXTRA=\"--opp-policy sample --opp-T 0.3\" && (~/cellref_sim.sh r3_barrel_cellref5e2_samp icebow/data/bench/rl_royale/rseries_r3/rseries_r3_u0050_barrel_cellref5e2.pt) > /dev/null 2>&1 < /dev/null &"
echo ABLATE_DONE
