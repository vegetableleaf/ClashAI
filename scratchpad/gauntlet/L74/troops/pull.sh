#!/bin/bash
# Laptop: copy one troops pod's results back, sha-verified, to pod_backup_weekend/pod1017_troops/<ARM>/.
#   pull.sh HOST PORT ARM       (ARM = f36 | f36tt; also copies the checks dir when present)
# Copies /workspace/results/{TT,LIVEEVAL_TT} and the arm's u0065 raw + grafted checkpoints; prints COPY_OK.
H=$1; P=$2; A=$3; R=rlarm_gae_${A}_u250; RLD=icebow/data/bench/rl_royale/$R
K="-o BatchMode=yes -o ConnectTimeout=20 -o ServerAliveInterval=30 -i $HOME/.ssh/runpod_clashbot"
D=/c/Users/benpe/pod_backup_weekend/pod1017_troops/$A; mkdir -p $D
ssh -n $K -p $P root@$H "cd /workspace && tar czf /tmp/tt_$A.tgz results/TT results/LIVEEVAL_TT \
  \$(ls cb_tt/$RLD/${R}_u0065*.pt 2>/dev/null) && sha256sum /tmp/tt_$A.tgz" | awk '{print $1}' > /tmp/tt_$A.rsha || exit 1
scp -q $K -P $P root@$H:/tmp/tt_$A.tgz $D/ || exit 1
[ "$(sha256sum $D/tt_$A.tgz | awk '{print $1}')" = "$(cat /tmp/tt_$A.rsha)" ] || { echo "SHA MISMATCH tt_$A.tgz"; exit 1; }
tar xzf $D/tt_$A.tgz -C $D && rm $D/tt_$A.tgz
# the checkpoints' own shas (recorded on the pod by run_pod.sh) must match the copies
if [ -f $D/results/TT/final.sha ]; then
  (cd $D && sed "s|  icebow/data/bench/rl_royale/$R/|  cb_tt/$RLD/|" results/TT/final.sha | sha256sum -c --quiet) || { echo "CKPT SHA MISMATCH"; exit 1; }
fi
echo "COPY_OK $A -> $D"
