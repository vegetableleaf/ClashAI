#!/bin/bash
# OPP-SIEGE fix 1: ftR + X-Bow-window rows oversampled K x (train_gen --opp-oversample), then _sim.pt, level A, per-card check.
# usage: bash run_ftx.sh NAME K STEPS     (30408; resumable per stage: a stage whose output exists is skipped)
set -euo pipefail
NAME=$1; K=$2; STEPS=$3
S=/workspace/siege; CB=$S/opp/cb; PY=$S/venv/bin/python; O=$CB/scratchpad/gauntlet/L74/plan1026/opp; D=$S/opp/live
OUT=$S/ft/$NAME; mkdir -p $OUT
export PYTHONPATH=$CB CB=$CB CUDA_VISIBLE_DEVICES=0 OMP_NUM_THREADS=8 MKL_NUM_THREADS=8 PYTHONDONTWRITEBYTECODE=1
cd $CB
[ -s $S/ft/mask_mix.npy ] || $PY $O/siege/make_mask.py $D/mix_train $D/mix_train_memory.npz $S/ft/mask_mix.npy | tee $S/ft/mask_mix.json
[ -s $OUT/opp_ft_s0.pt ] || $PY -u -m pipeline.train_gen --data $D/mix_train --out-dir $OUT --tag ft --seed 0 \
  --init $D/ft_s0/opp_ft_s0.pt --d-c 64 --bs 128 --lr 2e-5 --grid lattice --amp bf16 --feature-version 6 \
  --opp-timing --opp-ability --opp-deck-enc --opp-ctx band=6,mode=8,era=4 \
  --memory v2 --memory-tables $D/mix_train_memory.npz --hand-inferred mask_card \
  --max-steps $STEPS --eval-every 500 --eval-rows 46935 --opp-oversample $S/ft/mask_mix.npy:$K > $OUT/train.log 2>&1
[ -s $OUT/opp_ft_R_sim.pt ] || $PY $O/attach_sim.py --ckpt $OUT/opp_ft_s0.pt --data $D/mix_train --out $OUT/opp_ft_R_sim.pt --band 6 --mode 1 --era 2
[ -s $OUT/A_live_cal.json ] || $PY $O/siege/siege_a.py --ckpt $OUT/opp_ft_R_sim.pt --data $D/live_cal --memory-tables $D/live_cal_memory.npz --out $OUT/A_live_cal.json --dump $OUT/D_live_cal.npz > $OUT/A.log 2>&1
$PY $O/siege/cardcal.py $OUT/D_live_cal.npz > $OUT/cardcal.md
echo FTX_DONE $NAME
