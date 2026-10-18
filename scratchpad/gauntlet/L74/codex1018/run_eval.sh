#!/bin/bash
# SIM only: frozen C3 code, fork36 runtime, CLIII and cue_ab2 on standard and fresh seeds.
set -Eeuo pipefail
BASE=/workspace/codex1018
CB=$BASE/cb
PY=$BASE/venv/bin/python
OUT=$BASE/results
mkdir -p "$OUT"
exec >> "$OUT/chain.log" 2>&1
trap 'echo "FAILED $(date -u +%FT%TZ) line $LINENO"; touch "$OUT/FAILED"' ERR
test -e "$BASE/SETUP_OK"
test -e /workspace/KEEP
cd "$CB"
export PYTHONPATH="$CB" ROYALE_RUNTIME=fork36-linux ROYALE_HEROIW_FORM=hero OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1
EXTRA='--habit-log --live-levels --card-levels Rocket=16 Log=15 --opp-tower-troops DaggerDuchess:0.028,Cannoneer:0.028,ChefTower:0.014 --record-plays --ability-stats'
echo "START $(date -u +%FT%TZ) pid $$"
for NAME in clIII_ref cue_ab2_sample cue_ab2; do
  CK=icebow/data/bench/rl_royale/rlarm_succ_levels/rlarm_succ_levels_u0065_grafted.pt
  X=$EXTRA
  if [ "$NAME" != clIII_ref ]; then
    CK=icebow/data/bench/rl_royale/rlarm_gae_cue_ab2/rlarm_gae_cue_ab2_u0065_grafted.pt
  fi
  if [ "$NAME" = cue_ab2_sample ]; then X="$X --ability-head-decode sample"; fi
  sha256sum "$CK" >> "$OUT/checkpoints.sha"
  for S in 741200 742000 743000 744000; do
    echo "EVAL $NAME $S $(date -u +%FT%TZ)"
    flock /workspace/cpu.lock "$PY" scratchpad/gauntlet/L74/gap/gap.py --ckpt "$CK" --out "$OUT/${NAME}_$S" --arms D3 --seed-start "$S" --runtime fork36-linux --python "$PY" --census-file scratchpad/gauntlet/L74/mix/decks_live_eval.json --workers 26 --extra="$X" > "$OUT/${NAME}_$S.log" 2>&1
  done
done
echo "ALL_DONE $(date -u +%FT%TZ)"
touch "$OUT/ALL_DONE" "$OUT/DONE"
