#!/bin/bash
# 10-14 night (owner: "why is the model spamming cheap cards on repeat?"): live r1 locks into cheap-card loops in 13.3% of
# matches (old model 5.3%; those matches 1-19), 61% of loop plays under --tau-threatened 0.2. SIM A/B: r1 full graft D3
# WITHOUT tau_threatened vs the existing D3 rows (402/960, pod1014b_twin TWIN_live_*). Waits for the river A/B.
set -Eeuo pipefail
CB=/workspace/cb_tau; PY=/workspace/venv33/bin/python; R=/workspace/results/TAU_THREAT; mkdir -p $R
exec >> $R/run.log 2>&1
trap 'echo "exit_code=$?" > $R/DONE' EXIT
until [ -e /workspace/results/RIVER_DISTILL/DONE ]; do sleep 60; done
cd $CB
export PYTHONPATH=$CB ROYALE_RUNTIME=20261012-linux OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1
CK=icebow/data/bench/rl_royale/newsim_r1/newsim_base_r1_final_grafted.pt
for S in 741200 742000; do
  echo "$(date -u +%T) no_tau_threatened $S"
  flock /workspace/cpu.lock $PY scratchpad/gauntlet/L74/gap/gap.py --ckpt $CK --out $R/notau_$S --arms D3 --seed-start $S \
    --workers ${WORKERS:-25} --drop tau_threatened > $R/notau_$S.log 2>&1 || echo "FAILED $S"
  grep -E "^D3:" $R/notau_$S/SUMMARY.txt || true
done
echo "$(date -u +%T) done"
