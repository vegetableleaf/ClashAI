#!/bin/sh
cd /c/Users/benpe/ClashBot/scratchpad
PY=/c/Users/benpe/ClashBot/.venv/Scripts/python
run() { # tag, extra args...
  tag=$1; shift
  $PY rollout_search.py --matches 300 --seed0 5000000 --tag "$tag" --out "rs_${tag}.json" "$@" > "log_${tag}.txt" 2>&1
  echo "DONE $tag rc=$?"
}
run hfull  --horizon 999 --interval 5 --topk 4 &
run n1     --horizon 12  --interval 1 --topk 4 &
run h16    --horizon 16  --interval 5 --topk 4 &
run h30    --horizon 30  --interval 5 --topk 4 &
run k2     --horizon 12  --interval 5 --topk 2 &
run n3     --horizon 12  --interval 3 --topk 4 &
wait
echo "WAVE1 COMPLETE"
