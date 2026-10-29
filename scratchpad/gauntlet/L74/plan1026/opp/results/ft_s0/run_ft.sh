#!/bin/bash
# P2-OPP2 live fine-tune: --init v1 seed 0 on live train block + 20% HF (mix_rows.py), held-out = live split 1 (time-ordered tail)
set -euo pipefail
OUT=${1:-/workspace/opp/live/ft_s0}; BS=${BS:-128}; LR=${LR:-2e-5}; STEPS=${STEPS:-12000}; INIT=${INIT:-/workspace/opp/v1/run_s0/opp_v1_s0.pt}
export PYTHONPATH=/workspace/opp/cb CUDA_VISIBLE_DEVICES=0 OMP_NUM_THREADS=4 MKL_NUM_THREADS=4 PYTHONDONTWRITEBYTECODE=1
cd /workspace/opp/cb
exec /workspace/venvf16/bin/python -u -m pipeline.train_gen --data /workspace/opp/live/mix_train --out-dir "$OUT" --tag ft --seed 0 \
  --init "$INIT" --d-c 64 --bs $BS --lr $LR --grid lattice --amp bf16 --feature-version 6 \
  --opp-timing --opp-ability --opp-deck-enc --opp-ctx band=6,mode=8,era=4 \
  --memory v2 --memory-tables /workspace/opp/live/mix_train_memory.npz --hand-inferred mask_card \
  --max-steps $STEPS --eval-every 500 --eval-rows 46935
