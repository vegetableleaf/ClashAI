#!/bin/bash
# Step d RL arm chain (pod; cue_ab2/c3_chain.sh's shape). RUN = stepd_ctrl | stepd_reb | stepd_rebc3 (yaml L74/stepd/cfg/<RUN>.yaml):
# 130 updates on fin13-linux (/workspace/venvf13, Hero IW form hero; the yaml's heroiw_press: live sets the trainer's press),
# graft u250's refine heads, then the promotion eval (gap.py D3 + the c3 EXTRA) of u130 on the standard (741200 742000) AND
# fresh (743000 744000) seeds on fin13, the standard seeds on fork36 (continuity), and u65 on the standard fin13 seeds.
# REF=<grafted ckpt> NAME=<name>: no training, the same u130 evals of that checkpoint (CLIII's fin13 reference rows).
# Training + every eval hold /workspace/cpu.lock. Needs /workspace/stepd/smoke/SMOKE_OK. No pod stop, no watchdog, no deadline.
#   RUN=stepd_ctrl setsid nohup bash /workspace/stepd/bin/stepd_chain.sh > /dev/null 2>&1 < /dev/null &
set -uo pipefail
CB=/workspace/cb_stepd; RUNN=${RUN:-stepd_ctrl}; NAME=${NAME:-$RUNN}; O=/workspace/stepd/rl_$NAME
RL=icebow/data/bench/rl_royale; U250=$RL/rlarm_gae/rlarm_gae_u0250_grafted.pt; Y=scratchpad/gauntlet/L74/stepd/cfg/$RUNN.yaml
P13=/workspace/venvf13/bin/python; P36=/workspace/venvf36/bin/python
EV_EXTRA="--habit-log --live-levels --card-levels Rocket=16 Log=15 --opp-tower-troops DaggerDuchess:0.028,Cannoneer:0.028,ChefTower:0.014 --record-plays --ability-stats${DECODE:+ $DECODE}"
mkdir -p $O/eval; exec >> $O/chain.log 2>&1
log() { echo "$(date -u +%FT%TZ) $*"; }
trap 'log "exit"; touch $O/DONE' EXIT
cd $CB
unset ROYALE_HEROIW_PRESS                      # the yaml sets it for the trainer; gap.py sets its own (live rule)
export PYTHONPATH=$CB ROYALE_HEROIW_FORM=hero OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1
[ -e /workspace/stepd/smoke/SMOKE_OK ] || { log "no SMOKE_OK: not started"; exit 3; }
log "chain start pid $$ name $NAME${REF:+ ref $REF} EXTRA $EV_EXTRA"
ev() {   # ev CKPT TAG SEED RUNTIME PYTHON
  local D=$O/eval/$2_$3_${4%%-*}
  [ "$(grep -c '"outcome"' $D/D3/matches.jsonl 2>/dev/null)" = 480 ] && return 0
  rm -rf $D; log "eval $2 $3 $4"
  ROYALE_RUNTIME=$4 flock /workspace/cpu.lock $5 scratchpad/gauntlet/L74/gap/gap.py --ckpt $1 --out $D --arms D3 \
    --seed-start $3 --runtime $4 --python $5 --census-file scratchpad/gauntlet/L74/mix/decks_live_eval.json \
    --workers ${WORKERS:-26} --extra="$EV_EXTRA" > $D.log 2>&1 || log "GAP EXIT $? $2 $3 $4"
  log "$2 $3 $4 rows: $(grep -c '"outcome"' $D/D3/matches.jsonl 2>/dev/null)"
}
graft() { local G=${1%.pt}_grafted.pt; [ -f $G ] || $P13 scratchpad/gauntlet/L74/weekend/graft_generic.py $1 $U250 $G >> $O/graft.log 2>&1; echo $G; }
evall() {   # evall GRAFTED TAG: the u130 set
  for S in 741200 742000 743000 744000; do ev $1 $2 $S fin13-linux $P13; done
  for S in 741200 742000; do ev $1 $2 $S fork36-linux $P36; done
}
pack() {    # /workspace/stepd/out/<NAME>.tgz + .sha for the laptop relay (stepd/pull_stepd.sh); u65 ckpts ride along
  mkdir -p /workspace/stepd/out
  [ -n "${R:-}" ] && ln -f $RL/$R/${R}_u0065.pt $RL/$R/${R}_u0065_grafted.pt $O/ 2>/dev/null
  tar czf /workspace/stepd/out/$NAME.tgz.part -C /workspace/stepd rl_$NAME && mv /workspace/stepd/out/$NAME.tgz.part /workspace/stepd/out/$NAME.tgz \
    && (cd /workspace/stepd/out && sha256sum $NAME.tgz > $NAME.tgz.sha) && log "packed $NAME.tgz"
}
if [ -n "${REF:-}" ]; then
  sha256sum $REF > $O/eval_ckpt.sha; evall $REF $NAME; pack; touch $O/ALL_DONE; log "ALL_DONE"; exit 0
fi
R=rlarm_$RUNN; CK=$RL/$R/${R}_u0130.pt
if [ ! -f $CK ]; then
  RES=; [ -f $RL/$R/${R}_latest.pt ] && RES=--resume
  log "train $R $RES (waiting for cpu.lock)"
  ROYALE_RUNTIME=fin13-linux flock /workspace/cpu.lock $P13 -m pipeline.rl_royale --config $Y --run $R $RES >> $O/train.log 2>&1 \
    || log "TRAIN EXIT $?"
fi
cp scratchpad/gauntlet/L68/rl/$R/train_log.jsonl scratchpad/gauntlet/L68/rl/$R/config.yaml $O/ 2>/dev/null
[ -f $CK ] || { log "no final checkpoint $CK"; exit 4; }
G=$(graft $CK); [ -f $G ] || { log "graft failed"; exit 5; }
sha256sum $CK $G > $O/final.sha; ln -f $CK $G $O/
evall $G $NAME
G65=$(graft $RL/$R/${R}_u0065.pt)
for S in 741200 742000; do [ -f $G65 ] && ev $G65 ${NAME}_u65 $S fin13-linux $P13; done
pack; touch $O/ALL_DONE; log "ALL_DONE"
