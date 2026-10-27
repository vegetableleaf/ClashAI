#!/usr/bin/env bash
# run_only.sh RUN INPUTS BASE M1,M2,...   -- SME on the listed matches only (r62 comparator config); the other matches'
# results are copied from BASE (their inputs are byte-identical, and a match's result depends only on its own record).
RUN=$1; IN=$2; BASE=$3; ONLY=$4
cd /workspace/pilot/sme && env SME_LIB=/workspace/pilot/lib_008aa626 SME_BUILD=/workspace/pilot/sme/build_008aa626 SME_HP_PLACEHOLDER=1 SME_TORN_CMD=1 \
  SME_REPR=/workspace/pilot/sme/repr_v2.json SME_THREADS=4 SME_TORN_STEP=1 SME_STEP_CLOCK=1 SME_TORN_CMD3=1 \
  python3 sme_live.py all --workers 6 --inputs $IN --frames /workspace/pilot/sme_live/frames2 --only $ONLY --out /workspace/pilot/sme_live/$RUN.part > /workspace/pilot/sme_live/$RUN.log 2>&1
mkdir -p /workspace/pilot/sme_live/$RUN
python3 /workspace/pilot/bp/merge.py $BASE/results.jsonl /workspace/pilot/sme_live/$RUN.part/results.jsonl > /workspace/pilot/sme_live/$RUN/results.jsonl
for m in ${ONLY//,/ }; do mkdir -p /workspace/pilot/sme_live/$RUN/$m; cp /workspace/pilot/sme_live/$RUN.part/$m/plan.json /workspace/pilot/sme_live/$RUN/$m/; done
python3 round_cmp.py /workspace/pilot/inputs/inputs_rngfree.jsonl $BASE /workspace/pilot/sme_live/$RUN > /workspace/pilot/sme_live/$RUN.cmp.txt 2>&1
rm -rf /workspace/pilot/sme_live/$RUN.part/live_play_*/work
