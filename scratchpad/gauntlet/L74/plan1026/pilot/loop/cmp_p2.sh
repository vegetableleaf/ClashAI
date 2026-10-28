#!/bin/bash
# OPP-LEARN-A: compare.py with P2 timing-head opponents (pod 33308). usage:
#   CB=/workspace/opl/cb CPUS=140-147 GPU=0 bash cmp_p2.sh SRC_MSG.pkl OUT.json [msg_p2 args] -- [compare args]
# Builds OUT.msg.pkl (msg_p2.py: the timing checkpoint on every --every-th job), then runs compare.py on it in CB's tree
# with the pilot's process conditions (barrel decoy SIM, live hero IW press).
SRC=$1; OUT=$2; shift 2
M=(); while [ $# -gt 0 ] && [ "$1" != "--" ]; do M+=("$1"); shift; done; [ "$1" = "--" ] && shift
CB=${CB:-/workspace/opl/cb}; cd $CB || exit 1
L=scratchpad/gauntlet/L74/plan1026/pilot/loop
export PYTHONPATH=$CB:/workspace/d2/stage/pylib ROYALE_RUNTIME=fin16-linux ROYALE_HEROIW_FORM=hero OMP_NUM_THREADS=1 \
  MKL_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1 ROYALE_ENGINE=crforge \
  CRFORGE_LIB=${CF_LIB:-/workspace/crforge_main/fe364ceb/plain/lib} CRFORGE_TABLES=${TABLES:-/workspace/crforge_cache/tables/16.635.3} \
  CRFORGE_FACADE_BUILD=$CB/$L/jbuild_fe364ceb CUBLAS_WORKSPACE_CONFIG=:4096:8 CUDA_VISIBLE_DEVICES=${GPU:-0} \
  CRFORGE_BARREL_DECOY_SIM=1 ROYALE_HEROIW_PRESS=live CRFORGE_XMX=${XMX:-6g}
PY=${PY:-/workspace/venvf16/bin/python}
$PY -c "import sys; sys.path.insert(0, '$L'); import producer, pathlib, os; producer.compile_java(pathlib.Path(os.environ['CRFORGE_FACADE_BUILD']), pathlib.Path(os.environ['CRFORGE_LIB']))" || exit 1
MSG=$OUT.msg.pkl                                     # RAW=1: SRC as it is (the no-P2 regression, opp_style untouched)
if [ "${RAW:-0}" = 1 ]; then MSG=$SRC; else $PY $L/msg_p2.py "$SRC" "$MSG" "${M[@]}" || exit 1; fi
exec timeout ${TMO:-5400} taskset -c ${CPUS:-140-147} $PY -u $L/compare.py "$MSG" "$OUT" "$@" 2>&1 | grep -v "Warning\|self.encoder"
