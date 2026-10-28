#!/usr/bin/env bash
# runL.sh RUN TABLES INPUTS FRAMES [VAR=val ...] -- runF.sh's command with every flag before "$@", so any of them (SME_REPR=
# empty = no representation map) can be overridden for the per-flag SME activation runs. Base dir: $FRESH (default
# /workspace/pilot/fresh). With no override it is runF.sh's environment exactly (env takes the last assignment).
RUN=$1; T=$2; IN=$3; FR=$4; shift 4
F=${FRESH:-/workspace/pilot/fresh}; S=$F/sme10f; LIB=/workspace/pilot/lib_f635c; O=$F/runs/$RUN; mkdir -p $F/runs
cd $S && env SME_TABLES=$T SME_TORN_STEP=1 SME_STEP_CLOCK=1 SME_TORN_CMD3=1 SME_KIND_T=1 SME_BP_MIXPH=1 SME_BP_SNAP=1 \
  SME_SNAP_CLASS=SnapRun2 SME_SNAP_BUILD=$S/build_snap SME_BP_FITNEXT=1 SME_MECH_CROSS=1 SME_HIDDEN=1 SME_BANNER=1 \
  SME_LATE9=1 SME_MADE9=1 SME_LIB=$LIB SME_BUILD=$S/build SME_HP_PLACEHOLDER=1 SME_TORN_CMD=1 \
  SME_REPR=$S/repr_v2.json SME_THREADS=4 "$@" \
  python3 sme_live.py all --workers ${WORKERS:-9} ${ONLY:+--only $ONLY} --inputs $IN --frames $FR --out $O > $O.log 2>&1
[ -z "$KEEP" ] && rm -rf $O/live_play_*/work
echo done $RUN >> $O.log
