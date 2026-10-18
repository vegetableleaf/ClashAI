#!/bin/bash
# Laptop: copy one checkpoint pod -> laptop backup -> pods, sha256-verified at every hop (Git-Bash "hash *path" normalised).
#   relay_ckpt.sh SRC_HOST SRC_PORT SRC_ABS_PATH DEST_REL LOCAL_DIR [HOST PORT ...]
#   DEST_REL is relative to /workspace/cb_stepd on each destination pod; LOCAL_DIR under pod_backup_weekend/stepd/.
# e.g. the REB init:  relay_ckpt.sh 64.247.206.80 30988 /workspace/stepd/d2/il_cue_w_s0/gen_cuew_s0.pt \
#        icebow/data/pipeline/stepd_il/gen_cuew_s0.pt d2 64.247.206.120 19834 64.247.206.76 14009
set -euo pipefail
K="-o BatchMode=yes -o ConnectTimeout=20 -o ServerAliveInterval=30 -o StrictHostKeyChecking=no -i $HOME/.ssh/runpod_clashbot"
SH=$1; SP=$2; SRC=$3; DEST=$4; L=/c/Users/benpe/pod_backup_weekend/stepd/$5; shift 5
mkdir -p $L; F=$L/$(basename $SRC)
want=$(ssh -n $K -p $SP root@$SH "sha256sum $SRC" | awk '{print $1}')
scp -q $K -P $SP root@$SH:$SRC $F
[ "$(sha256sum $F | awk '{print $1}')" = "$want" ] || { echo "SHA MISMATCH laptop $F"; exit 1; }
echo "laptop $F ${want:0:16}"
while [ $# -ge 2 ]; do
  H=$1; P=$2; shift 2
  ssh -n $K -p $P root@$H "mkdir -p /workspace/cb_stepd/$(dirname $DEST)"
  scp -q $K -P $P $F root@$H:/workspace/cb_stepd/$DEST.part
  ssh -n $K -p $P root@$H "cd /workspace/cb_stepd && [ \$(sha256sum $DEST.part | cut -c1-64) = $want ] && mv $DEST.part $DEST && echo \"$H:$P $DEST ${want:0:16} ok\""
done
