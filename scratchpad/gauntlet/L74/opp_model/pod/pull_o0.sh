#!/bin/bash
# Pull the two O0 bundles sha-verified to pod_backup_weekend/o0 and unpack (Git-Bash sha256sum prints "hash *file": normalised).
set -euo pipefail
D=/c/Users/benpe/pod_backup_weekend/o0; mkdir -p $D; cd $D
for P in 13396 14009; do
  T=15; [ $P = 14009 ] && T=16
  scp -q -i ~/.ssh/runpod_clashbot -P $P root@64.247.206.76:/workspace/o0/o0_t$T.tgz root@64.247.206.76:/workspace/o0/o0_t$T.tgz.sha $D/
  want=$(awk '{print $1}' o0_t$T.tgz.sha); got=$(sha256sum o0_t$T.tgz | awk '{print $1}')
  [ "$want" = "$got" ] || { echo "SHA MISMATCH T$T $want $got"; exit 1; }
  echo "T$T sha ok $got"
  tar xzf o0_t$T.tgz
done
touch $D/COPY_OK
