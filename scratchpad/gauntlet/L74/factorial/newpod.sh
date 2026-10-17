#!/bin/bash
# Laptop: turn a FRESH pod (empty /workspace) into a factorial pod, the troops recipe: stream /workspace/in from a set-up
# pod through the laptop (repo_tt.tgz, data_rl.tgz, ckpts.tgz, rsdata.tgz + their .sha lists, the fork36 wheel,
# setup_troops.sh), extract + sha-verify into /workspace/cb_tt, overlay the factorial code (ship.sh), build venvf36
# (troops/setup_troops.sh: constraints + torch cu128 + royalegym + the wheel; activate() under fork36-linux must pass).
#   newpod.sh SRC_HOST SRC_PORT HOST PORT      -> /workspace/troops/SETUP_OK on the new pod (nothing started)
set -euo pipefail
SH=$1; SP=$2; H=$3; P=$4; FD=/c/Users/benpe/ClashBot/scratchpad/gauntlet/L74/factorial
K="-o BatchMode=yes -o ConnectTimeout=20 -o ServerAliveInterval=30 -o StrictHostKeyChecking=no -i $HOME/.ssh/runpod_clashbot"
IN="repo_tt.tgz data_rl.tgz data.sha ckpts.tgz ckpts.sha royalesim-0.1.36-cp310-abi3-manylinux_2_34_x86_64.whl rsdata.tgz rsdata.sha setup_troops.sh"
want=$(ssh -n $K -p $SP root@$SH "cd /workspace/in && sha256sum $IN")
ssh -n $K -p $P root@$H "mkdir -p /workspace/in /workspace/cb_tt /workspace/troops"
ssh -n $K -p $SP root@$SH "tar cf - -C /workspace/in $IN" | ssh $K -p $P root@$H "tar xf - -C /workspace/in --no-same-owner"
echo "$want" | ssh $K -p $P root@$H "cd /workspace/in && sha256sum -c --quiet - && echo IN_OK"
ssh -n $K -p $P root@$H "set -e; cd /workspace/cb_tt; tar xzf ../in/repo_tt.tgz --no-same-owner; \
  tar xzf ../in/data_rl.tgz --no-same-owner && sha256sum -c --quiet ../in/data.sha && echo DATA_OK; \
  tar xzf ../in/ckpts.tgz --no-same-owner && sha256sum -c --quiet ../in/ckpts.sha && echo CKPTS_OK; \
  tar xzf ../in/rsdata.tgz --no-same-owner && sha256sum -c --quiet ../in/rsdata.sha && echo RSDATA_OK"
bash $FD/ship.sh $H $P
ssh -n $K -p $P root@$H "cd /workspace/cb_tt && bash scratchpad/gauntlet/L74/troops/setup_troops.sh; tail -6 /workspace/troops/setup.log; \
  ls /workspace/troops/SETUP_OK"
