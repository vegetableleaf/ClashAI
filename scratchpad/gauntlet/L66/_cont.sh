#!/bin/bash
# L66m: continuation diagnostic. Same 12 tags, same candidates + the pro cell, two rollout modes.
cd ~/cb
export PYTHONPATH=~/cb:~/cb/research/ext/cr-native-sandbox
B=scratchpad/gauntlet/L64/s3/bench500_icebow.json
O=scratchpad/gauntlet/L66/cont; mkdir -p $O
for mode in both replay; do
  for s in 0 1 2 3; do
    python3 pipeline/s3_teacher.py run $B --out $O/${mode}_s$s.jsonl --port $((37031+s)) --shard $s/4 --limit 3 \
      --horizon 400 --refine 2 --score v2 --opponent $mode --include-pro --seed 1 > $O/${mode}_s$s.log 2>&1 &
  done
  wait
done
echo ALLDONE > $O/DONE
