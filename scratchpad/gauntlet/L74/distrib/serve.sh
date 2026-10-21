#!/usr/bin/env bash
# W16: start the remote actor server ON a pod (run there, from anywhere): loopback port 5601, WORKERS actors (default 24).
#   ssh ... 'bash /workspace/cb_w16/scratchpad/gauntlet/L74/distrib/serve.sh'      -> /workspace/w16/server.log
set -euo pipefail
cd /workspace/cb_w16
export PYTHONPATH=/workspace/cb_w16 ROYALE_RUNTIME=${ROYALE_RUNTIME:-fin13-linux} ROYALE_HEROIW_FORM=hero \
       OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1
unset ROYALE_HEROIW_PRESS
PY=${PY:-/workspace/venvf13/bin/python}
[ -n "${RL_DETERMINISTIC:-}" ] && export CUBLAS_WORKSPACE_CONFIG=:4096:8
ulimit -n 65536                                  # ~9 fds per actor: 100+ actors pass the 1024 default
mkdir -p /workspace/w16
if [ -s /workspace/w16/server.pid ] && kill -0 "$(cat /workspace/w16/server.pid)" 2>/dev/null; then
  echo "server already running pid $(cat /workspace/w16/server.pid)"; exit 0; fi
L=(); [ -n "${LOCK:-}" ] && L=(flock /workspace/cpu.lock)
setsid nohup "${L[@]}" $PY -m pipeline.remote_actors --port ${SERVE_PORT:-5601} --workers ${WORKERS:-24} \
  >> /workspace/w16/server.log 2>&1 < /dev/null &
echo $! > /workspace/w16/server.pid; echo "server pid $!"
