#!/bin/sh
export PYTHONHASHSEED=0
cd /c/Users/benpe/ClashBot/icebow
../.venv/Scripts/python.exe run.py --config data/bench/aggro1_run.yaml drills --reps 25 --seed 5 \
  --only tank_for_bow,bow_lane_choice,nado_king_activation \
  --policy C:/Users/benpe/ClashBot/scratchpad/gauntlet/L42/aggro1_live_m25.pt \
  > /c/Users/benpe/ClashBot/scratchpad/gauntlet/L42/drills_aggro1_m2500.txt 2>&1
../.venv/Scripts/python.exe run.py --config data/bench/aggro1_run.yaml drills --reps 25 --seed 5 \
  --only tank_for_bow,bow_lane_choice,nado_king_activation \
  --policy C:/Users/benpe/ClashBot/icebow/data/bench/gate05_m5k.pt \
  > /c/Users/benpe/ClashBot/scratchpad/gauntlet/L42/drills_gate05_m5k.txt 2>&1
echo DONE >> /c/Users/benpe/ClashBot/scratchpad/gauntlet/L42/drills_aggro1_m2500.txt
