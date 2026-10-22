#!/bin/bash
# trial30.sh CKPT SHA16 NAME : owner 10-22 capped live trial. Deploy CKPT via deploy_ckpt.sh (reader / LIVE_OPTIONS / LIVE_RANKED
# unchanged), wait for 30 Ranked results after the switch, then KEEP it only if wins >= 16 / 30 AND its idle-on-threat share
# (ape_score.py "idle >= 4 s with elixir") <= CLX's + 0.05; otherwise redeploy CLX. Log: trial30_<NAME>.log; Discord via deploy_ckpt.
cd /c/Users/benpe/ClashBot || exit 1
CK=$1; SHA=$2; NAME=$3; F=scratchpad/gauntlet/L70/live/overnight.out; L=scratchpad/gauntlet/L74/deploy/trial30_$NAME.log
CLX=icebow/data/models/ICEBOW/ICEBOW_Mark_CLX_PARITY_grafted.pt; CLXSHA=5d212358322eb0dd; PY=icebow/.venv/Scripts/python.exe
log() { echo "$(date '+%F %T') $*" >> $L; }
start=$(wc -l < $F); log "deploy $NAME ($CK, $SHA) at overnight.out line $start"
bash scratchpad/gauntlet/L74/deploy/deploy_ckpt.sh "$CK" "$SHA" "owner 10-22 30-match trial: $NAME" >> $L 2>&1 || { log "deploy failed"; exit 2; }
until [ "$(tail -n +$start $F | grep -c '\[ladder\] result:')" -ge 30 ]; do sleep 120; done
w=$(tail -n +$start $F | grep '\[ladder\] result:' | head -30 | grep -c WIN); log "30 results: $w W / $((30 - w)) L"
sha8=${SHA:0:8}
idle=$(cd scratchpad/gauntlet/L74/ape && ../../../../$PY ape_score.py live:CLX live:$sha8 --base live:CLX --since 20261019 2>/dev/null \
  | grep "idle >= 4 s with elixir" | sed -E 's/.*\| ([0-9.]+) \| ([0-9.]+) .*/\1 \2/')
log "idle-on-threat CLX / $NAME: $idle"
set -- $idle; base=${1:-0}; cand=${2:-9}
ok=$(awk -v w=$w -v b=$base -v c=$cand 'BEGIN{print (w >= 16 && c <= b + 0.05) ? 1 : 0}')
if [ "$ok" = 1 ]; then log "KEEP $NAME (passes the trial)"; exit 0; fi
grep -q "$(basename $CK)" scratchpad/gauntlet/L70/live/CKPT_OVERRIDE || { log "CKPT_OVERRIDE changed meanwhile; no revert"; exit 0; }
log "REVERT to CLX"; bash scratchpad/gauntlet/L74/deploy/deploy_ckpt.sh $CLX $CLXSHA "owner 10-22: $NAME failed its 30-match trial ($w W)" >> $L 2>&1
log "revert exit $?"
