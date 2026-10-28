#!/usr/bin/env bash
# ship_main.sh SHA8 [PORT ...] -- CF-MAIN (laptop): copy pod 30408's /workspace/crforge_main/SHA8 (plain/ + tickprobe/, each
# lib/ + BUILD.json + SHA256SUMS, made by pod/build_main.sh) to the other pods through the laptop (pods have no keys to each
# other), check every jar with sha256sum -c on every pod, and point /workspace/crforge_main/current at SHA8 on each.
set -euo pipefail
D=$1; shift; PODS=${*:-32657 33920 33308}
K="-o BatchMode=yes -o ConnectTimeout=20 -o StrictHostKeyChecking=no -i $HOME/.ssh/runpod_clashbot"; H=root@157.157.221.29
TGZ=$(mktemp); trap 'rm -f $TGZ' EXIT
ssh $K -p 30408 $H "cd /workspace/crforge_main && tar czf - $D" > $TGZ
for p in 30408 $PODS; do
  [ $p = 30408 ] || ssh $K -p $p $H "mkdir -p /workspace/crforge_main && cd /workspace/crforge_main && rm -rf $D && tar xzf -" < $TGZ
  ssh $K -p $p $H "cd /workspace/crforge_main/$D && (cd plain && sha256sum -c --quiet SHA256SUMS) && (cd tickprobe && sha256sum -c --quiet SHA256SUMS) && ln -sfn $D /workspace/crforge_main/current && echo pod $p $D OK core plain \$(grep core-1.0 plain/SHA256SUMS | cut -c1-16) tickprobe \$(grep core-1.0 tickprobe/SHA256SUMS | cut -c1-16)"
done
