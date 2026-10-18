#!/bin/bash
# L74 combo eval queue (pod; checkout /workspace/cb_combo, fork36 venv): run items in order, WORKERS each, one at a time, through
# combo_jobs.py (gap.py's D3 + combo_arms.ARMS[ARM]; COMBO_MEASURE=1 = measure_shim) -> /workspace/combo_rules/<name>/D3/ + <name>.DONE.
#   item "ARM SEED A B"           jobs A..B-1 of the paired block SEED     (name ARM_SEED_A_B)
#   item "ARM SEED picks:FILE"    the (census, seed) pairs in FILE         (name ARM_SEED_picks)
#   setsid nohup bash combo_queue.sh WORKERS "newh 741200 0 40" ... > /dev/null 2>&1 < /dev/null &      QUEUE_DONE at the end
set -uo pipefail
W=$1; shift
CB=/workspace/cb_combo; PY=/workspace/venvf36/bin/python; O=/workspace/combo_rules
CK=icebow/data/bench/rl_royale/rlarm_gae_cue_u250/rlarm_gae_cue_u250_u0130_grafted.pt
mkdir -p $O; exec >> $O/queue.log 2>&1
cd $CB || exit 1
export PYTHONPATH=$CB ROYALE_RUNTIME=fork36-linux ROYALE_HEROIW_FORM=hero OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1 \
  PYTHONNOUSERSITE=1 COMBO_MEASURE=1
echo "$(date -u +%FT%TZ) queue pid $$ workers $W: $*"; sha256sum $CK pipeline/decision_options.py
for item in "$@"; do
  set -- $item
  if [ "${3#picks:}" != "$3" ]; then NAME=$1_$2_picks; ARGS="$1 $2 $3 $W $O/$1_$2_picks"; else NAME=$1_$2_$3_$4; ARGS="$1 $2 $3 $4 $W $O/$NAME"; fi
  [ -e $O/$NAME.DONE ] && { echo "skip $NAME"; continue; }
  echo "$(date -u +%FT%TZ) $NAME"
  nice -n 5 $PY scratchpad/gauntlet/L74/combo/combo_jobs.py $ARGS > $O/$NAME.log 2>&1 || echo "EXIT $? $NAME"
  echo "$(date -u +%FT%TZ) rows $NAME: $(grep -c '"outcome"' $O/$NAME/D3/matches.jsonl 2>/dev/null)"
  touch $O/$NAME.DONE
done
touch $O/QUEUE_DONE; echo "$(date -u +%FT%TZ) QUEUE_DONE"
