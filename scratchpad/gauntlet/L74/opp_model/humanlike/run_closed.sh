#!/usr/bin/env bash
# run_closed.sh NAME OUTROOT SEED [SEED ...] -- P2-SCORE closed-loop rows for the scorecard (pod): CLXIII (the fixed live Mark)
# vs one opponent on crforge, gap.py D3 (LIVE_OPTIONS stack, live census, all16 levels), G2 handicap on, --record-board (both
# sides' plays at x, y + 1-s board: towers, enemy bodies, own X-Bows) + --habit-log + --crown-log. 480 games per seed block.
# env: OPP_CKPT (unset = E4, gap.py's default) OPP_T (0.1) OPP_EXTRA (extra decision flags for the opponent, e.g. I u40's
#      "--opp-decide-every 20 --opp-tau 0.2") CB (code copy) LIB (crforge build dir with lib/ + BUILD.json) PY WORKERS CPUS
# Writes OUTROOT/NAME_SEED/D3/matches.jsonl and OUTROOT/ENGINE.json (crforge build, facade sha, tables, code head, G2).
set -euo pipefail
NAME=$1; OUT=$2; shift 2
CB=${CB:-/workspace/score/cb}; LIB=$(readlink -f "${LIB:-/workspace/crforge_main/a677e080/plain}")
PY=${PY:-/workspace/venvf16/bin/python}; W=${WORKERS:-40}; CPUS=${CPUS:-0-255}
TABLES=${CRFORGE_TABLES:-/workspace/crforge_cache/tables/16.402.22}
FAC=$OUT/facade
G=icebow/data/models/ICEBOW/ICEBOW_Mark_CLXIII_NOLEAK.pt
G2="--tap-loss 1x:0.0180,2x:0.0363,ot2x:0.0388,ot3x:0.0890 --tap-slow 0.151:17"        # o4_gate v2 G2 (W18 measured)
mkdir -p "$OUT"
if [ ! -f "$FAC/CfCore.class" ]; then
  mkdir -p "$FAC" && cp "$CB/scratchpad/gauntlet/L74/crforge/facade/CfCore.java" "$FAC/" && javac -nowarn -cp "$LIB/lib/*" -d "$FAC" "$FAC/CfCore.java"
fi
cd "$CB"
cat > "$OUT/ENGINE.json" <<EOF
{"engine": "crforge", "build": $(cat "$LIB/BUILD.json"), "lib": "$LIB", "tables": "$TABLES",
 "facade_sha256": "$(sha256sum "$FAC/CfCore.java" | cut -c1-64)", "code_head": "$(cat CODE_HEAD 2>/dev/null || echo unknown)",
 "learner_sha256": "$(sha256sum $G | cut -c1-64)", "opp_ckpt": "${OPP_CKPT:-E4}", "opp_T": "${OPP_T:-0.1}",
 "opp_extra": "${OPP_EXTRA:-}", "g2": "$G2"}
EOF
unset ROYALE_HEROIW_PRESS
export HABITS_REC=1 PYTHONPATH=$CB:/workspace/cfspeed/pylib ROYALE_HEROIW_FORM=hero OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 \
  PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1 ROYALE_ENGINE=crforge ROYALE_RUNTIME=fin16-linux CRFORGE_LIB=$LIB/lib \
  CRFORGE_TABLES=$TABLES CRFORGE_FACADE_BUILD=$FAC CRFORGE_XMX=${CRFORGE_XMX:-1g} \
  JAVA_TOOL_OPTIONS="-XX:+UseSerialGC -XX:ActiveProcessorCount=1"
EX="--habit-log --live-levels --card-levels Rocket=16 Log=15 --ability-stats --ability-head-decode=sample --crown-log --record-board $G2"
OA=(); [ -n "${OPP_CKPT:-}" ] && OA=(--opp-ckpt "$OPP_CKPT" --opp-T "${OPP_T:-0.1}")
for S in "$@"; do
  D=$OUT/${NAME}_$S
  [ "$(grep -c '"outcome"' $D/D3/matches.jsonl 2>/dev/null)" = 480 ] && continue
  rm -rf "$D"; echo "$(date -u +%FT%TZ) $NAME $S start"
  nice -n 10 taskset -c $CPUS "$PY" scratchpad/gauntlet/L74/gap/gap.py --ckpt $G --out "$D" --arms D3 --seed-start $S \
    --runtime fin16-linux --python "$PY" --census-file scratchpad/gauntlet/L74/mix/decks_live_eval.json --workers $W \
    --levels all16 "${OA[@]}" --extra="$EX ${OPP_EXTRA:-}" > "$D.log" 2>&1 < /dev/null || echo "GAP EXIT $? $NAME $S"
  echo "$(date -u +%FT%TZ) $NAME $S rows $(grep -c '"outcome"' $D/D3/matches.jsonl 2>/dev/null)"
done
echo "$(date -u +%FT%TZ) CLOSED DONE $NAME"
