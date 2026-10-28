#!/usr/bin/env bash
# run_pretrain.sh DATA(.npz | extracted dir) OUTDIR TAG D LAYERS MAX_STEPS [GPU] [SEED] -- P2-OPP pretrain (code copy OPP_CODE,
# default /workspace/opp/cbt). env CELL_REFINE=C,LAYERS (P2-OPP2 v1: e.g. 32,4) adds --opp-cell-refine; absent = the v0 build.
# All plan heads on: timing (slot survival), ability press, deck encoder + deck id, band / mode / era tokens, memory v2
# trained jointly (memory tables = DATA's *_memory.npz). Held-out curve every 2,500 steps on 100k split-1 rows.
set -euo pipefail
DATA=$1; OUT=$2; TAG=$3; D=$4; L=$5; STEPS=$6; GPU=${7:-1}; SEED=${8:-0}
CB=${OPP_CODE:-/workspace/opp/cbt}
mkdir -p "$OUT"
export PYTHONPATH=$CB:/workspace/redrive/pylib CUDA_VISIBLE_DEVICES=$GPU OMP_NUM_THREADS=4 MKL_NUM_THREADS=4 PYTHONDONTWRITEBYTECODE=1
MEM=${DATA%/}; MEM=${MEM%.npz}_memory.npz
exec /workspace/venvf16/bin/python -u -m pipeline.train_gen --data "$DATA" --out-dir "$OUT" --tag "$TAG" --seed "$SEED" ${CELL_REFINE:+--opp-cell-refine $CELL_REFINE} \
  --d "$D" --layers "$L" --d-c 64 --bs 256 --lr 3e-4 --grid lattice --amp bf16 --feature-version 6 \
  --opp-timing --opp-ability --opp-deck-enc --opp-ctx band=6,mode=8,era=4 \
  --memory v2 --memory-tables "$MEM" --hand-inferred mask_card \
  --max-steps "$STEPS" --eval-every 2500 --eval-rows 100000
