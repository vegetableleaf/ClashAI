#!/bin/bash
# Lead 2026-10-09: wait for the Rocket+Tornado chain (PID $1, default 18537) to finish, then take cpu.lock for the
# mechanic queue. MECH_DONE is touched on ANY exit (the next job in line gates on it).
#   nohup bash /workspace/mech_pod_launch.sh 18537 > /workspace/results/mech_fork/launch.out 2>&1 &
R=/workspace/results/mech_fork; P=${1:-18537}
rm -f $R/MECH_DONE
trap "touch $R/MECH_DONE" EXIT
echo "[$(date +%T)] waiting for PID $P"
while kill -0 $P 2>/dev/null; do sleep 30; done
echo "[$(date +%T)] PID $P gone; flock cpu.lock"
flock /workspace/cpu.lock bash /workspace/mech_pod_queue.sh
echo "[$(date +%T)] queue exit rc=$?"
