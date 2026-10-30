#!/bin/bash
# SPEED2 on 33903: dump the pilot's actor messages (pilot.yaml minus opponent G u0160, absent on 33903) with a small
# warm start; the u0000 message lands in $CB/scratchpad/gauntlet/L68/rl/$RUN/fast_msg_u0000.pkl. usage: dump.sh RUN
RUN=$1; . /workspace/speed2/env.sh; cd $CB || exit 1
$PY -c "import sys; sys.path.insert(0, '$L'); import producer, pathlib, os; producer.compile_java(pathlib.Path(os.environ['CRFORGE_FACADE_BUILD']), pathlib.Path(os.environ['CRFORGE_LIB']))" || exit 1
CRFORGE_XMX=${XMX:-4g} FASTLOOP_DUMP=1 exec timeout ${TMO:-5400} taskset -c $CPUS $PY -u $L/fastloop.py \
  --producers 2 --matches 16 --threads 3 --devices cuda:0 --server eager --build /workspace/speed2/jbuild \
  -- --run $RUN --config /workspace/speed2/pilot_noG.yaml E=8 max_updates=1 n_actors=4 ability_bc_matches=16 \
  > /workspace/speed2/out/$RUN.log 2>&1
