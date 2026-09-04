#!/bin/sh
export PYTHONHASHSEED=0
cd /c/Users/benpe/ClashBot/icebow
O=/c/Users/benpe/ClashBot/scratchpad/gauntlet/L44
CK=C:/Users/benpe/ClashBot/icebow/data/bench/aggro1_m5k.pt
../.venv/Scripts/python.exe run.py --config data/bench/aggro1_run.yaml drills --reps 25 --seed 5 \
  --only tank_for_bow,bow_lane_choice,nado_king_activation --policy $CK > $O/drills_aggro1_m5k.txt 2>&1
../.venv/Scripts/python.exe run.py --config data/bench/aggro1_run.yaml drills --reps 25 --seed 6 \
  --only tank_for_bow,bow_lane_choice,nado_king_activation --policy $CK > $O/drills_aggro1_m5k_s6.txt 2>&1
../.venv/Scripts/python.exe run.py --config data/bench/aggro1_run.yaml drills --reps 25 --seed 6 \
  --only tank_for_bow,bow_lane_choice,nado_king_activation --policy C:/Users/benpe/ClashBot/icebow/data/bench/gate05_m5k.pt > $O/drills_gate05_m5k_s6.txt 2>&1
for s in 0 1 2; do ../.venv/Scripts/python.exe tools/gate_prior_probe.py $CK --seed $s > $O/ge6_m5k_s$s.txt 2>&1; done
echo PROBES_DONE >> $O/ge6_m5k_s2.txt
