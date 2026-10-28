#!/usr/bin/env bash
# usage: BASE=<run> INPUTS=<file> run8.sh RUN [VAR=val ...] -- a2c8: sme8 code, F635c lib, r78 comparator flags + extras
RUN=$1; shift
cd /workspace/pilot/sme8 && env SME_TORN_STEP=1 SME_STEP_CLOCK=1 SME_TORN_CMD3=1 SME_KIND_T=1 SME_BP_MIXPH=1 SME_BP_SNAP=1 \
  SME_SNAP_CLASS=SnapRun2 SME_SNAP_BUILD=/workspace/pilot/sme8/build_snap SME_BP_FITNEXT=1 "$@" \
  SME_LIB=/workspace/pilot/lib_f635c SME_BUILD=/workspace/pilot/sme8/build SME_HP_PLACEHOLDER=1 SME_TORN_CMD=1 \
  SME_REPR=/workspace/pilot/sme/repr_v2.json SME_THREADS=4 \
  python3 sme_live.py all --workers 12 --inputs $INPUTS --frames /workspace/pilot/sme_live/frames2 \
  --out /workspace/pilot/sme_live/$RUN > /workspace/pilot/sme_live/$RUN.log 2>&1
python3 round_cmp.py /workspace/pilot/inputs/inputs_rngfree.jsonl $BASE /workspace/pilot/sme_live/$RUN > /workspace/pilot/sme_live/$RUN.cmp.txt 2>&1
rm -rf /workspace/pilot/sme_live/$RUN/live_play_*/work
