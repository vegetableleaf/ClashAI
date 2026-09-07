#!/bin/bash
# L66n: oracle-future test. Same 12 tags, both-mode continuation, K=4 jittered opponent futures (common per state).
cd ~/cb
export PYTHONPATH=~/cb:~/cb/research/ext/cr-native-sandbox
B=scratchpad/gauntlet/L64/s3/bench500_icebow.json
O=scratchpad/gauntlet/L66/cont
for s in 0 1 2 3; do
  python3 pipeline/s3_teacher.py run $B --out $O/jit4_s$s.jsonl --port $((37031+s)) --shard $s/4 --limit 3 \
    --horizon 400 --refine 2 --score v2 --opponent both --include-pro --seed 1 \
    --futures 4 --jitter-ticks 60 --jitter-tiles 1.0 > $O/jit4_s$s.log 2>&1 &
done
wait
echo ALLDONE > $O/DONE_JIT
