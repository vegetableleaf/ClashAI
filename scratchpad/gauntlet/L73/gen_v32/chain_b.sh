#!/bin/bash
# gen_v3.2 chain resume (lead 21:2x): chain.sh stopped at CONTEXT FIT FAILED (fit_public_context.py accepted fv4 only; now fv4|fv5).
cd /c/Users/benpe/ClashBot; G=scratchpad/gauntlet/L73/gen_v32; LOG=$G/chain.log
log() { echo "[v32] $* $(date '+%F %T')" >> $LOG; }
R=.foreman/codex_autopilot/runs
research/ext/Royale/.venv/Scripts/python.exe scratchpad/gauntlet/L70/gen_v31/fit_public_context.py --data icebow/data/pipeline/gen_dataset_v32_fv5.npz \
  --labels $R/public_labels_full_reconstructed/labels.jsonl --rulings .foreman/codex_autopilot/LEAD_RULINGS.md \
  --xbow-validation scratchpad/gauntlet/L70/gen_v31/xbow_reach_public.json --out $R/public_context_v32 > $G/fit_context.out 2>&1 || { log "CONTEXT FIT FAILED"; exit 1; }
mkdir -p $R/public_context_v32_w4 && cp $R/public_context_v32/{classifier.pt,heldout_report.json,probability.npy} $R/public_context_v32_w4/
python - <<'PY'
import json
a=json.load(open('.foreman/codex_autopilot/runs/public_context_v32/artifact.json')); a['selected_weight']=4.0
a['weight_selection']='lead 2026-10-06: gen_v3.2 keeps gen_v3.1c weight 4.0 (owner asked; 2x->4x measured no Rocket-share change but best overall); only this field differs from public_context_v32'
json.dump(a,open('.foreman/codex_autopilot/runs/public_context_v32_w4/artifact.json','w'),indent=2)
PY
log "context refit done; train start"
icebow/.venv/Scripts/python.exe -u scratchpad/gauntlet/L69/gen_v2/_train_every_epoch.py --data icebow/data/pipeline/gen_dataset_v32_fv5.npz --seed 0 --epochs 4 --val-sample 30000 --grid lattice --feature-version 5 --amp bf16 --allow-causal-tti-unknowns --rocket-context-weight 4.0 --rocket-context-artifact $R/public_context_v32_w4/artifact.json --out-dir icebow/data/pipeline/gen_v32_s0 > $G/train.out 2>&1
log "train exit $?"
