#!/bin/sh
export PYTHONHASHSEED=0 PYTHONPATH=/c/Users/benpe/ClashBot/scratchpad/gauntlet/L48
cd /c/Users/benpe/ClashBot/icebow
O=/c/Users/benpe/ClashBot/scratchpad/gauntlet/L48; P=/c/Users/benpe/ClashBot/.venv/Scripts/python.exe
run() { tag=$1; ov=$2; shift; shift; env "$@" $P $O/doctrine_teacher.py --leg doctrine_$tag --override $ov --out $O/doctrine_${tag}_48.json 2>&1 | tail -1 > $O/doctrine_${tag}_48.txt; }
run d6body doctrine_v6 D4_MIN=4 D4_SKEL=1 D4_SKELMIN=3 &
run d6body_spam doctrine_v6 D4_MIN=3 D4_SKEL=1 D4_SKELMIN=1 &
run d4skel_slice2 doctrine_v4 D4_MIN=4 D4_SKEL=1 D4_SKELMIN=3 --seed0 5000048 &
wait
cat $O/doctrine_d6body_48.txt $O/doctrine_d6body_spam_48.txt $O/doctrine_d4skel_slice2_48.txt
