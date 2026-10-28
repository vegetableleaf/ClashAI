#!/bin/bash
# guarded.sh ENGINE RUN CPUS [rl_royale args...] -- run.sh in the background (own session) + memwatch.py on its process tree
# (log /workspace/cf3/logs/RUN.mem.tsv every 5 s; SIGKILLs only that run's tree if the shared 125 GB cgroup passes GUARD_GB, default 90).
# Env passes through (TREE=, CF_DUMP=, CRFORGE_XMX=, ...). Returns at once; the run's log is /workspace/cf3/logs/RUN.log.
E=$1; RUN=$2
cd /workspace/cf3 || exit 1
setsid nohup ./run.sh "$@" < /dev/null > /dev/null 2>&1 &
for i in 1 2 3 4 5 6 7 8 9 10; do
  sleep 1
  PID=$(pgrep -n -f "python -u -m pipeline.rl_royale --run $RUN( |\$)")
  [ -n "$PID" ] && break
done
[ -z "$PID" ] && { echo "run $RUN did not start"; exit 1; }
setsid nohup python3 memwatch.py logs/$RUN.mem.tsv $PID 1e9 ${GUARD_GB:-90} ${MEM_EVERY:-5} < /dev/null > /dev/null 2>&1 &
echo "started $RUN root pid $PID"
