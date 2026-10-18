#!/bin/bash
# L74 fastplays pod chain (10-17): Mark CXXXVIII on the FACTORIAL eval (mix/live_eval_pod.sh: fork36-linux, Hero IW + live press,
# D3, seeds 741200 + 742000 = 960 paired, EXTRA = live levels + card levels + habit log + tower troops at live rates) with
#   off   EXTRA + --record-plays                                     (= the factorial ref_cxxxviii row-for-row: identity check)
#   on    off + --pipeline-decisions --pipeline-tau-delta 0          (= live start_live.sh's fast plays: live_config.sh line 36)
#   offc  off + the live combo rules (LIVE_OPTIONS: log-air block, rocket-value 9 damage edge, rocket-tornado only, tornado-river)
#   onc   offc + fast plays (needs sim_patch.py P2: the SIM twin of live's follow-up taps + pipelined decisions together)
#   setsid nohup bash fp_chain.sh > /dev/null 2>&1 < /dev/null &      -> /workspace/fp/<arm>/, /workspace/fp/EVAL_DONE
set -uo pipefail
F=/workspace/fp; CB=/workspace/cb_tt; PY=/workspace/venvf36/bin/python; RT=fork36-linux
CK=icebow/data/bench/rl_royale/rlarm_gae_cue_u250/rlarm_gae_cue_u250_u0130_grafted.pt
BASE='--habit-log --live-levels --card-levels Rocket=16 Log=15 --opp-tower-troops DaggerDuchess:0.028,Cannoneer:0.028,ChefTower:0.014 --record-plays'
FAST='--pipeline-decisions --pipeline-tau-delta 0'
COMBO='--log-air block --rocket-value 9 --rocket-value-mode damage --rocket-value-hitbox edge --rocket-tornado only --tornado-river on'
mkdir -p $F; exec >> $F/chain.log 2>&1
cd $CB || exit 1
export PYTHONPATH=$CB ROYALE_RUNTIME=$RT ROYALE_HEROIW_FORM=hero OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1 \
  PYTHONNOUSERSITE=1
log() { echo "$(date -u +%FT%TZ) $*"; }
run() {  # NAME EXTRA
  [ -e $F/$1/$1.DONE ] && { log "skip $1 (done)"; return; }
  log "eval $1: $2"
  EXTRA="$2" CB=$CB PY=$PY RT=$RT O=$F/$1 WORKERS=${WORKERS:-26} bash scratchpad/gauntlet/L74/mix/live_eval_pod.sh none $1 $CK D3 \
    || log "EVAL EXIT $? $1"
  log "rows $1: $(cat $F/$1/${1}_741200/D3/matches.jsonl $F/$1/${1}_742000/D3/matches.jsonl 2>/dev/null | grep -c '"outcome"')"
}
log "fp chain start pid $$"
sha256sum $CK
run off "$BASE"
run on "$BASE $FAST"
run offc "$BASE $COMBO"
run onc "$BASE $COMBO $FAST"
touch $F/EVAL_DONE; log EVAL_DONE
