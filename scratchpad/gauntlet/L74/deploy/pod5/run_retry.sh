#!/bin/bash
# pod 5 (2026-10-12): Tornado retry. usage: run_retry.sh TORNADO_r1 "<extra train_pending args>"   (from the overnight orchestrator)
# Fresh /workspace/results/wk/NAME; writes SUMMARY.txt + DONE (DONE = ended, not accepted).
NAME=$1; TARGS=${2:-}
W=/workspace/wt_tornado; OUT=/workspace/results/wk/$NAME
cd $W || exit 1
export ROYALE_RUNTIME=20261006-linux OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 CB_MAIN=$W
mkdir "$OUT" || exit 1
echo "$TARGS" > "$OUT/train_args.txt"
flock /workspace/gpu.lock flock /workspace/cpu.lock nice -n 10 /workspace/venv/bin/python /workspace/retry/retry_driver.py --out "$OUT" --train-args "$TARGS" > "$OUT/run.log" 2>&1
rc=$?
if [ $rc -ne 0 ]; then printf 'VERDICT: FAILED (exit %s). See run.log. No candidate established; nothing deployed.\n' "$rc" > "$OUT/SUMMARY.txt"
elif [ ! -s "$OUT/SUMMARY.txt" ]; then printf 'VERDICT: FAILED: missing summary.\n' > "$OUT/SUMMARY.txt"; fi
touch "$OUT/DONE"; exit $rc
