#!/bin/bash
# usage: run_size_v1.sh NAME D LAYERS [SEED] [EPOCHS] [EXTRA] -- curve v1: curve v0's recipe (run_size.sh) unchanged except
# the data (mix_v1.npz = v32 + HF re-drive shards), the epoch count and the memory-mapped load (--mmap-cache-dir: pod
# 30408 caps the container at 62 GB; values identical). Trains on the pod, then scale_eval_v1. Restart = re-run.
NAME=$1; D=$2; L=$3; SEED=${4:-0}; EP=${5:-1}; EXTRA=${6:-}
W=/workspace/p4; R=$W/runs/${NAME}_s$SEED; mkdir -p $R
export OMP_NUM_THREADS=3 MKL_NUM_THREADS=3 PYTHONDONTWRITEBYTECODE=1 CUDA_VISIBLE_DEVICES=${GPU:-0}
PY=${PY:-/workspace/venvf16/bin/python}
cd $W/code
rm -rf $W/data/cache_$NAME $W/data/cache_ev_$NAME
nice -n 10 $PY -u -m pipeline.train_gen --data $W/data/mix_v1.npz --seed $SEED --epochs $EP \
  --val-sample 30000 --grid lattice --feature-version 5 --amp bf16 --allow-causal-tti-unknowns --inputs-only-arm \
  --d $D --layers $L --out-dir $R --tag $NAME --mmap-cache-dir $W/data/cache_$NAME $EXTRA > $R/train.out 2>&1
echo "train exit $?" >> $R/train.out
rm -rf $W/data/cache_$NAME
$PY -u scratchpad/gauntlet/L74/scale/v1/scale_eval_v1.py $W/code $R/gen_${NAME}_s$SEED.pt $W/data/mix_v1.npz $R/eval.json \
  --mmap-cache-dir $W/data/cache_ev_$NAME > $R/eval.out 2>&1
echo "eval exit $?" >> $R/eval.out
rm -rf $W/data/cache_ev_$NAME
