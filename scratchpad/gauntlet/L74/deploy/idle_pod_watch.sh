#!/bin/bash
# idle_pod_watch.sh SEEN : every 15 min, check every pod for SIM / RL / parity python processes; exit (printing it) once a pod
# has had none on 2 checks in a row and is not listed in SEEN ("host:port" lines already handled), so the lead wakes only to
# reassign a freed pod (owner 10-17: stop a pod only when no pod work is left; idle hours are waste).
SEEN=$1; touch "$SEEN"
K="-o BatchMode=yes -o ConnectTimeout=20 -i $HOME/.ssh/runpod_clashbot"
PODS="81.27.69.177:23363 64.247.206.79:19400 216.81.245.71:34210 216.81.245.71:29286 216.81.151.5:15617 64.247.206.76:14009 216.81.245.71:38758 64.247.206.76:19899"
declare -A idle
while :; do
  for hp in $PODS; do
    grep -qxF "$hp" "$SEEN" && continue
    H=${hp%:*}; P=${hp#*:}
    n=$(timeout 60 ssh -n $K -p $P root@$H 'ps -eo args | grep -cE "^[^ ]*(python[^ ]* .*(fights\.py|rl_royale|e1_eval|search_s0|gap\.py|livecal|eval6|maturin)|cargo|rustc)"' 2>/dev/null)
    [ -z "$n" ] && continue              # unreachable this round: not counted as idle
    if [ "$n" = 0 ]; then idle[$hp]=$(( ${idle[$hp]:-0} + 1 )); else idle[$hp]=0; fi
    if [ "${idle[$hp]}" -ge 2 ]; then echo "IDLE $hp $(date '+%F %T')"; exit 0; fi
  done
  sleep 900
done
