#!/bin/bash
# FAST-LIVEOPP: compare.py on a 'live'-partner message in /workspace/fliv/cb (pod 33903; launch_arm.sh's env).
#   bash cmp_live.sh SRC_MSG.pkl CONFIG.yaml OUT.json [compare args]
SRC=$1; CFGY=$2; OUT=$3; shift 3
CB=/workspace/fliv/cb; cd $CB || exit 1
L=scratchpad/gauntlet/L74/plan1026/pilot/loop
export XMX=3g ROYALE_ENGINE=crforge CRFORGE_LIB=/workspace/crforge_main/fe364ceb/plain/lib ROYALE_HEROIW_FORM=hero \
 CRFORGE_TABLES=/workspace/oplm/tables/16.635.3 CUDA_VISIBLE_DEVICES=0 PYTHONPATH=$CB/$L/hook:$CB \
 CUBLAS_WORKSPACE_CONFIG=:4096:8 CRFORGE_FACADE_BUILD=$CB/$L/jbuild_fe364ceb OMP_NUM_THREADS=1 CRFORGE_XMX=3g \
 ROYALE_RUNTIME=fin16-linux MKL_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1
PY=/workspace/venvf16/bin/python
$PY -m pyflakes $L/producer.py $L/msg_live.py || echo "PYFLAKES (see above)"
$PY -c "import sys; sys.path.insert(0, '$L'); import producer, pathlib, os; producer.compile_java(pathlib.Path(os.environ['CRFORGE_FACADE_BUILD']), pathlib.Path(os.environ['CRFORGE_LIB']))" || exit 1
MSG=$OUT.msg.pkl                                     # RAW=1: SRC as it is (the no-live regression)
if [ "${RAW:-0}" = 1 ]; then MSG=$SRC; else $PY $L/msg_live.py "$SRC" "$CFGY" "$MSG" --jobs ${JOBS:-16} || exit 1; fi
exec timeout ${TMO:-5400} taskset -c ${CPUS:-178-179} $PY -u $L/compare.py "$MSG" "$OUT" "$@" 2>&1 | grep -v "Warning\|self.encoder"
