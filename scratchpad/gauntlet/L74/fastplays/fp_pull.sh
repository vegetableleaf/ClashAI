#!/bin/bash
# Laptop: verified copy-back of the fastplays pod results -> C:/Users/benpe/pod_backup_weekend/pod1017_fastplays/ (every file's
# sha256 checked against the pod's list). Never stops the pod (owner rule 10-18: pods are kept; /workspace/KEEP stays).
#   fp_pull.sh HOST PORT
set -euo pipefail
H=$1; P=$2; LOC=/c/Users/benpe/pod_backup_weekend/pod1017_fastplays
K="-o BatchMode=yes -o ConnectTimeout=20 -o ServerAliveInterval=30 -o StrictHostKeyChecking=no -i $HOME/.ssh/runpod_clashbot"
mkdir -p $LOC
ssh -n $K -p $P root@$H "cd /workspace && tar czf /workspace/fp_out.tgz fp results/fastplays cb_tt/pipeline/e1_eval.py cb_tt/pipeline/search_s0.py \
  && (cd /workspace && tar tzf fp_out.tgz | grep -v '/$' | xargs sha256sum > /workspace/fp_out.sha) && sha256sum fp_out.tgz > fp_out.tgz.sha"
want=$(ssh -n $K -p $P root@$H "cat /workspace/fp_out.tgz.sha" | awk '{print $1}')
scp -q $K -P $P root@$H:/workspace/fp_out.tgz root@$H:/workspace/fp_out.sha $LOC/
got=$(sha256sum $LOC/fp_out.tgz | sed 's/ \*/  /' | awk '{print $1}')
[ "$got" = "$want" ] || { echo "TGZ SHA MISMATCH $got vs $want"; exit 1; }
rm -rf $LOC/x && mkdir -p $LOC/x && tar xzf $LOC/fp_out.tgz -C $LOC/x
(cd $LOC/x && sha256sum -c --quiet ../fp_out.sha) || { echo "FILE SHA MISMATCH"; exit 1; }
rm -rf $LOC/fp $LOC/fastplays $LOC/patched && mv $LOC/x/fp $LOC/fp && mv $LOC/x/results/fastplays $LOC/fastplays && \
  mv $LOC/x/cb_tt/pipeline $LOC/patched && rm -rf $LOC/x
echo "$H:$P $want $(wc -l < $LOC/fp_out.sha) files" > $LOC/COPY_OK; cat $LOC/COPY_OK
