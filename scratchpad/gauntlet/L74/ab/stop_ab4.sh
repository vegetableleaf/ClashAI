#!/bin/bash
# Owner 2026-10-15 ~15:20: "stop A/B4, and keep F1 with the incumbent settings (as long as the tau setting you choose isn't
# clearly worse)". A/B4 (notau vs tau 0.2) had 3-3 vs 3-2 and the SIM said no difference -> keep the incumbent tau 0.2.
#  1. STOP_AB (stop at the block boundary); wait for the runner to release RUNNING.lock (it restores the pre-A/B model and
#     leaves live STOPPED; the auto-switch makes no switch on STOP_AB)
#  2. LIVE_OPTIONS = the pre-A/B4 file (incumbent: tau 0.2 + tornado river on) + --log-frames (parity data, owner plan);
#     CKPT_OVERRIDE must be F1 u65 (693889c3); --check must pass
#  3. restart live (restart_live.py), first-match guard (main account + icebow deck)
cd /c/Users/benpe/ClashBot || exit 1
AB=scratchpad/gauntlet/L74/ab; L=scratchpad/gauntlet/L70/live; PY=icebow/.venv/Scripts/python.exe
log() { echo "$(date '+%F %T') $*"; }
post() { printf '%s\n' "$*" > $AB/_stop_msg.txt; $PY scratchpad/gauntlet/L69/discord/post.py $AB/_stop_msg.txt > /dev/null 2>&1; log "discord: $*"; }
live_running() {
  [ "$(powershell -NoProfile -Command "@(Get-CimInstance Win32_Process | Where-Object { \$_.CommandLine -match '[l]ive_play\.py|[r]un_live\.sh' }).Count" | tr -d '\r')" != 0 ]; }

touch $AB/STOP_AB; log "STOP_AB set"
for i in $(seq 1 120); do [ -e $AB/RUNNING.lock ] || break; sleep 60; done
if [ -e $AB/RUNNING.lock ]; then post ":rotating_light: [stop A/B4] runner still holds RUNNING.lock after 2 h; nothing changed."; exit 2; fi
for i in $(seq 1 60); do live_running || break; sleep 30; done
if live_running; then post ":rotating_light: [stop A/B4] live still running 30 min after the A/B stopped; nothing changed."; exit 3; fi
mv $AB/STOP_AB $AB/STOP_AB.done_$(date +%H%M)
log "A/B4 stopped: $(tail -n 4 $AB/ab4_run.out | head -3 | tr '\n' ' ')"

PRE=$(ls -t $L/LIVE_OPTIONS.pre_ab4_* | head -1)
cp -p $L/LIVE_OPTIONS $L/LIVE_OPTIONS.post_ab4_$(date +%Y%m%d_%H%M)
cp -p $PRE $L/LIVE_OPTIONS
grep -q -- "--log-frames" $L/LIVE_OPTIONS || sed -i 's/$/ --log-frames/' $L/LIVE_OPTIONS
grep -q -- "--tau-threatened 0.2" $L/LIVE_OPTIONS || { post ":rotating_light: [stop A/B4] restored LIVE_OPTIONS lacks tau 0.2; live left stopped."; exit 4; }
SHA=$(sha256sum "$(tr -d '\r\n' < $L/CKPT_OVERRIDE)" | cut -c1-8)
[ "$SHA" = 693889c3 ] || { post ":rotating_light: [stop A/B4] CKPT_OVERRIDE is not F1 u65 (sha $SHA); live left stopped."; exit 5; }
if ! bash $L/start_live.sh icebow --check 2>&1 | tail -1 | grep -q LIVE_CHECK_PASS; then
  post ":rotating_light: [stop A/B4] live --check failed with the restored options; live left stopped."; exit 6
fi
T0=$(date +%Y%m%d_%H%M%S)
$PY scratchpad/gauntlet/L74/deploy/restart_live.py "A/B4 stopped (owner); F1 u65 with incumbent options (tau 0.2, river on) + frame logging" || {
  post ":rotating_light: [stop A/B4] restart failed; check live."; exit 7; }
$PY $AB/first_match_guard.py --after $T0 > $AB/stop_ab4_guard.out 2>&1; rc=$?
log "guard exit $rc: $(tail -1 $AB/stop_ab4_guard.out)"
[ $rc = 0 ] && post "[ClashAI] A/B4 stopped (owner). Live = F1 u65, incumbent options (tau 0.2, river fix on) + per-frame logging for parity; first match passed the guard."
