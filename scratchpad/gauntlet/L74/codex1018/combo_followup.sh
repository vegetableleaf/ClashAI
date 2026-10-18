#!/bin/bash
# Complete the existing combo candidate's CLIII comparison. SIM only; no stop/deploy actions.
set -Eeuo pipefail
RUN=${RUN:?combo arm required}
BASE=/workspace/codex1018_combo_eval
CB=/workspace/cb_combo
PY=/workspace/venvf36/bin/python
O=$BASE/results
mkdir -p "$O"
exec >> "$O/chain.log" 2>&1
trap 'echo "FAILED $(date -u +%FT%TZ) line $LINENO"; touch "$O/FAILED"' ERR
test -e /workspace/KEEP
echo "WAIT $RUN $(date -u +%FT%TZ) pid $$"
until [ -e /workspace/combo/runs/$RUN/DONE ]; do sleep 30; done
cd "$CB"
export PYTHONPATH="$CB" ROYALE_RUNTIME=fork36-linux ROYALE_HEROIW_FORM=hero OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1
EV='--habit-log --live-levels --card-levels Rocket=16 Log=15 --opp-tower-troops DaggerDuchess:0.028,Cannoneer:0.028,ChefTower:0.014 --spell-log --record-plays'
COMBO='--log-air block --rocket-value 9 --rocket-value-mode damage --rocket-value-hitbox edge --rocket-tornado only --tornado-river full --rocket-tornado-window measured --rocket-tornado-order either --rocket-tornado-lone combo'
RL=icebow/data/bench/rl_royale
BASELINE=$RL/rlarm_succ_levels/rlarm_succ_levels_u0065_grafted.pt
CK=$RL/rlarm_$RUN/rlarm_${RUN}_u0065_grafted.pt
eval_one() {
  local N=$1 C=$2 S=$3 EXTRA=$4
  echo "EVAL $N $S $(date -u +%FT%TZ)"
  sha256sum "$C" >> "$O/checkpoints.sha"
  flock /workspace/cpu.lock "$PY" scratchpad/gauntlet/L74/gap/gap.py --ckpt "$C" --out "$O/${N}_$S" --arms D3 --seed-start "$S" --runtime fork36-linux --python "$PY" --census-file scratchpad/gauntlet/L74/mix/decks_live_eval.json --workers 26 --extra="$EXTRA" > "$O/${N}_$S.log" 2>&1
}
if [ "$RUN" = combo_ctl_c3 ]; then
  for S in 741200 742000 743000 744000; do eval_one clIII_ref "$BASELINE" "$S" "$EV"; done
fi
for S in 743000 744000; do eval_one "$RUN" "$CK" "$S" "$EV"; done
if [ "$RUN" = combo_rew_c3 ]; then
  for S in 741200 742000; do eval_one clIII_ref_offc "$BASELINE" "$S" "$EV $COMBO"; done
fi
echo "ALL_DONE $(date -u +%FT%TZ)"
touch "$O/ALL_DONE" "$O/DONE"
