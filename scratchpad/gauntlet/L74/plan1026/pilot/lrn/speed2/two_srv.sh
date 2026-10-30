#!/bin/bash
# SPEED2: N PolicyServer processes on ONE GPU at once (srvshape.py each, its own producers); rows/s add up if the
# server's GIL, not the GPU, is the limit. usage (pod): two_srv.sh TAG N K P MODE  (each instance K x P)
TAG=$1; N=$2; K=$3; P=$4; MODE=$5
. /workspace/speed2/env.sh; cd $CB || exit 1
for i in $(seq 1 $N); do
  taskset -c $CPUS timeout 1500 $PY -u ../srvshape.py --out ../out/${TAG}_$i.json --mode $MODE --configs ${K}x${P} --seconds 30 --max-batch ${MB:-2048} \
    > ../out/${TAG}_$i.log 2>&1 &
done
wait
grep -h "^{" ../out/${TAG}_*.log | cut -c1-200
