#!/bin/bash
# ROLLOUT-SPEED final block, corrected (screen_entries=1; the first try ran the 702-match init screen on 2 actors):
# full-stack fastloop with fastloop --mps (tests the flag), graphs + local-forward + overlap 1 + CELLS1 + SHARDS 3 +
# split_attn + trunk_graph 256, 32 x 16 x 1 = 512 / update. Holds the lock taken by final.sh.
cd /workspace/rs || exit 1
. ./env.sh
O=/workspace/rs/out; LOG=$O/chain.log
say() { echo "$(date -u +%FT%TZ) $*" >> $LOG; }
echo quit | CUDA_MPS_PIPE_DIRECTORY=/workspace/rs/mps_pipe nvidia-cuda-mps-control; sleep 2
rm -f cb/$L/fastloop.py && cp in/fastloop.py cb/$L/fastloop.py
say "full-stack (rs_full3, fastloop --mps) start"
FASTLOOP_CELLS1=1 FASTLOOP_SHARDS=3 bash fl.sh rs_full3 6-33 "--producers 32 --matches 16 --threads 1 --devices cuda:0 --server graphs --local-forward --overlap 1 --mps /workspace/rs/mps3" \
  max_updates=4 split_attn=true trunk_graph=256 screen_entries=1
say "full-stack done: $(grep 'fastloop\] u\|fastloop\] CUDA MPS\|Traceback\|Error' $O/rs_full3/loop.log | tail -7 | tr '\n' '|')"
if grep -q Traceback $O/rs_full3/loop.log || ! grep -q "u0002 512" $O/rs_full3/loop.log; then
  say "full-stack failed: rollout-only stack instead (no overlap, no learner keys)"
  FASTLOOP_CELLS1=1 FASTLOOP_SHARDS=3 bash fl.sh rs_full4 6-33 "--producers 32 --matches 16 --threads 1 --devices cuda:0 --server graphs --local-forward --mps /workspace/rs/mps4" \
    max_updates=4 screen_entries=1
  say "rollout-stack done: $(grep 'fastloop\] u\|Traceback\|Error' $O/rs_full4/loop.log | tail -6 | tr '\n' '|')"
fi
say "daemons left: $(pgrep -c nvidia-cuda-mps); final done"
unlock
