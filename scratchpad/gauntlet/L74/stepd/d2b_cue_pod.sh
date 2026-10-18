#!/bin/bash
# Step d D2b (pod GPU, after D1_DONE + D2A_DONE): IL-cue-w s0 = IL-nocue-w s0 (d2a_nocue_pod.sh) + --cue-data, ONE change; it is
# REB's init. Then the paired IL gate (il_compare.py, CI by val match) over all four checkpoints:
#   cuew:nocuew0     the cue effect (pre-registered: cue-attached val rows; "helps" = a CI excluding 0 beyond the seed noise)
#   nocuew1:nocuew0  seed noise of the weighted recipe
#   nocuew0:v32      weights + platform vs the old line;   cuew:v32  the new base vs the old line
set -euo pipefail
CB=${CB:-/workspace/cb_stepd}; PY=${PY:-/workspace/venvf36/bin/python}; D1=${D1:-/workspace/stepd/d1}; OUT=${OUT:-/workspace/stepd/d2}
DATA=${DATA:-$CB/icebow/data/pipeline/gen_dataset_v32_fv5.npz}; W3=${W3:-/workspace/stepd/v32_w3.npy}
cd "$CB"; mkdir -p "$OUT"
[ -f "$D1/D1_DONE" ] || { echo "no D1_DONE"; exit 1; }
export PYTHONPATH="$CB" OMP_NUM_THREADS=4 MKL_NUM_THREADS=4 PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1
R=.foreman/codex_autopilot/runs/public_context_v32_w4/artifact.json
COMMON="--data $DATA --epochs 4 --val-sample 30000 --grid lattice --feature-version 5 --amp bf16 --allow-causal-tti-unknowns \
 --rocket-context-weight 4.0 --rocket-context-artifact $R --row-weights $W3"
log() { echo "[d2b] $* $(date -u +%FT%TZ)" >> "$OUT/d2.log"; }
log "IL-cue-w s0 start"
mkdir -p "$OUT/il_cue_w_s0"
$PY -u scratchpad/gauntlet/L69/gen_v2/_train_every_epoch.py $COMMON --seed 0 --tag cuew --cue-data "$D1/v32_cue.npz" \
    --out-dir "$OUT/il_cue_w_s0" > "$OUT/il_cue_w_s0.out" 2>&1 || { log "IL-cue-w s0 FAILED"; exit 1; }
log "IL-cue-w s0 done"
[ -f "$OUT/D2A_DONE" ] || { log "waiting for D2A_DONE"; while [ ! -f "$OUT/D2A_DONE" ]; do sleep 60; done; }
log "compare"
$PY scratchpad/gauntlet/L74/stepd/il_compare.py --data "$DATA" --cue-data "$D1/v32_cue.npz" \
    --ckpt cuew="$OUT/il_cue_w_s0/gen_cuew_s0.pt" --ckpt nocuew0="$OUT/il_nocue_w_s0/gen_nocuew_s0.pt" \
    --ckpt nocuew1="$OUT/il_nocue_w_s1/gen_nocuew_s1.pt" --ckpt v32=icebow/data/pipeline/gen_v32_s0/gen_s0.pt \
    --pairs cuew:nocuew0 nocuew1:nocuew0 nocuew0:v32 cuew:v32 --out "$OUT/il_compare.json" > "$OUT/il_compare.out" 2>&1
(cd "$OUT" && sha256sum il_cue_w_s0/gen_cuew_s0.pt) > "$OUT/SHA256SUMS_cue"
log "done"; touch "$OUT/D2_DONE"
