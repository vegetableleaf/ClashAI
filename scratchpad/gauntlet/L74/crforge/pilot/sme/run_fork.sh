#!/usr/bin/env bash
# usage: BASE=<run to compare> run_fork.sh RUN LIB BUILD [VAR=val ...]   -- ticket A2c round 4 runs on the fork build
RUN=$1; LIB=$2; BUILD=$3; shift 3
BASE=${BASE:-/workspace/pilot/sme_live/run13}
cd /workspace/pilot/sme && env "$@" SME_LIB=$LIB SME_BUILD=$BUILD SME_HP_PLACEHOLDER=1 SME_TORN_CMD=1 SME_REPR=/workspace/pilot/sme/repr_v1.json SME_THREADS=4 \
  python3 sme_live.py all --workers 12 --inputs /workspace/pilot/inputs_v2/inputs_rngfree.jsonl --frames /workspace/pilot/sme_live/frames2 \
  --out /workspace/pilot/sme_live/$RUN > /workspace/pilot/sme_live/$RUN.log 2>&1
python3 round_cmp.py /workspace/pilot/inputs/inputs_rngfree.jsonl $BASE /workspace/pilot/sme_live/$RUN > /workspace/pilot/sme_live/$RUN.cmp.txt 2>&1
