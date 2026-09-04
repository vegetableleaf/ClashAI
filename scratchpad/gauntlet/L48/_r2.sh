#!/bin/sh
export PYTHONHASHSEED=0 PYTHONPATH=/c/Users/benpe/ClashBot/scratchpad/gauntlet/L48 D4_MIN=99 D4_SKEL=1 D4_SKELMIN=3
cd /c/Users/benpe/ClashBot/icebow
O=/c/Users/benpe/ClashBot/scratchpad/gauntlet/L48; P=/c/Users/benpe/ClashBot/.venv/Scripts/python.exe
$P $O/doctrine_teacher.py --leg doctrine_d6nok --override doctrine_v6 --seed0 5000000 --out $O/doctrine_d6nok_48.json 2>&1 | tail -1 > $O/doctrine_d6nok_48.txt &
$P $O/doctrine_teacher.py --leg doctrine_d6nok --override doctrine_v6 --seed0 5000048 --out $O/doctrine_d6nok_s2.json 2>&1 | tail -1 > $O/doctrine_d6nok_s2.txt &
ONLY= $P $O/doctrine_drills.py doctrine_v6 $O/drills_doc_d6nok.json > $O/drills_doc_d6nok.txt 2>&1 &
wait
cat $O/doctrine_d6nok_48.txt $O/doctrine_d6nok_s2.txt; tail -2 $O/drills_doc_d6nok.txt | head -1
echo R2_DONE
