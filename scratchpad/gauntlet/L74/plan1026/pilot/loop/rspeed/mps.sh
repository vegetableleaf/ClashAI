#!/bin/bash
# ROLLOUT-SPEED: the same bench under CUDA MPS (private pipe dir: only processes with this env join; daemon quit at the end).
cd /workspace/rs || exit 1
. ./env.sh
O=/workspace/rs/out; LOG=$O/chain.log
say() { echo "$(date -u +%FT%TZ) $*" >> $LOG; }
export CUDA_MPS_PIPE_DIRECTORY=/workspace/rs/mps_pipe CUDA_MPS_LOG_DIRECTORY=/workspace/rs/mps_log
mkdir -p $CUDA_MPS_PIPE_DIRECTORY $CUDA_MPS_LOG_DIRECTORY
lock "MPS benches (CPUs 6-33, GPU)"
nvidia-cuda-mps-control -d && say "MPS daemon up"
bench() {
  local n=$1 e=$2; shift 2
  say "bench $n start"
  (cd cb && env $e timeout 1200 taskset -c 6-33 $PY -u $L/bench.py ../in/pilot_u0000.pkl $O/bench_$n.json --warm 75 --seconds 150 "$@" > $O/bench_$n.log 2>&1)
  say "bench $n rc $? $($PY -c "import json; d=json.load(open('$O/bench_$n.json')); print(round(d['matches_per_h']), 'matches/h', d['gpu_util_mean'], 'cores', round(d['cores_busy'], 1), '+srv', round(d['server_cores_busy'], 1), 'stage/match', {k: round(v, 3) for k, v in d['stage_s_per_match'].items()})" 2>&1 | tail -1)"
}
B="--devices cuda:0 --local-forward"
bench mps_g_16x32x2 "X=1" --producers 16 --matches 32 --threads 2 --server graphs $B
bench mps_${MPSB:-gcs}_24x32x1 "FASTLOOP_CELLS1=1 FASTLOOP_SHARDS=3" --producers 24 --matches 32 --threads 1 --server graphs $B
bench mps_gcs_32x32x1 "FASTLOOP_CELLS1=1 FASTLOOP_SHARDS=3" --producers 32 --matches 32 --threads 1 --server graphs $B
echo quit | nvidia-cuda-mps-control; say "MPS daemon quit"
unset CUDA_MPS_PIPE_DIRECTORY CUDA_MPS_LOG_DIRECTORY
bench gcs_32x32x1 "FASTLOOP_CELLS1=1 FASTLOOP_SHARDS=3" --producers 32 --matches 32 --threads 1 --server graphs $B
bench gcs_40x32x1 "FASTLOOP_CELLS1=1 FASTLOOP_SHARDS=3" --producers 40 --matches 32 --threads 1 --server graphs $B
say "mps done"
unlock
