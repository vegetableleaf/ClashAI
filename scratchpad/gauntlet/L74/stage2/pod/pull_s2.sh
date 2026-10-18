#!/bin/bash
# Laptop relay: copy finished Stage-2 jobs back, sha-verified, to pod_backup_weekend/stage2/<JOB>/ and mark the pod copy
# (runs/<JOB>/COPIED). Never stops a pod.   bash pull_s2.sh HOST PORT [HOST PORT ...]   (safe to repeat)
LOC=/c/Users/benpe/pod_backup_weekend/stage2; mkdir -p $LOC
K="-o BatchMode=yes -o ConnectTimeout=20 -o ServerAliveInterval=30 -o StrictHostKeyChecking=no -i $HOME/.ssh/runpod_clashbot"
while [ $# -ge 2 ]; do
  H=$1; P=$2; shift 2
  for j in $(ssh -n $K -p $P root@$H 'cd /workspace/s2/out 2>/dev/null && ls *.tgz.sha 2>/dev/null' | sed 's/\.tgz\.sha$//'); do
    [ -e $LOC/$j/COPY_OK ] && cmp -s $LOC/$j.tgz.sha <(ssh -n $K -p $P root@$H "cat /workspace/s2/out/$j.tgz.sha") && continue
    scp -q $K -P $P root@$H:/workspace/s2/out/$j.tgz root@$H:/workspace/s2/out/$j.tgz.sha $LOC/ || { echo "scp $j failed"; continue; }
    want=$(awk '{print $1}' $LOC/$j.tgz.sha); got=$(sha256sum $LOC/$j.tgz | awk '{print $1}')   # Git-Bash prints "hash *path"
    [ "$want" = "$got" ] || { echo "SHA MISMATCH $j"; continue; }
    rm -rf $LOC/$j; tar xzf $LOC/$j.tgz -C $LOC && touch $LOC/$j/COPY_OK && ssh -n $K -p $P root@$H "touch /workspace/s2/runs/$j/COPIED" \
      && echo "copied $j ($H:$P)"
    if [ -f $LOC/$j/ckpts.sha ]; then    # a train job: also the gate checkpoints (u0025 / u0045 / u0065 / u0130), sha-checked
      mkdir -p $LOC/$j/ckpts
      for f in $(awk '{print $2}' $LOC/$j/ckpts.sha | grep -E '_u0(025|045|060|065|100|130)\.pt$'); do
        scp -q $K -P $P root@$H:/workspace/cb_tt/icebow/data/bench/rl_royale/$j/$f $LOC/$j/ckpts/ || { echo "scp $f failed"; continue; }
        [ "$(sha256sum $LOC/$j/ckpts/$f | awk '{print $1}')" = "$(awk -v f=$f '$2 == f {print $1}' $LOC/$j/ckpts.sha)" ]           && echo "  ckpt $f sha ok" || echo "  CKPT SHA MISMATCH $f"
      done
    fi
  done
done
