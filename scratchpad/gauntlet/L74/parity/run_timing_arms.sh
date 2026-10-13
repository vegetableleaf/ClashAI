#!/bin/bash
# PARITY own-timing / swarm-pairing arms (2026-10-13) on the frozen pod-D fixed cohort; one change per step:
#   A tap (reproduces pod D: fork unit MAE 1.2885) -> B spawn -> C spawn + swarm pairing -> D spawn_mid + swarm pairing
# Usage on the pod: nohup bash scratchpad/gauntlet/L74/parity/run_timing_arms.sh > /workspace/results/PARITY_T.out 2>&1 &
set -u
cd /workspace/clashbot
export PYTHONPATH=$PWD OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1
OUT=${OUT:-/workspace/results/PARITY_T}; COHORT=${COHORT:-/workspace/parity_fixed/sources}; mkdir -p $OUT
run() { name=$1; shift
  flock /workspace/cpu.lock /workspace/venv33/bin/python scratchpad/gauntlet/L74/parity/driver.py run --runtime fork \
    --cohort $COHORT --mechanics-replay --fix-artefacts --workers 24 --out $OUT/$name "$@" > $OUT/$name.log 2>&1
  echo "$(date -u +%T) $name exit $?"; }
run A_tap --own-timing tap
run B_spawn --own-timing spawn
run C_spawn_pair --own-timing spawn --pair-swarms-by-position
run D_mid_pair --own-timing spawn_mid --pair-swarms-by-position
touch $OUT/DONE
