#!/bin/bash
# Overnight 10-16: pull one live-pool eval (both seeds) from a pod, sha-verified, and compare it with F1 u250 (0.1.35 baseline).
#   pull_cmp.sh HOST PORT REMOTE_DIR NAME     e.g. pull_cmp.sh 81.27.69.179 37671 /workspace/results/T1EARLY t1_s74_u150
H=$1; P=$2; RD=$3; N=$4
K="-o BatchMode=yes -o ConnectTimeout=20 -o ServerAliveInterval=30 -i $HOME/.ssh/runpod_clashbot"
D=/c/Users/benpe/pod_backup_weekend/rt35/RT35
ssh -n $K -p $P root@$H "cd $RD && tar czf /tmp/$N.tgz ${N}_741200 ${N}_742000 ${N}_741200.log ${N}_742000.log && sha256sum /tmp/$N.tgz" | awk '{print $1}' > /tmp/$N.rsha || exit 1
scp -q $K -P $P root@$H:/tmp/$N.tgz $D/$N.tgz || exit 1
[ "$(sha256sum $D/$N.tgz | awk '{print $1}')" = "$(cat /tmp/$N.rsha)" ] || { echo "SHA MISMATCH $N"; exit 1; }
tar xzf $D/$N.tgz -C $D && rm $D/$N.tgz && echo "COPY_OK $N"
cd /c/Users/benpe/ClashBot && research/ext/Royale/.venv/Scripts/python.exe scratchpad/gauntlet/L74/mix/live_cmp.py $D --base live_f1u250 $N
