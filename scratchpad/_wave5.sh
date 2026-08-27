#!/bin/sh
cd /c/Users/benpe/ClashBot/scratchpad
PY=/c/Users/benpe/ClashBot/.venv/Scripts/python
run() { tag=$1; shift; $PY rollout_search.py --matches 300 --seed0 5000000 --tag "$tag" --out "rs_${tag}.json" "$@" > "log_${tag}.txt" 2>&1; echo "DONE $tag"; }
run jP025 --horizon 12 --interval 5 --topk 4 --jit-pos 0.25 --jit-play &
run jP100 --horizon 12 --interval 5 --topk 4 --jit-pos 1.0  --jit-play &
wait
echo "WAVE5 COMPLETE"
