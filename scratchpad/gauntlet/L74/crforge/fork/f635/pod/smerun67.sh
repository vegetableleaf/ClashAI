#!/usr/bin/env bash
# usage: smerun67.sh RUN LIBDIR [BASE_RUN]  -- F635b: SME on the 109 old-client (16.402.22) matches on the CURRENT best inputs
# (pod 32657 /workspace/pilot/bp/inputs_v9_bpall = a2c6 + body-position rules, run bpA = 67/109), comparator of bpA
# (repr_v2, torn_step, step_clock, torn_cmd3; sme_live a2c6). 8 workers x 3 threads.
RUN=$1; LIB=$2; BASE=$3; F=/workspace/f635; OUT=$F/sme/$RUN
mkdir -p $F/sme $F/smebuild/$RUN && javac -d $F/smebuild/$RUN -cp "$LIB/*" $F/pilot/sme/SmeRun.java || exit 1
IN=$F/pilot/inputs_bp67/inputs_rngfree.jsonl; FR=$F/pilot/sme_live/frames2; FL=$F/pilot/inputs/inputs_rngfree.jsonl
cd $F/pilot/sme && JAVA_TOOL_OPTIONS=-XX:ActiveProcessorCount=3 SME_TABLES=$F/crforge_cache/tables/16.402.22 SME_LIB=$LIB SME_BUILD=$F/smebuild/$RUN \
  SME_HP_PLACEHOLDER=1 SME_TORN_CMD=1 SME_REPR=$F/pilot/sme/repr_v2.json SME_THREADS=3 SME_TORN_STEP=1 SME_STEP_CLOCK=1 SME_TORN_CMD3=1 \
  python3 sme_live.py all --workers ${WORKERS:-8} ${ONLY:+--only $ONLY} --inputs $IN --frames $FR --out $OUT > $OUT.log 2>&1
rm -rf $OUT/live_play_*/work
[ -n "$BASE" ] && python3 round_cmp.py $FL $BASE $OUT > $OUT.cmp.txt 2>&1
echo done $RUN
