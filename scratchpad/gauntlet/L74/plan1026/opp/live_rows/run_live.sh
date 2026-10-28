#!/usr/bin/env bash
# V1-LIVEROWS full build on pod 33553 (resumable: every step skips finished logs / chunks; re-run while logs are still arriving).
#   bash run_live.sh [WORKERS_REC] [WORKERS_ROWS] [final]   -- 'final' also writes the npz dirs + the self-check summaries
set -euo pipefail
source "$(dirname "$0")/env.sh"
WR=${1:-32}; WW=${2:-16}
cd "$V1"
for B in train calibration; do
  LG="$V1/logs"; [ $B = calibration ] && [ -d "$V1/logs_cal" ] && LG="$V1/logs_cal"   # 2nd copy stream (calibration logs)
  nice -n 10 "$PY" "$LR/live_records.py" --logs "$LG" --out "$V1/rec" --block $B --workers "$WR"
  nice -n 10 "$PY" "$LR/live_rows.py" --rec "$V1/rec/$B" --src "$V1/src/$B" --logs "$LG" --workers "$WW"
done
if [ "${3:-}" = final ]; then
  mkdir -p "$V1/out"
  for B in train calibration; do
    rm -rf "$V1/out/live_$B" "$V1/out/live_${B}_memory.npz"
    nice -n 10 "$PY" "$LR/live_npz.py" --src "$V1/src/$B" --index "$V1/rec/$B/index.jsonl" --block $B --vocab "$OPP_VOCAB" \
      --deck-map "${DECKMAP:-$V1/hfmap_v1}" --out "$V1/out/live_$B"
  done
  "$PY" "$LR/selfcheck.py" summarize "$V1/src/train" "$V1/src/calibration" > "$V1/out/selfcheck.json"
  "$PY" "$LR/selfcheck.py" summarize "$V1/src/train" > "$V1/out/selfcheck_train.json"
  "$PY" "$LR/selfcheck.py" summarize "$V1/src/calibration" > "$V1/out/selfcheck_calibration.json"
fi
echo RUN_LIVE_DONE
