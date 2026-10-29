#!/bin/bash
# OPP-LEARN-C calibration eval (pod): every saved checkpoint of a calibration run that has no rows yet -> one 480-game
# closed-loop block of CLXIII (gap.py D3 = the live stack, as level B) vs it (opponent T 1 = its imitation temperature),
# rows OUTROOT/NAME_uNNNN/NAME_uNNNN_SEED/ (+ ENGINE.json). Score on the laptop (THRESHOLDS v6, quick stats; sealed block never
# opened):
#   card.py score --name NAME_uNNNN --sim LOCAL_ROWS/NAME_uNNNN --no-c --no-d --out OUT/NAME_uNNNN
# usage: calib_eval.sh CKPT_DIR NAME OUTROOT [SEED] [EVERY]   (SEED default 741200 = level B's first block, paired with
# v0fix / v1s0; EVERY default 5 = the run's save_every; loops until CKPT_DIR/STOP_EVAL exists, polling every 120 s)
# env as run_closed.sh: CB LIB WORKERS CPUS G2_ON (default on = level B v0fix / v1s0's setting).
set -uo pipefail
CK=$1; NAME=$2; OUT=$3; SEED=${4:-741200}; EVERY=${5:-5}
H=$(dirname "$(readlink -f "$0")")/../../../opp_model/humanlike
export G2_ON=${G2_ON:-on} OPP_T=1.0
while [ ! -f "$CK/STOP_EVAL" ]; do
  for P in $(ls "$CK"/${NAME}_u[0-9][0-9][0-9][0-9].pt 2>/dev/null | sort); do
    U=$(basename "$P" .pt); U=${U##*_u}
    [ $((10#$U % EVERY)) = 0 ] || continue
    D=$OUT/${NAME}_u$U
    [ "$(grep -c '"outcome"' $D/${NAME}_u${U}_$SEED/D3/matches.jsonl 2>/dev/null)" = 480 ] && continue
    OPP_CKPT=$P bash "$H/run_closed.sh" ${NAME}_u$U "$D" $SEED
  done
  sleep 120
done
echo "$(date -u +%FT%TZ) CALIB EVAL STOP $NAME"
