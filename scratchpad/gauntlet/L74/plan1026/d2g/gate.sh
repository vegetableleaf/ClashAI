#!/bin/bash
# gate.sh ENGINE TAG MODE CPUS WORKERS SEED... -- D2-G CLXIII re-baseline: push_cal/gate_eval.sh's command (gap.py D3, all16, live
# census, LIVE_OPTIONS decision stack) on fin16-linux with ROYALE_ENGINE=ENGINE. MODE e4 | iu40. Tower troops dropped (the crforge
# facade refuses them) on BOTH engines; --record-plays / --record-board dropped (output only).
E=$1; TAG=$2; MODE=$3; CPUS=$4; W=$5; shift 5
CB=/workspace/d2/cb; PYX=/workspace/venvf16/bin/python; G=icebow/data/models/ICEBOW/ICEBOW_Mark_CLXIII_NOLEAK.pt
cd $CB || exit 1
unset ROYALE_HEROIW_PRESS
export HABITS_REC=1 PYTHONPATH=$CB:/workspace/d2/stage/pylib ROYALE_HEROIW_FORM=hero OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 \
  PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1 O3_PLAYS=1 ROYALE_ENGINE=$E ROYALE_RUNTIME=fin16-linux \
  CRFORGE_LIB=/workspace/d2/stage/lib CRFORGE_TABLES=/workspace/crforge_cache/tables/16.402.22 CRFORGE_FACADE_BUILD=/workspace/d2/build
EX="--habit-log --live-levels --card-levels Rocket=16 Log=15 --ability-stats --ability-head-decode=sample --crown-log"
OA=(); XF=""
if [ "$MODE" = iu40 ]; then
  OA=(--opp-ckpt icebow/data/pipeline/o2/w14opp_I.pt --opp-T 0.1 --opp-decide-every 40); XF="--opp-decide-every 20 --opp-tau 0.2"
fi
sha256sum $G
for S in "$@"; do
  D=/workspace/d2/ev/$TAG/${TAG}_${S}
  [ "$(grep -c '"outcome"' $D/D3/matches.jsonl 2>/dev/null)" = 480 ] && continue
  rm -rf $D; mkdir -p $(dirname $D); echo "$(date -u +%FT%TZ) $TAG $S start"
  taskset -c $CPUS "$PYX" scratchpad/gauntlet/L74/gap/gap.py --ckpt $G --out $D --arms D3 --seed-start $S --runtime fin16-linux \
    --python "$PYX" --census-file scratchpad/gauntlet/L74/mix/decks_live_eval.json --workers $W --levels all16 "${OA[@]}" \
    --extra="$EX $XF" > $D.log 2>&1 < /dev/null || echo "GAP EXIT $? $TAG $S"
  echo "$(date -u +%FT%TZ) $TAG $S rows $(grep -c '"outcome"' $D/D3/matches.jsonl 2>/dev/null)"
done
echo "$(date -u +%FT%TZ) GATE DONE $TAG"
