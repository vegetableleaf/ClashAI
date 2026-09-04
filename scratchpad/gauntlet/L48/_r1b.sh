#!/bin/sh
export PYTHONHASHSEED=0 PYTHONPATH=/c/Users/benpe/ClashBot/scratchpad/gauntlet/L48 ONLY=wall_breakers
cd /c/Users/benpe/ClashBot/icebow
O=/c/Users/benpe/ClashBot/scratchpad/gauntlet/L48; P=/c/Users/benpe/ClashBot/.venv/Scripts/python.exe
$P $O/doctrine_drills.py doctrine_v2 $O/_wb_v2.json 2>&1 | grep wall &
D4_MIN=4 D4_SKEL=0 $P $O/doctrine_drills.py doctrine_v4 $O/_wb_v4.json 2>&1 | grep wall &
D4_MIN=4 D4_SKEL=1 D4_SKELMIN=3 $P $O/doctrine_drills.py doctrine_v4 $O/_wb_v4skel.json 2>&1 | grep wall &
D4_MIN=99 D4_SKEL=0 $P $O/doctrine_drills.py doctrine_v6 $O/_wb_v6only.json 2>&1 | grep wall &
wait; echo R1B_DONE
