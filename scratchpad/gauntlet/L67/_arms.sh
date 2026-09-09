#!/usr/bin/env bash
# L67h search arms: identical seeds, identical view (degraded = what the live student sees), interval 1.
cd /c/Users/benpe/ClashBot
PY=./icebow/.venv/Scripts/python.exe
CK=icebow/data/pipeline/s1_icebow_v6lat_s0.pt
until [ -f scratchpad/gauntlet/L67/student_sim_deg.json ]; do sleep 20; done
for MODE in force_play random search; do
  $PY scratchpad/gauntlet/L67/student_search.py --ckpt $CK --matches 12 --interval 1 --degrade \
      --mode $MODE --out scratchpad/gauntlet/L67/arm_$MODE.json \
      > scratchpad/gauntlet/L67/arm_$MODE.out 2>&1
  echo "done $MODE"
done
