#!/usr/bin/env bash
# runR.sh RUN TOOL INPUTS FRAMES [VAR=val ...] -- SME-REBUILD (10-30): f1fix/runH.sh's gate env on the rebuilt tree
# $R/sme (rebuild_gate.sh; pod 33903), lib 5e8089a4 tickprobe, SME_BANNER_GIVEN=1, ASSIGN on (runH default; a trailing
# SME_HIDDEN_ASSIGN=0 turns it off). TOOL = gate (sme_live.py all) | recon (recon/recon_search.py all; extra args in
# RARGS, e.g. RARGS="--beam 4 --ops shift,point"). Pinned to CPUS (default 226-237 = 12, 33903's share), WORKERS x
# SME_THREADS <= 12. Output $R/runs/RUN{,.log}; work dirs removed unless KEEP=1.
RUN=$1; TOOL=$2; IN=$3; FR=$4; shift 4
R=${R:-/workspace/smeR}; S=$R/sme; O=$R/runs/$RUN; mkdir -p $O
T=/workspace/crforge_cache/tables/16.635.3
case $TOOL in gate) P="sme_live.py all";; recon) P="recon/recon_search.py all $RARGS";; plant) P="recon/plant_recall.py $RARGS";; partA) P="recon/r5_partA.py";; ablate) P="recon/ablate.py $RARGS";; ablate2) P="recon/ablate_edits.py $RARGS";; *) echo bad tool; exit 2;; esac
cd $S && env SME_TABLES=$T SME_TORN_STEP=1 SME_STEP_CLOCK=1 SME_TORN_CMD3=1 SME_KIND_T=1 SME_BP_MIXPH=1 SME_BP_SNAP=1 \
  SME_SNAP_CLASS=SnapRun2 SME_SNAP_BUILD=$S/build_snap SME_BP_FITNEXT=1 SME_MECH_CROSS=1 SME_HIDDEN=1 SME_BANNER=1 \
  SME_LATE9=1 SME_MADE9=1 SME_LIB=/workspace/crforge_main/5e8089a4/tickprobe/lib SME_BUILD=$S/build SME_HP_PLACEHOLDER=1 \
  SME_TORN_CMD=1 SME_REPR=$S/repr_v2.json SME_THREADS=${SME_THREADS:-4} SME_HIDDEN_ASSIGN=1 SME_CLS_TICKS=1 \
  SME_BANNER_GIVEN=1 "$@" \
  taskset -c ${CPUS:-226-237} python3 $P --workers ${WORKERS:-3} ${ONLY:+--only $ONLY} --inputs $IN --frames $FR --out $O \
  > $O.log 2>&1
[ -z "$KEEP" ] && rm -rf $O/live_play_*/work
echo done $RUN >> $O.log
