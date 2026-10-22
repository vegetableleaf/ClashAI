#!/bin/bash
# W19 queue 2 (c13, BASE0): king-after-princess check (W18 lead 1), classifier pass 2 (tower-target artefact removed) on the
# failing fights and on ALL strict fights (control: how often does a passing fight show the same first divergence?).
B=/workspace/w19; C=$B/cb22; P=$C/scratchpad/gauntlet/L74/parity; PY=/workspace/venvf15/bin/python
export PYTHONPATH=$C PARITY_SIM_PATH=$B/rsfork_fin15 OMP_NUM_THREADS=1
exec >> $B/queue2.log 2>&1
echo "$(date -u +%T) king"
$PY $P/w19/king_pocket.py $B/logs $B/res/BASE0/c13/c13_0* > $B/res/KING_c13.txt 2>&1 &
for d in $B/ch/c13_*; do
  ( PARITY_ATTACKS=$d/attacks.json PARITY_BUFFS=$d/buffs.json nice -n 5 $PY $P/w19/cls.py run --base $B/res/BASE0/c13/$(basename $d) \
      --out $B/res/CLS1/$(basename $d) --live $d/live --workers 2 > $B/res/cls1_$(basename $d).log 2>&1
    CLS_ALL=1 PARITY_ATTACKS=$d/attacks.json PARITY_BUFFS=$d/buffs.json nice -n 5 $PY $P/w19/cls.py run --base $B/res/BASE0/c13/$(basename $d) \
      --out $B/res/CLSALL/$(basename $d) --live $d/live --workers 2 > $B/res/clsall_$(basename $d).log 2>&1 ) &
done
wait
cat $B/res/CLS1/*/cls.jsonl > $B/res/CLS1/cls_all.jsonl; cat $B/res/CLSALL/*/cls.jsonl > $B/res/CLSALL/cls_all.jsonl
echo "$(date -u +%T) queue2 end"; touch $B/res/Q2_DONE
