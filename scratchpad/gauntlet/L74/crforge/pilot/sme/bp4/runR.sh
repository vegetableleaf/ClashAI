#!/usr/bin/env bash
# runR.sh RUN LIB INPUTS [VAR=val ...] -- A2c-BP4: a2c6 chain7 r78 config (33920) on pod 32657, from bp4/from33920/sme
RUN=$1; LIB=$2; IN=$3; shift 3
F=/workspace/pilot/bp4/from33920; O=/workspace/pilot/sme_live/$RUN
cd $F/sme && env SME_TORN_STEP=1 SME_STEP_CLOCK=1 SME_TORN_CMD3=1 SME_KIND_T=1 SME_BP_MIXPH=1 SME_BP_SNAP=1 SME_SNAP_CLASS=SnapRun2 \
  SME_SNAP_BUILD=$F/bp/build_snap2b SME_BP_FITNEXT=1 "$@" SME_LIB=$LIB SME_BUILD=$F/sme/build_008aa626 SME_HP_PLACEHOLDER=1 SME_TORN_CMD=1 \
  SME_REPR=$F/sme/repr_v2.json SME_THREADS=4 \
  python3 sme_live.py all --workers ${WORKERS:-12} ${ONLY:+--only $ONLY} --inputs $IN --frames /workspace/pilot/sme_live/frames2 --out $O > $O.log 2>&1
[ -n "$BASE" ] && python3 round_cmp.py /workspace/pilot/inputs/inputs_rngfree.jsonl $BASE $O > $O.cmp.txt 2>&1
[ -z "$KEEP" ] && rm -rf $O/live_play_*/work
echo done $RUN >> $O.log
