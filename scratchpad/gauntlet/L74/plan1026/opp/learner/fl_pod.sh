#!/bin/bash
# OPP-LEARN-C part C (33903 defaults: CPU only; on 33308: CB=/workspace/oplc/cb TABLES=/workspace/crforge_cache/tables/16.635.3 GPU=1 LOGS=/workspace/oplc/logs). usage: fl.sh fast RUN CPUS CONFIG [rl args]   (DUMP=1: FASTLOOP_DUMP every update = compare msgs, 45 MB each)
#                                                                      fl.sh cmp MSG OUT CPUS [compare args]
MODE=$1; shift
CB=${CB:-/workspace/opplearnc/cbc}; LOGS=${LOGS:-/workspace/opplearnc/logs}; cd $CB || exit 1
L=scratchpad/gauntlet/L74/plan1026/pilot/loop
export PYTHONPATH=$CB/$L/hook:$CB ROYALE_RUNTIME=fin16-linux ROYALE_HEROIW_FORM=hero OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 \
  PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1 RL_BATCH_SHA=1 ROYALE_ENGINE=crforge CRFORGE_LIB=/workspace/crforge_main/fe364ceb/plain/lib \
  CRFORGE_TABLES=${TABLES:-/workspace/opplearn/tables/16.635.3} CRFORGE_FACADE_BUILD=$CB/$L/jbuild_fe364ceb CUBLAS_WORKSPACE_CONFIG=:4096:8 \
  CRFORGE_XMX=${XMX:-6g} CUDA_VISIBLE_DEVICES=${GPU:-}
[ "${DECOY:-0}" = 1 ] && export CRFORGE_BARREL_DECOY_SIM=1   # pilot SIM; off = level B / the rl smokes
PY=/workspace/venvf16/bin/python
mkdir -p $LOGS
$PY -c "import sys; sys.path.insert(0, '$L'); import producer, pathlib, os; producer.compile_java(pathlib.Path(os.environ['CRFORGE_FACADE_BUILD']), pathlib.Path(os.environ['CRFORGE_LIB']))" || exit 1
if [ "$MODE" = fast ]; then
  RUN=$1; CPUS=$2; CFG=$3; shift 3
  FASTLOOP_DUMP=${DUMP:-} exec timeout ${TMO:-7200} taskset -c $CPUS $PY -u $L/fastloop.py ${FAST_ARGS:---producers 1 --matches 8 --threads 2 --devices cpu} \
    -- --run $RUN --config $CFG actor_device=cpu learner_device=cpu "$@" > $LOGS/$RUN.log 2>&1
else
  MSG=$1; OUT=$2; CPUS=$3; shift 3
  ROYALE_HEROIW_PRESS=live exec timeout ${TMO:-7200} taskset -c $CPUS $PY -u $L/compare.py "$MSG" "$OUT" --device cpu "$@" 2>&1 | grep -v "Warning\|self.encoder"
fi
