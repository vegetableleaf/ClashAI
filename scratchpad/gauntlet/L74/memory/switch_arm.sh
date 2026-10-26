#!/bin/bash
# switch_arm.sh OLD NEW WORKERS -- pod-side: stop arm OLD (chain, drift test, trainer, evals: by process group; bracket patterns
# so this script never matches itself) and start arm_chain.sh NEW (its cfg must exist in /workspace/cb_arm/.../cfg/).
set -uo pipefail
OLD=$1; NEW=$2; W=${3:-50}
O1="[a]rm_chain.sh $OLD"; O2="[d]rift_test.sh $OLD"
for pat in "$O1" "$O2"; do
  for p in $(pgrep -f "$pat"); do g=$(ps -o pgid= -p $p | tr -d ' '); [ -n "$g" ] && kill -TERM -- -$g 2>/dev/null; done
done
TP=$(cat /workspace/exploit/drift/$OLD/train.pid 2>/dev/null)
[ -n "$TP" ] && { g=$(ps -o pgid= -p $TP 2>/dev/null | tr -d ' '); [ -n "$g" ] && kill -TERM -- -$g 2>/dev/null; }
sleep 15
left=$(ps -eo args | grep -c "^/workspace/venvf15/bin/python -m pipeline.rl_royale")
[ "$left" = 0 ] || { echo "$OLD: $left trainer processes still alive"; exit 2; }
[ -f /workspace/cb_arm/scratchpad/gauntlet/L74/stepd/cfg/$NEW.yaml ] || { echo "no cfg $NEW"; exit 3; }
setsid nohup bash /workspace/abl/arm_chain.sh $NEW $W > /workspace/abl/chain_$NEW.out 2>&1 < /dev/null &
sleep 3; head -1 /workspace/abl/res_$NEW.txt
