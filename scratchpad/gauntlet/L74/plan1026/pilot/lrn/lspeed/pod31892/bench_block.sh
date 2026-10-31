#!/bin/bash
# LEARNER-SPEED finite 31892 block (run under locked.sh): whole-step identity + speed, then whole updates S / L at 512 matches
source /workspace/lspeed/env.sh; cd $CB
SB="taskset -c $CPUS timeout 2400 $PY -u scratchpad/gauntlet/L74/plan1026/pilot/lrn/lspeed/step_bench.py --config scratchpad/gauntlet/L74/plan1026/pilot/lrn/lspeed/pilot_noG.yaml"
O=/workspace/lspeed/out; R1=/workspace/lspeed/rec/res_e32g4.pkl; R2=/workspace/lspeed/rec/res_e96g4_s2.pkl
$SB --res $R1 --mb 256 --steps 30 --ppo --out $O/step_mb256.json > $O/step_mb256.log 2>&1
$SB --res $R1 --mb 1024 --steps 20 --out $O/step_mb1024.json > $O/step_mb1024.log 2>&1
if [ -f $R2.ok ]; then
  $SB --res $R1 $R2 --mb 256 --no-step --ppo --arms base,both --out $O/upd_S512.json > $O/upd_S512.log 2>&1
  $SB --res $R1 $R2 --mb 1024 --no-step --ppo --ppo-mb 65536 --micro 1024 --ppo-lr 2e-5 --arms base,both --out $O/upd_L512.json > $O/upd_L512.log 2>&1
fi
echo BLOCK_DONE > $O/BLOCK_DONE
