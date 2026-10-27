#!/usr/bin/env bash
# usage: smerun.sh RUN LIBDIR old|new [BASE_RUN]  -- SME on the 109 old-client (16.402.22) or the 47 new-client (16.635.3)
# matches with one crforge lib; comparator config of r61 (repr_v2, torn_step, step_clock). 8 workers x 3 threads.
RUN=$1; LIB=$2; SET=$3; BASE=$4; F=/workspace/f635; OUT=$F/sme/$RUN
mkdir -p $F/sme $F/smebuild/$RUN && javac -d $F/smebuild/$RUN -cp "$LIB/*" $F/pilot/sme/SmeRun.java || exit 1
if [ $SET = old ]; then T=16.402.22; IN=$F/pilot/inputs_v5/inputs_rngfree.jsonl; FR=$F/pilot/sme_live/frames2; FL=$F/pilot/inputs/inputs_rngfree.jsonl
else T=16.635.3; IN=$F/r64/inputs635_rngfree.jsonl; FR=$F/r64/frames635; FL=$IN; fi
cd $F/pilot/sme && JAVA_TOOL_OPTIONS=-XX:ActiveProcessorCount=3 SME_TABLES=$F/crforge_cache/tables/$T SME_LIB=$LIB SME_BUILD=$F/smebuild/$RUN SME_HP_PLACEHOLDER=1 SME_TORN_CMD=1 \
  SME_REPR=$F/pilot/sme/repr_v2.json SME_THREADS=3 SME_TORN_STEP=1 SME_STEP_CLOCK=1 \
  python3 sme_live.py all --workers ${WORKERS:-8} ${ONLY:+--only $ONLY} --inputs $IN --frames $FR --out $OUT > $OUT.log 2>&1
rm -rf $OUT/live_play_*/work
[ -n "$BASE" ] && python3 round_cmp.py $FL $F/sme/$BASE $OUT > $OUT.cmp.txt 2>&1
echo done $RUN
