#!/bin/bash
# OPP-SIEGE2 fix 2 (ONE learned change vs ftR): ftR fine-tuned with the rows of SUCCESSFUL human X-Bow defences oversampled K x
# (windows (t_x, t_x + 600] after an enemy reach X-Bow that did NOT lock; make_mask.py MASK_WALL=600 MASK_FAILED=1), else
# exactly run_ftx.sh's recipe (4,000 steps, bs 128, lr 2e-5, init ftR), then _sim.pt, level A + cardcal, then level B
# (CLXIII vs it, T 1, crforge 5e8089a4, G2 on, 4 x 480, same seeds as ftR5e). usage: bash run_ftd.sh NAME K STEPS (30408)
set -euo pipefail
NAME=$1; K=$2; STEPS=$3
S=/workspace/siege; CB=$S/opp/cb; PY=$S/venv/bin/python; O=$CB/scratchpad/gauntlet/L74/plan1026/opp; D=$S/opp/live
OUT=$S/ft/$NAME; MASK=$S/ft/mask_fail600.npy; mkdir -p $OUT
export PYTHONPATH=$CB CB=$CB CUDA_VISIBLE_DEVICES=0 OMP_NUM_THREADS=8 MKL_NUM_THREADS=8 PYTHONDONTWRITEBYTECODE=1
cd $CB
[ -s $MASK ] || MASK_WALL=600 MASK_FAILED=1 $PY $O/siege/make_mask.py $D/mix_train $D/mix_train_memory.npz $MASK | tee $S/ft/mask_fail600.json
[ -s $OUT/opp_ft_s0.pt ] || $PY -u -m pipeline.train_gen --data $D/mix_train --out-dir $OUT --tag ft --seed 0 \
  --init $D/ft_s0/opp_ft_s0.pt --d-c 64 --bs 128 --lr 2e-5 --grid lattice --amp bf16 --feature-version 6 \
  --opp-timing --opp-ability --opp-deck-enc --opp-ctx band=6,mode=8,era=4 \
  --memory v2 --memory-tables $D/mix_train_memory.npz --hand-inferred mask_card \
  --max-steps $STEPS --eval-every 500 --eval-rows 46935 --opp-oversample $MASK:$K > $OUT/train.log 2>&1
[ -s $OUT/opp_ft_R_sim.pt ] || $PY $O/attach_sim.py --ckpt $OUT/opp_ft_s0.pt --data $D/mix_train --out $OUT/opp_ft_R_sim.pt --band 6 --mode 1 --era 2
[ -s $OUT/A_live_cal.json ] || $PY $O/siege/siege_a.py --ckpt $OUT/opp_ft_R_sim.pt --data $D/live_cal --memory-tables $D/live_cal_memory.npz --out $OUT/A_live_cal.json --dump $OUT/D_live_cal.npz > $OUT/A.log 2>&1
$PY $O/siege/cardcal.py $OUT/D_live_cal.npz > $OUT/cardcal.md
echo FTX_DONE $NAME
cd $S/score && PY=$PY CB=$CB LIB=/workspace/crforge_main/5e8089a4/plain CRFORGE_TABLES=$S/crforge_cache/tables/16.402.22 \
  OPP_CKPT=$OUT/opp_ft_R_sim.pt OPP_T=1.0 WORKERS=44 CPUS=0-255 G2_ON=on \
  bash $CB/scratchpad/gauntlet/L74/opp_model/humanlike/run_closed.sh $NAME $S/score/rows/$NAME 741200 742000 742800 743600
