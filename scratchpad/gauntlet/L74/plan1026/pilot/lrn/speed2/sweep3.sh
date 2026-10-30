#!/bin/bash
# SPEED2: the server process's GIL switch interval (5 ms default) vs 0.5 / 0.2 ms at the box shape, eager + graphs.
. /workspace/speed2/env.sh; cd $CB || exit 1
O=/workspace/speed2/out/s3; mkdir -p $O
nvidia-smi --query-compute-apps=pid,used_memory --format=csv,noheader > $O/gpu_apps.txt
for m in eager graphs; do for sw in 5 0.5 0.2; do
  taskset -c $CPUS timeout 900 $PY -u ../srvshape.py --out $O/${m}_sw$sw.json --mode $m --configs 16x21 --seconds 30 \
    --max-batch 512 --switch-ms $sw > $O/${m}_sw$sw.log 2>&1
done; done
nvidia-smi --query-compute-apps=pid,used_memory --format=csv,noheader >> $O/gpu_apps.txt
touch $O/DONE
