#!/bin/bash
# pod 5 (2026-10-12): the SAME pending-head fine-tune as TORNADO (train_pending defaults, reusing TORNADO's pending index) starting from
# the ADAPT final grafted checkpoint; drift < 1% required; 8-game smoke (fixed model, pipelining ON, hard opponent); no full eval.
# usage: run_adaptfix.sh /workspace/adaptfix/adaptive_final_grafted.pt     -> /workspace/results/wk/ADAPTFIX/{adapt_fixed.pt,SUMMARY.txt,DONE}
INIT=$1; W=/workspace/wt_tornado; OUT=/workspace/results/wk/ADAPTFIX
cd $W || exit 1
export ROYALE_RUNTIME=20261006-linux OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 CB_MAIN=$W
rm -rf "$OUT"; mkdir -p "$OUT"
fail() { printf 'VERDICT: FAILED (%s). Nothing deployed.\n' "$1" > "$OUT/SUMMARY.txt"; touch "$OUT/DONE"; exit 1; }
DATA=icebow/data/pipeline/gen_dataset_v32_fv5.npz
nice -n 10 bash /workspace/retry/train_locked.sh --data $DATA --pending /workspace/results/wk/TORNADO/icebow/pending.npz --init "$INIT" --out "$OUT/adapt_fixed.pt" --device cuda > "$OUT/train.log" 2>&1 || fail "train_pending failed"
/workspace/venv/bin/python /workspace/retry/adaptfix_check.py "$OUT" > "$OUT/smoke.log" 2>&1 || fail "drift/smoke check failed"
{ echo 'VERDICT: built'; echo "init: $INIT"; cat "$OUT/smoke.log"; } > "$OUT/SUMMARY.txt"; touch "$OUT/DONE"
