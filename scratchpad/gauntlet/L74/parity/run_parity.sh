#!/usr/bin/env bash
set -Eeuo pipefail
HERE=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
REPO=$(cd "$HERE/../../../.." && pwd)
OUT=${OUT:-/workspace/results/PARITY}
OLD_PY=${OLD_PY:-/workspace/venv/bin/python}
NEW_PY=${NEW_PY:-/workspace/venv33/bin/python}
FORK_PY=${FORK_PY:-$NEW_PY}
WORKERS=${WORKERS:-24}
MATCHES=${MATCHES:-100}
SINCE=${SINCE:-20261008}
# Logs do not expose levels. No implicit level-15 claim: caller must opt in.
extra=()
if [[ ${MECHANICS_REPLAY:-0} == 1 ]]; then extra+=(--mechanics-replay); fi
if [[ -n ${ASSUME_LEVEL:-} ]]; then extra+=(--assume-level "$ASSUME_LEVEL"); fi
if [[ -n ${COHORT:-} ]]; then extra+=(--cohort "$COHORT"); fi
[[ $# == 0 ]] || { echo 'Use documented environment variables; no positional arguments' >&2; exit 2; }
[[ $WORKERS =~ ^[0-9]+$ && $MATCHES =~ ^[0-9]+$ ]] || exit 2
(( WORKERS >= 1 && WORKERS <= 24 && MATCHES >= 1 )) || exit 2
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1
cd "$REPO"
export PYTHONPATH="$REPO"
exec 9>/workspace/cpu.lock
echo 'Waiting for cpu.lock; ETA excludes lock wait.'
flock 9
mkdir -p "$OUT"
[[ ! -e "$OUT/STARTED" && ! -e "$OUT/DONE" && ! -e "$OUT/selection.json" ]] || { echo 'Output already used; choose fresh OUT' >&2; exit 2; }
date -u > "$OUT/STARTED"
finish() {
  rc=$?
  trap - EXIT
  if [[ ! -s "$OUT/SUMMARY.txt" ]]; then
    printf 'FAILED before parity report (exit %s). Read driver.log. No fidelity result.\n' "$rc" > "$OUT/SUMMARY.txt"
  fi
  printf 'exit_code=%s\nDONE means finished; read SUMMARY.txt for coverage and verdict.\n' "$rc" > "$OUT/DONE"
  exit "$rc"
}
trap finish EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
echo 'Unbenchmarked ETA: 5-30 minutes for 3 x 100 matches at 24 workers; first batches report measured ETA.'
"$OLD_PY" "$HERE/driver.py" run --runtime old new fork --matches "$MATCHES" --since "$SINCE" \
  --workers "$WORKERS" --old-python "$OLD_PY" --new-python "$NEW_PY" --fork-python "$FORK_PY" \
  --out "$OUT" "${extra[@]}" > "$OUT/driver.log" 2>&1
