#!/bin/bash
# LEARNER-SPEED: mb 256 step timing on a quiet pod, both arm orders (the block's first run overlapped the tail of another
# bench's CPU load: cgroup throttling); cpu.stat before / after each run
source /workspace/lspeed/env.sh; cd $CB; O=/workspace/lspeed/out
SBP=scratchpad/gauntlet/L74/plan1026/pilot/lrn/lspeed/step_bench.py
CFG=scratchpad/gauntlet/L74/plan1026/pilot/lrn/lspeed/pilot_noG.yaml
for o in "base,attn,graph,both" "both,graph,attn,base"; do
  t=$(echo $o | tr , _)
  { uptime; grep throttled /sys/fs/cgroup/cpu.stat; } > $O/q256_$t.cpu
  taskset -c $CPUS timeout 1200 "$PY" -u $SBP --config $CFG --res /workspace/lspeed/rec/res_e32g4.pkl --steps 60 \
    --mb 256 --arms $o --out $O/q256_$t.json > $O/q256_$t.log 2>&1
  { uptime; grep throttled /sys/fs/cgroup/cpu.stat; } >> $O/q256_$t.cpu
done
echo done > $O/Q256_DONE
