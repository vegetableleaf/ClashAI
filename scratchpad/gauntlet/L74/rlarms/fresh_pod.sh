#!/bin/bash
# Fresh-seed re-score of the live candidates (HANDOFF 10-15 ~07:55: picking the best seed / length on the 741200 + 742000
# pairs inflates its estimate). After WAIT_DIR/DONE: D3 (the live rule stack, grafted) on NEW seed sets 743000 + 744000
# for r1 (incumbent, the pairing base), F1 s74 u65 (live in A/B5), u150 and u250. -> /workspace/results/FRESH/<name>_<seed>.
#   fresh_pod.sh WAIT_DIR      (CB=/workspace/clashbot)
set -Eeuo pipefail
W=$1; CB=${CB:-/workspace/clashbot}; PY=/workspace/venv33/bin/python; O=/workspace/results/FRESH; RL=icebow/data/bench/rl_royale
mkdir -p $O; exec >> $O/run.log 2>&1
echo "$(date -u +%T) queued after $W"
until [ -e $W/DONE ]; do sleep 60; done
cd $CB
export PYTHONPATH=$CB ROYALE_RUNTIME=20261012-linux OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1
for NC in r1:$RL/newsim_r1/newsim_base_r1_final_grafted.pt f1u65:$RL/rlarm_gae/rlarm_gae_u0065_grafted.pt \
          f1u150:$RL/rlarm_gae/rlarm_gae_u0150_grafted.pt f1u250:$RL/rlarm_gae/rlarm_gae_u0250_grafted.pt; do
  N=${NC%%:*}; CK=${NC#*:}
  [ -f $CK ] || { echo "missing $CK"; continue; }
  sha256sum $CK >> $O/ckpts.sha
  for S in 743000 744000; do
    echo "$(date -u +%T) $N $S"
    flock /workspace/cpu.lock $PY scratchpad/gauntlet/L74/gap/gap.py --ckpt $CK --out $O/${N}_$S --arms D3 --seed-start $S \
      --workers ${WORKERS:-25} > $O/${N}_$S.log 2>&1 || echo "GAP EXIT $? $N $S"
  done
done
touch $O/DONE
echo "$(date -u +%T) done"
