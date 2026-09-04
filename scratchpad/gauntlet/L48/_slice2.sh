#!/bin/sh
export PYTHONHASHSEED=0 PYTHONPATH=/c/Users/benpe/ClashBot/scratchpad/gauntlet/L48
cd /c/Users/benpe/ClashBot/icebow
O=/c/Users/benpe/ClashBot/scratchpad/gauntlet/L48; P=/c/Users/benpe/ClashBot/.venv/Scripts/python.exe
run() { tag=$1; ov=$2; shift; shift; env "$@" $P $O/doctrine_teacher.py --seed0 5000048 --leg doctrine_$tag --override $ov --out $O/doctrine_${tag}_s2.json 2>&1 | tail -1 > $O/doctrine_${tag}_s2.txt; }
run base doctrine_none X=1 &
run d4skel doctrine_v4 D4_MIN=4 D4_SKEL=1 D4_SKELMIN=3 &
run d6body doctrine_v6 D4_MIN=4 D4_SKEL=1 D4_SKELMIN=3 &
wait
cat $O/doctrine_base_s2.txt $O/doctrine_d4skel_s2.txt $O/doctrine_d6body_s2.txt
