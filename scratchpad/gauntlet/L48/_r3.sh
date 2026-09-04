#!/bin/sh
export PYTHONHASHSEED=0 PYTHONPATH=/c/Users/benpe/ClashBot/scratchpad/gauntlet/L48 D4_MIN=99 D4_SKEL=1 D4_SKELMIN=3
cd /c/Users/benpe/ClashBot/icebow
O=/c/Users/benpe/ClashBot/scratchpad/gauntlet/L48; P=/c/Users/benpe/ClashBot/.venv/Scripts/python.exe
run() { tag=$1; shift; s0=$1; shift; env "$@" $P $O/doctrine_teacher.py --leg doctrine_$tag --override doctrine_v7 --seed0 $s0 --out $O/doctrine_${tag}_$s0.json 2>&1 | tail -1 > $O/doctrine_${tag}_$s0.txt; }
run d7tank 5000000 D7_TANK=1 & run d7tank 5000048 D7_TANK=1 &
run d7xbow 5000000 D7_XBOW=1 & run d7xbow 5000048 D7_XBOW=1 &
wait
cat $O/doctrine_d7tank_5000000.txt $O/doctrine_d7tank_5000048.txt $O/doctrine_d7xbow_5000000.txt $O/doctrine_d7xbow_5000048.txt
echo R3_DONE
