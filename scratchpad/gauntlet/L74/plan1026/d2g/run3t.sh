#!/bin/bash
# run3t.sh TREE ENGINE RUN CPUS DETCUDA(0|1) [rl_royale args] -- d2g/run3.sh with the tree as an argument (D2-T paired runs)
T=$1; E=$2; RUN=$3; CPUS=$4; DET=$5; shift 5
cd $T || exit 1
export PYTHONPATH=/workspace/d2/cb/scratchpad/gauntlet/L74/plan1026/d2g/detcuda:$T:/workspace/d2/stage/pylib \
  ROYALE_RUNTIME=fin16-linux ROYALE_HEROIW_FORM=hero OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1 \
  PYTHONNOUSERSITE=1 RL_BATCH_SHA=1 ROYALE_ENGINE=$E CRFORGE_LIB=${CF_LIB:-/workspace/d2/stage/lib} \
  CRFORGE_TABLES=/workspace/crforge_cache/tables/16.402.22 CRFORGE_FACADE_BUILD=${FACADE_BUILD:-/workspace/d2/build}
[ "$DET" = 1 ] && export D2_DET_CUDA=1 CUBLAS_WORKSPACE_CONFIG=:4096:8
mkdir -p /workspace/d2t/logs
exec taskset -c $CPUS timeout 14400 /workspace/venvf16/bin/python -u -m pipeline.rl_royale --run $RUN "$@" \
  > /workspace/d2t/logs/$RUN.log 2>&1
