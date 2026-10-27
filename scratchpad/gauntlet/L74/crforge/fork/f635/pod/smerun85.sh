#!/usr/bin/env bash
# usage: smerun85.sh RUN LIBDIR [BASE_RUN_DIR] -- F635c: SME old client on a2c6 round-7 config (pod 33920 chain7.sh r78:
# inputs_v19, repr_v2, TORN_STEP STEP_CLOCK TORN_CMD3 KIND_T BP_MIXPH BP_SNAP SnapRun2 BP_FITNEXT), copy in /workspace/f635c/pilot
RUN=$1; LIB=$2; BASE=$3; P=/workspace/f635c/pilot; OUT=/workspace/f635c/sme/$RUN; mkdir -p /workspace/f635c/sme
B=/workspace/f635c/build/$RUN; rm -rf $B; mkdir -p $B/sme $B/snap
javac -d $B/sme -cp "$LIB/*" $P/sme/SmeRun.java && javac -d $B/snap -cp "$LIB/*" $P/bp/src/SnapRun2.java || exit 1
cd $P/sme && env SME_TABLES=/workspace/f635/crforge_cache/tables/16.402.22 SME_TORN_STEP=1 SME_STEP_CLOCK=1 SME_TORN_CMD3=1 SME_KIND_T=1 \
  SME_BP_MIXPH=1 SME_BP_SNAP=1 SME_SNAP_CLASS=SnapRun2 SME_SNAP_BUILD=$B/snap SME_BP_FITNEXT=1 SME_LIB=$LIB SME_BUILD=$B/sme \
  SME_HP_PLACEHOLDER=1 SME_TORN_CMD=1 SME_REPR=$P/sme/repr_v2.json SME_THREADS=4 \
  python3 sme_live.py all --workers 12 --inputs $P/inputs_v19/inputs_rngfree.jsonl --frames /workspace/f635/pilot/sme_live/frames2 \
  --out $OUT > $OUT.log 2>&1
rm -rf $OUT/live_play_*/work
[ -n "$BASE" ] && python3 round_cmp.py /workspace/f635/pilot/inputs/inputs_rngfree.jsonl $BASE $OUT > $OUT.cmp.txt 2>&1
echo done $RUN
