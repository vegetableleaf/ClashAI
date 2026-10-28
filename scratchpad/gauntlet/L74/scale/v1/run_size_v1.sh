#!/bin/bash
# usage: run_size_v1.sh NAME D LAYERS [SEED] [EPOCHS] [EXTRA] -- curve v1: curve v0's recipe (run_size.sh) unchanged except
# the data (mix_v1.npz = v32 + HF re-drive shards) and the epoch count. Trains on the pod, then scale_eval_v1.
NAME=$1; D=$2; L=$3; SEED=${4:-0}; EP=${5:-2}; EXTRA=${6:-}
W=/workspace/p4; R=$W/runs/${NAME}_s$SEED; mkdir -p $R
export OMP_NUM_THREADS=3 MKL_NUM_THREADS=3 PYTHONDONTWRITEBYTECODE=1
PY=${PY:-/workspace/venvf16/bin/python}
cd $W/code
nice -n 10 $PY -u -m pipeline.train_gen --data $W/data/mix_v1.npz --seed $SEED --epochs $EP \
  --val-sample 30000 --grid lattice --feature-version 5 --amp bf16 --allow-causal-tti-unknowns --inputs-only-arm \
  --d $D --layers $L --out-dir $R --tag $NAME $EXTRA > $R/train.out 2>&1
echo "train exit $?" >> $R/train.out
$PY -u scratchpad/gauntlet/L74/scale/v1/scale_eval_v1.py $W/code $R/gen_${NAME}_s$SEED.pt $W/data/mix_v1.npz $R/eval.json \
  > $R/eval.out 2>&1
echo "eval exit $?" >> $R/eval.out
