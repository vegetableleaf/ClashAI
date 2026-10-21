#!/bin/bash
# W14 laptop relay (Git Bash): pull every finished w14_*.tgz from the two W14 pods (sha-checked; Git-Bash sha256sum prints
# "hash *file": compare field 1) into pod_backup_weekend/w14/o3/ and extract it; then print the brief O4-Ranked table.
#   bash scratchpad/gauntlet/L74/opp_model/w14/pull.sh [--no-table]
set -uo pipefail
NOTAB=${1:-}
KEY=$HOME/.ssh/runpod_clashbot
D=/c/Users/benpe/pod_backup_weekend/w14/o3; mkdir -p $D; cd $D || exit 1
for HP in "root@64.247.206.80 48148" "root@64.247.206.76 19899" "root@213.192.2.123 40116"; do
  set -- $HP
  for f in $(ssh -i $KEY -p $2 $1 'cd /workspace/o3w12/out && ls w14*.tgz 2>/dev/null'); do
    n=${f%.tgz}; [ -f $n.OK ] && continue
    scp -q -i $KEY -P $2 $1:/workspace/o3w12/out/$f $1:/workspace/o3w12/out/$f.sha . || continue
    want=$(awk '{print $1}' $f.sha); got=$(sha256sum $f | awk '{print $1}')
    if [ "$want" = "$got" ]; then rm -rf $n; tar xzf $f && touch $n.OK && echo "pulled $n ($2)"; else echo "SHA MISMATCH $n"; fi
  done
done
[ "$NOTAB" = --no-table ] && exit 0
cd /c/Users/benpe/ClashBot && icebow/.venv/Scripts/python.exe -B scratchpad/gauntlet/L74/opp_model/w14/o4r_table.py $D --brief
