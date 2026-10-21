#!/bin/bash
# O3 / O4 / new-baseline SIM evals against a chosen opponent (L74/opp_model/OPP_MODEL.md section 6). Pod-local only.
#   setsid nohup bash /workspace/o3/opp_eval.sh NAME LEARNER_CKPT OPP_CKPT OPP_T OPP_DE OPP_RT SEED [SEED ...] > /dev/null 2>&1 < /dev/null &
# Every eval: gap.py arm D3, fin15-linux, live-mirrored pool, ALL cards and towers at level 16 (--levels all16: the owner's 10-20
# default), the step-d promotion EXTRA + --crown-log (exact tower falls in each row) + the sampled ability head (CLX's live decode).
# Opponent: OPP_CKPT at temperature OPP_T, deciding every OPP_DE ticks with OPP_RT extra reaction ticks ('-' = gap.py default).
# Telemetry: an ISOLATED hard-link copy /workspace/o3/cb of /workspace/cb_stepd whose pipeline/search_s0.py is a NEW file (never
# the linked original) adding rec['o3_plays'] = both sides' accepted plays [landing tick, card] when O3_PLAYS=1. cb_stepd is
# untouched. Output /workspace/o3/out/NAME/NAME_SEED/D3/matches.jsonl, then /workspace/o3/out/NAME.tgz + .sha.
# W14 (opt-in, absent = unchanged): EVLOCK=<lock file> instead of /workspace/cpu.lock (gate evals beside a training run).
set -uo pipefail
NAME=$1; CK=$2; OPP=$3; T=$4; DE=$5; RT=$6; shift 6; SEEDS="$*"
B=${O3B:-/workspace/o3}; CB=$B/cb; O=$B/out/$NAME; P15=/workspace/venvf15/bin/python
EV_EXTRA="--habit-log --live-levels --card-levels Rocket=16 Log=15 --opp-tower-troops DaggerDuchess:0.028,Cannoneer:0.028,ChefTower:0.014 --record-plays --ability-stats --crown-log ${DECODE---ability-head-decode=sample}"
mkdir -p $O; exec >> $O/run.log 2>&1
log() { echo "$(date -u +%FT%TZ) $*"; }
trap 'log exit' EXIT
if [ ! -f $CB/O3_PATCHED ]; then
  ( flock 9
    if [ ! -f $CB/O3_PATCHED ]; then
      rm -rf $CB; cp -al /workspace/cb_stepd $CB || exit 2
      S=$CB/pipeline/search_s0.py; cp $S $S.orig_link && rm $S && cp $S.orig_link $S && rm $S.orig_link   # break the hard link
      $P15 $B/o3_patch.py $S || exit 3
      touch $CB/O3_PATCHED; log "patched copy ready"
    fi ) 9> $B/patch.lock
fi
[ -f $CB/O3_PATCHED ] || { log "no patched copy"; exit 3; }
cd $CB || exit 2
unset ROYALE_HEROIW_PRESS
export PYTHONPATH=$CB ROYALE_HEROIW_FORM=hero OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1 O3_PLAYS=1
OPP_ARGS=(--opp-ckpt $OPP --opp-T $T); [ "$DE" != "-" ] && OPP_ARGS+=(--opp-decide-every $DE); [ "$RT" != "-" ] && OPP_ARGS+=(--opp-reaction-ticks $RT)
sha256sum $CK $OPP pipeline/search_s0.py > $O/inputs.sha
log "start $NAME learner $CK opp ${OPP_ARGS[*]} seeds $SEEDS"
for S in $SEEDS; do
  D=$O/${NAME}_$S
  [ "$(grep -c '"outcome"' $D/D3/matches.jsonl 2>/dev/null)" = 480 ] && continue
  rm -rf $D; log "eval $S"
  ROYALE_RUNTIME=fin15-linux flock ${EVLOCK:-/workspace/cpu.lock} $P15 scratchpad/gauntlet/L74/gap/gap.py --ckpt $CK --out $D --arms D3 \
    --seed-start $S --runtime fin15-linux --python $P15 --census-file scratchpad/gauntlet/L74/mix/decks_live_eval.json \
    --workers ${WORKERS:-26} --levels all16 "${OPP_ARGS[@]}" --extra="$EV_EXTRA" > $D.log 2>&1 || log "GAP EXIT $? $S"
  log "rows $S: $(grep -c '"outcome"' $D/D3/matches.jsonl 2>/dev/null) with o3_plays: $(grep -c o3_plays $D/D3/matches.jsonl 2>/dev/null)"
done
cd $B/out && tar czf $NAME.tgz.part $NAME && mv $NAME.tgz.part $NAME.tgz && sha256sum $NAME.tgz > $NAME.tgz.sha
touch $O/ALL_DONE; log ALL_DONE
