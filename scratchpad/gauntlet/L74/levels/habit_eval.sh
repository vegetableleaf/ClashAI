#!/bin/bash
# One-block (480 paired games, seed 741200) promotion-eval read of ONE checkpoint at level 11 vs live levels, both with
# --habit-log (L74 factor D + habits, 10-17). fork36-linux, D3, live-mirrored pool -- live_eval_pod.sh's gap.py command.
#   habit_eval.sh CKPT NAME [WORKERS]   -> /workspace/results/LV/hab_{L11,live}_NAME/ + .DONE
set -uo pipefail
CK=$1; N=$2; W=${3:-60}; CB=/workspace/cb_lv; PY=/workspace/venvf36/bin/python; O=/workspace/results/LV
cd $CB
export PYTHONPATH=$CB ROYALE_RUNTIME=fork36-linux OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1
run() {  # TAG EXTRA
  $PY scratchpad/gauntlet/L74/gap/gap.py --ckpt $CK --out $O/hab_$1_$N --arms D3 --seed-start 741200 --runtime fork36-linux \
    --python $PY --census-file scratchpad/gauntlet/L74/mix/decks_live_eval.json --workers $W --extra="$2" > $O/hab_$1_$N.log 2>&1
  echo "$(date -u +%T) $1 exit $?" >> $O/hab_$N.status
}
run L11 "--habit-log" &
run live "--habit-log --live-levels --card-levels Rocket=16 Log=15" &
wait
touch $O/hab_$N.DONE
