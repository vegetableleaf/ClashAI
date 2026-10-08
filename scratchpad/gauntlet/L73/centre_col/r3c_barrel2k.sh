#!/bin/bash
# R3c u0030: barrel branch with 2,000 updates, CellRefine 2ep on top, counterfactual, SIMs (v2 192 + barrel-heavy 96).
HERE="$(cd "$(dirname "$0")" && pwd)"; cd "$HERE/../../../.."
touch "$HERE/gpu.lock"
PY=/c/Users/benpe/ClashBot/icebow/.venv/Scripts/python.exe
DATA=/c/Users/benpe/ClashBot/icebow/data/pipeline/gen_dataset_v32_fv5.npz
REL=icebow/data/bench/rl_royale/rseries_r3c; D=/c/Users/benpe/ClashBot/$REL; S=rseries_r3c_u0030
OUT="$HERE/cand_r3c_u0030/barrel2k"; mkdir -p "$OUT"
VM=clashbot-gauntlet@34.148.91.90; KEY=~/.ssh/clashbot_gcp
$PY scratchpad/gauntlet/L73/barrel_branch/train_branch.py --base $D/$S.pt --data $DATA --out-dir $D/barrel2k_$S --updates 2000 --device cuda > "$OUT/barrel.out" 2>&1
cp $D/barrel2k_$S/gen_branch_s0.pt $D/${S}_barrel2k.pt; cp $D/barrel2k_$S/result.json "$OUT/barrel_result.json"
$PY -m pipeline.train_cell_refine --base $D/${S}_barrel2k.pt --data $DATA --epochs 2 --channels 48 --layers 5 --out $D/${S}_barrel2k_cellref.pt > "$OUT/cellref.out" 2> "$OUT/cellref.err"
rm -f "$HERE/gpu.lock"
scp -i $KEY $D/${S}_barrel2k.pt $D/${S}_barrel2k_cellref.pt $VM:ClashBot/$REL/
ssh -i $KEY $VM "cd ~/ClashBot && export SIM_EXTRA=\"--opp-policy sample --opp-T 0.3\" && (~/cellref_sim.sh r3c_u0030_barrel2k_cellref $REL/${S}_barrel2k_cellref.pt; ~/barrel_sim.sh r3c_u0030_barrel2k $REL/${S}_barrel2k.pt; ~/barrel_sim.sh r3c_u0030_barrel2k_cellref $REL/${S}_barrel2k_cellref.pt) > /dev/null 2>&1 < /dev/null &"
(cd scratchpad/gauntlet/L73/barrel_lane && CUDA_VISIBLE_DEVICES= $PY model_counterfactual.py --data $DATA --out "$OUT/cf.json" --ckpt barrel2k=$D/${S}_barrel2k.pt --ckpt barrel2k_cellref=$D/${S}_barrel2k_cellref.pt > "$OUT/cf.out" 2>&1)
echo R3C_2K_DONE
