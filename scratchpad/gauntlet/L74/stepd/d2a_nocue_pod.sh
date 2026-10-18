#!/bin/bash
# Step d D2a (pod GPU, needs NO D1): owner decision 5 (10-18) puts the ~3x unfavourable-matchup weights into imitation, so the
# imitation runs all carry --row-weights (L74/stepd/row_weights.py, factor 3) and every comparison is made on THIS pod / torch:
#   IL-nocue-w s0 = the gen_v32_s0 recipe (L73/gen_v32/chain_b.sh) + --row-weights      (the cue run's exact twin, D2b)
#   IL-nocue-w s1 = the same, seed 1                                                  (seed noise of the weighted recipe)
# gen_v32_s0 (laptop RTX 5050, Windows torch, unweighted) stays the reference to the old line: IL-nocue-w s0 - gen_v32_s0 =
# weights + platform, NOT weights alone. Both runs go concurrently on the one GPU (dataset ~3 GB on GPU each).
set -euo pipefail
CB=${CB:-/workspace/cb_stepd}; PY=${PY:-/workspace/venvf36/bin/python}; OUT=${OUT:-/workspace/stepd/d2}
DATA=${DATA:-$CB/icebow/data/pipeline/gen_dataset_v32_fv5.npz}; W3=${W3:-/workspace/stepd/v32_w3.npy}
cd "$CB"; mkdir -p "$OUT"
export PYTHONPATH="$CB" OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1
R=.foreman/codex_autopilot/runs/public_context_v32_w4/artifact.json
COMMON="--data $DATA --epochs 4 --val-sample 30000 --grid lattice --feature-version 5 --amp bf16 --allow-causal-tti-unknowns \
 --rocket-context-weight 4.0 --rocket-context-artifact $R --row-weights $W3"
log() { echo "[d2a] $* $(date -u +%FT%TZ)" >> "$OUT/d2.log"; }
[ -f "$W3" ] || { $PY scratchpad/gauntlet/L74/stepd/row_weights.py --data "$DATA" --out "$W3" > "$OUT/weights.out" 2>&1; log "weights $(tail -1 $OUT/weights.out)"; }
log "IL-nocue-w s0 + s1 start"
for S in 0 1; do
  mkdir -p "$OUT/il_nocue_w_s$S"
  nice -n 5 $PY -u scratchpad/gauntlet/L69/gen_v2/_train_every_epoch.py $COMMON --seed $S --tag nocuew \
      --out-dir "$OUT/il_nocue_w_s$S" > "$OUT/il_nocue_w_s$S.out" 2>&1 &
  echo $! > "$OUT/il_nocue_w_s$S.pid"
done
wait
for S in 0 1; do
  [ -f "$OUT/il_nocue_w_s$S/gen_nocuew_s$S.pt" ] || { log "IL-nocue-w s$S FAILED"; exit 1; }
done
(cd "$OUT" && sha256sum il_nocue_w_s*/gen_nocuew_s*.pt) > "$OUT/SHA256SUMS_nocue"
log "done"; touch "$OUT/D2A_DONE"
