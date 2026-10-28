#!/bin/bash
# RX-X23 SIM runs (X2 farm audit / X3 SIM calibration) = d2g/gate.sh's command (gap.py D3: deployed LIVE_OPTIONS stack, all16,
# live census, gate EX flags) + the gate's opponent tower troops, on crforge, worker = sim_worker.py (policy + recorder).
#   run_x23.sh job TAG POLICY MODE CPUS WORKERS SEED [CKPT]     one 480-game block -> $X23_ROOT/ev/TAG
#   run_x23.sh lane QUEUE CPUS WORKERS                         pops "TAG POLICY MODE SEED [CKPT]" lines from QUEUE (flock)
# MODE e4 | iu40 (gate.sh's opponents). Env (pod paths): X23_ROOT (/workspace/rx23: cb/ = code, lib/{lib,facade}, simcards.json),
# X23_PYLIB, X23_TABLES.
R=${X23_ROOT:-/workspace/rx23}
if [ "$1" = lane ]; then
  Q=$2; CPUS=$3; W=$4
  while true; do
    L=$(flock "$Q.lock" sh -c "head -1 '$Q'; sed -i 1d '$Q'")
    [ -z "$L" ] && break
    set -- $L
    bash "$0" job "$1" "$2" "$3" "$CPUS" "$W" "$4" "${5:-}"
  done
  echo "$(date -u +%FT%TZ) LANE DONE $Q $CPUS"; exit 0
fi
[ "$1" = job ] || { echo "usage: run_x23.sh job|lane ..."; exit 2; }
TAG=$2; POL=$3; MODE=$4; CPUS=$5; W=$6; S=$7; G=${8:-icebow/data/models/ICEBOW/ICEBOW_Mark_CLXIII_NOLEAK.pt}
CB=$R/cb; PYX=/workspace/venvf16/bin/python
cd $CB || exit 1
unset ROYALE_HEROIW_PRESS
export X23_POLICY=$POL HABITS_REC=1 PYTHONPATH=$CB:$X23_PYLIB ROYALE_HEROIW_FORM=hero OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 \
  PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1 O3_PLAYS=1 ROYALE_ENGINE=crforge ROYALE_RUNTIME=fin16-linux \
  CRFORGE_LIB=$R/lib/lib CRFORGE_FACADE_BUILD=$R/lib/facade CRFORGE_TABLES=$X23_TABLES CRFORGE_XMX=1500m \
  JAVA_TOOL_OPTIONS="-XX:+UseSerialGC -XX:ActiveProcessorCount=1" \
  RX_CATALOG=$CB/research/ext/cr-native-sandbox/native_core/data/live_card_catalog.json RX_STATS=$CB/icebow/config/cards_stats.json \
  RX_SIMCARDS=$R/simcards.json
EX="--habit-log --live-levels --card-levels Rocket=16 Log=15 --ability-stats --ability-head-decode=sample --crown-log"
EX="$EX --opp-tower-troops DaggerDuchess:0.028,Cannoneer:0.028,ChefTower:0.014"
OA=(); XF=""
if [ "$MODE" = iu40 ]; then
  OA=(--opp-ckpt icebow/data/pipeline/o2/w14opp_I.pt --opp-T 0.1 --opp-decide-every 40); XF="--opp-decide-every 20 --opp-tau 0.2"
fi
D=$R/ev/$TAG
[ "$(grep -c '"outcome"' $D/D3/matches.jsonl 2>/dev/null)" = 480 ] && exit 0
rm -rf $D; mkdir -p $(dirname $D); echo "$(date -u +%FT%TZ) $TAG start $(sha256sum $G | cut -c1-16)"
taskset -c $CPUS "$PYX" scratchpad/gauntlet/L74/plan1026/rx/x23/run_x23.py --ckpt $G --out $D --arms D3 --seed-start $S \
  --runtime fin16-linux --python "$PYX" --census-file scratchpad/gauntlet/L74/mix/decks_live_eval.json --workers $W \
  --levels all16 "${OA[@]}" --extra="$EX $XF" > $D.log 2>&1 < /dev/null || echo "GAP EXIT $? $TAG"
echo "$(date -u +%FT%TZ) $TAG rows $(grep -c '"outcome"' $D/D3/matches.jsonl 2>/dev/null)"
