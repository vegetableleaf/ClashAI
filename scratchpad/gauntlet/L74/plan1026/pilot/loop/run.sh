#!/bin/bash
# run.sh ARM(rl|fast) RUN CPUS [rl_royale k=v ...] -- LOOP-INT: one arm of the correctness test (pod: /workspace/loop/cb).
# FAST_ARGS (env) = fastloop.py options (default: 2 producers x 64 matches x 4 threads on cuda:0).
ARM=$1; RUN=$2; CPUS=$3; shift 3
CB=${CB:-/workspace/loop/cb}; cd $CB || exit 1
HOOK=; [ "${NOTF32:-1}" = 1 ] && HOOK=$CB/scratchpad/gauntlet/L74/plan1026/pilot/loop/hook:
export PYTHONPATH=$HOOK$CB:/workspace/d2/stage/pylib ROYALE_RUNTIME=fin16-linux ROYALE_HEROIW_FORM=hero OMP_NUM_THREADS=1 \
  MKL_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1 RL_BATCH_SHA=1 ROYALE_ENGINE=crforge \
  CRFORGE_LIB=${CF_LIB:-/workspace/d2t2/lib_cfclone} CRFORGE_TABLES=/workspace/crforge_cache/tables/16.402.22 \
  CRFORGE_FACADE_BUILD=${FACADE_BUILD:-$CB/scratchpad/gauntlet/L74/plan1026/pilot/loop/jbuild} CUBLAS_WORKSPACE_CONFIG=:4096:8
CFG=${CFG:-scratchpad/gauntlet/L74/plan1026/pilot/loop/ref_v0.yaml}
PY=/workspace/venvf16/bin/python
mkdir -p /workspace/loop/logs
$PY -c "import sys; sys.path.insert(0, 'scratchpad/gauntlet/L74/plan1026/pilot/loop'); import producer, pathlib, os; producer.compile_java(pathlib.Path(os.environ['CRFORGE_FACADE_BUILD']), pathlib.Path(os.environ['CRFORGE_LIB']))" || exit 1
if [ "$ARM" = fast ]; then
  exec taskset -c $CPUS $PY -u scratchpad/gauntlet/L74/plan1026/pilot/loop/fastloop.py ${FAST_ARGS:---producers 2 --matches 64 --threads 4 --devices cuda:0} \
    -- --run $RUN --config $CFG "$@" > /workspace/loop/logs/$RUN.log 2>&1
else
  exec taskset -c $CPUS $PY -u -m pipeline.rl_royale --run $RUN --config $CFG "$@" > /workspace/loop/logs/$RUN.log 2>&1
fi
