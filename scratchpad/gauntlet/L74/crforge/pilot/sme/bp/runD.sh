#!/usr/bin/env bash
# runD.sh RUN [VAR=val ...] -- A2c-BP2: the bpD config (r63b comparator + inputs_v9_bpall + MIXPH + SNAP on SnapRun2/lib_bp) plus extra vars
RUN=$1; shift
cd /workspace/pilot/sme_live && BASE=${BASE:-/workspace/pilot/sme_live/bpD} INPUTS=${INPUTS:-/workspace/pilot/bp/inputs_v9_bpall/inputs_rngfree.jsonl} REPR=/workspace/pilot/sme/repr_v2.json \
  bash run_fork.sh $RUN /workspace/pilot/lib_bp /workspace/pilot/sme/build_008aa626 SME_TORN_STEP=1 SME_STEP_CLOCK=1 SME_TORN_CMD3=1 \
  SME_BP_MIXPH=1 SME_BP_SNAP=1 SME_SNAP_BUILD=/workspace/pilot/bp/build_snap2 SME_SNAP_CLASS=SnapRun2 "$@"
