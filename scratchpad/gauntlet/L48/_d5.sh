#!/bin/sh
export PYTHONHASHSEED=0 PYTHONPATH=/c/Users/benpe/ClashBot/scratchpad/gauntlet/L48
cd /c/Users/benpe/ClashBot/icebow
O=/c/Users/benpe/ClashBot/scratchpad/gauntlet/L48; P=/c/Users/benpe/ClashBot/.venv/Scripts/python.exe
run() { tag=$1; shift; env "$@" $P $O/doctrine_teacher.py --leg doctrine_$tag --override ${OV:-doctrine_v4} --out $O/doctrine_${tag}_48.json 2>&1 | tail -1 > $O/doctrine_${tag}_48.txt; }
run d5spam D4_MIN=3 D4_SKEL=1 D4_SKELMIN=1 &
run d5spamiw D4_MIN=3 D4_SKEL=1 D4_SKELMIN=1 D4_IW=3 &
run d4skeliw5 D4_MIN=4 D4_SKEL=1 D4_SKELMIN=3 D4_IW=5 &
wait
cat $O/doctrine_d5spam_48.txt $O/doctrine_d5spamiw_48.txt $O/doctrine_d4skeliw5_48.txt
