#!/bin/bash
# arm.sh RUN [rl_royale k=v ...] -- PILOT2 pod side: one training arm on a pod booted by loop_pod.sh (ENTRY=-c), full speed
# stack (HANDOFF 10-30 21:10): fastloop --mps --server graphs --local-forward --overlap 1, 32 producers x 16 matches x 1 thread
# = 512 matches / update, FASTLOOP_CELLS1 + FASTLOOP_SHARDS 3 (env.sh), config pilot2/pilot2.yaml + the k=v (arm L's learner).
# CPUs: producers / servers / MPS on PCPUS (default 0-23), the learner (= fastloop's main process) on its own LCPUS (24-26);
# a pinner re-applies both every 30 s (children spawned later inherit the main process's set). auto_stop.py (patience 50,
# 0.5 pp, HOURS cap AUTO_HOURS default 48 = a runaway guard only) writes STOP in OUT; max_updates 600 is in the config.
# Outputs OUT=/workspace/loop/p2/RUN: loop.log, loop.rc (exit code), pids, throughput.jsonl, FINAL, STOP, auto_stop.log,
# pin.log, gpu.log. Checkpoints: /workspace/loop/cb/icebow/data/bench/rl_royale/RUN/.
RUN=$1; shift
. /workspace/p2/env.sh || exit 1
OUT=$W/p2/$RUN; PC=${PCPUS:-0-23}; LC=${LCPUS:-24-26}
mkdir -p $OUT; cd $CB || exit 1
case " $* " in *" --resume "*) kill $(sed -n 's/^auto_stop //p' $OUT/pids 2> /dev/null) 2> /dev/null; mv $OUT/loop.log $OUT/loop.log.$(date +%s) 2> /dev/null; rm -f $OUT/FINAL $OUT/STOP $OUT/loop.rc ;;   # crash resume
  *) [ -e scratchpad/gauntlet/L68/rl/$RUN ] && { echo "run $RUN exists (rl_royale refuses a re-used name; pass --resume)"; exit 1; } ;; esac
$PY -c "import sys, pathlib, os; sys.path.insert(0, '$L'); import producer; producer.compile_java(pathlib.Path(os.environ['CRFORGE_FACADE_BUILD']), pathlib.Path(os.environ['CRFORGE_LIB']))" || exit 1
setsid nohup sh -c 'taskset -c '$PC' "$0" "$@"; echo $? > '$OUT/loop.rc $PY -u $L/fastloop.py --producers ${PRODUCERS:-32} \
  --matches ${MATCHES:-16} --threads 1 --devices cuda:0 --server graphs --local-forward --overlap 1 --mps $OUT/mps \
  --build $CRFORGE_FACADE_BUILD --out $OUT -- --run $RUN --config $CB/$P2/pilot2.yaml "$@" > $OUT/loop.log 2>&1 < /dev/null &
SH=$!; sleep 5
MAIN=$(pgrep -P $SH -f fastloop.py | head -1)
[ -n "$MAIN" ] || { echo "no fastloop process under sh $SH"; exit 1; }
echo "sh $SH main $MAIN" > $OUT/pids
setsid nohup $PY -u $L/auto_stop.py $OUT/loop.log $OUT ${AUTO_HOURS:-48} > $OUT/auto_stop.out 2>&1 < /dev/null &
echo "auto_stop $!" >> $OUT/pids
setsid nohup bash -c '
desc() { for c in $(pgrep -P $1); do echo $c; desc $c; done; }
while kill -0 '$MAIN' 2> /dev/null; do
  taskset -a -p -c '$LC' '$MAIN' > /dev/null 2>&1
  n=0; for c in $(desc '$MAIN'); do taskset -a -p -c '$PC' $c > /dev/null 2>&1 && n=$((n + 1)); done
  echo "$(date -u +%T) main -> '$LC', $n descendants -> '$PC'" > '$OUT'/pin.log
  nvidia-smi --query-gpu=utilization.gpu,memory.used --format=csv,noheader >> '$OUT'/gpu.log
  sleep 30
done' > /dev/null 2>&1 < /dev/null &
echo "pinner $!" >> $OUT/pids
echo "started $RUN: $(cat $OUT/pids | tr '\n' ' '); log $OUT/loop.log; checkpoints $CB/icebow/data/bench/rl_royale/$RUN/"
