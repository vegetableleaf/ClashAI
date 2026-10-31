#!/bin/bash
# check.sh TAG [CPUS [rl_royale k=v ...]] -- PILOT2 pre-launch check on a booted pod (pod side): (1) a REAL fast-loop rl_royale --smoke on
# pilot2.yaml (memory 256 + snap + encoder unfrozen + target_obs + ability_head_from_init + the speed keys) with the training
# stack flags (graphs, local-forward, overlap 1, MPS), E=4, critic_warmup_updates=1 so u0001 is a PPO policy step, FASTLOOP_DUMP
# -> (2) compare.py on its u0000 message (fast loop vs production, same device, under MPS, CELLS1 + SHARDS 3 from env.sh).
# Logs / results: /workspace/p2/check_TAG/{smoke.log,cmp.json,cmp.log}; last line of chain.log = CHECK_DONE.
TAG=$1; C=${2:-0-15}
. /workspace/p2/env.sh || exit 1
O=/workspace/p2/check_$TAG; RUN=p2smoke_$TAG; mkdir -p $O; cd $CB || exit 1
say() { echo "$(date -u +%FT%TZ) $*" >> $O/chain.log; }
$PY -c "import sys, pathlib, os; sys.path.insert(0, '$L'); import producer; producer.compile_java(pathlib.Path(os.environ['CRFORGE_FACADE_BUILD']), pathlib.Path(os.environ['CRFORGE_LIB']))" || { say "javac failed"; exit 1; }
say "smoke $RUN start"
FASTLOOP_DUMP=1 timeout 3600 taskset -c $C $PY -u $L/fastloop.py --producers 1 --matches 8 --threads 4 --devices cuda:0 \
  --server graphs --local-forward --overlap 1 --mps $O/mps_smoke --build $CRFORGE_FACADE_BUILD --out $O/smoke_out -- \
  --run $RUN --config $CB/$P2/pilot2.yaml n_actors=1 E=4 max_updates=2 critic_warmup_updates=1 "${@:3}" --smoke > $O/smoke.log 2>&1 < /dev/null
say "smoke rc $? $(grep -c 'SMOKE PASS' $O/smoke.log) SMOKE PASS lines; $(grep -m1 'config sha' $O/smoke.log | grep -o 'config sha [0-9a-f]*')"
M=$CB/scratchpad/gauntlet/L68/rl/$RUN/fast_msg_u0000.pkl
[ -f $M ] || { say "no dumped message $M"; say CHECK_DONE; exit 1; }
export CUDA_MPS_PIPE_DIRECTORY=$O/mps_cmp/pipe CUDA_MPS_LOG_DIRECTORY=$O/mps_cmp/log
mkdir -p $CUDA_MPS_PIPE_DIRECTORY $CUDA_MPS_LOG_DIRECTORY && nvidia-cuda-mps-control -d
FASTLOOP_MEMHASH=1 CRFORGE_BARREL_DECOY_SIM=1 ROYALE_HEROIW_PRESS=live timeout 3600 taskset -c $C $PY -u $L/compare.py $M $O/cmp.json \
  --device cuda --in-flight 8 --matches 8 --threads 4 --server graphs --local-forward --init $(grep '^init:' $CB/$P2/pilot2.yaml | cut -d' ' -f2) \
  > $O/cmp.log 2>&1 < /dev/null
rc=$?; echo quit | nvidia-cuda-mps-control
say "compare rc $rc $(tail -1 $O/cmp.log | cut -c1-900)"
say CHECK_DONE
