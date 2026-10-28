#!/bin/bash
# test_pod.sh CPUS PYTEST_ARGS... -- pytest on pod 32657 against /workspace/cf3/cfh with the crforge engine (run via ssh; log to a file)
cd /workspace/cf3/${TREE_NAME:-cfh} || exit 1
export PYTHONPATH=/workspace/cf3/${TREE_NAME:-cfh}:/workspace/cfspeed/pylib ROYALE_RUNTIME=fin16-linux ROYALE_HEROIW_FORM=hero OMP_NUM_THREADS=1 \
  MKL_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1 ROYALE_ENGINE=${ENGINE:-crforge} \
  CRFORGE_LIB=${CRFORGE_LIB:-/workspace/pilot/lib_cfclone3} CRFORGE_TABLES=${CRFORGE_TABLES:-/workspace/crforge_cache/tables/16.402.22} \
  CRFORGE_FACADE_BUILD=${CRFORGE_FACADE_BUILD:-/workspace/cf3/build}
CPUS=$1; shift
exec taskset -c $CPUS /workspace/venvf16/bin/python -m pytest -q "$@"
