#!/bin/bash
# usage: run_size.sh NAME D LAYERS [SEED] ; trains on the pod, then evals. Same data/recipe for every size.
NAME=$1; D=$2; L=$3; SEED=${4:-0}; EXTRA=${5:-}
W=/workspace/scale; R=$W/runs/${NAME}_s$SEED; mkdir -p $R
export OMP_NUM_THREADS=3 MKL_NUM_THREADS=3
cd $W/code
nice -n 10 ${PY:-/workspace/venvf15/bin/python} -u -m pipeline.train_gen --data $W/data/gen_dataset_v32_fv5.npz --seed $SEED --epochs 4 \
  --val-sample 30000 --grid lattice --feature-version 5 --amp bf16 --allow-causal-tti-unknowns --inputs-only-arm \
  --d $D --layers $L --out-dir $R --tag $NAME $EXTRA > $R/train.out 2>&1
echo "train exit $?" >> $R/train.out
