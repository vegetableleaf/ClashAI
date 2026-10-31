#!/bin/bash
# LEARNER-SPEED: arm L lr probe on 512 B0 matches (T_gate 0.1, fresh Adam = the A/B's first policy update): where does one
# update's KL land vs the 0.02 cap? (lr 2e-5 measured: 6 steps, no stop)
source /workspace/lspeed/env.sh; cd $CB; O=/workspace/lspeed/out
SBP=scratchpad/gauntlet/L74/plan1026/pilot/lrn/lspeed/step_bench.py
CFG=scratchpad/gauntlet/L74/plan1026/pilot/lrn/lspeed/pilot_noG.yaml
for lr in 2e-5 3e-5 4e-5 5.5e-5; do
  taskset -c $CPUS timeout 1200 "$PY" -u $SBP --config $CFG --res /workspace/lspeed/rec/res_e32g4.pkl /workspace/lspeed/rec/res_e96g4_s2.pkl \
    --mb 1024 --no-step --ppo --ppo-mb 65536 --micro 1024 --ppo-lr $lr --arms both --out $O/upd_L512_lr$lr.json > $O/upd_L512_lr$lr.log 2>&1
done
echo done > $O/LRL_DONE
