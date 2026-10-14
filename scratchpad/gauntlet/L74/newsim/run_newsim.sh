#!/usr/bin/env bash
# NEWSIM: one arm per run, never deploys.
# ETA: roughly 12-16 h after locks, L40 / 27-30 vCPU, WORKERS=24.
# ADAPT2 measured 55 min / 20 updates: 105 updates ~=4.8 h training;
# add screens/startup/census and 7,680 eval games (~6 h at ADAPT's rate).
# New-runtime speed is unmeasured. ARM=base|fast; fast pipeline fraction=0.3.
# No network: provision wheelhouse unless /workspace/venv33 already verifies.
set -Eeuo pipefail
HERE=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
ROOT=$(cd "$HERE/../../../.." && pwd)
ARM=${ARM:-base}
case "$ARM" in base|fast) ;; *) echo 'ARM must be base or fast' >&2; exit 2 ;; esac
OUT=/workspace/results/NEWSIM_$ARM
NEW=/workspace/venv33
OLD_PY=${OLD_PY:-/workspace/venv/bin/python}
WORKERS=${WORKERS:-24}
WHEELHOUSE=${WHEELHOUSE:-/workspace/wheelhouse}
mkdir -p "$OUT"
if [[ -e "$OUT/DONE" || -e "$OUT/STARTED" ]]; then
  echo "Output already used: $OUT; refusing to overwrite evidence." >&2
  exit 2
fi
# Claim output before any failure trap can write it, including while queued.
mkdir "$OUT/.claim" || { echo "Output claimed by another launcher: $OUT" >&2; exit 2; }
finish() {
  rc=$?
  trap - EXIT
  if [[ $rc != 0 || ! -s "$OUT/SUMMARY.txt" ]]; then
    [[ ! -s "$OUT/SUMMARY.txt" ]] || cp "$OUT/SUMMARY.txt" "$OUT/PARTIAL_SUMMARY.txt"
    printf 'VERDICT: Failed; no result established. Nothing deployed.\nExit code %s. Inspect driver.log, smoke.log and install.log.\n' "$rc" > "$OUT/SUMMARY.txt"
    [[ $rc != 0 ]] || rc=1
  fi
  printf 'exit_code=%s\n' "$rc" > "$OUT/DONE"
  exit "$rc"
}
trap finish EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
[[ $# == 0 ]] || { echo 'Use ARM and WORKERS environment variables; no positional arguments.' >&2; exit 2; }
[[ $WORKERS =~ ^[0-9]+$ ]] || exit 2
(( WORKERS >= 1 && WORKERS <= 24 )) || exit 2
export ROYALE_RUNTIME=20261012-linux OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
export PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1 PYTHONPATH="$ROOT"
export PIP_NO_INDEX=1 PIP_DISABLE_PIP_VERSION_CHECK=1
cd "$ROOT"
# Descriptor locks do not leave nested flock processes resident. Maximum:
# shell + driver + trainer/evaluator + spawn resource tracker + WORKERS <=28.
exec 9>/workspace/gpu.lock
flock 9
exec 8>/workspace/cpu.lock
flock 8
if [[ -e "$OUT/DONE" || -e "$OUT/STARTED" ]]; then
  trap - EXIT
  echo 'Another run used the output while this launcher waited for locks.' >&2
  exit 2
fi
date -u > "$OUT/STARTED"
if [[ ! -e "$NEW" ]]; then
  "$OLD_PY" -m venv "$NEW"
  # Same isolated install and read-only heavy-dependency link as HEROIW.
  "$OLD_PY" "$HERE/../heroiw/validate.py" link-deps --venv "$NEW"
  "$NEW/bin/python" -m pip install --no-index --find-links "$WHEELHOUSE" --ignore-installed --no-deps \
    --only-binary=:all: royalesim==0.1.33 royalegym==0.1.23 > "$OUT/install.log" 2>&1
fi
# Existing venv is reused only after hashes, versions and compiled provenance verify.
"$NEW/bin/python" -c 'import json; from pipeline.royale_runtime import activate; print(json.dumps(activate()))' > "$OUT/runtime_verify.json" 2> "$OUT/runtime_verify.log"
"$NEW/bin/python" -m pip freeze > "$OUT/venv33.freeze.txt"
"$NEW/bin/python" "$HERE/driver.py" --arm "$ARM" --workers "$WORKERS" --out "$OUT" > "$OUT/driver.log" 2>&1
