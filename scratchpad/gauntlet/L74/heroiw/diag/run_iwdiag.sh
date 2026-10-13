#!/usr/bin/env bash
# IWDIAG ETA: 1.5-3.1 hours / 1,920 games at 25 workers, plus cpu.lock wait.
# Telemetry allowance is unmeasured. Requires existing HEROIW venv33 and old venv.
# No network, package installs, live scripts, or runtime changes.
set -Eeuo pipefail
HERE=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
REPO=$(cd "$HERE/../../../../.." && pwd)
OUT=/workspace/results/IWDIAG
OLD_PY=${OLD_PY:-/workspace/venv/bin/python}
NEW_PY=${NEW_PY:-/workspace/venv33/bin/python}
WORKERS=${WORKERS:-25}
[[ $# == 0 ]] || { echo 'No positional arguments.' >&2; exit 2; }
[[ $WORKERS =~ ^[0-9]+$ ]] || exit 2
(( WORKERS >= 1 && WORKERS <= 25 )) || exit 2
[[ -x "$OLD_PY" && -x "$NEW_PY" ]] || { echo 'Provisioned old/new Python missing; no install attempted.' >&2; exit 2; }
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1
cd "$REPO"
export PYTHONPATH="$REPO"
exec 9>/workspace/cpu.lock
flock 9
# Atomic claim after lock; never overwrite another run, including a failed one.
mkdir "$OUT" || { echo "Output already exists or parent missing: $OUT" >&2; exit 2; }
finish() {
  rc=$?
  trap - EXIT
  if [[ $rc != 0 || ! -s "$OUT/SUMMARY.txt" || ! -s "$OUT/score.json" ]]; then
    if [[ $rc == 0 ]]; then rc=1; fi
    if [[ -s "$OUT/SUMMARY.txt" ]]; then cp "$OUT/SUMMARY.txt" "$OUT/PARTIAL_SUMMARY.txt"; fi
    printf 'FAILED: IWDIAG exit %s. ETA budget 1.5-3.1 h at 25 workers plus lock wait.\nRead driver.log and arm chunk logs; partial games are not complete pairs.\n' "$rc" > "$OUT/SUMMARY.txt"
  fi
  printf 'exit_code=%s\n' "$rc" > "$OUT/DONE"
  exit "$rc"
}
trap finish EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
date -u > "$OUT/STARTED"
printf 'RUNNING: IWDIAG | ETA 1.5-3.1 h at 25 workers (unmeasured telemetry allowance).\n' > "$OUT/SUMMARY.txt"
# Check each installed runtime, offline, before dispatch; activate verifies hashes.
ROYALE_RUNTIME=20261012-linux ROYALE_HEROIW_FORM=hero ROYALE_HEROIW_PRESS=off "$NEW_PY" -c \
  'import json; from pipeline.royale_runtime import activate; print(json.dumps(activate()))' > "$OUT/new_runtime.json"
ROYALE_RUNTIME=20261006-linux ROYALE_HEROIW_FORM=hero ROYALE_HEROIW_PRESS=off "$OLD_PY" -c \
  'import json; from pipeline.royale_runtime import activate; print(json.dumps(activate()))' > "$OUT/old_runtime.json"
"$OLD_PY" "$HERE/iwdiag.py" --out "$OUT" --old-python "$OLD_PY" --new-python "$NEW_PY" --workers "$WORKERS" > "$OUT/driver.log" 2>&1
