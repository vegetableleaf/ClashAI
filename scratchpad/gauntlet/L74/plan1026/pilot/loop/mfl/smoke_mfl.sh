#!/bin/bash
# MEMFULL-LOOP: fast-loop smoke + message dump with memory_e_max 256 / memory_board_snap on, 33903 CPUs 162-169, no GPU
# (GPU has other jobs): serve.py + learner on CPU. critic_warmup_updates=1 (tower_phat refuses 0): u0001 = a PPO policy step. bash smoke_mfl.sh RUN [rl_royale k=v ...]   log /workspace/mfl/out/RUN.out
RUN=$1; shift
CB=${CB:-/workspace/mfl/cb}; cd $CB || exit 1
L=scratchpad/gauntlet/L74/plan1026/pilot/loop
export RL_BATCH_SHA=1 ROYALE_ENGINE=crforge CRFORGE_LIB=/workspace/crforge_main/fe364ceb/plain/lib ROYALE_HEROIW_FORM=hero \
 CRFORGE_TABLES=/workspace/oplm/tables/16.635.3 CUDA_VISIBLE_DEVICES= PYTHONPATH=$CB/$L/hook:$CB:/workspace/d2/stage/pylib \
 CUBLAS_WORKSPACE_CONFIG=:4096:8 CRFORGE_FACADE_BUILD=$CB/$L/jbuild_mfl OMP_NUM_THREADS=2 CRFORGE_XMX=4g \
 ROYALE_RUNTIME=fin16-linux MKL_NUM_THREADS=2 PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1 CRFORGE_BARREL_DECOY_SIM=1 \
 ROYALE_HEROIW_PRESS=live FASTLOOP_DUMP=1
PY=/workspace/venvf16/bin/python
exec timeout ${TMO:-3000} taskset -c ${CPUS:-162-169} $PY -u $L/fastloop.py --producers 1 --matches 8 --threads 4 --devices cpu ${SERVER_ARGS:---server eager} -- \
 --run $RUN --config /workspace/mfl/mfl.yaml n_actors=1 E=4 max_updates=2 critic_warmup_updates=1 --smoke "$@" > /workspace/mfl/out/$RUN.out 2>&1 < /dev/null
