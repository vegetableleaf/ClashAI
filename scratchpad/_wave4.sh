#!/bin/sh
cd /c/Users/benpe/ClashBot/scratchpad
PY=/c/Users/benpe/ClashBot/.venv/Scripts/python
run() { tag=$1; shift; $PY rollout_search.py --seed0 5000000 --tag "$tag" --out "rs_${tag}.json" "$@" > "log_${tag}.txt" 2>&1; echo "DONE $tag"; }
run ceil --matches 300 --horizon 12 --interval 1 --topk 4 --cells 3 --dump-decisions &
run jitD --matches 300 --horizon 12 --interval 5 --topk 4 --jit-drop 0.18 --jit-play &
run jitP --matches 300 --horizon 12 --interval 5 --topk 4 --jit-pos 0.5 --jit-play &
wait
echo "WAVE4 COMPLETE"
