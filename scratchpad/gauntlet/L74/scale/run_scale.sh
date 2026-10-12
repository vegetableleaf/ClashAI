#!/usr/bin/env bash
# ETA: 12-24 h, one L40, measured update after first epoch. Offline dependencies/data must already exist.
set -Eeuo pipefail
HERE=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
REPO=$(cd "$HERE/../../../.." && pwd)
OUT=${SCALE_OUT:-/workspace/results/SCALE}
PY=${SCALE_PY:-/workspace/venv/bin/python}
mkdir -p "$OUT"
if [[ -e "$OUT/DONE" || -e "$OUT/STARTED" ]]; then
  echo "SCALE output already used: $OUT" >&2
  exit 2
fi
# Atomic ownership; never overwrite another run or its failure evidence.
if ! mkdir "$OUT/run.lock" 2>/dev/null; then
  echo "SCALE output already claimed: $OUT" >&2
  exit 2
fi
finish() {
  rc=$?
  trap - EXIT
  if [[ ! -s "$OUT/DONE" ]]; then
    printf 'Verdict: no evidence.\nETA: 12-24 hours on one L40; run ended early.\nStatus: FAILED (exit %s). Read launcher.log, driver.log, tests.log and preflight.log. No deployment.\n' "$rc" > "$OUT/SUMMARY.txt"
    printf 'FAILED exit_code=%s\n' "$rc" > "$OUT/DONE"
  fi
  exit "$rc"
}
trap finish EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
exec >> "$OUT/launcher.log" 2>&1
printf 'Verdict: pending measurement.\nETA: 12-24 hours on one L40.\nStatus: PREFLIGHT. No deployment.\n' > "$OUT/SUMMARY.txt"
date -u > "$OUT/STARTED"
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
export PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1 CUBLAS_WORKSPACE_CONFIG=:4096:8
cd "$REPO"
export PYTHONPATH="$REPO"
export SCALE_TEST_ROOT="$OUT/test_artifacts"
exec 9>/workspace/gpu.lock
flock -n 9 || { echo 'GPU lock held; SCALE not launched.' >> "$OUT/preflight.log"; exit 2; }
nvidia-smi --query-gpu=name,memory.total --format=csv > "$OUT/preflight.log"
jobs=$(nvidia-smi --query-compute-apps=pid --format=csv,noheader)
if [[ -n "$jobs" ]]; then
  echo 'GPU compute processes already running; refusing concurrent job.' >> "$OUT/preflight.log"
  exit 2
fi
"$PY" -m pytest "$HERE/test_scale.py" -q -p no:tmpdir -p no:cacheprovider > "$OUT/tests.log" 2>&1
"$PY" -u "$HERE/scale.py" "$@" --out "$OUT" > "$OUT/driver.log" 2>&1
