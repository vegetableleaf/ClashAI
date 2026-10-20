#!/bin/bash
# W10 laptop side: ship EXACTLY commit C's rocket_tower files (HEAD + the W10 patch; never the shared working copy, which
# carries other workers' uncommitted edits) to a pod.   bash ship.sh <commit> <pod-port> <pod-host>
#   e.g. bash ship.sh <W10 commit> 14009 64.247.206.76
set -euo pipefail
C=$1; PORT=$2; HOST=$3; R=$(git rev-parse --show-toplevel); S=$(mktemp -d)
for p in pipeline/reward_terms.py pipeline/rl_royale.py pipeline/e1_eval.py pipeline/tests/test_rocket_tower_1020.py \
         scratchpad/gauntlet/L74/stepd/cfg/stepd_l16_rocket_s74.yaml scratchpad/gauntlet/L74/rocket/pod/w10_smoke.sh; do
  git -C "$R" show "$C:$p" > "$S/$(basename $p)"
done
(cd "$S" && sha256sum * | sed 's/ \*/  /' > SHA256)        # Git-Bash star trap: normalise to "hash  name"
echo "$C" > "$S/COMMIT"
ssh -i ~/.ssh/runpod_clashbot -p "$PORT" "root@$HOST" 'mkdir -p /workspace/w10/ship'
scp -i ~/.ssh/runpod_clashbot -P "$PORT" "$S"/* "root@$HOST:/workspace/w10/ship/"
echo "shipped $C -> $HOST:$PORT /workspace/w10/ship; on the pod: setsid nohup bash /workspace/w10/ship/w10_smoke.sh > /dev/null 2>&1 < /dev/null &"
