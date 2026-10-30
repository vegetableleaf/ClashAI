#!/bin/bash
# wait_log.sh LOGPATTERN REGEX MAXSEC: poll the pod until REGEX appears in the log(s), then print the tail
S=$(date +%s)
while :; do
  O=$(ssh -o BatchMode=yes -o ConnectTimeout=15 -i ~/.ssh/runpod_clashbot -p 33903 root@157.157.221.29 "grep -lE '$2' $1 2>/dev/null")
  [ -n "$O" ] && { echo "HIT $O"; break; }
  [ $(( $(date +%s) - S )) -gt $3 ] && { echo TIMEOUT; break; }
  sleep 30
done
ssh -o BatchMode=yes -o ConnectTimeout=15 -i ~/.ssh/runpod_clashbot -p 33903 root@157.157.221.29 "tail -3 $1 | cut -c1-400; tail -1 /workspace/grow/out/gpumon.txt"
