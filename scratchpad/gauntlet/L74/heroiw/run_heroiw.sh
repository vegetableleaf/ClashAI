#!/usr/bin/env bash
# Run from the pod checkout. This script installs only into a new /workspace/venv33.
set -Eeuo pipefail
HERE=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
REPO=$(cd "$HERE/../../../.." && pwd)
OUT=/workspace/results/HEROIW
NEW=/workspace/venv33
OLD_PY=${OLD_PY:-/workspace/venv/bin/python}
WORKERS=${WORKERS:-25}
mkdir -p "$OUT"
if [[ -e "$OUT/DONE" || -e "$OUT/STARTED" ]]; then
  echo "Output already used: $OUT; refusing to overwrite evidence." >&2
  exit 2
fi
finish() {
  rc=$?
  trap - EXIT
  if [[ $rc != 0 || ! -s "$OUT/SUMMARY.txt" ]]; then
    if [[ -s "$OUT/SUMMARY.txt" ]]; then cp "$OUT/SUMMARY.txt" "$OUT/PARTIAL_SUMMARY.txt"; fi
    printf 'FAILED (exit %s): HEROIW validation did not complete. No deployment.\nRead driver.log, install.log and stage receipts; partial results are not acceptance.\n' "$rc" > "$OUT/SUMMARY.txt"
  fi
  printf 'exit_code=%s\n' "$rc" > "$OUT/DONE"
  exit "$rc"
}
trap finish EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
[[ $WORKERS =~ ^[0-9]+$ ]] || exit 2
(( WORKERS >= 1 && WORKERS <= 25 )) || exit 2
[[ $# == 0 ]] || { echo 'Use INCLUDE_P3=1 to add P3; no positional arguments.' >&2; exit 2; }
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1
cd "$REPO"
export PYTHONPATH="$REPO"
exec 9>/workspace/cpu.lock
flock 9
if [[ -e "$OUT/DONE" || -e "$OUT/STARTED" ]]; then
  trap - EXIT
  echo 'Another run used the output while this launcher waited for cpu.lock.' >&2
  exit 2
fi
date -u > "$OUT/STARTED"
# Never reuse or modify another environment at this name, even after a failed install.
[[ ! -e "$NEW" ]] || { echo "$NEW already exists; inspect it before choosing a fresh run." >&2; exit 2; }
ROYALE_RUNTIME=20261006-linux "$OLD_PY" "$HERE/validate.py" preflight --out "$OUT" > "$OUT/preflight.log" 2>&1
"$OLD_PY" -m venv "$NEW"
# Reuse heavy dependencies read-only (torch, numpy, etc.) without copying/installing into the old venv.
"$OLD_PY" "$HERE/validate.py" link-deps --venv "$NEW"
"$NEW/bin/python" -m pip install --ignore-installed --no-deps --only-binary=:all: royalesim==0.1.33 royalegym==0.1.23 > "$OUT/install.log" 2>&1
"$NEW/bin/python" -m pip freeze > "$OUT/venv33.freeze.txt"
extra=()
if [[ ${INCLUDE_P3:-0} == 1 ]]; then extra+=(--include-p3); fi
ROYALE_RUNTIME=20261012-linux "$NEW/bin/python" "$HERE/validate.py" run --out "$OUT" --old-python "$OLD_PY" --workers "$WORKERS" "${extra[@]}" > "$OUT/driver.log" 2>&1
ROYALE_RUNTIME=20261006-linux "$OLD_PY" "$HERE/validate.py" unchanged --out "$OUT" >> "$OUT/preflight.log" 2>&1
