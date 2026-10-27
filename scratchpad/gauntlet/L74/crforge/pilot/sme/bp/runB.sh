#!/usr/bin/env bash
# runB.sh RUN INPUTS LIB [VAR=val ...] -- A2c-BP2 runs from /workspace/pilot/bp2/sme (sme copy + FITNEXT patch): the bpD
# comparator (r63b + MIXPH + SNAP on SnapRun2) on LIB (main run and snapshots), plus extra vars; compared with BASE (bpD)
RUN=$1; IN=$2; LIB=$3; shift 3
BASE=${BASE:-/workspace/pilot/sme_live/bpD}; O=/workspace/pilot/sme_live/$RUN
cd /workspace/pilot/bp2/sme && env "$@" SME_LIB=$LIB SME_BUILD=/workspace/pilot/sme/build_008aa626 SME_HP_PLACEHOLDER=1 SME_TORN_CMD=1 \
  SME_REPR=/workspace/pilot/sme/repr_v2.json SME_THREADS=4 SME_TORN_STEP=1 SME_STEP_CLOCK=1 SME_TORN_CMD3=1 SME_BP_MIXPH=1 SME_BP_SNAP=1 \
  SME_SNAP_BUILD=/workspace/pilot/bp/build_snap2 SME_SNAP_CLASS=SnapRun2 \
  python3 sme_live.py all --workers ${WORKERS:-12} ${ONLY:+--only $ONLY} --inputs $IN --frames /workspace/pilot/sme_live/frames2 --out $O > $O.log 2>&1
python3 round_cmp.py /workspace/pilot/inputs/inputs_rngfree.jsonl $BASE $O > $O.cmp.txt 2>&1
rm -rf $O/live_play_*/work
echo done $RUN >> $O.log
