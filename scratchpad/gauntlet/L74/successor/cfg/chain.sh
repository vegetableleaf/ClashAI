#!/bin/bash
# L74 SUCCESSOR pod chain (10-18; factorial/chain.sh with the successor paths). Needs /workspace/succ/smoke/SMOKE_OK.
#   setsid nohup bash /workspace/succ/chain.sh > /dev/null 2>&1 < /dev/null &
# Runs /workspace/succ/queue.txt top to bottom, ONE job at a time, re-reading the queue before each job (append / delete
# lines to re-plan a pod while it runs; the running job is not touched). Entries:
#   succ_*        train rlarm_<run> (successor/cfg/<run>.yaml: Mark CXXXVIII raw u0130 + 65 updates, seed 74, fork36-linux,
#                 Hero IW rule press; flock cpu.lock; resumes from _latest) -> graft from u250 grafted (= the heads Mark
#                 CXXXVIII carries) -> PROMOTION eval (mix/live_eval_pod.sh: fork36, D3, seeds 741200 + 742000, 960 paired,
#                 the factorial EXTRA) = the exact command ref_cxxxviii (607 / 960) was scored with
#   fresh_<x>     the same eval on FRESH seeds 743000 + 744000 (x = a trained succ_* run on this pod, or a refs.txt name)
#   gap13k_<x>    13k-gap probe: the promotion eval with the EXPLOITER as the opponent (gap.py --opp-ckpt, T .1) instead of E4
#   a job = /workspace/succ/runs/<JOB>/ + DONE (or FAILED: skipped; delete it to retry); bundle out/<JOB>.tgz + .sha (the .sha
#   last = the laptop's ready marker for pull.sh). Queue done -> CHAIN_DONE. NO pod stop, NO watchdog, NO LAST: /workspace/KEEP
#   stays (owner 10-17: a pod is stopped only when no delegable work is left -- the laptop session decides, never this script).
set -uo pipefail
F=/workspace/succ; CB=/workspace/cb_tt; PY=/workspace/venvf36/bin/python; RT=fork36-linux
RL=icebow/data/bench/rl_royale; U250=$RL/rlarm_gae/rlarm_gae_u0250_grafted.pt; FD=scratchpad/gauntlet/L74/successor/cfg
EXPL=$RL/rlarm_exploit/rlarm_exploit_u0065.pt
EV_EXTRA='--habit-log --live-levels --card-levels Rocket=16 Log=15 --opp-tower-troops DaggerDuchess:0.028,Cannoneer:0.028,ChefTower:0.014'
mkdir -p $F/runs $F/out; exec >> $F/chain.log 2>&1
cd $CB || exit 1
[ -e $F/smoke/SMOKE_OK ] || { echo "$(date -u +%FT%TZ) no SMOKE_OK: not started"; exit 3; }
export PYTHONPATH=$CB ROYALE_RUNTIME=$RT ROYALE_HEROIW_FORM=hero OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1 \
  PYTHONNOUSERSITE=1
log() { echo "$(date -u +%FT%TZ) $*"; }
next() {
  local r
  while read -r r _; do
    [ -n "$r" ] && [ "${r:0:1}" != "#" ] && [ ! -e $F/runs/$r/DONE ] && [ ! -e $F/runs/$r/FAILED ] && { echo $r; return; }
  done < $F/queue.txt
}
bundle() { tar czf $F/out/$1.tgz -C $F/runs $1 && (cd $F/out && sha256sum $1.tgz > $1.tgz.sha) || log "bundle $1 failed"; }
fail() { log "FAILED $1: $2"; touch $F/runs/$1/FAILED; bundle $1; }
ckpt_of() {  # NAME -> grafted checkpoint of a trained succ_* run, else the refs.txt path
  local p=$RL/rlarm_$1/rlarm_${1}_u0065_grafted.pt
  [ -f $p ] && echo $p || awk -v r=$1 '$1 == r {print $2}' $FD/refs.txt
}
seeds_eval() {  # JOB CKPT SEED1 SEED2 [gap.py opponent flags]: live_eval_pod.sh's gap.py call with other seeds / opponent
  local j=$1 ck=$2 s1=$3 s2=$4 S; shift 4
  for S in $s1 $s2; do
    [ "$(grep -c '"outcome"' $F/runs/$j/eval/${j}_$S/D3/matches.jsonl 2>/dev/null)" = 480 ] && continue
    rm -rf $F/runs/$j/eval/${j}_$S                                 # a partial half is re-run, never kept
    flock /workspace/cpu.lock $PY scratchpad/gauntlet/L74/gap/gap.py --ckpt $ck --out $F/runs/$j/eval/${j}_$S --arms D3 \
      --seed-start $S --runtime $RT --python $PY --census-file scratchpad/gauntlet/L74/mix/decks_live_eval.json \
      --workers ${WORKERS:-26} "$@" --extra="$EV_EXTRA" > $F/runs/$j/eval/${j}_$S.log 2>&1 || log "GAP EXIT $? $j $S"
  done
}
run_one() {
  local r=$1 D=$F/runs/$1 ck R s1=741200 s2=742000
  mkdir -p $D/eval; rm -f $D/COPIED $F/out/$r.tgz.sha
  case $r in
    fresh_*)  ck=$(ckpt_of ${r#fresh_}); s1=743000; s2=744000
              [ -f "$ck" ] || { fail $r "missing checkpoint for ${r#fresh_}"; return; }
              sha256sum $ck > $D/eval_ckpt.sha; log "eval $r $ck (fresh seeds)"; seeds_eval $r $ck $s1 $s2 ;;
    gap13k_*) ck=$(ckpt_of ${r#gap13k_})
              [ -f "$ck" ] && [ -f $EXPL ] || { fail $r "missing checkpoint ($ck / $EXPL)"; return; }
              sha256sum $ck $EXPL > $D/eval_ckpt.sha; log "eval $r $ck (opponent = exploiter)"
              seeds_eval $r $ck $s1 $s2 --opp-ckpt $EXPL --opp-T .1 ;;
    succ_*)   R=rlarm_$r; ck=$RL/$R/${R}_u0065.pt
              if [ ! -f $ck ]; then
                local RES=; [ -f $RL/$R/${R}_latest.pt ] && RES=--resume
                log "train $R $RES"
                flock /workspace/cpu.lock $PY -m pipeline.rl_royale --config $FD/$r.yaml --run $R $RES >> $D/train.log 2>&1 \
                  || log "TRAIN EXIT $? $r"
              fi
              cp scratchpad/gauntlet/L68/rl/$R/train_log.jsonl scratchpad/gauntlet/L68/rl/$R/config.yaml $D/ 2>/dev/null
              [ -f $ck ] || { fail $r "no final checkpoint $ck"; return; }
              [ -f ${ck%.pt}_grafted.pt ] || $PY scratchpad/gauntlet/L74/weekend/graft_generic.py $ck $U250 ${ck%.pt}_grafted.pt >> $D/graft.log 2>&1
              [ -f ${ck%.pt}_grafted.pt ] || { fail $r graft; return; }
              ln -f $ck ${ck%.pt}_grafted.pt $D/
              (cd $D && sha256sum $(basename $ck) $(basename ${ck%.pt}_grafted.pt) > final.sha)
              ck=${ck%.pt}_grafted.pt; sha256sum $ck > $D/eval_ckpt.sha; log "eval $r $ck"
              [ -e $D/eval/$r.DONE ] || EXTRA="$EV_EXTRA" CB=$CB PY=$PY RT=$RT O=$D/eval WORKERS=${WORKERS:-26} \
                bash scratchpad/gauntlet/L74/mix/live_eval_pod.sh none $r $ck D3 || log "EVAL EXIT $? $r" ;;
    *)        fail $r "unknown job kind"; return ;;
  esac
  local n; n=$(cat $D/eval/${r}_$s1/D3/matches.jsonl $D/eval/${r}_$s2/D3/matches.jsonl 2>/dev/null | grep -c '"outcome"')
  [ "$n" = 960 ] || { fail $r "eval has $n / 960 rows"; return; }
  touch $D/DONE; bundle $r; log "DONE $r ($n games)"
}
log "chain start pid $$ (queue: $(grep -c . $F/queue.txt) lines)"
while r=$(next); [ -n "$r" ]; do run_one $r; done
touch $F/CHAIN_DONE; log "CHAIN_DONE (pod stays up: KEEP)"
