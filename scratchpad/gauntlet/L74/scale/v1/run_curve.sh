#!/bin/bash
# run_curve.sh NAME D LAYERS SEED [STAGE] -- curve v1 point: the P4-10M base recipe (run_base.sh pre = the step trainer, fv6 + memory
# v2, lr 3e-4, bs 256, 51,000 steps = 1 epoch of the mix's 13.05 M train rows) at width D x LAYERS and seed SEED, then the
# held-out eval (scale_eval_v1.py: all groups + latency) -> runs/cv1_NAME_sSEED/eval.json. m10 seed 0 is base_pre itself.
# STAGE v32 (default pre): the CONTROL (lead 10-28): the same recipe and step count on data/v32_v1.npz (v32 train rows only, ~4 epochs of
# 3.17 M) -> runs/ctl_NAME_sSEED. It separates the data effect (v0 m10 vs control) from the recipe/family effect (control vs v1 m10).
# Why not curve v0's legacy trainer (run_size_v1.sh, attempt 1 of 10-28): train_gen.main refuses the mix
# (require_complete_training: effects_missing_timing 5,158,487 != effects_capability_masked 1,080,104; "owner/lead source
# decision required"); the step trainer (opp_mode) has no such gate and is what the base itself used. Restart = re-run.
NAME=$1; D=$2; L=$3; SEED=${4:-0}; STAGE=${5:-pre}
P=cv1; [ "$STAGE" = v32 ] && P=ctl
W=/workspace/p4; V=$W/code/scratchpad/gauntlet/L74/scale/v1; PY=${PY:-/workspace/venvf16/bin/python}
R=$W/runs/${P}_${NAME}_s$SEED; mkdir -p $R
D=$D L=$L SEED=$SEED TAG=${P}_$NAME bash $V/run_base.sh $STAGE $R ${PRE_STEPS:-51000}
grep -q '"FINAL"' $R/train.out || { echo "train failed: $R/train.out"; exit 1; }
rm -rf $W/data/cache_ev_$NAME
$PY -u $V/scale_eval_v1.py $W/code $R/opp_${P}_${NAME}_s$SEED.pt $W/data/mix_v1.npz $R/eval.json \
  --memory-tables $W/data/mix_v1_memory.npz --mmap-cache-dir $W/data/cache_ev_$NAME > $R/eval.out 2>&1
echo "eval exit $?" >> $R/eval.out
rm -rf $W/data/cache_ev_$NAME
[ -f $R/eval.json ] || { echo "eval failed: $R/eval.out"; exit 1; }
