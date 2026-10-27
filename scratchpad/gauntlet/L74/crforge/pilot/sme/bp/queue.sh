#!/usr/bin/env bash
# run after the given PID exits: queue.sh PID RUN INPUTS [VAR=val ...]   (r62 comparator config, BASE = bp1)
P=$1; RUN=$2; IN=$3; shift 3
while kill -0 $P 2>/dev/null; do sleep 20; done
cd /workspace/pilot/sme_live && BASE=${BASE:-/workspace/pilot/sme_live/bp1} INPUTS=$IN REPR=/workspace/pilot/sme/repr_v2.json \
  bash run_fork.sh $RUN /workspace/pilot/lib_008aa626 /workspace/pilot/sme/build_008aa626 SME_TORN_STEP=1 SME_STEP_CLOCK=1 SME_TORN_CMD3=1 "$@"
