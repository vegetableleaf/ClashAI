#!/bin/bash
# Live ladder supervisor. Default checkpoint comes from CKPT_OVERRIDE; explicit CKPT env overrides it. tau 0.35
# (the live setting since 09-30), Trophy Road via ladder_nav (Play Again; after the day's 4th win OK -> chests -> Battle;
# Trophy Road rewards collected), local recording at the start and every30 min.
# Restarts after a stop, at most MAX_RESTARTS (default10), each stop recorded locally.
# NO end time: it ends only when $L/STOP exists (touch it to stop between matches).
# Owner 2026-10-04: --no-anti-leak tests R1e's learned play/wait gate without forced spending. All other settings stay.
# If a ladder live_play is ALREADY running when this starts (a supervisor swap), it is adopted: waited for, and its stop
# counts as the first restart -- never a second live_play beside it.
cd /c/Users/benpe/ClashBot
L=scratchpad/gauntlet/L70/live
PY=icebow/.venv/Scripts/python.exe
MAX=${MAX_RESTARTS:-10}
post() { printf '%s\n' "$1" >> "$L/supervisor.log"; }
running() {   # number of ladder live_play python processes (fail -> 1: assume running, never start a second one)
  local n
  n=$(powershell -NoProfile -Command "@(Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | Where-Object {\$_.CommandLine -like '*live_play.py*--ladder*'}).Count" 2>/dev/null | tr -dc '0-9')
  echo "${n:-1}"
}
last_stop() { grep -aE '\[live\] run stopped|\[nav\] run stopped|\[ladder\] STOP|stop file|new checkpoint deployed' $L/overnight.out | tail -1; }
state() { cat scratchpad/gauntlet/L68/live_reader/ladder_state.json 2>/dev/null; }
CKPT_ARGS=()
if [ -n "${CKPT:-}" ]; then CKPT_ARGS=(--ckpt "$CKPT"); fi
restarts=0
if [ "$(running)" -gt 0 ]; then
  echo "[sup] adopting the running live_play $(date) (restart counter reset, limit $MAX)" >> $L/supervisor.log
  while [ "$(running)" -gt 0 ]; do sleep 20; done
  why=$(last_stop)
  echo "[sup] adopted run exited $(date): $why" >> $L/supervisor.log
  if [ ! -e $L/STOP ]; then
    restarts=1
    post "ClashAI live run stopped $(date +%H:%M): ${why:-no reason logged}. State $(state). Restart $restarts/$MAX in 60 s."
    sleep 60
  fi
fi
while [ ! -e $L/STOP ]; do
  echo "[sup] start (restarts used $restarts/$MAX) $(date)" >> $L/supervisor.log
  $PY -u scratchpad/gauntlet/L68/live_reader/live_play.py --ladder --matches 400 \
    "${CKPT_ARGS[@]}" --tau 0.35 --no-anti-leak --max-seconds 600 \
    --clip-every 1800 --overlay reader --stop-file $L/STOP >> $L/overnight.out 2>&1
  rc=$?
  why=$(last_stop)
  echo "[sup] exit $rc $(date): $why" >> $L/supervisor.log
  [ -e $L/STOP ] && break
  if [ $restarts -ge $MAX ]; then
    post "ClashAI live run stopped $(date +%H:%M) (rc $rc): ${why:-no reason logged}. Restart limit $MAX reached -- NOT restarting. State $(state)."
    break
  fi
  restarts=$((restarts + 1))
  post "ClashAI live run stopped $(date +%H:%M) (rc $rc): ${why:-no reason logged}. State $(state). Restart $restarts/$MAX in 60 s."
  sleep 60
done
post "ClashAI live ladder run ended $(date +%H:%M). Tally $(state)"
echo "[sup] done $(date)" >> $L/supervisor.log
