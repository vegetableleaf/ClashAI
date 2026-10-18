#!/bin/bash
# Step d D2 (pod GPU): the two imitation runs on IDENTICAL rows, then the paired IL gate. NOT RUN YET.
#   IL-cue  s0 = the gen_v32_s0 recipe (L73/gen_v32/chain_b.sh) + --cue-data   (ONE change vs gen_v32_s0)
#   IL-nocue s1 = the same recipe, seed 1, no cues                            (seed noise of the recipe)
# Needs D1_DONE ($D1/v32_cue.npz), gen_v32_s0/gen_s0.pt (61011b6c...) and the v32 rocket-context artifact
# (.foreman/codex_autopilot/runs/public_context_v32_w4/: artifact.json + probability.npy + classifier.pt).
set -euo pipefail
CB=${CB:-/workspace/cb_stepd}; PY=${PY:-/workspace/venvf36/bin/python}; D1=${D1:-/workspace/stepd/d1}
OUT=${OUT:-/workspace/stepd/d2}; DATA=${DATA:-$CB/icebow/data/pipeline/gen_dataset_v32_fv5.npz}
cd "$CB"; mkdir -p "$OUT"
[ -f "$D1/D1_DONE" ] || { echo "no D1_DONE"; exit 1; }
R=.foreman/codex_autopilot/runs/public_context_v32_w4/artifact.json
COMMON="--data $DATA --epochs 4 --val-sample 30000 --grid lattice --feature-version 5 --amp bf16 --allow-causal-tti-unknowns \
 --rocket-context-weight 4.0 --rocket-context-artifact $R"
log() { echo "[d2] $* $(date -u +%FT%TZ)" >> "$OUT/d2.log"; }
log "IL-cue s0 start"
$PY -u scratchpad/gauntlet/L69/gen_v2/_train_every_epoch.py $COMMON --seed 0 --tag cue --cue-data "$D1/v32_cue.npz" \
    --out-dir "$OUT/il_cue" > "$OUT/il_cue.out" 2>&1
log "IL-nocue s1 start"
$PY -u scratchpad/gauntlet/L69/gen_v2/_train_every_epoch.py $COMMON --seed 1 --tag nocue --out-dir "$OUT/il_nocue" \
    > "$OUT/il_nocue.out" 2>&1
log "compare"
$PY scratchpad/gauntlet/L74/stepd/il_compare.py --data "$DATA" --cue-data "$D1/v32_cue.npz" \
    --ckpt cue="$OUT/il_cue/gen_cue_s0.pt" --ckpt v32=icebow/data/pipeline/gen_v32_s0/gen_s0.pt \
    --ckpt nocue1="$OUT/il_nocue/gen_nocue_s1.pt" --pairs cue:v32 nocue1:v32 cue:nocue1 \
    --out "$OUT/il_compare.json" > "$OUT/il_compare.out" 2>&1
sha256sum "$OUT"/il_cue/gen_cue_s0.pt "$OUT"/il_nocue/gen_nocue_s1.pt | sed 's/ \*/  /' > "$OUT/SHA256SUMS"
log "done"; touch "$OUT/D2_DONE"
