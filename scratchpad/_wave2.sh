#!/bin/sh
cd /c/Users/benpe/ClashBot/scratchpad
PY=/c/Users/benpe/ClashBot/.venv/Scripts/python
run() { tag=$1; shift; $PY rollout_search.py --matches 300 --seed0 5000000 --tag "$tag" --out "rs_${tag}.json" "$@" > "log_${tag}.txt" 2>&1; echo "DONE $tag rc=$?"; }
run k8    --horizon 12 --interval 5 --topk 8 &
run n10   --horizon 12 --interval 10 --topk 4 &
run phE   --horizon 12 --interval 5 --topk 4 --phase-hi 60  --dump-decisions &
run phM   --horizon 12 --interval 5 --topk 4 --phase-lo 60 --phase-hi 120 --dump-decisions &
run phL   --horizon 12 --interval 5 --topk 4 --phase-lo 120 --dump-decisions &
run jit   --horizon 12 --interval 5 --topk 4 --jit-drop 0.18 --jit-pos 0.5 --jit-hp 0.25 --jit-play --dump-decisions &
wait
echo "WAVE2 COMPLETE"
