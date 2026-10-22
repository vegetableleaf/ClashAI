#!/bin/bash
# restart_long.sh SAVE_UPDATE -- 10-22 (lead, laptop): restart the long run with remote actors right after its
# u<SAVE_UPDATE> checkpoint is written (save_every 25, so nothing is lost), by exact PIDs, then resume with
# remote_actors=icebow/data/w16_ep.txt (outside config_sha). Run attach_remote.sh first.
set -euo pipefail
U=$(printf %04d $1); H=157.157.221.29; P=32525; R=rlarm_tn_long_e1i_s74
K="-n -o StrictHostKeyChecking=no -i $HOME/.ssh/runpod_clashbot"
D=/workspace/cb_stepd/icebow/data/bench/rl_royale/$R
until ssh $K -p $P root@$H "[ -f $D/${R}_u$U.pt ] && [ \$(( \$(date +%s) - \$(stat -c %Y $D/${R}_u$U.pt) )) -gt 20 ]"; do sleep 30; done
# kill the trainer + ONLY its own children (actors / resource tracker), never the checkpoint eval's gap.py workers
ssh $K -p $P root@$H "PIDS=\$(pgrep -f '[r]l_royale.*$R' | tr '\n' ' '); KIDS=\$(for p in \$PIDS; do pgrep -P \$p; done | tr '\n' ' ');
  echo killing \$PIDS children \$KIDS; kill \$PIDS \$KIDS 2>/dev/null; sleep 10; kill \$KIDS 2>/dev/null;
  pgrep -f '[r]l_royale.*$R' && echo STILL_RUNNING || echo STOPPED"
ssh $K -p $P root@$H "sed -i 's#--run \$R \$RES#--run \$R \$RES remote_actors=icebow/data/w16_ep.txt#' /workspace/long_train.sh; grep -c remote_actors /workspace/long_train.sh; bash /workspace/long_train.sh tn_long_e1i_s74"
