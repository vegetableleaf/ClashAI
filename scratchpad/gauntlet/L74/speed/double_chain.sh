#!/bin/bash
# S1b on the double pod (33308: 108.8-core quota, 2x 4090, 125 GB container limit): measured, not projected.
#   FAST=refine,cue bash double_chain.sh
cd /workspace/cb; export ROYALE_RUNTIME=fin15-linux PYTHONPATH=/workspace/cb
INTERP=/workspace/venvf15/bin/python; H=scratchpad/gauntlet/L74/speed/harness.py
C=scratchpad/gauntlet/L74/stepd/cfg/succ48_x_s101.yaml; O=/workspace/speed; F=${FAST:-refine,cue}; T=$(echo $F | tr , _)
mem() { cat /sys/fs/cgroup/memory/memory.max_usage_in_bytes; }
# one policy server (GPU 0), 100 workers
for E in 512 1024; do
  N=$((E * 4))
  CUDA_VISIBLE_DEVICES=0 "$INTERP" $H --cfg $C --E $E --G 4 --mode batched --workers 100 --cohorts 2 --device cuda --fast $F --out $O/d1_n${N}_$T > $O/d1_n${N}_$T.log 2>&1
  echo "d1_n${N}_$T maxmem $(mem)" >> $O/double_mem.txt
done
# two policy servers (one per GPU), 50 workers each, N/2 matches each, run at the same time
for E in 256 512; do
  N=$((E * 8))
  CUDA_VISIBLE_DEVICES=0 "$INTERP" $H --cfg $C --E $E --G 4 --mode batched --workers 50 --cohorts 2 --device cuda --fast $F --out $O/d2a_n${N}_$T > $O/d2a_n${N}_$T.log 2>&1 &
  CUDA_VISIBLE_DEVICES=1 "$INTERP" $H --cfg $C --E $E --G 4 --mode batched --workers 50 --cohorts 2 --device cuda --fast $F --set seed=202 --out $O/d2b_n${N}_$T > $O/d2b_n${N}_$T.log 2>&1
  wait
  echo "d2_n${N}_$T maxmem $(mem)" >> $O/double_mem.txt
done
touch $O/DOUBLE_DONE_$T
