#!/bin/bash
# run.sh ENGINE(crforge|royalesim) RUN CPUS [rl_royale args...] -- D2-G: rl_royale on fin16-linux runtime, engine by ROYALE_ENGINE
E=$1; RUN=$2; CPUS=$3; shift 3
cd /workspace/d2/cb || exit 1
export PYTHONPATH=/workspace/d2/cb:/workspace/d2/stage/pylib ROYALE_RUNTIME=fin16-linux ROYALE_HEROIW_FORM=hero OMP_NUM_THREADS=1 \
  MKL_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1 RL_BATCH_SHA=1 ROYALE_ENGINE=$E \
  CRFORGE_LIB=/workspace/d2/stage/lib CRFORGE_TABLES=/workspace/crforge_cache/tables/16.402.22 CRFORGE_FACADE_BUILD=/workspace/d2/build
mkdir -p /workspace/d2/logs
exec taskset -c $CPUS timeout 7200 /workspace/venvf16/bin/python -u -m pipeline.rl_royale --run $RUN "$@" > /workspace/d2/logs/$RUN.log 2>&1
