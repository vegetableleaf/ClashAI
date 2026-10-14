#!/bin/bash
# Owner 2026-10-13 ~22:30: "Resume A/B1 once live is free (once Roblox is closed on MuMu)". Launched via WMI; logs to
# scratchpad/gauntlet/L74/ab/ab1_resume.out. Waits for Roblox closed (2 checks) + no live process, backs up the Log Bait
# settings someone set at 20:11, sets LIVE_DECK=icebow, removes the dead runner's RUNNING.lock only if its pid is gone,
# resumes run 20261013_094843_05dad0bc, then (once the new lock exists) re-arms the auto-switch watcher.
cd /c/Users/benpe/ClashBot || exit 1
AB=scratchpad/gauntlet/L74/ab; L=scratchpad/gauntlet/L70/live; PY=icebow/.venv/Scripts/python.exe
RID=20261013_094843_05dad0bc
A="A:v1:C:/Users/benpe/ClashBot/icebow/data/bench/rl_royale/newsim_r1/newsim_base_r1_final_grafted.pt:off"
B="B:old:C:/Users/benpe/ClashBot/icebow/data/bench/rl_royale/rseries_r3c/rseries_r3c_u0030_barrel2k_cellref_towerref_w2.pt:off"
ADB="bash scratchpad/gauntlet/L68/live_reader/adb.sh"
log() { echo "$(date '+%F %T') $*"; }
live_running() {   # bracket patterns never match this check's own command line (pkill self-match trap)
  [ "$(powershell -NoProfile -Command "@(Get-CimInstance Win32_Process | Where-Object { \$_.CommandLine -match '[l]ive_play\.py|[r]un_live\.sh' }).Count" | tr -d '\r')" != 0 ]; }
free=0
while [ $free -lt 2 ]; do
  $ADB connect 127.0.0.1:16384 > /dev/null 2>&1
  rb=$($ADB -s 127.0.0.1:16384 shell pidof com.roblox.client 2>/dev/null | tr -d '\r')
  if [ -z "$rb" ] && ! live_running; then free=$((free+1)); else free=0; fi
  log "roblox='${rb}' free_checks=$free"
  [ $free -lt 2 ] && sleep 60
done
BK=$L/backup_pre_ab1_resume_$(date +%Y%m%d_%H%M); mkdir -p $BK
for f in CKPT_OVERRIDE LIVE_FAST LIVE_DECK LIVE_EMOTES LIVE_OPTIONS; do [ -e $L/$f ] && cp -p $L/$f $BK/; done
log "backed up live settings to $BK"
printf 'icebow\n' > $L/LIVE_DECK
old=$(sed -n 's/.*"pid": \([0-9]*\).*/\1/p' $AB/RUNNING.lock 2>/dev/null)
if [ -n "$old" ]; then
  if tasklist //FI "PID eq $old" 2>/dev/null | grep -q " $old "; then log "RUNNING.lock pid $old is ALIVE: not resuming"; exit 2; fi
  mv $AB/RUNNING.lock $AB/RUNNING.lock.dead_$old; log "stale RUNNING.lock (pid $old, gone) moved aside"
fi
log "resuming A/B1 $RID"
$PY $AB/live_ab.py --arm "$A" --arm "$B" --block 5 --total 150 --resume-run $RID >> $AB/ab1_run_20261013.out 2>&1 &
runner=$!
for i in $(seq 1 60); do [ -e $AB/RUNNING.lock ] && break; sleep 5; done
if [ -e $AB/RUNNING.lock ]; then
  log "runner holds RUNNING.lock: $(cat $AB/RUNNING.lock); arming auto-switch"
  $PY $AB/ab_autoswitch.py --run-id $RID --arm "$A" --arm "$B" --total 150 >> $AB/ab1_autoswitch.out 2>&1 &
else
  log "runner did not take RUNNING.lock within 5 min; auto-switch NOT armed"
fi
wait $runner; log "live_ab exited $?"
wait; log "auto-switch exited"
