#!/bin/bash
# OPP-LEARN-C part C on 33903 (CPU only; P2-OPP2 owns the GPU). usage: fl.sh fast RUN CPUS CONFIG [rl args]   (FASTLOOP_DUMP=1 fastloop)
#                                                                      fl.sh cmp MSG OUT CPUS [compare args]
MODE=$1; shift
CB=/workspace/opplearnc/cbc; cd $CB || exit 1
L=scratchpad/gauntlet/L74/plan1026/pilot/loop
export PYTHONPATH=$CB/$L/hook:$CB ROYALE_RUNTIME=fin16-linux ROYALE_HEROIW_FORM=hero OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 \
  PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1 RL_BATCH_SHA=1 ROYALE_ENGINE=crforge CRFORGE_LIB=/workspace/crforge_main/fe364ceb/plain/lib \
  CRFORGE_TABLES=/workspace/opplearn/tables/16.635.3 CRFORGE_FACADE_BUILD=$CB/$L/jbuild_fe364ceb CUBLAS_WORKSPACE_CONFIG=:4096:8 \
  CRFORGE_BARREL_DECOY_SIM=1 CRFORGE_XMX=${XMX:-6g} CUDA_VISIBLE_DEVICES=
PY=/workspace/venvf16/bin/python
mkdir -p /workspace/opplearnc/logs
$PY -c "import sys; sys.path.insert(0, '$L'); import producer, pathlib, os; producer.compile_java(pathlib.Path(os.environ['CRFORGE_FACADE_BUILD']), pathlib.Path(os.environ['CRFORGE_LIB']))" || exit 1
if [ "$MODE" = fast ]; then
  RUN=$1; CPUS=$2; CFG=$3; shift 3
  FASTLOOP_DUMP=1 exec timeout ${TMO:-7200} taskset -c $CPUS $PY -u $L/fastloop.py ${FAST_ARGS:---producers 1 --matches 8 --threads 2 --devices cpu} \
    -- --run $RUN --config $CFG actor_device=cpu learner_device=cpu "$@" > /workspace/opplearnc/logs/$RUN.log 2>&1
else
  MSG=$1; OUT=$2; CPUS=$3; shift 3
  ROYALE_HEROIW_PRESS=live exec timeout ${TMO:-7200} taskset -c $CPUS $PY -u $L/compare.py "$MSG" "$OUT" --device cpu "$@" 2>&1 | grep -v "Warning\|self.encoder"
fi
