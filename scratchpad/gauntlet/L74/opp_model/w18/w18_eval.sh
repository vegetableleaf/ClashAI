#!/bin/bash
# W18 SIM eval on the dedicated pod (pod-local; DIAG_12.md): opp_model/pod/opp_eval_fin15.sh's recipe (gap.py arm D3, fin15,
# all16, crown log, o3_plays telemetry) with three changes, all opt-in:
#   W18_EXTRA = more search_s0 flags (--tap-loss SPEC: OUR side loses taps at the live rate; --opp-tau X: the opponent's
#               play / wait threshold); absent = the opp_eval_fin15 command.
#   its OWN isolated copy ($B/cb, B=/workspace/w18/o3 by default) made from /workspace/cb_stepd AFTER the W18 code is there
#   (refuses if e1_eval lacks parse_tap_loss), with o3_patch + pos_patch v2 (pos telemetry only when O3_POS=1).
#   EVLOCK = the stream's lock (two streams in parallel at WORKERS each; default 26 = half of the 54 cores).
#     bash w18_eval.sh NAME LEARNER_CKPT OPP_CKPT OPP_T OPP_DE OPP_RT SEED [SEED ...]
set -uo pipefail
NAME=$1; CK=$2; OPP=$3; T=$4; DE=$5; RT=$6; shift 6; SEEDS="$*"
SRC=/workspace/cb_stepd; L=scratchpad/gauntlet/L74/opp_model
B=${O3B:-/workspace/w18/o3}; CB=$B/cb; O=$B/out/$NAME; P15=/workspace/venvf15/bin/python
EV_EXTRA="--habit-log --live-levels --card-levels Rocket=16 Log=15 --opp-tower-troops DaggerDuchess:0.028,Cannoneer:0.028,ChefTower:0.014 --record-plays --ability-stats --crown-log ${DECODE---ability-head-decode=sample} ${W18_EXTRA:-}"
mkdir -p $O; exec >> $O/run.log 2>&1
log() { echo "$(date -u +%FT%TZ) $*"; }
trap 'log exit' EXIT
grep -q "def parse_tap_loss" $SRC/pipeline/e1_eval.py && grep -q -- '"--tap-loss"' $SRC/pipeline/search_s0.py \
  || { log "cb_stepd lacks the W18 code (e1_eval parse_tap_loss / search_s0 --tap-loss)"; exit 3; }
if [ ! -f $CB/O3_PATCHED ]; then
  ( flock 9
    if [ ! -f $CB/O3_PATCHED ]; then
      rm -rf $CB; cp -al $SRC $CB || exit 2
      S=$CB/pipeline/search_s0.py; cp $S $S.orig_link && rm $S && cp $S.orig_link $S && rm $S.orig_link   # break the hard link
      $P15 $SRC/$L/pod/o3_patch.py $S || exit 3
      $P15 $SRC/$L/w14/pos_patch.py $S || exit 3
      touch $CB/O3_PATCHED; log "patched copy ready (o3 + pos v2)"
    fi ) 9> $B/patch.lock
fi
[ -f $CB/O3_PATCHED ] || { log "no patched copy"; exit 3; }
cd $CB || exit 2
unset ROYALE_HEROIW_PRESS
export PYTHONPATH=$CB ROYALE_HEROIW_FORM=hero OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1 O3_PLAYS=1
OPP_ARGS=(--opp-ckpt $OPP --opp-T $T); [ "$DE" != "-" ] && OPP_ARGS+=(--opp-decide-every $DE); [ "$RT" != "-" ] && OPP_ARGS+=(--opp-reaction-ticks $RT)
sha256sum $CK $OPP pipeline/search_s0.py pipeline/e1_eval.py > $O/inputs.sha
log "start $NAME learner $CK opp ${OPP_ARGS[*]} extra '${W18_EXTRA:-}' pos '${O3_POS:-}' seeds $SEEDS"
for S in $SEEDS; do
  D=$O/${NAME}_$S
  [ "$(grep -c '"outcome"' $D/D3/matches.jsonl 2>/dev/null)" = 480 ] && continue
  rm -rf $D; log "eval $S"
  ROYALE_RUNTIME=fin15-linux flock ${EVLOCK:-/workspace/w18/evalA.lock} $P15 scratchpad/gauntlet/L74/gap/gap.py --ckpt $CK --out $D --arms D3 \
    --seed-start $S --runtime fin15-linux --python $P15 --census-file scratchpad/gauntlet/L74/mix/decks_live_eval.json \
    --workers ${WORKERS:-26} --levels all16 "${OPP_ARGS[@]}" --extra="$EV_EXTRA" > $D.log 2>&1 || log "GAP EXIT $? $S"
  log "rows $S: $(grep -c '"outcome"' $D/D3/matches.jsonl 2>/dev/null) with o3_plays: $(grep -c o3_plays $D/D3/matches.jsonl 2>/dev/null)"
done
cd $B/out && tar czf $NAME.tgz.part $NAME && mv $NAME.tgz.part $NAME.tgz && sha256sum $NAME.tgz > $NAME.tgz.sha
touch $O/ALL_DONE; log ALL_DONE
