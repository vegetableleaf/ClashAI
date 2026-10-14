#!/bin/bash
# 10-14 evening, pod 12037 (after DISTILL_ADAPT): (1) distillation diagnosis -- pro agreement on the pro VAL rows, plain
# ADAPT vs the distilled student (did fine-tuning on teacher rows damage what the model learned from pros?); (2) the
# --tornado-river SIM A/B: r1 full graft, live stack D3 + the deployed Rocket+Tornado flags, river off vs on, 960 pairs
# each (runtime 20261012-linux = RoyaleSim 0.1.33, which holds ground troops at the bank).
# Runs from a fresh code checkout (CB=/workspace/cb_new: current main) that links the original pod's data.
set -Eeuo pipefail
CB=${CB:-/workspace/cb_new}; PY=/workspace/venv33/bin/python; R=/workspace/results/RIVER_DISTILL; mkdir -p $R
exec >> $R/run.log 2>&1
trap 'echo "exit_code=$?" > $R/DONE' EXIT
cd $CB
export PYTHONPATH=$CB ROYALE_RUNTIME=20261012-linux OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1
RL=icebow/data/bench/rl_royale; DATA=icebow/data/pipeline/gen_dataset_v32_fv5.npz
echo "$(date -u +%T) pro agreement"
for ck in $RL/wk_adapt_main/wk_adapt_main_latest.pt $RL/distill/distill_adapt_d3.pt; do
  $PY -m pipeline.eval_gen --ckpt $ck --data $DATA --out $R/pro_$(basename ${ck%.pt}).json > $R/pro_$(basename ${ck%.pt}).log 2>&1 \
    || echo "eval FAILED $ck"
done
CK=$RL/newsim_r1/newsim_base_r1_final_grafted.pt
COMBO="--rocket-value 9 --rocket-value-mode damage --rocket-value-hitbox edge --rocket-tornado only"
for arm in off on; do for S in 741200 742000; do
  echo "$(date -u +%T) river $arm $S"
  flock /workspace/cpu.lock $PY scratchpad/gauntlet/L74/gap/gap.py --ckpt $CK --out $R/river_${arm}_$S --arms D3 --seed-start $S \
    --workers ${WORKERS:-25} --extra "$COMBO --tornado-river $arm" > $R/river_${arm}_$S.log 2>&1 || echo "FAILED $arm $S"
  grep -E "^D3:" $R/river_${arm}_$S/SUMMARY.txt || true
done; done
echo "$(date -u +%T) done"
