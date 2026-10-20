#!/bin/bash
# Pull every finished /workspace/o3/out/NAME.tgz (+ .sha) from the given pods, sha-verified, unpacked into
# pod_backup_weekend/o3/<port>/ (Git-Bash sha256sum prints "hash *file": compare the hash field only). Safe to repeat.
#   bash pull_o3.sh 48148 40548
set -uo pipefail
for P in "$@"; do
  D=/c/Users/benpe/pod_backup_weekend/o3/$P; mkdir -p $D; cd $D || exit 1
  for f in $(ssh -i ~/.ssh/runpod_clashbot -p $P root@64.247.206.80 'cd /workspace/o3/out && ls *.tgz 2>/dev/null'); do
    n=${f%.tgz}
    [ -f $D/$n.OK ] && continue
    scp -q -i ~/.ssh/runpod_clashbot -P $P root@64.247.206.80:/workspace/o3/out/$f root@64.247.206.80:/workspace/o3/out/$f.sha $D/ || continue
    want=$(awk '{print $1}' $f.sha); got=$(sha256sum $f | awk '{print $1}')
    if [ "$want" = "$got" ]; then tar xzf $f && touch $n.OK && echo "pulled $P $n"; else echo "SHA MISMATCH $P $n"; fi
  done
done
