#!/bin/bash
# A1b: cls_down.py on the c22 down fights, both arms (A15 fin15 / A16 fin16), one process per chunk.
#   bash cls_down.sh > /workspace/f16/res/cls_down.log 2>&1   -> res/CLS_{A15,A16}/c22_0k/cls.jsonl
B=/workspace/f16; C=$B/cb; PY=/workspace/venvf15/bin/python; P=$C/scratchpad/gauntlet/L74/parity
mkdir -p $C/scratchpad/gauntlet/L68; [ -e $C/scratchpad/gauntlet/L68/live_reader ] || ln -s $B/logs $C/scratchpad/gauntlet/L68/live_reader
for arm in A15 A16; do
  [ $arm = A16 ] && { SIM=$B/rsfork_fin16; T=1; } || { SIM=$B/rsfork_fin15; T=0; }
  for d in $B/ch/c22_*; do
    k=$(basename $d); o=$B/res/CLS_$arm/$k; mkdir -p $o
    ( cd $o && PYTHONPATH=$C PARITY_SIM_PATH=$SIM PARITY_TABLE_1019=$T PARITY_ATTACKS=$d/attacks.json PARITY_BUFFS=$d/buffs.json \
        CLS_ALL=1 OMP_NUM_THREADS=1 PYTHONHASHSEED=0 nice -n 5 $PY $P/fin16/cls_down.py $B/res/moved_c22.json down run \
        --base $B/res/$arm/c22/$k --out $o --live $d/live --workers 1 > $o/run.log 2>&1 ) &
  done
done
wait; echo CLS_DOWN_DONE
