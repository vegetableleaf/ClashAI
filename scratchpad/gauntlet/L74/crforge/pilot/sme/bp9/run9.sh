#!/usr/bin/env bash
# run9.sh RUN LIB INPUTS [VAR=val ...] -- A2c-9R: round-8 (r87) config on pod 32657: sme8 code, r78 comparator flags + CROSS/HIDDEN/BANNER
RUN=$1; LIB=$2; IN=$3; shift 3
S=${SME_DIR:-/workspace/pilot/sme8}; O=/workspace/pilot/sme_live/$RUN
cd $S && env SME_TORN_STEP=1 SME_STEP_CLOCK=1 SME_TORN_CMD3=1 SME_KIND_T=1 SME_BP_MIXPH=1 SME_BP_SNAP=1 \
  SME_SNAP_CLASS=SnapRun2 SME_SNAP_BUILD=$S/build_snap SME_BP_FITNEXT=1 SME_MECH_CROSS=1 SME_HIDDEN=1 SME_BANNER=1 "$@" \
  SME_LIB=$LIB SME_BUILD=${SME_BUILD:-$S/build} SME_HP_PLACEHOLDER=1 SME_TORN_CMD=1 \
  SME_REPR=$S/repr_v2.json SME_THREADS=4 \
  python3 sme_live.py all --workers ${WORKERS:-12} ${ONLY:+--only $ONLY} --inputs $IN --frames /workspace/pilot/sme_live/frames2 --out $O > $O.log 2>&1
[ -n "$BASE" ] && python3 round_cmp.py /workspace/pilot/inputs/inputs_rngfree.jsonl $BASE $O > $O.cmp.txt 2>&1
[ -z "$KEEP" ] && rm -rf $O/live_play_*/work
echo done $RUN >> $O.log
