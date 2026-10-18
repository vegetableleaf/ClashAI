#!/bin/bash
# Laptop: make a pod with NO RL stack (e.g. the parity pod P3) a combo pod, the troops recipe without the factorial overlay:
# stream /workspace/in from a set-up pod through the laptop (repo_tt.tgz, data_rl.tgz, ckpts.tgz, rsdata.tgz + .sha lists, the
# fork36 wheel, setup_troops.sh), extract + sha-verify into /workspace/cb_tt, then START troops/setup_troops.sh in the
# background (builds /workspace/venvf36: uv + torch cu128 + royalegym + the wheel; one process, network-bound).
#   newpod.sh SRC_HOST SRC_PORT HOST PORT     -> poll HOST for /workspace/troops/SETUP_OK, then combo/ship.sh HOST PORT
set -euo pipefail
SH=$1; SP=$2; H=$3; P=$4
K="-o BatchMode=yes -o ConnectTimeout=20 -o ServerAliveInterval=30 -o StrictHostKeyChecking=no -i $HOME/.ssh/runpod_clashbot"
IN="repo_tt.tgz data_rl.tgz data.sha ckpts.tgz ckpts.sha royalesim-0.1.36-cp310-abi3-manylinux_2_34_x86_64.whl rsdata.tgz rsdata.sha setup_troops.sh"
want=$(ssh -n $K -p $SP root@$SH "cd /workspace/in && sha256sum $IN")
ssh -n $K -p $P root@$H "mkdir -p /workspace/in /workspace/cb_tt /workspace/troops"
ssh -n $K -p $SP root@$SH "tar cf - -C /workspace/in $IN" | ssh $K -p $P root@$H "tar xf - -C /workspace/in --no-same-owner"
echo "$want" | ssh $K -p $P root@$H "cd /workspace/in && sha256sum -c --quiet - && echo IN_OK"
ssh -n $K -p $P root@$H "set -e; cd /workspace/cb_tt; tar xzf ../in/repo_tt.tgz --no-same-owner; \
  tar xzf ../in/data_rl.tgz --no-same-owner && sha256sum -c --quiet ../in/data.sha && echo DATA_OK; \
  tar xzf ../in/ckpts.tgz --no-same-owner && sha256sum -c --quiet ../in/ckpts.sha && echo CKPTS_OK; \
  tar xzf ../in/rsdata.tgz --no-same-owner && sha256sum -c --quiet ../in/rsdata.sha && echo RSDATA_OK; \
  setsid nohup bash scratchpad/gauntlet/L74/troops/setup_troops.sh > /dev/null 2>&1 < /dev/null & echo SETUP_STARTED"
