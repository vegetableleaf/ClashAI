#!/bin/bash
# ROLLOUT-SPEED last 31892 block (after LEARNER-SPEED's BLOCK_DONE): under CUDA MPS (private pipe dir)
# (1) bench mps_g_32x32x1 (the pair for mps_gcs_32x32x1: F3 + F2' under MPS), (2) the full-stack fastloop pilot run:
# --server graphs --local-forward --overlap 1 + CELLS1 + SHARDS 3 + split_attn + trunk_graph 256, 32 x 16 x 1 = 512 / update.
cd /workspace/rs || exit 1
. ./env.sh
O=/workspace/rs/out; LOG=$O/chain.log
say() { echo "$(date -u +%FT%TZ) $*" >> $LOG; }
until [ -f /workspace/lspeed/out/BLOCK_DONE ] && [ ! -f /workspace/BENCH_LOCK ]; do sleep 15; done
lock "final: MPS bench pair + full-stack fastloop (CPUs 6-33, GPU, ~25 min)"
export CUDA_MPS_PIPE_DIRECTORY=/workspace/rs/mps_pipe CUDA_MPS_LOG_DIRECTORY=/workspace/rs/mps_log
nvidia-cuda-mps-control -d && say "final: MPS daemon up"
say "bench mps_g_32x32x1 start"
(cd cb && timeout 1200 taskset -c 6-33 $PY -u $L/bench.py ../in/pilot_u0000.pkl $O/bench_mps_g_32x32x1.json --warm 75 --seconds 150 \
   --producers 32 --matches 32 --threads 1 --server graphs --devices cuda:0 --local-forward > $O/bench_mps_g_32x32x1.log 2>&1)
say "bench mps_g_32x32x1 rc $? $($PY -c "import json; d=json.load(open('$O/bench_mps_g_32x32x1.json')); print(round(d['rows_per_s']), 'rows/s', round(d['matches_per_h']), 'matches/h', round(d['cores_busy'], 1), '+', round(d['server_cores_busy'], 1))" 2>&1 | tail -1)"
say "full-stack fastloop start"
FASTLOOP_CELLS1=1 FASTLOOP_SHARDS=3 bash fl.sh rs_full 6-33 "--producers 32 --matches 16 --threads 1 --devices cuda:0 --server graphs --local-forward --overlap 1" \
  max_updates=4 split_attn=true trunk_graph=256
say "full-stack done: $(grep 'fastloop\] u\|Traceback\|Error' $O/rs_full/loop.log | tail -6 | tr '\n' '|')"
if grep -q Traceback $O/rs_full/loop.log || ! grep -q "u0002 512" $O/rs_full/loop.log; then
  say "full-stack failed: rollout-only stack instead (no overlap, no learner keys)"
  FASTLOOP_CELLS1=1 FASTLOOP_SHARDS=3 bash fl.sh rs_full2 6-33 "--producers 32 --matches 16 --threads 1 --devices cuda:0 --server graphs --local-forward" max_updates=4
  say "rollout-stack done: $(grep 'fastloop\] u\|Traceback\|Error' $O/rs_full2/loop.log | tail -6 | tr '\n' '|')"
fi
echo quit | nvidia-cuda-mps-control; say "final: MPS quit; final done"
unlock
