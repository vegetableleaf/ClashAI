#!/bin/bash
# Owner 2026-10-14: refit the refine heads on the RL model's OWN trunk instead of grafting r3c's (rltest/FINDING.md:
# grafted heads +5.8 pp on ADAPT -> +1.0 on r1). Same recipe as the old live model (L73/centre_col/r3c_barrel2k.sh +
# L73/chip_rocket w_chip 2): CellRefine 2 epochs (48 channels, 5 layers) on the frozen base, then TowerRefine w_chip 2,
# 4000 steps on the frozen base+CellRefine, folded (fold_tower_refine.py). The base keeps its own projectile_target_*.
# Needs CUDA (train_tower_refine.py). Usage from the repo root: bash scratchpad/gauntlet/L74/rltest/refit_heads.sh BASE.pt NAME
set -Eeuo pipefail
BASE=$1; NAME=$2; PY=${PY:-/workspace/venv33/bin/python}
DATA=icebow/data/pipeline/gen_dataset_v32_fv5.npz
CELL=${BASE%.pt}_cellref.pt; OUT=${BASE%.pt}_refit.pt; TR=tr_w2_$NAME.pt
O=${O:-/workspace/results/REFIT_$NAME}; mkdir -p $O
export PYTHONPATH=$PWD PYTHONDONTWRITEBYTECODE=1
echo "$(date -u +%T) CellRefine on $BASE"
$PY -m pipeline.train_cell_refine --base $BASE --data $DATA --epochs 2 --channels 48 --layers 5 --out $CELL > $O/cellref.out 2> $O/cellref.err
echo "$(date -u +%T) TowerRefine w_chip 2 on $CELL"
$PY scratchpad/gauntlet/L73/chip_rocket/train_tower_refine.py --w-chip 2 --steps 4000 --base $CELL --out $TR > $O/towerref.out 2>&1
$PY scratchpad/gauntlet/L74/rltest/fold_tower_refine.py $CELL scratchpad/gauntlet/L73/chip_rocket/$TR $OUT > $O/fold.out 2>&1
sha256sum $BASE $CELL $OUT > $O/refit.sha
echo "$(date -u +%T) refit done -> $OUT"
