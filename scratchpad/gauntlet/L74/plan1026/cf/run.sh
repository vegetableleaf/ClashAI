#!/bin/bash
# run.sh ENGINE(crforge|royalesim) RUN CPUS [rl_royale args...] -- P3-FORK on pod 32657: rl_royale from /workspace/cf3/cb
# engine: default lib_cfclone3 + build (pilot2); for the shipped main: CRFORGE_LIB=/workspace/crforge_main/fe364ceb/plain/lib CRFORGE_FACADE_BUILD=/workspace/cf3/build_fe (lead 10-28)
# (fin16-linux runtime; engine by ROYALE_ENGINE; crforge = lib_cfclone3 + the HEAD facade c003fc74 compiled to /workspace/cf3/build)
E=$1; RUN=$2; CPUS=$3; shift 3
TREE=${TREE:-/workspace/cf3/cb}; cd $TREE || exit 1
export PYTHONPATH=$TREE:/workspace/cfspeed/pylib ROYALE_RUNTIME=fin16-linux ROYALE_HEROIW_FORM=hero OMP_NUM_THREADS=1 \
  MKL_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1 RL_BATCH_SHA=1 ROYALE_ENGINE=$E \
  CRFORGE_LIB=${CRFORGE_LIB:-/workspace/pilot/lib_cfclone3} CRFORGE_TABLES=${CRFORGE_TABLES:-/workspace/crforge_cache/tables/16.402.22} \
  CRFORGE_FACADE_BUILD=${CRFORGE_FACADE_BUILD:-/workspace/cf3/build}
mkdir -p /workspace/cf3/logs
exec taskset -c $CPUS timeout ${TIMEOUT_S:-14400} /workspace/venvf16/bin/python -u -m pipeline.rl_royale --run $RUN "$@" > /workspace/cf3/logs/$RUN.log 2>&1
