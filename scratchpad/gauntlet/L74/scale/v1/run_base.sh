#!/bin/bash
# run_base.sh STAGE OUT STEPS [INIT] -- P4-10M icebow successor base (imitation): CLXIII's feature version 6 + the memory
# v2 encoder (trained jointly from step 0, zero_empty), d 320 x 7 (curve v0's 10.6 M point + fv6 + memory), train_gen's
# step trainer (held-out total every EVERY steps on EROWS split-1 rows = HF held-out; best checkpoint kept).
#   STAGE pre:  all decks (mix_v1.npz + mix_v1_memory.npz, memory-mapped), lr 3e-4
#   STAGE ice:  fine-tune from INIT on the icebow-deck rows (ice_v1.npz + ice_v1_memory.npz), lr 1e-4
# env: GPU (0), EVERY (5000), EROWS (100000). Restart = re-run the same command (a fresh run).
STAGE=$1; OUT=$2; STEPS=$3; INIT=${4:-}
W=/workspace/p4; PY=${PY:-/workspace/venvf16/bin/python}
if [ "$STAGE" = ice ]; then DATA=$W/data/ice_v1.npz; LR=1e-4; X="--init $INIT"; MM=""
else DATA=$W/data/mix_v1.npz; LR=3e-4; X=""; MM="--mmap-cache-dir $W/data/cache_base_$STAGE"; fi
mkdir -p $OUT
export CUDA_VISIBLE_DEVICES=${GPU:-0} OMP_NUM_THREADS=4 MKL_NUM_THREADS=4 PYTHONDONTWRITEBYTECODE=1
cd $W/code
rm -rf $W/data/cache_base_$STAGE
nice -n 10 $PY -u -m pipeline.train_gen --data $DATA --out-dir $OUT --tag base_$STAGE --seed 0 \
  --d 320 --layers 7 --d-c 64 --bs 256 --lr $LR --grid lattice --amp bf16 --feature-version 6 \
  --memory v2 --memory-tables ${DATA%.npz}_memory.npz --hand-inferred mask_card \
  --max-steps $STEPS --eval-every ${EVERY:-5000} --eval-rows ${EROWS:-100000} $X $MM > $OUT/train.out 2>&1
echo "train exit $?" >> $OUT/train.out
rm -rf $W/data/cache_base_$STAGE
