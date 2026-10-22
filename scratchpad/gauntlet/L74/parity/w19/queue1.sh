#!/bin/bash
# W19 queue 1: after BASE0 (K=0, c13): the first-divergence classifier on its failing fights, then BASE8 (K=8, c13) = the
# FIN15C reproduction (the round table's "before").
B=/workspace/w19; C=$B/cb22; P=$C/scratchpad/gauntlet/L74/parity; PY=/workspace/venvf15/bin/python
exec >> $B/queue1.log 2>&1
until [ -e $B/res/BASE0/DONE ]; do sleep 20; done
echo "$(date -u +%T) cls start"
for d in $B/ch/c13_*; do
  PYTHONPATH=$C PARITY_SIM_PATH=$B/rsfork_fin15 PARITY_ATTACKS=$d/attacks.json PARITY_BUFFS=$d/buffs.json OMP_NUM_THREADS=1 \
    nice -n 5 $PY $P/w19/cls.py run --base $B/res/BASE0/c13/$(basename $d) --out $B/res/CLS0/$(basename $d) --live $d/live --workers 6 \
    > $B/res/cls_$(basename $d).log 2>&1 &
done
wait
echo "$(date -u +%T) cls end"; touch $B/res/CLS0_DONE
SIM=$B/rsfork_fin15 OUT=$B/res/BASE8 COHORTS=c13 W=6 K=8 bash $P/w19/base_run.sh
echo "$(date -u +%T) BASE8 c13 end"
