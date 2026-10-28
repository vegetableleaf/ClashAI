#!/usr/bin/env bash
# runH.sh RUN TABLES INPUTS FRAMES [VAR=val ...] -- SME-F1FIX on pod 32657: the hardened comparator (SME-HARDEN h11b =
# a10G1's command + sme11 code) from /workspace/pilot/f1fix/sme11f (= sme11 + sme.py TABLES from SME_TABLES, as sme10f),
# every flag before "$@" so SME_LIB= etc. can be overridden. The run dir lives on /dev/shm (root disk is tight) and is
# copied to /workspace/pilot/f1fix/runs/RUN after the work dirs are removed.
RUN=$1; T=$2; IN=$3; FR=$4; shift 4
S=/workspace/pilot/f1fix/sme11f; O=/dev/shm/f1fix_$RUN; D=/workspace/pilot/f1fix/runs; mkdir -p $D $O
cd $S && env SME_TABLES=$T SME_TORN_STEP=1 SME_STEP_CLOCK=1 SME_TORN_CMD3=1 SME_KIND_T=1 SME_BP_MIXPH=1 SME_BP_SNAP=1 \
  SME_SNAP_CLASS=SnapRun2 SME_SNAP_BUILD=$S/build_snap SME_BP_FITNEXT=1 SME_MECH_CROSS=1 SME_HIDDEN=1 SME_BANNER=1 \
  SME_LATE9=1 SME_MADE9=1 SME_LIB=/workspace/pilot/lib_f635c SME_BUILD=$S/build SME_HP_PLACEHOLDER=1 SME_TORN_CMD=1 \
  SME_REPR=$S/repr_v2.json SME_THREADS=4 "$@" \
  python3 sme_live.py all --workers ${WORKERS:-48} ${ONLY:+--only $ONLY} --inputs $IN --frames $FR --out $O > $O.log 2>&1
[ -z "$KEEP" ] && rm -rf $O/live_play_*/work
echo done $RUN >> $O.log
rm -rf $D/$RUN && cp -a $O $D/$RUN && cp $O.log $D/$RUN.log && rm -rf $O $O.log
