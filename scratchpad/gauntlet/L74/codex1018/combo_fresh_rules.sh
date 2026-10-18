#!/bin/bash
# SIM holdout for the existing combo-rule setting. Runs after the first follow-up.
set -Eeuo pipefail
RUN=${RUN:?combo arm required}
BASE=/workspace/codex1018_combo_fresh_rules
CB=/workspace/cb_combo
PY=/workspace/venvf36/bin/python
O=$BASE/results
mkdir -p "$O"
exec >> "$O/chain.log" 2>&1
trap 'echo "FAILED $(date -u +%FT%TZ) line $LINENO"; touch "$O/FAILED"' ERR
test -e /workspace/KEEP
echo "WAIT $RUN $(date -u +%FT%TZ) pid $$"
until [ -e /workspace/codex1018_combo_eval/results/DONE ]; do sleep 30; done
cd "$CB"
export PYTHONPATH="$CB" ROYALE_RUNTIME=fork36-linux ROYALE_HEROIW_FORM=hero OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1
EV='--habit-log --live-levels --card-levels Rocket=16 Log=15 --opp-tower-troops DaggerDuchess:0.028,Cannoneer:0.028,ChefTower:0.014 --spell-log --record-plays'
COMBO='--log-air block --rocket-value 9 --rocket-value-mode damage --rocket-value-hitbox edge --rocket-tornado only --tornado-river full --rocket-tornado-window measured --rocket-tornado-order either --rocket-tornado-lone combo'
RL=icebow/data/bench/rl_royale
eval_one() {
  local N=$1 C=$2 S=$3
  echo "EVAL $N $S $(date -u +%FT%TZ)"
  sha256sum "$C" >> "$O/checkpoints.sha"
  flock /workspace/cpu.lock "$PY" scratchpad/gauntlet/L74/gap/gap.py --ckpt "$C" --out "$O/${N}_$S" --arms D3 --seed-start "$S" --runtime fork36-linux --python "$PY" --census-file scratchpad/gauntlet/L74/mix/decks_live_eval.json --workers 26 --extra="$EV $COMBO" > "$O/${N}_$S.log" 2>&1
}
if [ "$RUN" = combo_rew_c3 ]; then
  for S in 743000 744000; do eval_one clIII_ref_offc "$RL/rlarm_succ_levels/rlarm_succ_levels_u0065_grafted.pt" "$S"; done
fi
for S in 743000 744000; do eval_one "$RUN" "$RL/rlarm_$RUN/rlarm_${RUN}_u0065_grafted.pt" "$S"; done
echo "ALL_DONE $(date -u +%FT%TZ)"
touch "$O/ALL_DONE" "$O/DONE"
