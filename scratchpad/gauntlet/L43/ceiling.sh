#!/bin/sh
export PYTHONHASHSEED=0
cd /c/Users/benpe/ClashBot/icebow
CK=C:/Users/benpe/ClashBot/scratchpad/gauntlet/L43/_rs_gatec2_m10k.pt
O=/c/Users/benpe/ClashBot/scratchpad/gauntlet/L43
../.venv/Scripts/python.exe ../scratchpad/rollout_search.py --ckpt $CK --matches 48 --seed0 5000000 --horizon 0 --tag base --out $O/base.json > $O/base.txt 2>&1 &
../.venv/Scripts/python.exe ../scratchpad/rollout_search.py --ckpt $CK --matches 48 --seed0 5000000 --horizon 12 --interval 1 --topk 4 --cells 3 --tag teacher --out $O/teacher.json > $O/teacher.txt 2>&1 &
wait
echo CEILING_DONE >> $O/teacher.txt
