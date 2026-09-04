#!/bin/sh
# L46: full drill suite, same instrument for init and c2r_m10k (seed 5, 25 reps, c2r run config)
export PYTHONHASHSEED=0
cd /c/Users/benpe/ClashBot/icebow
O=/c/Users/benpe/ClashBot/scratchpad/gauntlet/L46
for ck in gatec2_m10k c2r_m10k; do
  ../.venv/Scripts/python.exe run.py --config data/bench/c2r_run.yaml drills --reps 25 --seed 5 \
    --policy C:/Users/benpe/ClashBot/icebow/data/bench/$ck.pt > $O/drills_$ck.txt 2>&1
done
echo DRILLS_DONE >> $O/drills_c2r_m10k.txt
