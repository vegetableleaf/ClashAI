#!/bin/bash
# A/B3 (owner 2026-10-14 ~13:30: "go straight to the ice wizard ability press test. Stop A/B2").
# ONE change: A never presses the Hero Ice Wizard ability (--iw-press never: the button is still watched and
# should_press still runs, no tap); B = the live press rule (incumbent; an exact tie keeps B). Both arms = r1 full graft.
# SIM: never pressing +8 pp vs the live rule (IWDIAG N3 48.1% vs N2 40.0%). Same guards as resume_ab1.sh: waits for
# Roblox closed in MuMu + no live process, backs up the live settings, sets LIVE_DECK=icebow + emotes off, then arms the
# auto-switch (which now carries a winning arm's flags into LIVE_OPTIONS). live_ab's account guard stops on the bait account.
# Launch via WMI; logs to scratchpad/gauntlet/L74/ab/ab3_launch.out.
cd /c/Users/benpe/ClashBot || exit 1
AB=scratchpad/gauntlet/L74/ab; L=scratchpad/gauntlet/L70/live; PY=icebow/.venv/Scripts/python.exe
A="A:nopress:C:/Users/benpe/ClashBot/icebow/data/bench/rl_royale/newsim_r1/newsim_base_r1_final_grafted.pt:off"; AX="A=--iw-press never"
B="B:press:C:/Users/benpe/ClashBot/icebow/data/bench/rl_royale/newsim_r1/newsim_base_r1_final_grafted.pt:off"
ADB="bash scratchpad/gauntlet/L68/live_reader/adb.sh"
log() { echo "$(date '+%F %T') $*"; }
live_running() {   # bracket patterns never match this check's own command line (pkill self-match trap)
  [ "$(powershell -NoProfile -Command "@(Get-CimInstance Win32_Process | Where-Object { \$_.CommandLine -match '[l]ive_play\.py|[r]un_live\.sh' }).Count" | tr -d '\r')" != 0 ]; }
for i in $(seq 1 120); do [ -e $AB/RUNNING.lock ] || break; [ $i = 1 ] && log "waiting for A/B2 to stop ($(cat $AB/RUNNING.lock))"; sleep 30; done
[ -e $AB/RUNNING.lock ] && { log "RUNNING.lock still held after 60 min: $(cat $AB/RUNNING.lock); not starting"; exit 2; }
rm -f $AB/STOP_AB                    # A/B2's stop request; a present STOP_AB makes live_ab refuse to start
free=0
while [ $free -lt 2 ]; do
  $ADB connect 127.0.0.1:16384 > /dev/null 2>&1
  rb=$($ADB -s 127.0.0.1:16384 shell pidof com.roblox.client 2>/dev/null | tr -d '\r')
  if [ -z "$rb" ] && ! live_running; then free=$((free+1)); else free=0; fi
  log "roblox='${rb}' free_checks=$free"
  [ $free -lt 2 ] && sleep 60
done
BK=$L/backup_pre_ab3_$(date +%Y%m%d_%H%M); mkdir -p $BK
for f in CKPT_OVERRIDE LIVE_FAST LIVE_DECK LIVE_EMOTES LIVE_OPTIONS; do [ -e $L/$f ] && cp -p $L/$f $BK/; done
log "backed up live settings to $BK"
printf 'icebow\n' > $L/LIVE_DECK
printf 'off\n' > $L/LIVE_EMOTES     # the A/B measures play (A/B1 ran without; emotes add 0.6 s card-tap holds)
log "starting A/B3"
$PY $AB/live_ab.py --arm "$A" --arm "$B" --arm-extra "$AX" --block 5 --total 150 >> $AB/ab3_run.out 2>&1 &
runner=$!
for i in $(seq 1 60); do [ -e $AB/RUNNING.lock ] && break; sleep 5; done
if [ -e $AB/RUNNING.lock ]; then
  RID=$(sed -n 's/.*"run_id": "\([^"]*\)".*/\1/p' $AB/RUNNING.lock)
  log "runner holds RUNNING.lock: $(cat $AB/RUNNING.lock); arming auto-switch for $RID"
  $PY $AB/ab_autoswitch.py --run-id $RID --arm "$A" --arm "$B" --arm-extra "$AX" --total 150 >> $AB/ab3_autoswitch.out 2>&1 &
else
  log "runner did not take RUNNING.lock within 5 min; auto-switch NOT armed"
fi
wait $runner; log "live_ab exited $?"
wait; log "auto-switch exited"
