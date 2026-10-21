#!/usr/bin/env bash
# W16: ship this worktree's COMMITTED pipeline/ + distrib/ to a pod as /workspace/cb_w16 (a hard-link copy of
# /workspace/cb_stepd with its own pipeline/ -- cb_stepd is never written) + the shared token (gitignored, never printed).
#   bash scratchpad/gauntlet/L74/distrib/ship.sh 13396 [REF]      (host 64.247.206.76; HOST=... to override)
set -euo pipefail
PORT=$1; REF=${2:-HEAD}; HOST=${HOST:-root@64.247.206.76}
SSH="ssh -i $HOME/.ssh/runpod_clashbot -o StrictHostKeyChecking=no -p $PORT $HOST"
ROOT=$(git rev-parse --show-toplevel); TOK=$ROOT/icebow/data/remote_actors.token
[ -s "$TOK" ] || { echo "no token at $TOK"; exit 2; }
$SSH 'set -e; [ -d /workspace/cb_w16 ] || cp -al /workspace/cb_stepd /workspace/cb_w16
      rm -rf /workspace/cb_w16/pipeline /workspace/cb_w16/scratchpad/gauntlet/L74/distrib; mkdir -p /workspace/w16'
git -C "$ROOT" archive "$REF" pipeline scratchpad/gauntlet/L74/distrib | $SSH 'tar x -C /workspace/cb_w16'
$SSH 'umask 077; cat > /workspace/cb_w16/icebow/data/remote_actors.token.tmp && mv /workspace/cb_w16/icebow/data/remote_actors.token.tmp /workspace/cb_w16/icebow/data/remote_actors.token' < "$TOK"
$SSH 'cd /workspace/cb_w16 && find pipeline -name "*.py" -not -path "*/tests/*" | sort | xargs sha256sum | sha256sum | cut -c1-16'
echo "SHIPPED $(git -C "$ROOT" rev-parse --short "$REF") -> $PORT"
