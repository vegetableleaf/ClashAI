#!/bin/sh
export PYTHONHASHSEED=0 PYTHONPATH=/c/Users/benpe/ClashBot/scratchpad/gauntlet/L48
cd /c/Users/benpe/ClashBot/icebow
O=/c/Users/benpe/ClashBot/scratchpad/gauntlet/L48; P=/c/Users/benpe/ClashBot/.venv/Scripts/python.exe; CK=/c/Users/benpe/ClashBot/scratchpad/gauntlet/L47/_rs_c2rbest.pt
$P $O/doctrine_teacher.py --seed0 5000048 --leg policy --ckpt $CK --out $O/policy_s2.json 2>&1 | tail -1 > $O/policy_s2.txt &
$P /c/Users/benpe/ClashBot/scratchpad/rollout_search.py --ckpt $CK --matches 48 --seed0 5000048 --horizon 12 --interval 1 --topk 4 --cells 3 --tag teacher_s2 --out $O/teacher_s2.json > $O/teacher_s2.txt 2>&1 &
wait
tail -1 $O/policy_s2.txt; tail -1 $O/teacher_s2.txt
echo SLICE2B_DONE
