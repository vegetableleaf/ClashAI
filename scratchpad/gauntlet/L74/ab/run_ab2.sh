#!/bin/bash
# A/B2 (owner 2026-10-14: "Heads only grafting goes into future A/B"; launch only on the owner's MuMu go-ahead).
# ONE change vs the live model: A keeps r1's own RL-trained projectile_target_* layers (heads-only graft, SIM +1.46 pp
# [+0.00, +2.92] vs the full graft, rltest/FINDING.md section 3); B = r1 full graft, live since A/B1 (incumbent; an exact
# tie keeps B). Same guards as resume_ab1.sh: waits for Roblox closed in MuMu + no live process, backs up the live
# settings, sets LIVE_DECK=icebow, then arms the auto-switch. live_ab's account guard stops on the bait account.
# Launch via WMI; logs to scratchpad/gauntlet/L74/ab/ab2_launch.out.
cd /c/Users/benpe/ClashBot || exit 1
AB=scratchpad/gauntlet/L74/ab; L=scratchpad/gauntlet/L70/live; PY=icebow/.venv/Scripts/python.exe
A="A:ho:C:/Users/benpe/ClashBot/icebow/data/bench/rl_royale/rltest/r1_u0060_heads_only_graft.pt:off"
B="B:v1:C:/Users/benpe/ClashBot/icebow/data/bench/rl_royale/newsim_r1/newsim_base_r1_final_grafted.pt:off"
ADB="bash scratchpad/gauntlet/L68/live_reader/adb.sh"
log() { echo "$(date '+%F %T') $*"; }
live_running() {   # bracket patterns never match this check's own command line (pkill self-match trap)
  [ "$(powershell -NoProfile -Command "@(Get-CimInstance Win32_Process | Where-Object { \$_.CommandLine -match '[l]ive_play\.py|[r]un_live\.sh' }).Count" | tr -d '\r')" != 0 ]; }
[ -e $AB/RUNNING.lock ] && { log "RUNNING.lock exists: $(cat $AB/RUNNING.lock); not starting"; exit 2; }
free=0
while [ $free -lt 2 ]; do
  $ADB connect 127.0.0.1:16384 > /dev/null 2>&1
  rb=$($ADB -s 127.0.0.1:16384 shell pidof com.roblox.client 2>/dev/null | tr -d '\r')
  if [ -z "$rb" ] && ! live_running; then free=$((free+1)); else free=0; fi
  log "roblox='${rb}' free_checks=$free"
  [ $free -lt 2 ] && sleep 60
done
BK=$L/backup_pre_ab2_$(date +%Y%m%d_%H%M); mkdir -p $BK
for f in CKPT_OVERRIDE LIVE_FAST LIVE_DECK LIVE_EMOTES LIVE_OPTIONS; do [ -e $L/$f ] && cp -p $L/$f $BK/; done
log "backed up live settings to $BK"
printf 'icebow\n' > $L/LIVE_DECK
log "starting A/B2"
$PY $AB/live_ab.py --arm "$A" --arm "$B" --block 5 --total 150 >> $AB/ab2_run.out 2>&1 &
runner=$!
for i in $(seq 1 60); do [ -e $AB/RUNNING.lock ] && break; sleep 5; done
if [ -e $AB/RUNNING.lock ]; then
  RID=$(sed -n 's/.*"run_id": "\([^"]*\)".*/\1/p' $AB/RUNNING.lock)
  log "runner holds RUNNING.lock: $(cat $AB/RUNNING.lock); arming auto-switch for $RID"
  $PY $AB/ab_autoswitch.py --run-id $RID --arm "$A" --arm "$B" --total 150 >> $AB/ab2_autoswitch.out 2>&1 &
else
  log "runner did not take RUNNING.lock within 5 min; auto-switch NOT armed"
fi
wait $runner; log "live_ab exited $?"
wait; log "auto-switch exited"
