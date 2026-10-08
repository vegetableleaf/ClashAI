#!/bin/bash
# Per-candidate chain (laptop GPU, one job at a time): fetch the candidate from the VM, barrel branch (fv6, frozen base),
# CellRefine v2 on top (both frozen except the module), offline checks, push both checkpoints to the VM and start the
# 192-game SIM A/Bs there.   cand.sh NAME VM_RELPATH   e.g. cand.sh r3c_u0030 icebow/data/bench/rl_royale/rseries_r3c/rseries_r3c_u0030.pt
set -e
NAME=$1; REL=$2
HERE="$(cd "$(dirname "$0")" && pwd)"; WT="$(cd "$HERE/../../../.." && pwd)"
PY=/c/Users/benpe/ClashBot/icebow/.venv/Scripts/python.exe
DATA=/c/Users/benpe/ClashBot/icebow/data/pipeline/gen_dataset_v32_fv5.npz
VM=clashbot-gauntlet@34.148.91.90; KEY=~/.ssh/clashbot_gcp
DIR=/c/Users/benpe/ClashBot/$(dirname "$REL"); BASE=/c/Users/benpe/ClashBot/$REL; STEM=$(basename "$REL" .pt)
OUT="$HERE/cand_$NAME"; mkdir -p "$OUT" "$DIR"
log() { echo "[cand $NAME] $* $(date '+%F %T')" | tee -a "$OUT/chain.log"; }
[ -f "$BASE" ] || scp -i $KEY "$VM:ClashBot/$REL" "$BASE"
log "fetched $(sha256sum "$BASE" | cut -c1-16)"
cd "$WT"
while [ -f "$HERE/gpu.lock" ]; do sleep 20; done          # another GPU job (gen_s0 extra) is running
$PY scratchpad/gauntlet/L73/barrel_branch/train_branch.py --base "$BASE" --data "$DATA" --out-dir "$DIR/barrel_$STEM" --updates ${BARREL_UPDATES:-2000} --device cuda > "$OUT/barrel.out" 2>&1 || log "barrel checks FAILED (see barrel.out)"
cp "$DIR/barrel_$STEM/result.json" "$OUT/barrel_result.json"
BAR="$DIR/${STEM}_barrel.pt"; cp "$DIR/barrel_$STEM/gen_branch_s0.pt" "$BAR"
log "barrel done: $(grep RESULT "$OUT/barrel.out")"
scp -i $KEY "$BAR" "$VM:ClashBot/$(dirname "$REL")/"
ssh -i $KEY $VM "cd ~/ClashBot && export SIM_EXTRA=\"--opp-policy sample --opp-T 0.3\" && (~/cellref_sim.sh ${NAME}_v2base $REL; ~/cellref_sim.sh ${NAME}_barrel $(dirname "$REL")/${STEM}_barrel.pt) > /dev/null 2>&1 < /dev/null &"
log "SIM A/Bs started on the VM (base, barrel; sequential)"
$PY -m pipeline.train_cell_refine --base "$BAR" --data "$DATA" --epochs ${EPOCHS:-2} --channels 48 --layers 5 --out "$DIR/${STEM}_barrel_cellref5.pt" > "$OUT/cellref.out" 2> "$OUT/cellref.err"
REF="$DIR/${STEM}_barrel_cellref5.pt"
log "cellref done: $(grep '"done"' "$OUT/cellref.out")"
scp -i $KEY "$REF" "$VM:ClashBot/$(dirname "$REL")/"
ssh -i $KEY $VM "cd ~/ClashBot && export SIM_EXTRA=\"--opp-policy sample --opp-T 0.3\" && (~/cellref_sim.sh ${NAME}_barrel_cellref5 $(dirname "$REL")/${STEM}_barrel_cellref5.pt) > /dev/null 2>&1 < /dev/null &"
log "SIM A/B started on the VM (barrel+cellref5)"
(cd scratchpad/gauntlet/L73/barrel_lane && CUDA_VISIBLE_DEVICES= $PY model_counterfactual.py --data "$DATA" --out "$OUT/cf.json" --ckpt base="$BASE" --ckpt barrel="$BAR" --ckpt barrel_cellref5="$REF" > "$OUT/cf.out" 2>&1)
log "counterfactual done"
$PY scratchpad/gauntlet/L73/centre_col/offline_eval.py "$OUT/offline.json" "$BASE" "$BAR" "$REF" > "$OUT/offline.out" 2> "$OUT/offline.err"
$PY scratchpad/gauntlet/L73/centre_col/table.py "$OUT/offline.json" > "$OUT/offline_table.txt"
log "CAND_DONE"
