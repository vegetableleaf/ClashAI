#!/bin/bash
# On-pod self-stop (10-16 lesson: a laptop reboot left 4 finished pods idle 4-8 h). Waits for DONE_FILE, then GRACE seconds
# (time for the laptop to copy results back), then stops this pod unless /workspace/KEEP exists or a SIM/RL job still runs.
#   setsid nohup bash pod_watchdog.sh DONE_FILE [GRACE=7200] > /workspace/watchdog.log 2>&1 &
D=$1; G=${2:-7200}
echo "$(date -u +%T) watching $D, grace $G s"
until [ -e "$D" ]; do sleep 60; done
echo "$(date -u +%T) $D exists; grace"; sleep "$G"
busy=$(( $(ps -eo args | grep -c "[p]ython.*\(rl_royale\|gap.py\|search_s0\|livecal\)") ))
if [ -e /workspace/KEEP ] || [ "$busy" != 0 ]; then echo "$(date -u +%T) not stopping (KEEP or $busy busy)"; exit 0; fi
echo "$(date -u +%T) stopping pod"
export $(tr "\0" "\n" < /proc/1/environ | grep -E "^RUNPOD_(API_KEY|POD_ID)=")
runpodctl config --apiKey "$RUNPOD_API_KEY" > /dev/null 2>&1; runpodctl stop pod "$RUNPOD_POD_ID"
