#!/bin/bash
# SPEED2 multi-server-per-GPU test (33903): 1 server x 22 producers vs 2 x 11 vs 3 x 7 at the box shape (K 16), MODE.
MODE=${1:-eager}
. /workspace/speed2/env.sh; cd $CB || exit 1
O=/workspace/speed2/out/s2; mkdir -p $O
nvidia-smi --query-compute-apps=pid,used_memory --format=csv,noheader > $O/gpu_apps_$MODE.txt
MB=512 bash /workspace/speed2/two_srv.sh s2/one_$MODE 1 16 22 $MODE > /dev/null 2>&1
MB=512 bash /workspace/speed2/two_srv.sh s2/two_$MODE 2 16 11 $MODE > /dev/null 2>&1
MB=512 bash /workspace/speed2/two_srv.sh s2/three_$MODE 3 16 7 $MODE > /dev/null 2>&1
nvidia-smi --query-compute-apps=pid,used_memory --format=csv,noheader >> $O/gpu_apps_$MODE.txt
touch $O/DONE_$MODE
