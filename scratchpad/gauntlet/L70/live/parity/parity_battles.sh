#!/bin/bash
# Owner 10-20: classic-challenge parity battles with the 3 owner decks (11 rare cards). ONE classic battle per live_play run
# (no navigation: the owner starts each battle in the Classic Challenge screen). Model = CKPT_OVERRIDE (CLX), options =
# parity/LIVE_OPTIONS (= icebow LIVE_OPTIONS minus the learned IW press, so the generic hero rule presses EVERY hero),
# frames + phase-3 captures on (the data we need). Stop between battles: touch L70/live/STOP.
#   bash scratchpad/gauntlet/L70/live/parity/parity_battles.sh 15 deck1
cd /c/Users/benpe/ClashBot
L=scratchpad/gauntlet/L70/live; N=${1:-15}; TAG=${2:-deck}
source "$L/live_config.sh" || exit 2
LIVE_FAST=off load_live_config icebow || exit 2
for i in $(seq 1 $N); do
  [ -e "$L/STOP" ] && { echo "STOP file: ending before battle $i"; break; }
  echo "$(date +%T) [$TAG] battle $i/$N: start the classic battle now"
  $PY -u $LIVE_ENTRY --ckpt-override-file $L/CKPT_OVERRIDE --live-options-file $L/parity/LIVE_OPTIONS --tau 0.35 \
    --no-anti-leak --max-seconds 1500 2>&1 | tee -a $L/parity/parity_${TAG}.out | grep -E "^\{|\[live\] (start|end|result)|error" | tail -2
  sleep 5
done
