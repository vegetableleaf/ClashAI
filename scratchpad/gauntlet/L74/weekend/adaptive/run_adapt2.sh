#!/bin/bash
# ADAPT2: 3 more 20/15 cycles, same graft and 960-pair yardstick; never deploys.
# ETA: 10-14 hours after WAIT_FOR and both locks clear, on comparable hardware.
# ADAPT logs: 7.59h rollout/update + 1.46h eval, plus screens/startup/overhead.
# Planning estimate only; ADAPT2 runtime has not been measured.
set -euo pipefail
HERE=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
ROOT=$(cd "$HERE/../../../../.." && pwd)
OUT=/workspace/results/wk/ADAPT2
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
rm -f "$OUT/DONE"
WAIT_FOR=${WAIT_FOR:-/workspace/results/wk/ADAPT/DONE}
while [ ! -f "$WAIT_FOR" ]; do sleep 30; done
cd "$ROOT"
export ROYALE_RUNTIME=20261006-linux OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 CB_MAIN="$ROOT"
PY=${PY:-/workspace/venv/bin/python}
CK=icebow/data/bench/rl_royale
# Numbered exp1-3 are the final frozen weights already named in ADAPT's league.
# Serial stages: 20 actors/workers + learner, tracker, shell and flock holders
# leave headroom within the same <=28 process budget as ADAPT.
flock /workspace/gpu.lock flock /workspace/cpu.lock "$PY" "$HERE/driver.py" \
  --out "$OUT" --init "$CK/wk_adapt_main/wk_adapt_main_latest.pt" \
  --extra-exploiters "$CK/wk_adapt_exp1/wk_adapt_exp1_u0015.pt,$CK/wk_adapt_exp2/wk_adapt_exp2_u0015.pt,$CK/wk_adapt_exp3/wk_adapt_exp3_u0015.pt" \
  --cycles 3 --tag adapt2 > "$OUT/adaptive.log" 2>&1
