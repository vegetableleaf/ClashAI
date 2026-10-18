#!/bin/bash
# L74 combo pod chain (owner 10-17 plan: RL the Rocket + Tornado combo with a spell-value reward). The factorial chain's pattern
# (factorial/chain.sh): runs /workspace/combo/queue.txt top to bottom, ONE run at a time, re-reading the queue before each run.
#   setsid nohup bash chain.sh > /dev/null 2>&1 < /dev/null &        (needs /workspace/cb_tt + venvf36: combo/ship.sh)
#   a run = /workspace/combo/runs/<RUN>/ (logs, checkpoints, eval_<V>/) + DONE (or FAILED: skipped; delete it to retry)
#   combo_* : train rlarm_<RUN> (combo/cfg/<RUN>.yaml: 65 updates from Mark CXXXVIII raw; flock cpu.lock; resumes from _latest)
#             -> graft from Mark CXXXVIII grafted (weekend/graft_generic.py) -> evals;  ref_* : evals of the checkpoint in refs.txt
#   evals  = mix/live_eval_pod.sh: fork36-linux, Hero IW, D3, seeds 741200 + 742000 = 960 paired games, EV = the factorial's
#            EXTRA (live levels + card levels + habit log + opponent tower troops at live rates) + --spell-log --record-plays:
#              off   EV                          (the promotion eval: Mark CXXXVIII 'off' = 607 / 960, fast plays off)
#              offc  EV + the LIVE combo rules   (= LIVE_OPTIONS' rocket-value / rocket-tornado / log-air / tornado-river: what
#                                                 deploying it with today's live rules would mean; Mark CXXXVIII 'offc' = 610)
#              on    EV + fast plays             (only runs whose name has _pipe, and ref_*: --pipeline-decisions, tau delta 0)
#   bundle = /workspace/combo/out/<RUN>.tgz + .sha (copy-back unit; the .sha is written last). Never stops the pod, arms no
#   watchdog / timer (owner rule 10-17: /workspace/KEEP stays); CHAIN_DONE when the queue is empty.
#   env: WORKERS (eval workers, default 26)
set -uo pipefail
F=/workspace/combo; CB=${CB:-/workspace/cb_tt}; PY=/workspace/venvf36/bin/python; RT=fork36-linux
RL=icebow/data/bench/rl_royale; LIVE=$RL/rlarm_gae_cue_u250/rlarm_gae_cue_u250_u0130_grafted.pt; FD=scratchpad/gauntlet/L74/combo
EV='--habit-log --live-levels --card-levels Rocket=16 Log=15 --opp-tower-troops DaggerDuchess:0.028,Cannoneer:0.028,ChefTower:0.014 --spell-log --record-plays'
COMBO='--log-air block --rocket-value 9 --rocket-value-mode damage --rocket-value-hitbox edge --rocket-tornado only --tornado-river on'
FAST='--pipeline-decisions --pipeline-tau-delta 0'
mkdir -p $F/runs $F/out; exec >> $F/chain.log 2>&1
cd $CB || exit 1
export PYTHONPATH=$CB ROYALE_RUNTIME=$RT ROYALE_HEROIW_FORM=hero OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1 \
  PYTHONNOUSERSITE=1
log() { echo "$(date -u +%FT%TZ) $*"; }
next() {  # first queued run with neither DONE nor FAILED
  local r
  while read -r r _; do
    [ -n "$r" ] && [ "${r:0:1}" != "#" ] && [ ! -e $F/runs/$r/DONE ] && [ ! -e $F/runs/$r/FAILED ] && { echo $r; return; }
  done < $F/queue.txt
}
bundle() { tar czf $F/out/$1.tgz -C $F/runs $1 && (cd $F/out && sha256sum $1.tgz > $1.tgz.sha) || log "bundle $1 failed"; }
fail() { log "FAILED $1: $2"; touch $F/runs/$1/FAILED; bundle $1; }
evals() {  # RUN CKPT: the eval variants this run gets
  local r=$1 ck=$2 v x n
  for v in off offc on; do
    case $v in
      off) x="$EV" ;; offc) x="$EV $COMBO" ;;
      on) [[ $r == *_pipe* || $r == ref_* ]] || continue; x="$EV $FAST" ;;
    esac
    [ -e $F/runs/$r/eval_$v/$r.DONE ] || EXTRA="$x" CB=$CB PY=$PY RT=$RT O=$F/runs/$r/eval_$v WORKERS=${WORKERS:-26} \
      bash scratchpad/gauntlet/L74/mix/live_eval_pod.sh none $r $ck D3 || log "EVAL EXIT $? $r $v"
    n=$(cat $F/runs/$r/eval_$v/${r}_741200/D3/matches.jsonl $F/runs/$r/eval_$v/${r}_742000/D3/matches.jsonl 2>/dev/null \
        | grep -c '"outcome"')
    [ "$n" = 960 ] || { fail $r "eval $v has $n / 960 rows"; return 1; }
    log "eval $r $v: $n rows, $(cat $F/runs/$r/eval_$v/${r}_7*/D3/matches.jsonl | grep -c '"outcome": "win"') wins"
  done
}
run_one() {
  local r=$1 D=$F/runs/$1 ck R
  mkdir -p $D; rm -f $F/out/$r.tgz.sha
  if [ "${r:0:4}" = ref_ ]; then
    ck=$(awk -v r=$r '$1 == r {print $2}' $FD/refs.txt)
  else
    R=rlarm_$r; ck=$RL/$R/${R}_u0065.pt
    if [ ! -f $ck ]; then
      local RES=; [ -f $RL/$R/${R}_latest.pt ] && RES=--resume
      log "train $R $RES"
      flock /workspace/cpu.lock $PY -m pipeline.rl_royale --config $FD/cfg/$r.yaml --run $R $RES >> $D/train.log 2>&1 \
        || log "TRAIN EXIT $? $r"
    fi
    cp scratchpad/gauntlet/L68/rl/$R/train_log.jsonl scratchpad/gauntlet/L68/rl/$R/config.yaml $D/ 2>/dev/null
    [ -f $ck ] || { fail $r "no final checkpoint $ck"; return; }
    [ -f ${ck%.pt}_grafted.pt ] || $PY scratchpad/gauntlet/L74/weekend/graft_generic.py $ck $LIVE ${ck%.pt}_grafted.pt >> $D/graft.log 2>&1
    [ -f ${ck%.pt}_grafted.pt ] || { fail $r graft; return; }
    ln -f $ck ${ck%.pt}_grafted.pt $D/
    (cd $D && sha256sum $(basename $ck) $(basename ${ck%.pt}_grafted.pt) > final.sha)
    ck=${ck%.pt}_grafted.pt
  fi
  [ -f "$ck" ] || { fail $r "missing checkpoint '$ck'"; return; }
  sha256sum $ck > $D/eval_ckpt.sha
  log "evals $r $ck"
  evals $r $ck || return
  touch $D/DONE
  bundle $r
  log "DONE $r"
}
log "chain start pid $$ (queue: $(grep -c . $F/queue.txt) lines)"
while r=$(next); [ -n "$r" ]; do run_one $r; done
touch $F/CHAIN_DONE; log "CHAIN_DONE"
