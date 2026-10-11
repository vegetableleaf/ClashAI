#!/bin/bash
# Offline-authored pod driver. Explicit invocation only; never deploys.
set -euo pipefail
HERE=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
ROOT=$(cd "$HERE/../../../.." && pwd)
cd "$ROOT"
PY=${PY:-/workspace/venv/bin/python}
RESULTS=${RESULTS:-/workspace/results/wk}
export ROYALE_RUNTIME=${ROYALE_RUNTIME:-20261006-linux} OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 CB_MAIN="$ROOT"
# Gate before locks: waiting never prevents the preceding job from finishing.
if [ -n "${WAIT_FOR:-}" ]; then
  while [ ! -f "$WAIT_FOR" ]; do sleep 30; done
fi
for phase in P1 P2 P3 P4; do
  out="$RESULTS/MEM$phase"
  mkdir -p "$out"
  # DONE marks termination, SUCCESS alone permits dependency progression.
  (
    finish() {
      rc=$?
      trap - EXIT
      if [ "$rc" -ne 0 ]; then
        rm -f "$out/SUCCESS"
        printf 'VERDICT: FAILED (exit %s). See phase.log. No result established; nothing deployed.\n' "$rc" > "$out/SUMMARY.txt"
      elif [ ! -s "$out/SUMMARY.txt" ]; then
        printf 'VERDICT: FAILED: missing summary. Nothing deployed.\n' > "$out/SUMMARY.txt"
        rc=1
      fi
      [ "$rc" -ne 0 ] || touch "$out/SUCCESS"
      touch "$out/DONE"
      exit "$rc"
    }
    trap finish EXIT
    trap 'exit 130' INT
    trap 'exit 143' TERM
    rm -f "$out/DONE"
    if [ "$phase" = P2 ] || [ "$phase" = P3 ]; then
      flock /workspace/gpu.lock flock /workspace/cpu.lock "$PY" "$HERE/driver.py" --phase "$phase" --results "$RESULTS" "$@"
    else
      flock /workspace/cpu.lock "$PY" "$HERE/driver.py" --phase "$phase" --results "$RESULTS" "$@"
    fi
  ) > "$out/phase.log" 2>&1
done
