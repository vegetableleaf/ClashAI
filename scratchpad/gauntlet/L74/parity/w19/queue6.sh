#!/bin/bash
# W19 queue 6: the walk-speed census (speeds.py) over every stamped strict fight of BASE0 for each cohort, W workers per chunk.
B=/workspace/w19; C=$B/cb22; P=$C/scratchpad/gauntlet/L74/parity; PY=/workspace/venvf15/bin/python; W=${W:-3}
export PYTHONPATH=$C PARITY_SIM_PATH=$B/rsfork_fin15 OMP_NUM_THREADS=1
exec >> $B/queue6.log 2>&1
for CO in ${COHORTS:-c13 c22}; do
  until [ -n "$(ls $B/res/BASE0/$CO/${CO}_07/DONE 2>/dev/null)" ]; do sleep 20; done
  echo "$(date -u +%T) hits $CO"
  for d in $B/ch/${CO}_*; do
    ( PARITY_ATTACKS=$d/attacks.json PARITY_BUFFS=$d/buffs.json nice -n 5 $PY $P/w19/speeds.py run --base $B/res/BASE0/$CO/$(basename $d) \
        --out $B/res/SPEEDS/$(basename $d) --live $d/live --workers $W > $B/res/speeds_$(basename $d).log 2>&1 ) &
  done
  wait
  cat $B/res/SPEEDS/${CO}_*/speeds.jsonl > $B/res/SPEEDS/speeds_$CO.jsonl; echo "$(date -u +%T) hits $CO done"
done
touch $B/res/Q6_DONE
