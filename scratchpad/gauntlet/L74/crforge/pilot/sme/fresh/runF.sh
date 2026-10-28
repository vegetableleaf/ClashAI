#!/usr/bin/env bash
# runF.sh RUN TABLES INPUTS FRAMES [VAR=val ...] -- SME-FRESH: a10G1's command (bp9/run9.sh RUN lib_f635c IN SME_LATE9=1 SME_MADE9=1,
# SME_DIR=/workspace/pilot/sme10, WORKERS=48) with the frames dir and the tables as arguments. Code: /workspace/pilot/fresh/sme10f
# = sme10 + sme.py TABLES read from SME_TABLES (one line; default 16.402.22). Pod 32657.
RUN=$1; T=$2; IN=$3; FR=$4; shift 4
S=/workspace/pilot/fresh/sme10f; LIB=/workspace/pilot/lib_f635c; O=/workspace/pilot/fresh/runs/$RUN; mkdir -p /workspace/pilot/fresh/runs
cd $S && env SME_TABLES=$T SME_TORN_STEP=1 SME_STEP_CLOCK=1 SME_TORN_CMD3=1 SME_KIND_T=1 SME_BP_MIXPH=1 SME_BP_SNAP=1 \
  SME_SNAP_CLASS=SnapRun2 SME_SNAP_BUILD=$S/build_snap SME_BP_FITNEXT=1 SME_MECH_CROSS=1 SME_HIDDEN=1 SME_BANNER=1 \
  SME_LATE9=1 SME_MADE9=1 "$@" \
  SME_LIB=$LIB SME_BUILD=$S/build SME_HP_PLACEHOLDER=1 SME_TORN_CMD=1 \
  SME_REPR=$S/repr_v2.json SME_THREADS=4 \
  python3 sme_live.py all --workers ${WORKERS:-48} ${ONLY:+--only $ONLY} --inputs $IN --frames $FR --out $O > $O.log 2>&1
[ -z "$KEEP" ] && rm -rf $O/live_play_*/work
echo done $RUN >> $O.log
