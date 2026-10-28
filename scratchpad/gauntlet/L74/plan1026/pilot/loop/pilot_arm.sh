#!/bin/bash
# pilot_arm.sh ARM GPU CPUS [rl_royale k=v ...] -- LOOP-INT2 (lead 10-28): ONE pilot arm on pod 33308, from /workspace/loop/cb
# (origin/main tree + loop/ files): rl_royale's learner AND its serve.py on GPU (CUDA_VISIBLE_DEVICES=GPU, cuda:0 inside),
# the producers + ActorPool actors on CPUS (taskset), config = pilot/ops/pilot.yaml (fastloop block stripped by fastloop.py)
# + the k=v overrides (arm L: LEARNER-SCALE's learner keys). Two arms run side by side, one per GPU, same seed (pilot.yaml).
# env: RUN (pilot_ARM), PRODUCERS 3, MATCHES 256 (matches in flight per producer), SERVER eager, STOP_AT (epoch seconds:
# a STOP file in the --out dir at that time -> rl_royale stops after the update in progress, saves, FINAL), OUT
# (/workspace/loop/pilot/RUN: throughput.jsonl, STOP, FINAL), RECORDS (a dir: every update's rollout results; big).
# Log: /workspace/loop/logs/RUN.log. Checkpoints: /workspace/loop/cb/icebow/data/bench/rl_royale/RUN/.
ARM=$1; GPU=$2; CPUS=$3; shift 3
RUN=${RUN:-pilot_$ARM}; OUT=${OUT:-/workspace/loop/pilot/$RUN}
CB=${CB:-/workspace/loop/cb}; L=scratchpad/gauntlet/L74/plan1026/pilot/loop
mkdir -p $OUT /workspace/loop/logs
[ -e $CB/scratchpad/gauntlet/L68/rl/$RUN ] && { echo "run $RUN exists (rl_royale refuses a re-used name)"; exit 1; }
if [ -n "${STOP_AT:-}" ]; then                            # the auto-stop: rl_royale finishes the update, saves, FINAL
  setsid nohup sh -c "sleep \$(( $STOP_AT - \$(date +%s) )); echo auto-stop > $OUT/STOP" > /dev/null 2>&1 < /dev/null &
  echo "auto-stop at $(date -d @$STOP_AT) (pid $!)"
fi
export CUDA_VISIBLE_DEVICES=$GPU CFG=${CFG:-scratchpad/gauntlet/L74/plan1026/pilot/ops/pilot.yaml}
[ -n "${RECORDS:-}" ] && export FASTLOOP_RECORDS=$RECORDS
export FAST_ARGS="--producers ${PRODUCERS:-3} --matches ${MATCHES:-256} --threads 4 --devices cuda:0 --server ${SERVER:-eager} --out $OUT"
cd $CB && exec bash $L/run.sh fast $RUN $CPUS "$@"
