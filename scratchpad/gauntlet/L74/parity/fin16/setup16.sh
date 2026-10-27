#!/bin/bash
# A1 (10-27, pod 32657): logs + exports -> chunk dirs (w19/split_export.py, 8 chunks per cohort), as w19/pod_setup.sh.
#   bash setup16.sh > /workspace/f16/setup16.log 2>&1   -> SETUP_c13 / SETUP_c22
set -euo pipefail
B=/workspace/f16; I=$B/in; cd $B
S=$B/cb/scratchpad/gauntlet/L74/parity/w19/split_export.py
mkdir -p logs
if [ ! -e SETUP_c22 ] && [ -e $I/caplogs22.tgz ]; then
  tar --no-same-owner -xzf $I/caplogs22.tgz -C logs
  for k in 0 1 2 3; do gunzip -kf $I/attacks22_$k.json.gz $I/buffs22_$k.json.gz; done
  python3 $S $B/logs $B/ch c22 8 $(for k in 0 1 2 3; do echo $I/attacks22_$k.json $I/buffs22_$k.json; done)
  touch SETUP_c22
fi
if [ ! -e SETUP_c13 ] && [ -e $I/attacks13.json.gz ]; then
  tar --no-same-owner -xzf $I/caplogs13.tgz -C logs
  gunzip -kf $I/attacks13.json.gz $I/buffs13.json.gz
  python3 $S $B/logs $B/ch c13 8 $I/attacks13.json $I/buffs13.json
  touch SETUP_c13
fi
echo "logs $(ls logs | wc -l)"; ls -d ch/* | wc -l; echo SETUP_END
