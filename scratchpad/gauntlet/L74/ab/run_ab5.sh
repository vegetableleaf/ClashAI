#!/bin/bash
# A/B5 (owner 2026-10-14 ~22:45: "F1 is worth testing out live as soon as we get a chance ... slot a relatively shorter A/B5
# of F1 against a reasonable checkpoint in for tonight"). A/B3 stopped 22:47 (never-press 27-45 vs press 35-35; kept: press).
# A = F1 (rlarm_gae_u0065 + OLD's grafted heads, 693889c3; SIM +6.77 pp [+2.81, +10.73] vs B), B = r1 full graft (fce50ebb,
# live, incumbent: a tie keeps B). Press rule in both (A/B3's base LIVE_OPTIONS, no --iw-press never). 75/arm (overnight).
# The owner analyses it in the morning; the tornado-40 + A/B4 chain is re-armed only after the owner's clip.
# Launch via WMI; logs scratchpad/gauntlet/L74/ab/ab5_launch.out.
cd /c/Users/benpe/ClashBot || exit 1
AB=scratchpad/gauntlet/L74/ab; L=scratchpad/gauntlet/L70/live; PY=icebow/.venv/Scripts/python.exe
A="A:f1:C:/Users/benpe/ClashBot/icebow/data/bench/rl_royale/rlarm_gae/rlarm_gae_u0065_grafted.pt:off"
B="B:v1:C:/Users/benpe/ClashBot/icebow/data/bench/rl_royale/newsim_r1/newsim_base_r1_final_grafted.pt:off"
ADB="bash scratchpad/gauntlet/L68/live_reader/adb.sh"
log() { echo "$(date '+%F %T') $*"; }
post() { printf '%s\n' "$*" > $AB/_ab5_msg.txt; $PY scratchpad/gauntlet/L69/discord/post.py $AB/_ab5_msg.txt > /dev/null 2>&1; }
live_running() {   # bracket patterns never match this check's own command line (pkill self-match trap)
  [ "$(powershell -NoProfile -Command "@(Get-CimInstance Win32_Process | Where-Object { \$_.CommandLine -match '[l]ive_play\.py|[r]un_live\.sh' }).Count" | tr -d '\r')" != 0 ]; }
for i in $(seq 1 180); do [ -e $AB/RUNNING.lock ] || break; [ $i = 1 ] && log "waiting for A/B3 to stop"; sleep 30; done
[ -e $AB/RUNNING.lock ] && { log "A/B3 still running after 90 min; not starting"; post ":rotating_light: A/B5 not started: A/B3 did not stop within 90 min"; exit 2; }
for i in $(seq 1 40); do grep -q "auto-switch exited" $AB/ab3_launch.out && break; sleep 15; done   # A/B3's auto-switch done
log "A/B3 stopped: $(tail -1 $AB/ab3_autoswitch.out)"
rm -f $AB/STOP_AB
free=0
while [ $free -lt 2 ]; do
  $ADB connect 127.0.0.1:16384 > /dev/null 2>&1
  rb=$($ADB -s 127.0.0.1:16384 shell pidof com.roblox.client 2>/dev/null | tr -d '\r')
  if [ -z "$rb" ] && ! live_running; then free=$((free+1)); else free=0; fi
  log "roblox='${rb}' free_checks=$free"
  [ $free -lt 2 ] && sleep 60
done
BK=$L/backup_pre_ab5_$(date +%Y%m%d_%H%M); mkdir -p $BK
for f in CKPT_OVERRIDE LIVE_FAST LIVE_DECK LIVE_EMOTES LIVE_OPTIONS; do [ -e $L/$f ] && cp -p $L/$f $BK/; done
log "backed up live settings to $BK"
printf 'icebow\n' > $L/LIVE_DECK
printf 'off\n' > $L/LIVE_EMOTES
sed -i 's/ --iw-press never//' $L/LIVE_OPTIONS        # press rule in both arms (A/B3 kept B)
grep -q -- "--iw-press never" $L/LIVE_OPTIONS && { log "could not restore the press rule"; exit 3; }
log "starting A/B5"
$PY $AB/live_ab.py --arm "$A" --arm "$B" --block 5 --total 75 >> $AB/ab5_run.out 2>&1 &
runner=$!
for i in $(seq 1 60); do [ -e $AB/RUNNING.lock ] && break; sleep 5; done
if [ -e $AB/RUNNING.lock ]; then
  RID=$(sed -n 's/.*"run_id": "\([^"]*\)".*/\1/p' $AB/RUNNING.lock)
  log "runner holds RUNNING.lock: $(cat $AB/RUNNING.lock); arming auto-switch for $RID"
  post "[ClashAI] A/B5 started (run $RID): A = F1 (per-decision credit, SIM +6.8 pp vs r1) vs B = r1 (live), press rule, 75/arm."
  $PY $AB/ab_autoswitch.py --run-id $RID --arm "$A" --arm "$B" --total 75 >> $AB/ab5_autoswitch.out 2>&1 &
else
  log "runner did not take RUNNING.lock within 5 min; auto-switch NOT armed"; post ":rotating_light: A/B5 runner did not start (ab5_run.out)"
fi
wait $runner; log "live_ab exited $?"
wait; log "auto-switch exited"
