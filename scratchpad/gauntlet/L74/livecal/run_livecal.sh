#!/usr/bin/env bash
# From the pod repo root: bash scratchpad/gauntlet/L74/livecal/run_livecal.sh [--quick]
set -Eeuo pipefail
HERE=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
REPO=$(cd "$HERE/../../../.." && pwd)
OUT=${LIVECAL_OUT:-/workspace/results/LIVECAL}
PY=${PY:-/workspace/venv/bin/python}
mkdir -p "$OUT"
# Reject reruns without touching their artifacts.
if [[ -e "$OUT/DONE" || -e "$OUT/plan.json" || -e "$OUT/chunks" ]]; then
  echo "Output already used: $OUT. Set LIVECAL_OUT to a fresh directory." >&2
  exit 2
fi
finish() {
  rc=$?
  trap - EXIT
  if [[ $rc != 0 || ! -s "$OUT/SUMMARY.txt" ]]; then
    printf 'FAILED: no pool can be named (exit %s). See driver.log. No deployment.\n' "$rc" > "$OUT/SUMMARY.txt"
  fi
  printf 'exit_code=%s\n' "$rc" > "$OUT/DONE"
  exit "$rc"
}
trap finish EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
for arg in "$@"; do
  if [[ "$arg" == --out || "$arg" == --out=* ]]; then
    echo 'Use LIVECAL_OUT to set the output directory for the shell driver.' >&2
    exit 2
  fi
done
export ROYALE_RUNTIME=${ROYALE_RUNTIME:-20261006-linux}
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1
cd "$REPO"
# Hold the lock across preflight, all worker children and scoring.
exec 9>/workspace/cpu.lock
flock 9
"$PY" "$HERE/livecal.py" --out "$OUT" "$@" > "$OUT/driver.log" 2>&1
