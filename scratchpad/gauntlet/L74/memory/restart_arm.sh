#!/bin/bash
# restart_arm.sh ARM LEAK_W WORKERS [TREE] [CHAIN] -- pod-side, 10-25 night: stop ARM's chain / drift test / trainer / evals by
# their own process groups, wipe its run + drift + eval dirs, set habit_leak_w LEAK_W in its cfg, relaunch.
#   CHAIN 1 (default) = arm_chain.sh (train -> gate -> ablation); 0 = plain drift_test.sh (the no-memory control).
# Why (measured): the no-memory control on CLXIII's recipe flagged the leak at u25 (time at full 13.5 -> 25.8 s, first play
# 12.7 -> 22.4 s), as x_s101 / x_s102 did; at leak .03 the memory arms (same recipe) would be tripped at u50.
set -uo pipefail
ARM=$1; W=$2; WK=$3; T=${4:-cb_arm}; CH=${5:-1}
CB=/workspace/$T; C=$CB/scratchpad/gauntlet/L74/stepd/cfg/$ARM.yaml
for pat in "[a]rm_chain.sh $ARM" "[d]rift_test.sh $ARM"; do
  for p in $(pgrep -f "$pat"); do g=$(ps -o pgid= -p $p | tr -d ' '); [ -n "$g" ] && kill -TERM -- -$g 2>/dev/null; done
done
TP=$(cat /workspace/exploit/drift/$ARM/train.pid 2>/dev/null)
[ -n "$TP" ] && { g=$(ps -o pgid= -p $TP 2>/dev/null | tr -d ' '); [ -n "$g" ] && kill -TERM -- -$g 2>/dev/null; }
sleep 15
for p in $(pgrep -f "[r]l_royale.*cfg/$ARM[.]yaml") $(pgrep -f "[g]ap.py.*ev/${ARM}_u"); do kill -KILL $p 2>/dev/null; done
sleep 3
left=$(pgrep -fc "[r]l_royale.*cfg/$ARM[.]yaml"); [ "$left" = 0 ] || { echo "$ARM: $left trainer processes still alive"; exit 2; }
rm -rf /workspace/exploit/drift/$ARM /workspace/stepd/rl_$ARM $CB/scratchpad/gauntlet/L68/rl/rlarm_$ARM \
  $CB/icebow/data/bench/rl_royale/rlarm_$ARM /workspace/exploit/ev/${ARM}_u* /workspace/exploit/ckpt/rlarm_${ARM}_u* /workspace/abl/res_$ARM.txt
sed -i "s/^habit_leak_w: .*/habit_leak_w: $W/" $C
sed -i "1i # 10-25 night restart: habit_leak_w $W (the .03 recipe re-learned the leak by u25 in the no-memory control)" $C
grep -E "^habit_leak_w" $C
if [ "$CH" = 1 ]; then
  setsid nohup bash /workspace/abl/arm_chain.sh $ARM $WK > /workspace/abl/chain_$ARM.out 2>&1 < /dev/null &
else
  CB=$CB setsid nohup bash /workspace/exploit/drift_test.sh $ARM 100 > /workspace/exploit/drift_$ARM.out 2>&1 < /dev/null &
fi
sleep 5; echo "$ARM relaunched (leak $W)"
