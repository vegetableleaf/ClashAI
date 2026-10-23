#!/bin/bash
# gate_eval.sh QUEUE -- PUSH_CAL gate run (pod 32525): board-recorded CLX evals vs an opponent setting, scored by
# push_cal.py. = exploit/ev.sh's command (D3, all16, live census, same EXTRA + --record-board) with per-line extra flags.
# Queue line: TAG|MODE|EXTRA_FLAGS|SEED...   MODE e4 | iu40 (W14 I u40, T .1, decide 40). Writes only /workspace/pushcal/ev.
set -uo pipefail
CB=/workspace/cb_stepd; PYB=/workspace/venvf15/bin/python; X=/workspace/pushcal
G=/workspace/ckev/ckpt/rlarm_stepd_ctrl_nos2_u0130_grafted.pt          # CLX (5d212358), as clx_rb
OPP=$CB/icebow/data/pipeline/o2/w14opp_I.pt
cd $CB || exit 1
unset ROYALE_HEROIW_PRESS
export HABITS_REC=1 PYTHONPATH=$CB ROYALE_HEROIW_FORM=hero OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1 O3_PLAYS=1
EX="--habit-log --live-levels --card-levels Rocket=16 Log=15 --opp-tower-troops DaggerDuchess:0.028,Cannoneer:0.028,ChefTower:0.014 --record-plays --ability-stats --ability-head-decode=sample --crown-log --record-board"
log() { echo "$(date -u +%FT%TZ) $*"; }
sha256sum $G $OPP
exec 9>/workspace/cpu.lock; flock 9
while IFS='|' read -r TAG MODE XF SEEDS; do
  [ -z "$TAG" ] && continue
  OA=(); [ "$MODE" = iu40 ] && OA=(--opp-ckpt $OPP --opp-T 0.1 --opp-decide-every 40)
  for S in $SEEDS; do
    D=$X/ev/$TAG/${TAG}_${S}; [ "$(grep -c '"outcome"' $D/D3/matches.jsonl 2>/dev/null)" = 480 ] && continue
    mkdir -p $(dirname $D); log "$TAG $MODE $S start ($XF)"
    ROYALE_RUNTIME=fin15-linux "$PYB" scratchpad/gauntlet/L74/gap/gap.py --ckpt $G --out $D --arms D3 --seed-start $S \
      --runtime fin15-linux --python "$PYB" --census-file scratchpad/gauntlet/L74/mix/decks_live_eval.json --workers ${WORKERS:-48} \
      --levels all16 "${OA[@]}" --extra="$EX $XF" > $D.log 2>&1 < /dev/null || log "GAP EXIT $? $TAG $S"
    log "$TAG $MODE $S rows $(grep -c '"outcome"' $D/D3/matches.jsonl 2>/dev/null)"
  done
done < $1
log "QUEUE DONE $1"
