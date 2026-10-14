#!/bin/bash
# From the l74-drills-xl2 worktree. Explicit invocation only; never deploys.
set -euo pipefail
HERE=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
ROOT=$(cd "$HERE/../../../../.." && pwd)
OUT=/workspace/results/wk/ADAPT
mkdir -p "$OUT"
finish() {
  rc=$?
  trap - EXIT
  if [ "$rc" -ne 0 ]; then
    printf 'VERDICT: Failed; no result established. Nothing deployed.\nExit code: %s. Inspect adaptive.log and stage logs.\n' "$rc" > "$OUT/SUMMARY.txt"
  elif [ ! -s "$OUT/SUMMARY.txt" ]; then
    printf 'VERDICT: Failed; summary missing. Nothing deployed.\n' > "$OUT/SUMMARY.txt"
    rc=1
  fi
  touch "$OUT/DONE"
  exit "$rc"
}
trap finish EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
while [ ! -f /workspace/results/wk/ICEBOW_DONE ]; do sleep 30; done
cd "$ROOT"
export ROYALE_RUNTIME=20261006-linux OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 CB_MAIN="$ROOT"
PY=${PY:-/workspace/venv/bin/python}
# Serial stages: 20 actors/workers leave room for trainer, helper, resource
# tracker, shell and lock holders, keeping the process budget below 28.
flock /workspace/gpu.lock flock /workspace/cpu.lock "$PY" "$HERE/driver.py" --out "$OUT" > "$OUT/adaptive.log" 2>&1
