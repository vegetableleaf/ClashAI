#!/bin/sh
export PYTHONHASHSEED=0 PYTHONPATH=/c/Users/benpe/ClashBot/scratchpad/gauntlet/L48 D4_MIN=4 D4_SKEL=1 D4_SKELMIN=3
cd /c/Users/benpe/ClashBot/icebow
O=/c/Users/benpe/ClashBot/scratchpad/gauntlet/L48; P=/c/Users/benpe/ClashBot/.venv/Scripts/python.exe
$P $O/doctrine_drills.py none $O/drills_doc_stock.json > $O/drills_doc_stock.txt 2>&1 &
$P $O/doctrine_drills.py doctrine_v6 $O/drills_doc_d6body.json > $O/drills_doc_d6body.txt 2>&1 &
$P $O/doctrine_regret.py 12 doctrine_v6 $O/regret_d6body.json > $O/regret_d6body.txt 2>&1 &
wait
tail -1 $O/drills_doc_stock.txt; tail -2 $O/drills_doc_d6body.txt | head -1; sed -n 14,40p $O/regret_d6body.txt
echo R1_DONE
