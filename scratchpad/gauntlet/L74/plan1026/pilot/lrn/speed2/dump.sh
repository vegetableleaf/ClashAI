#!/bin/bash
# SPEED2 on 33903: one pilot update through fastloop (pilot.yaml minus opponent G u0160, absent on 33903) with a small
# B6 warm start, dumping the actor messages (CB/scratchpad/gauntlet/L68/rl/RUN/fast_msg_u0000.pkl) and the learner's
# phase profile (RL_PROFILE). usage: dump.sh RUN [rl_royale k=v ...]
RUN=$1; shift; . /workspace/speed2/env.sh; cd $CB || exit 1
$PY -c "import sys; sys.path.insert(0, '$L'); import producer, pathlib, os; producer.compile_java(pathlib.Path(os.environ['CRFORGE_FACADE_BUILD']), pathlib.Path(os.environ['CRFORGE_LIB']))" || exit 1
RL_PROFILE=1 RL_BATCH_SHA=1 CRFORGE_XMX=${XMX:-4g} FASTLOOP_DUMP=1 exec timeout ${TMO:-5400} taskset -c $CPUS $PY -u $L/fastloop.py \
  --producers 2 --matches 16 --threads 3 --devices cuda:0 --server ${SRV:-graphs} --build /workspace/speed2/jbuild \
  -- --run $RUN --config /workspace/speed2/pilot_noG.yaml E=${E:-8} max_updates=1 n_actors=4 ability_bc_matches=16 "$@" \
  > /workspace/speed2/out/$RUN.log 2>&1
