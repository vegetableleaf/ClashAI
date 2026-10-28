#!/usr/bin/env bash
# sweep.sh LIST [SEED ...] -- V1-STRENGTH driver on 33553: for each line "NAME CKPT T" of LIST run humanlike/run_closed.sh (CLXIII vs the
# opponent, crforge fe364ceb, tables 16.635.3, G2 off, barrel-decoy SIM on) into ROWS/NAME for each seed block (480 games each; a
# finished block is skipped, an unfinished one is redone).  env: WORKERS (12) CPUS (0-27) ROWS (/workspace/strength/rows) CB LIB PY
# Restart = the same command (resumable).  Several drivers can run at once only on disjoint CPUS.
set -uo pipefail
LIST=$1; shift
SEEDS=${*:-741200}
HERE=$(cd "$(dirname "$0")" && pwd)
export CB=${CB:-/workspace/strength/cb} PY=${PY:-/workspace/venv/bin/python} CPUS=${CPUS:-0-27} WORKERS=${WORKERS:-12} \
  CRFORGE_TABLES=${CRFORGE_TABLES:-/workspace/crforge_cache/tables/16.635.3} CRFORGE_BARREL_DECOY_SIM=1
ROWS=${ROWS:-/workspace/strength/rows}
mkdir -p "$ROWS"
while read -r NAME CKPT T; do
  case "$NAME" in ""|\#*) continue;; esac
  echo "$(date -u +%FT%TZ) SETTING $NAME $CKPT T=$T seeds $SEEDS"
  OPP_CKPT=$CKPT OPP_T=$T bash "$CB/scratchpad/gauntlet/L74/opp_model/humanlike/run_closed.sh" "$NAME" "$ROWS/$NAME" $SEEDS
done < "$LIST"
echo "$(date -u +%FT%TZ) SWEEP DONE $LIST"
