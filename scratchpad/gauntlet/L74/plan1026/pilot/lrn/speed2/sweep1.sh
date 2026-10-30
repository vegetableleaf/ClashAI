#!/bin/bash
# SPEED2 server sweep on a free GPU (33903): single server at the box shapes, eager + graphs; then N servers per GPU.
. /workspace/speed2/env.sh; cd $CB || exit 1
O=/workspace/speed2/out/s1; mkdir -p $O
nvidia-smi --query-gpu=utilization.gpu,memory.used --format=csv,noheader > $O/gpu_before.txt
for m in eager graphs; do
  taskset -c $CPUS timeout 1800 $PY -u ../srvshape.py --out $O/one_$m.json --mode $m --configs 16x21,64x5,128x3 --seconds 30 > $O/one_$m.log 2>&1
done
bash /workspace/speed2/two_srv.sh s1/two_graphs 2 16 11 graphs > $O/two_graphs.txt 2>&1
bash /workspace/speed2/two_srv.sh s1/three_graphs 3 16 7 graphs > $O/three_graphs.txt 2>&1
bash /workspace/speed2/two_srv.sh s1/two_eager 2 16 11 eager > $O/two_eager.txt 2>&1
nvidia-smi --query-gpu=utilization.gpu,memory.used --format=csv,noheader > $O/gpu_after.txt
touch $O/DONE
