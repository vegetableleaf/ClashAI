#!/bin/bash
# pairs.sh TAG TREE FACADE_BUILD NPAIRS [rl_royale k=v ...] -- D2-T2 item 4 (pod 33308): NPAIRS paired runs crforge vs fin16
# (royalesim), succ48_x_s101 at 24 actors, max_updates 4 (3 timed intervals u0001-u0003), both runs of a pair at once on
# disjoint CPU sets + GPUs, sets swapped every pair (D2-T: the CPU set moves totals 10-20%). Per run: the log, a 20 s CPU
# sample of the main python + its live children (cpusample.sh), then cpu_per_update.py on the run dir.
TAG=$1; T=$2; FB=$3; NP=$4; shift 4
S0=0-25; S1=32-57
D=/workspace/d2t2/$TAG; mkdir -p $D
for p in $(seq 1 $NP); do
  if [ $((p % 2)) = 1 ]; then CF=$S0; RS=$S1; GCF=0; GRS=1; else CF=$S1; RS=$S0; GCF=1; GRS=0; fi
  for e in cf rs; do
    if [ $e = cf ]; then ENG=crforge; C=$CF; G=$GCF; else ENG=royalesim; C=$RS; G=$GRS; fi
    RUN=${TAG}_p${p}_$e
    echo "$(date +%s) start $RUN cpus $C cuda:$G" >> $D/chain.log
    FACADE_BUILD=$FB setsid bash /workspace/d2t/run3t.sh $T $ENG $RUN $C 0 --config scratchpad/gauntlet/L74/stepd/cfg/succ48_x_s101.yaml \
      n_actors=24 max_updates=4 learner_device=cuda:$G "$@" &
  done
  sleep 20
  for e in cf rs; do
    RUN=${TAG}_p${p}_$e
    PY=$(pgrep -f -- "--run $RUN " | while read q; do [ "$(cat /proc/$q/comm)" = python ] && echo $q; done | head -1)
    echo "$(date +%s) $RUN python pid $PY" >> $D/chain.log
    setsid bash /workspace/d2/cpusample.sh $PY $D/cpu_$RUN.txt &
  done
  wait
  for e in cf rs; do
    RUN=${TAG}_p${p}_$e
    cp /workspace/d2t/logs/$RUN.log $D/
    /workspace/venvf16/bin/python /workspace/d2/cpu_per_update.py $D/cpu_$RUN.txt $T/scratchpad/gauntlet/L68/rl/$RUN > $D/upd_$RUN.txt 2>&1
    echo "$(date +%s) done $RUN $(grep -c Traceback $D/$RUN.log) tracebacks; $(tr '\n' ';' < $D/upd_$RUN.txt)" >> $D/chain.log
  done
done
echo "$(date +%s) CHAIN DONE" >> $D/chain.log
