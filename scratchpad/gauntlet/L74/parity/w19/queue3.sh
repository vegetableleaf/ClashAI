#!/bin/bash
# W19 queue 3: classifier pass 3 (hp tolerance 5, spawn-timing kinds) on BASE0 COHORT: failing fights, then ALL strict fights
# (control). COHORT=c13|c22 W=workers per chunk.
B=/workspace/w19; C=$B/cb22; P=$C/scratchpad/gauntlet/L74/parity; PY=/workspace/venvf15/bin/python; CO=${COHORT:-c13}; W=${W:-3}
export PYTHONPATH=$C PARITY_SIM_PATH=$B/rsfork_fin15 OMP_NUM_THREADS=1
exec >> $B/queue3_$CO.log 2>&1
echo "$(date -u +%T) start $CO"
for d in $B/ch/${CO}_*; do
  ( PARITY_ATTACKS=$d/attacks.json PARITY_BUFFS=$d/buffs.json nice -n 5 $PY $P/w19/cls.py run --base $B/res/BASE0/$CO/$(basename $d) \
      --out $B/res/CLS3/$(basename $d) --live $d/live --workers $W > $B/res/cls3_$(basename $d).log 2>&1 ) &
done
wait
cat $B/res/CLS3/${CO}_*/cls.jsonl > $B/res/CLS3/cls_$CO.jsonl; echo "$(date -u +%T) failing done"
for d in $B/ch/${CO}_*; do
  ( CLS_ALL=1 PARITY_ATTACKS=$d/attacks.json PARITY_BUFFS=$d/buffs.json nice -n 5 $PY $P/w19/cls.py run --base $B/res/BASE0/$CO/$(basename $d) \
      --out $B/res/CLS3ALL/$(basename $d) --live $d/live --workers $W > $B/res/cls3all_$(basename $d).log 2>&1 ) &
done
wait
cat $B/res/CLS3ALL/${CO}_*/cls.jsonl > $B/res/CLS3ALL/cls_$CO.jsonl; echo "$(date -u +%T) all done"; touch $B/res/Q3_${CO}_DONE
