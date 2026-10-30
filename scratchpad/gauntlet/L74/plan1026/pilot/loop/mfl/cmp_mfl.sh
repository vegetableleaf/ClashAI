#!/bin/bash
# MEMFULL-LOOP: compare.py in /workspace/mfl/cb (33903, CPUs 162-169). bash cmp_mfl.sh MSG.pkl OUT.json [compare args]
MSG=$1; OUT=$2; shift 2
CB=${CB:-/workspace/mfl/cb}; cd $CB || exit 1
L=scratchpad/gauntlet/L74/plan1026/pilot/loop
export ROYALE_ENGINE=crforge CRFORGE_LIB=/workspace/crforge_main/fe364ceb/plain/lib ROYALE_HEROIW_FORM=hero \
 CRFORGE_TABLES=/workspace/oplm/tables/16.635.3 PYTHONPATH=$CB/$L/hook:$CB \
 CUBLAS_WORKSPACE_CONFIG=:4096:8 CRFORGE_FACADE_BUILD=$CB/$L/jbuild_mfl OMP_NUM_THREADS=1 CRFORGE_XMX=4g \
 ROYALE_RUNTIME=fin16-linux MKL_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1 FASTLOOP_MEMHASH=1
[ -n "$GPU" ] && export CUDA_VISIBLE_DEVICES=$GPU
PY=/workspace/venvf16/bin/python
$PY -m pyflakes $L/producer.py $L/compare.py $L/serve.py $L/bench.py $L/fastloop.py $L/msg_memfull.py || echo "PYFLAKES (see above)"
$PY -c "import sys; sys.path.insert(0, '$L'); import producer, pathlib, os; producer.compile_java(pathlib.Path(os.environ['CRFORGE_FACADE_BUILD']), pathlib.Path(os.environ['CRFORGE_LIB']))" || exit 1
exec timeout ${TMO:-2400} taskset -c ${CPUS:-162-169} $PY -u $L/compare.py "$MSG" "$OUT" "$@" 2>&1 | grep -v "Warning\|self.encoder"
