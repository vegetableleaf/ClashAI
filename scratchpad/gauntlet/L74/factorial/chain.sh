#!/bin/bash
# L74 factorial pod chain (10-17).  setsid nohup bash chain.sh > /dev/null 2>&1 < /dev/null &
# Runs /workspace/fact/queue.txt top to bottom, ONE run at a time, re-reading the queue before each run. To move a queued
# run to another pod: delete its line here, add it to that pod's queue.txt (that pod needs the same code tar).
#   a run = /workspace/fact/runs/<RUN>/ (logs, checkpoints, eval/) + DONE (or FAILED: skipped; delete it to retry)
#   factNN : train rlarm_factNN (factorial/cfg/factNN.yaml: 65 updates from u250 raw; flock cpu.lock; resumes from _latest)
#            -> graft from u250 (weekend/graft_generic.py) -> eval;   ref_* : eval the checkpoint named in factorial/refs.txt
#   eval   = mix/live_eval_pod.sh: fork36-linux, Hero IW (gap.py press live), D3, seeds 741200 + 742000 = 960 paired games,
#            EXTRA = live levels + card levels + habit log + opponent tower troops at live rates (the same for every run)
#   bundle = /workspace/fact/out/<RUN>.tgz + .sha (copy-back unit; the laptop's pull.sh writes runs/<RUN>/COPIED)
#   queue done -> CHAIN_DONE; then LAST as soon as the laptop wrote ALL_COPIED, or BACKSTOP_S (default 4 h) after
#   CHAIN_DONE without it (pod_watchdog.sh is armed on LAST; /workspace is WIPED when the pod stops).
#   env: WORKERS (eval workers, default 26), BACKSTOP_S
set -uo pipefail
F=/workspace/fact; CB=/workspace/cb_tt; PY=/workspace/venvf36/bin/python; RT=fork36-linux
RL=icebow/data/bench/rl_royale; U250=$RL/rlarm_gae/rlarm_gae_u0250_grafted.pt; FD=scratchpad/gauntlet/L74/factorial
EV_EXTRA='--habit-log --live-levels --card-levels Rocket=16 Log=15 --opp-tower-troops DaggerDuchess:0.028,Cannoneer:0.028,ChefTower:0.014'
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
bundle() {  # RUN -> out/<RUN>.tgz + .sha (the .sha is written last: it is the laptop's "ready" marker)
  tar czf $F/out/$1.tgz -C $F/runs $1 && (cd $F/out && sha256sum $1.tgz > $1.tgz.sha) || log "bundle $1 failed"
}
fail() { log "FAILED $1: $2"; touch $F/runs/$1/FAILED; bundle $1; }   # logs still go back; the chain moves on
run_one() {
  local r=$1 D=$F/runs/$1 ck R
  mkdir -p $D; rm -f $D/COPIED $F/out/$r.tgz.sha              # a retried run is copied again
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
    [ -f ${ck%.pt}_grafted.pt ] || $PY scratchpad/gauntlet/L74/weekend/graft_generic.py $ck $U250 ${ck%.pt}_grafted.pt >> $D/graft.log 2>&1
    [ -f ${ck%.pt}_grafted.pt ] || { fail $r graft; return; }
    ln -f $ck ${ck%.pt}_grafted.pt $D/                     # same filesystem: the bundle carries both, no extra disk
    (cd $D && sha256sum $(basename $ck) $(basename ${ck%.pt}_grafted.pt) > final.sha)
    ck=${ck%.pt}_grafted.pt
  fi
  [ -f "$ck" ] || { fail $r "missing checkpoint '$ck'"; return; }
  sha256sum $ck > $D/eval_ckpt.sha
  log "eval $r $ck"
  [ -e $D/eval/$r.DONE ] || EXTRA="$EV_EXTRA" CB=$CB PY=$PY RT=$RT O=$D/eval WORKERS=${WORKERS:-26} \
    bash scratchpad/gauntlet/L74/mix/live_eval_pod.sh none $r $ck D3 || log "EVAL EXIT $? $r"
  local n; n=$(cat $D/eval/${r}_741200/D3/matches.jsonl $D/eval/${r}_742000/D3/matches.jsonl 2>/dev/null | grep -c '"outcome"')
  [ "$n" = 960 ] || { fail $r "eval has $n / 960 rows"; return; }
  touch $D/DONE                                            # before the tar so the bundle carries it
  bundle $r
  log "DONE $r ($n games)"
}
log "chain start pid $$ (queue: $(grep -c . $F/queue.txt) lines)"
while r=$(next); [ -n "$r" ]; do run_one $r; done
touch $F/CHAIN_DONE; log "CHAIN_DONE"
for ((t = 0; t < ${BACKSTOP_S:-14400}; t += 60)); do [ -e $F/ALL_COPIED ] && break; sleep 60; done
log "LAST ($([ -e $F/ALL_COPIED ] && echo all copied || echo "backstop: NOT all copied"))"; touch $F/LAST
