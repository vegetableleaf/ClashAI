#!/bin/bash
# Explicit-only, no network or deployment. Fresh OUT required; DONE means ended.
set -euo pipefail
HERE=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
ROOT=$(cd "$HERE/../../../.." && pwd)
cd "$ROOT"
PY=${PY:-/workspace/venv/bin/python}
OUT=${OUT:-/workspace/results/wk/TORNADO}
export ROYALE_RUNTIME=${ROYALE_RUNTIME:-20261006-linux} OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 CB_MAIN="$ROOT"
# Wait before taking shared locks, so the preceding job can finish.
if [ -n "${WAIT_FOR:-}" ]; then
  while [ ! -f "$WAIT_FOR" ]; do sleep 30; done
fi
mkdir -p "$(dirname "$OUT")"
mkdir "$OUT"  # refuse stale results, concurrent runs and stale DONE
finish() {
  rc=$?
  trap - EXIT
  if [ "$rc" -ne 0 ]; then
    printf 'VERDICT: FAILED (exit %s). See run.log and per-stage logs. No candidate established; nothing deployed.\n' "$rc" > "$OUT/SUMMARY.txt"
  elif [ ! -s "$OUT/SUMMARY.txt" ]; then
    printf 'VERDICT: FAILED: missing summary. Nothing deployed.\n' > "$OUT/SUMMARY.txt"
    rc=1
  fi
  touch "$OUT/DONE"
  exit "$rc"
}
trap finish EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
flock /workspace/gpu.lock flock /workspace/cpu.lock nice -n 10 "$PY" "$HERE/driver.py" --out "$OUT" "$@" > "$OUT/run.log" 2>&1
