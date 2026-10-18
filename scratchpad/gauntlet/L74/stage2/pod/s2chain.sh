#!/bin/bash
# Stage-2 pod chain (S2-06..S2-08; successor/cfg/chain.sh's pattern). Runs /workspace/s2/queue.txt top to bottom, ONE job at a
# time under flock /workspace/cpu.lock, re-reading the queue before each job (append / delete lines to re-plan). Lines:
#   smoke NAME CFG                     rl_royale --smoke (pre-ship rule; times the update)
#   train NAME CFG                     rl_royale to max_updates (resumes from _latest); ckpts icebow/data/bench/rl_royale/NAME/
#   eval  NAME CB CKPT POOL [flags]    gap.py D3 on seeds 741200 + 742000 (2 x 480 = 960 paired), the promotion-eval EXTRA;
#                                      CB = checkout (/workspace/cb_tt = live_levels.json, /workspace/cb_13k = levels13k.json);
#                                      POOL = census file (checkout-relative); flags = gap.py opponent flags (--opp-ckpt ...)
#   telem NAME CB CKPT POOL [flags]    the same eval on ONE seed set (741200, 480 games) through the isolated telemetry copy
#                                      (/workspace/cb_tel: econ_sim_patch + livecal --behaviour-telemetry) -> opp_behaviour sim
# A job = /workspace/s2/runs/NAME/ + DONE (or FAILED: skipped; delete it to retry); out/NAME.tgz + .sha (the .sha last = the
# laptop's ready marker). NO pod stop, NO watchdog, NO deadline (owner 10-18): /workspace/KEEP stays; idle = report it.
#   setsid nohup bash /workspace/s2/s2chain.sh > /dev/null 2>&1 < /dev/null &
set -uo pipefail
F=/workspace/s2; PY=/workspace/venvf36/bin/python; RT=fork36-linux; L=scratchpad/gauntlet/L74
EV_EXTRA='--habit-log --live-levels --card-levels Rocket=16 Log=15 --opp-tower-troops DaggerDuchess:0.028,Cannoneer:0.028,ChefTower:0.014'
mkdir -p $F/runs $F/out; exec >> $F/chain.log 2>&1
export ROYALE_RUNTIME=$RT ROYALE_HEROIW_FORM=hero OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1
q=$(awk '{print int($1 / ($2 ? $2 : 100000))}' /sys/fs/cgroup/cpu.max 2>/dev/null || echo $(( $(cat /sys/fs/cgroup/cpu/cpu.cfs_quota_us) / 100000 )))
[ "${q:-0}" -ge 2 ] 2>/dev/null || q=27
W=${WORKERS:-$(( q - 1 > 26 ? 26 : q - 1 ))}
log() { echo "$(date -u +%FT%TZ) $*"; }
next() { local k n; while read -r k n _; do [ -n "$k" ] && [ "${k:0:1}" != "#" ] && [ ! -e $F/runs/$n/DONE ] && [ ! -e $F/runs/$n/FAILED ] && { echo $n; return; }; done < $F/queue.txt; }
line() { awk -v n=$1 '$2 == n {print; exit}' $F/queue.txt; }
bundle() { tar czf $F/out/$1.tgz -C $F/runs $1 && (cd $F/out && sha256sum $1.tgz > $1.tgz.sha) || log "bundle $1 failed"; }
fail() { log "FAILED $1: $2"; touch $F/runs/$1/FAILED; bundle $1; }
rows() { cat $F/runs/$1/${1}_*/D3/matches.jsonl 2>/dev/null | grep -c '"outcome"'; }
gapeval() {  # NAME CB CKPT POOL SEEDS... -- flags
  local n=$1 cb=$2 ck=$3 pool=$4 S; shift 4; local seeds=(); while [ $# -gt 0 ] && [ "$1" != -- ]; do seeds+=($1); shift; done; shift
  for S in "${seeds[@]}"; do
    [ "$(grep -c '"outcome"' $F/runs/$n/${n}_$S/D3/matches.jsonl 2>/dev/null)" = 480 ] && continue
    rm -rf $F/runs/$n/${n}_$S
    (cd $cb && PYTHONPATH=$cb flock /workspace/cpu.lock $PY $L/gap/gap.py --ckpt $ck --out $F/runs/$n/${n}_$S --arms D3 \
      --seed-start $S --runtime $RT --python $PY --census-file $pool --workers $W "$@" --extra="$EV_EXTRA") \
      > $F/runs/$n/${n}_$S.log 2>&1 || log "GAP EXIT $? $n $S"
  done
}
run_one() {
  local n=$1 D=$F/runs/$1; set -- $(line $1); local kind=$1; shift 2
  mkdir -p $D; rm -f $F/out/$n.tgz.sha; echo "$(line $n)" > $D/JOB
  case $kind in
    smoke|train)
      local cfg=$1 R=$n; local CB=/workspace/cb_tt; cd $CB
      [ $kind = train ] && [ ! -e $F/runs/${n}_smoke/DONE ] && { fail $n "no passed smoke job ${n}_smoke (pre-ship rule)"; return; }
      sha256sum $cfg > $D/cfg.sha; [ $kind = smoke ] && { R=smoke_$n; rm -rf $L/../L68/rl/$R icebow/data/bench/rl_royale/$R; }
      local RES=; [ $kind = train ] && [ -f icebow/data/bench/rl_royale/$R/${R}_latest.pt ] && RES=--resume
      log "$kind $R $RES"
      PYTHONPATH=$CB flock /workspace/cpu.lock $PY -m pipeline.rl_royale --config $cfg --run $R ${RES} $([ $kind = smoke ] && echo --smoke) \
        >> $D/train.log 2>&1 || log "RL EXIT $? $n"
      cp $L/../L68/rl/$R/train_log.jsonl $L/../L68/rl/$R/config.yaml $D/ 2>/dev/null
      if [ $kind = smoke ]; then grep -q 'SMOKE PASS' $D/train.log || { fail $n "no SMOKE PASS"; return; }
      else
        local mx; mx=$(awk '$1 == "max_updates:" {printf "%04d", $2}' $cfg)
        [ -f icebow/data/bench/rl_royale/$R/${R}_u$mx.pt ] || { fail $n "no final checkpoint u$mx"; return; }
        (cd icebow/data/bench/rl_royale/$R && sha256sum ${R}_u*.pt > $D/ckpts.sha)
      fi ;;
    eval|telem)
      local cb=$1 ck=$2 pool=$3; shift 3
      [ -f $cb/$ck ] && [ -f $cb/$pool ] || { fail $n "missing $ck or $pool in $cb"; return; }
      (cd $cb && sha256sum $ck $pool $L/levels/live_levels.json $(echo "$@" | grep -oE '[^ ]+\.pt') > $D/eval_inputs.sha)
      if [ $kind = eval ]; then
        log "eval $n"; gapeval $n $cb $ck $pool 741200 742000 -- "$@"
        local k; k=$(rows $n); [ "$k" = 960 ] || { fail $n "eval has $k / 960 rows"; return; }
      else
        log "telem $n"; gapeval $n /workspace/cb_tel $ck $pool 741200 -- "$@"
        local k; k=$(rows $n); [ "$k" = 480 ] || { fail $n "telem has $k / 480 rows"; return; }
        (cd /workspace/cb_tel && PYTHONPATH=/workspace/cb_tel $PY $L/human/opp_behaviour.py sim $n $F/runs/$n > $D/extract.log 2>&1 \
          && cp $L/human/data/sim_$n.json.gz $D/) || { fail $n "opp_behaviour extract"; return; }
      fi ;;
    *) fail $n "unknown job kind $kind"; return ;;
  esac
  touch $D/DONE; bundle $n; log "DONE $n"
}
rm -f $F/CHAIN_DONE
log "chain start pid $$ (WORKERS $W)"
while n=$(next); [ -n "$n" ]; do (run_one $n); done
touch $F/CHAIN_DONE; log "CHAIN_DONE (pod stays up: KEEP; idle -> report)"
