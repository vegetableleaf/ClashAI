#!/bin/bash
# bench.sh OUT.json CPUS [bench.py args] -- LOOP-INT throughput on a pod laid out as 33553 (/workspace/venv, /workspace/loop/cb,
# d2/stage/pylib, d2t2/lib_cfclone, crforge_cache/tables/16.402.22; set PY / CB / CF_LIB / TABLES / PYLIB on other pods).
OUT=$1; CPUS=$2; shift 2
CB=${CB:-/workspace/loop/cb}; cd $CB || exit 1
PY=${PY:-/workspace/venv/bin/python}
export PYTHONPATH=$CB/scratchpad/gauntlet/L74/plan1026/pilot/loop/hook:$CB:${PYLIB:-/workspace/d2/stage/pylib} \
  ROYALE_RUNTIME=fin16-linux ROYALE_HEROIW_FORM=hero OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1 \
  PYTHONNOUSERSITE=1 ROYALE_ENGINE=crforge CRFORGE_LIB=${CF_LIB:-/workspace/d2t2/lib_cfclone} \
  CRFORGE_TABLES=${TABLES:-/workspace/crforge_cache/tables/16.402.22} \
  CRFORGE_FACADE_BUILD=$CB/scratchpad/gauntlet/L74/plan1026/pilot/loop/jbuild CUBLAS_WORKSPACE_CONFIG=:4096:8
$PY -c "import sys; sys.path.insert(0, 'scratchpad/gauntlet/L74/plan1026/pilot/loop'); import producer, pathlib, os; producer.compile_java(pathlib.Path(os.environ['CRFORGE_FACADE_BUILD']), pathlib.Path(os.environ['CRFORGE_LIB']))" || exit 1
exec taskset -c $CPUS $PY -u scratchpad/gauntlet/L74/plan1026/pilot/loop/bench.py ${MSG:-/workspace/loop/msg_u0000.pkl} $OUT "$@"
