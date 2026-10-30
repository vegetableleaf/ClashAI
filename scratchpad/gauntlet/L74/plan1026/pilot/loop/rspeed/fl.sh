#!/bin/bash
# ROLLOUT-SPEED: fastloop.py on the pilot config (31892). usage: bash fl.sh RUN CPUS "FASTLOOP ARGS" [rl_royale k=v ...]
RUN=$1; CPUS=$2; FA=$3; shift 3
cd /workspace/rs/cb && . ../env.sh || exit 1
OUT=/workspace/rs/out/$RUN; mkdir -p $OUT
$PY -u ../gpumon.py $OUT/gpu.jsonl & MON=$!
FASTLOOP_DUMP=${DUMP:-} taskset -c $CPUS $PY -u $L/fastloop.py $FA --build $CRFORGE_FACADE_BUILD --out $OUT -- --run $RUN \
  --config /workspace/loop/in/pilot.yaml n_actors=2 save_every=1000 "$@" > $OUT/loop.log 2>&1
echo "rc $?" >> $OUT/loop.log
kill $MON
