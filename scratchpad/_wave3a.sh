#!/bin/sh
cd /c/Users/benpe/ClashBot/scratchpad
PY=/c/Users/benpe/ClashBot/.venv/Scripts/python
run() { tag=$1; shift; $PY rollout_search.py --matches 60 --seed0 5000000 --tag "$tag" --out "rs_${tag}.json" "$@" > "log_${tag}.txt" 2>&1; echo "DONE $tag"; }
run cl12  --horizon 12  --interval 5 --topk 4 --dump-decisions &
run cl20  --horizon 20  --interval 5 --topk 4 --dump-decisions &
run cl30  --horizon 30  --interval 5 --topk 4 --dump-decisions &
run clfull --horizon 999 --interval 5 --topk 4 --dump-decisions &
wait
echo "WAVE3A COMPLETE"
