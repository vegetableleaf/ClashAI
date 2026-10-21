#!/usr/bin/env bash
# W16 test learner ON the learner pod: tn_base_s74 + test overrides, RL_BATCH_SHA=1 (per-update batch + weights sha).
#   bash run_learner.sh NAME N_LOCAL ENDPOINTS|none [key=value ...]     -> /workspace/w16/NAME.log
# ENDPOINTS: a repo-relative endpoints file (one host:port per line), e.g. scratchpad/gauntlet/L74/distrib/ep_1.txt
set -uo pipefail
NAME=$1; N=$2; EP=$3; shift 3
cd /workspace/cb_w16
export PYTHONPATH=/workspace/cb_w16 ROYALE_RUNTIME=${ROYALE_RUNTIME:-fin13-linux} ROYALE_HEROIW_FORM=hero \
       OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1 RL_BATCH_SHA=1
unset ROYALE_HEROIW_PRESS
PY=${PY:-/workspace/venvf13/bin/python}
EXTRA=(); [ "$EP" != none ] && EXTRA=(remote_actors=$EP)
flock /workspace/cpu.lock $PY -m pipeline.rl_royale --config scratchpad/gauntlet/L74/stepd/cfg/tn_base_s74.yaml \
  --run w16_$NAME n_actors=$N max_updates=3 screen_every=1000 proagree_every=1000 critic_warmup_updates=0 \
  screen_entries=8 "screen_seeds=[0]" save_every=1000 "${EXTRA[@]}" "$@" > /workspace/w16/$NAME.log 2>&1
echo "EXIT $? $NAME" >> /workspace/w16/$NAME.log
