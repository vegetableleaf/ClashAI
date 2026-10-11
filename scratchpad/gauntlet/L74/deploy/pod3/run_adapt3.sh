#!/bin/bash
# Pod 3 ADAPT (owner 2026-10-11): run_adaptive.sh without the ICEBOW_DONE gate, no inner flock (the chain holds gpu.lock then cpu.lock).
# Run from /workspace/wk_adapt.  The pod-3 driver.py differs from the branch only in 20 -> 12 actors/workers (pod 3 quota 13.6 vCPU).
set -uo pipefail
ROOT=/workspace/wk_adapt; HERE=$ROOT/scratchpad/gauntlet/L74/weekend/adaptive
OUT=/workspace/results/wk/ADAPT; mkdir -p "$OUT"; rm -f "$OUT/DONE"
cd "$ROOT"
export ROYALE_RUNTIME=20261006-linux OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 CB_MAIN="$ROOT"
/workspace/venv/bin/python "$HERE/driver.py" --out "$OUT" > "$OUT/adaptive.log" 2>&1
rc=$?
if [ $rc -ne 0 ]; then
  printf 'VERDICT: Failed; no result established. Nothing deployed.\nExit code: %s. Inspect adaptive.log and stage logs.\n' "$rc" > "$OUT/SUMMARY.txt"
elif [ ! -s "$OUT/SUMMARY.txt" ]; then
  printf 'VERDICT: Failed; summary missing. Nothing deployed.\n' > "$OUT/SUMMARY.txt"
fi
touch "$OUT/DONE"
exit $rc
