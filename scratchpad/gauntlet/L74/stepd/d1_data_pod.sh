#!/bin/bash
# Step d D1 (pod, CPU only): cue drive of every gen_dataset_v32_fv5 replay -> cue sidecar -> unfavourable-row weights.
# NOT RUN YET. Ships nothing, installs nothing. Needs on the pod (paths relative to $CB):
#   the repo at the step-d commit; icebow/data/pipeline/gen_dataset_v32_fv5.npz (466 MB; laptop sha256 in PLAN.md);
#   the crawl CSV dirs below (~130 MB, CSV only -- the 13 GB native corpus is NOT needed in this mode);
#   a runtime venv ($PY, $RT: fin13 once registered in pipeline/royale_runtime.py, else fork36-linux -- say which).
# Planning cost (b): ~11-13 s / replay on one laptop core -> 14,661 replays ~45-50 core-h -> ~2-2.5 h at 24 workers.
set -euo pipefail
CB=${CB:-/workspace/cb_stepd}; PY=${PY:-/workspace/venvf36/bin/python}; RT=${RT:-fork36-linux}; W=${WORKERS:-24}
OUT=${OUT:-/workspace/stepd/d1}; DATA=${DATA:-$CB/icebow/data/pipeline/gen_dataset_v32_fv5.npz}
cd "$CB"; mkdir -p "$OUT"
export ROYALE_RUNTIME=$RT OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
CR="scratchpad/gauntlet/L68/generalist/pilot/crawl scratchpad/gauntlet/ext/crawl_hf_icebow scratchpad/gauntlet/ext/crawl_hf_hogeq icebow/data/royaleapi/crawl2 hogeq/data/royaleapi/crawl2"
log() { echo "[d1] $* $(date -u +%FT%TZ)" >> "$OUT/d1.log"; }
log "start runtime=$RT data=$DATA"
# 0. ten replays, one worker: timing + sanity (fails fast; the full run skips what exists)
$PY scratchpad/gauntlet/L74/stepd/cue_drive.py --from-data "$DATA" --crawl $CR --out "$OUT/cues" --limit 10 \
    > "$OUT/drive_smoke.out" 2>&1 || { log "SMOKE FAILED"; exit 1; }
log "smoke ok"
# 1. the full drive (resumable)
$PY scratchpad/gauntlet/L74/stepd/cue_drive.py --from-data "$DATA" --crawl $CR --out "$OUT/cues" --workers "$W" \
    > "$OUT/drive.out" 2>&1 || { log "DRIVE FAILED"; exit 1; }
log "drive done"
# 2. the sidecar at the pre-registered bar (row Dice >= 0.9 on the dataset's own tokens + the per-token gate)
$PY scratchpad/gauntlet/L74/stepd/cue_sidecar.py --data "$DATA" --cues "$OUT/cues" --out "$OUT/v32_cue.npz" --min-fid 0.9 \
    > "$OUT/sidecar.out" 2>&1 || { log "SIDECAR FAILED"; exit 1; }
# 3. unfavourable-matchup weights (an IL run uses them only if told to: PLAN.md section c)
$PY scratchpad/gauntlet/L74/stepd/row_weights.py --data "$DATA" --out "$OUT/v32_w3.npy" > "$OUT/weights.out" 2>&1
sha256sum "$OUT/v32_cue.npz" "$OUT/v32_w3.npy" | sed 's/ \*/  /' > "$OUT/SHA256SUMS"
log "done"; touch "$OUT/D1_DONE"
