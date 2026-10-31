#!/bin/bash
# LEARNER-SPEED: arm L update-2 (warmed Adam) per-step KL probe on 31892 (run under locked.sh)
source /workspace/lspeed/env.sh; cd $CB; O=/workspace/lspeed/out
taskset -c $CPUS timeout 2400 "$PY" -u scratchpad/gauntlet/L74/plan1026/pilot/lrn/lspeed/warm_probe.py \
  --config scratchpad/gauntlet/L74/plan1026/pilot/lrn/lspeed/pilot_noG.yaml \
  --res /workspace/lspeed/rec/res_e32g4.pkl /workspace/lspeed/rec/res_e96g4_s2.pkl --lrs 2e-5,3e-5,4e-5 \
  --out $O/warm_probe.json > $O/warm_probe.log 2>&1
echo done > $O/WARM_DONE
