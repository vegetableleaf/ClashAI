#!/usr/bin/env bash
# Offline only. No installation, downloads, training, deployment or auto-start.
set -euo pipefail
if [[ ${1:-} != --run ]]; then
  echo 'Default OFF. Usage: bash scratchpad/gauntlet/L74/pro2/build_rows.sh --run [--allow-unknown-forms] [--limit N]'
  echo 'Needs the pinned Linux SIM runtime, numpy/torch and repo catalogs already provisioned.'
  exit 0
fi
shift
ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../.." && pwd)
cd "$ROOT"
export ROYALE_RUNTIME=${ROYALE_RUNTIME:-20261006-linux}
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
PYTHON=${PRO2_PYTHON:-python3}
SOURCE=${PRO2_SOURCE:-$ROOT/scratchpad/gauntlet/L74/pro2/output/replays.jsonl}
OUT=${PRO2_OUT:-/workspace/results/PRO2}
"$PYTHON" scratchpad/gauntlet/L74/pro2/build_rows.py --source "$SOURCE" --out "$OUT" "$@"
