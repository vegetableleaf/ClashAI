#!/bin/bash
# stop_pod.sh HOST PORT : stop a RunPod pod ONLY if it runs no SIM / RL / parity / build job (owner 10-18: stop released pods
# yourself once their results are verified on the laptop). Refuses (exit 3) when anything is still running -- 10-18 a stop
# went through with 2 jobs alive. Copy-back must be verified by the caller before calling this.
H=$1; P=$2
ssh -n -o BatchMode=yes -o ConnectTimeout=20 -i "$HOME/.ssh/runpod_clashbot" -p "$P" "root@$H" '
n=$(ps -eo args | grep -cE "^[^ ]*(python[^ ]* .*(fights\.py|rl_royale|e1_eval|search_s0|gap\.py|livecal|eval6|maturin)|cargo|rustc|flock)")
if [ "$n" != 0 ]; then echo "REFUSED: $n job processes still running"; ps -eo pid,etimes,args | grep -E "rl_royale|gap\.py|fights\.py|e1_eval|cargo|flock" | grep -v grep | head -5 | cut -c1-140; exit 3; fi
export $(tr "\0" "\n" < /proc/1/environ | grep -E "^RUNPOD_(API_KEY|POD_ID)=")
runpodctl config --apiKey "$RUNPOD_API_KEY" > /dev/null 2>&1
runpodctl stop pod "$RUNPOD_POD_ID"'
