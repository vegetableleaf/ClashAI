#!/usr/bin/env bash
# W16: from the LEARNER pod, open an SSH tunnel to a REMOTE pod's actor server (loopback 5601 there) on the learner's
# loopback LOCAL_PORT. Uses a per-learner key generated on the learner pod (no laptop key is copied to a pod); the
# laptop authorises it on the remote once. Run on the laptop:
#   bash scratchpad/gauntlet/L74/distrib/tunnel.sh LEARNER_PORT REMOTE_PORT LOCAL_PORT     (e.g. 13396 14009 5611)
set -euo pipefail
LP=$1; RP=$2; LOCAL=$3; HOST=${HOST:-root@64.247.206.76}; RHOST=${RHOST:-$HOST}
K="-i $HOME/.ssh/runpod_clashbot -o StrictHostKeyChecking=no"
ssh $K -p $LP $HOST '[ -f ~/.ssh/w16_tunnel ] || ssh-keygen -q -t ed25519 -N "" -f ~/.ssh/w16_tunnel -C w16-learner'
PUB=$(ssh $K -p $LP $HOST 'cat ~/.ssh/w16_tunnel.pub')
ssh $K -p $RP $RHOST "mkdir -p ~/.ssh && touch ~/.ssh/authorized_keys && grep -qF '$PUB' ~/.ssh/authorized_keys || echo '$PUB' >> ~/.ssh/authorized_keys"
ssh $K -p $LP $HOST "setsid nohup ssh -N -i ~/.ssh/w16_tunnel -o StrictHostKeyChecking=no -o ExitOnForwardFailure=yes \
  -o ServerAliveInterval=30 -o ServerAliveCountMax=3 -p $RP -L 127.0.0.1:$LOCAL:127.0.0.1:${SERVE_PORT:-5601} ${RHOST} \
  > /workspace/w16/tunnel_$RP.log 2>&1 < /dev/null & echo \$! > /workspace/w16/tunnel_$RP.pid; sleep 3; \
  kill -0 \$(cat /workspace/w16/tunnel_$RP.pid) && echo TUNNEL_UP 127.0.0.1:$LOCAL '->' $RP"
