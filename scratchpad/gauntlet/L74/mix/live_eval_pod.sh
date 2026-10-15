#!/bin/bash
# Live-mirrored SIM eval (owner 10-15 matchup-mix plan): after WAIT (a file, e.g. an arm's DONE, or "none"), score CKPT with
# gap.py --census-file L74/mix/decks_live_eval.json (opponents drawn with P(deck) ~ its live frequency; CAL c opponent
# policy E4 T .1) on the standard paired seeds 741200 + 742000 (960 games), arms ARMS (default D3 = the live rule stack).
#   live_eval_pod.sh WAIT NAME CKPT [ARMS]      (CB = checkout with gap.py --census-file; results /workspace/results/LIVEEVAL)
set -Eeuo pipefail
W=$1; NAME=$2; CK=$3; ARMS=${4:-D3}; CB=${CB:-/workspace/clashbot}; PY=/workspace/venv33/bin/python
O=/workspace/results/LIVEEVAL; mkdir -p $O; exec >> $O/run.log 2>&1
echo "$(date -u +%T) queued $NAME ($CK) after $W"
[ "$W" = none ] || until [ -e $W ]; do sleep 60; done
cd $CB
export PYTHONPATH=$CB ROYALE_RUNTIME=20261012-linux OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1
[ -f $CK ] || { echo "missing $CK"; exit 2; }
sha256sum $CK >> $O/ckpts.sha
for S in 741200 742000; do
  echo "$(date -u +%T) $NAME $S"
  flock /workspace/cpu.lock $PY scratchpad/gauntlet/L74/gap/gap.py --ckpt $CK --out $O/${NAME}_$S --arms $ARMS --seed-start $S \
    --census-file scratchpad/gauntlet/L74/mix/decks_live_eval.json --workers ${WORKERS:-25} > $O/${NAME}_$S.log 2>&1 \
    || echo "GAP EXIT $? $NAME $S"
done
touch $O/${NAME}.DONE
echo "$(date -u +%T) done $NAME"
