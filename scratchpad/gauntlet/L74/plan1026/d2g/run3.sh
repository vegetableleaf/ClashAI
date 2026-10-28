#!/bin/bash
# run3.sh ENGINE RUN CPUS DETCUDA(0|1) [rl_royale args] -- run.sh's env (pod 33308) + optional deterministic CUDA
# (torch.use_deterministic_algorithms via detcuda/sitecustomize.py, CUBLAS_WORKSPACE_CONFIG=:4096:8).
E=$1; RUN=$2; CPUS=$3; DET=$4; shift 4
cd /workspace/d2/cb || exit 1
export PYTHONPATH=/workspace/d2/cb/scratchpad/gauntlet/L74/plan1026/d2g/detcuda:/workspace/d2/cb:/workspace/d2/stage/pylib \
  ROYALE_RUNTIME=fin16-linux ROYALE_HEROIW_FORM=hero OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1 \
  PYTHONNOUSERSITE=1 RL_BATCH_SHA=1 ROYALE_ENGINE=$E CRFORGE_LIB=/workspace/d2/stage/lib \
  CRFORGE_TABLES=/workspace/crforge_cache/tables/16.402.22 CRFORGE_FACADE_BUILD=/workspace/d2/build
[ "$DET" = 1 ] && export D2_DET_CUDA=1 CUBLAS_WORKSPACE_CONFIG=:4096:8
mkdir -p /workspace/d2/logs
exec taskset -c $CPUS timeout 14400 /workspace/venvf16/bin/python -u -m pipeline.rl_royale --run $RUN "$@" \
  > /workspace/d2/logs/$RUN.log 2>&1
