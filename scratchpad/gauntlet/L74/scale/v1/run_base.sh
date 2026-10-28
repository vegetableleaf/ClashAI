#!/bin/bash
# run_base.sh STAGE OUT STEPS [GPU] [INIT] -- P4-10M icebow successor base (imitation): CLXIII's feature version 6 +
# the memory v2 encoder (trained jointly from step 0, zero_empty), d 320 x 7 (curve v0's 10.6 M point + fv6 + memory),
# train_gen's step trainer (held-out total every 5,000 steps on 100k split-1 rows; best checkpoint kept).
#   STAGE pre:  all decks (mix_v1.npz + mix_v1_memory.npz), lr 3e-4
#   STAGE ice:  fine-tune from INIT on the icebow-deck rows (ice_v1.npz + ice_v1_memory.npz), lr 1e-4
# Restart = re-run the same command (a fresh run; OUT's curve jsonl is appended to).
STAGE=$1; OUT=$2; STEPS=$3; GPU=${4:-0}; INIT=${5:-}
W=/workspace/p4; PY=${PY:-/workspace/venvf16/bin/python}
if [ "$STAGE" = pre ]; then DATA=$W/data/mix_v1.npz; LR=3e-4; X=""; else DATA=$W/data/ice_v1.npz; LR=1e-4; X="--init $INIT"; fi
mkdir -p $OUT
export CUDA_VISIBLE_DEVICES=$GPU OMP_NUM_THREADS=4 MKL_NUM_THREADS=4 PYTHONDONTWRITEBYTECODE=1
cd $W/code
nice -n 10 $PY -u -m pipeline.train_gen --data $DATA --out-dir $OUT --tag base_$STAGE --seed 0 \
  --d 320 --layers 7 --d-c 64 --bs 256 --lr $LR --grid lattice --amp bf16 --feature-version 6 \
  --memory v2 --memory-tables ${DATA%.npz}_memory.npz --hand-inferred mask_card \
  --max-steps $STEPS --eval-every 5000 --eval-rows 100000 $X > $OUT/train.out 2>&1
echo "train exit $?" >> $OUT/train.out
