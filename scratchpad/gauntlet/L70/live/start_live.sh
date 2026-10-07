#!/bin/bash
# One command to start the live ladder bot (owner, 2026-10-04). Run from Git Bash:  bash scratchpad/gauntlet/L70/live/start_live.sh
# Starts MuMu, waits for Android, opens Clash Royale, clears the Play Store "update" overlay if present (never updates),
# then starts the supervisor (run_live.sh: restarts up to10x, local logs only). The model = CKPT_OVERRIDE
# unless the owner supplies CKPT explicitly. HAND_READER is opt-in (default file = 0).
# --check loads the selected model offline, before any emulator/ADB/startup side effect.
# Stop between matches: bash scratchpad/gauntlet/L70/live/stop_live.sh
cd /c/Users/benpe/ClashBot
L=scratchpad/gauntlet/L70/live; ADB="bash scratchpad/gauntlet/L68/live_reader/adb.sh"
source "$L/live_config.sh" || exit 2
load_live_config || exit 2
if [ "${1:-}" = --check ]; then
  [ "$#" = 1 ] || { echo "usage: start_live.sh [--check]"; exit 2; }
  echo "hand-reader model input: $HAND_READER_EFFECTIVE"
  "$PY" "$LIVE_ENTRY" "${CKPT_ARGS[@]}" --tau 0.35 --no-anti-leak --device cpu --check
  exit $?
fi
[ "$#" = 0 ] || { echo "usage: start_live.sh [--check]"; exit 2; }
if powershell -NoProfile -Command "@(Get-CimInstance Win32_Process -Filter \"Name='bash.exe'\" | Where-Object {\$_.CommandLine -like '*live/run_live.sh*'}).Count" | grep -q '^[1-9]'; then
  echo "a live supervisor is already running -- not starting a second one"; exit 1; fi
"/c/Program Files/Netease/MuMuPlayer/nx_main/MuMuManager.exe" control -v 0 launch > /dev/null
echo "waiting for MuMu / Android to boot..."
for i in $(seq 1 60); do
  $ADB connect 127.0.0.1:16384 > /dev/null 2>&1
  [ "$($ADB -s 127.0.0.1:16384 shell getprop sys.boot_completed 2>/dev/null | tr -d '\r')" = 1 ] && break; sleep 5; done
$ADB -s 127.0.0.1:16384 shell getprop sys.boot_completed 2>/dev/null | grep -q 1 || { echo "MuMu did not boot -- open it by hand"; exit 1; }
$ADB -s 127.0.0.1:16384 shell monkey -p com.supercell.clashroyale -c android.intent.category.LAUNCHER 1 > /dev/null 2>&1
sleep 15
if $ADB -s 127.0.0.1:16384 shell dumpsys activity activities 2>/dev/null | grep -m1 topResumedActivity | grep -q -v clashroyale; then
  echo "clearing an overlay over the game (Play Store / MuMu ad)"
  $ADB -s 127.0.0.1:16384 shell am force-stop com.mumu.store; $ADB -s 127.0.0.1:16384 shell input keyevent 4; sleep 5; fi
# MuMu's store app can float an advert over the game a little later (seen 2026-10-04: it covered the Battle button)
$ADB -s 127.0.0.1:16384 shell am force-stop com.mumu.store; sleep 30; $ADB -s 127.0.0.1:16384 shell am force-stop com.mumu.store
# owner 2026-10-07: the emulator gets the CPU before training / sim jobs (live_play raises its own priority)
powershell -NoProfile -Command "Get-Process MuMuNxDevice -ErrorAction SilentlyContinue | ForEach-Object { \$_.PriorityClass = 'AboveNormal' }" > /dev/null 2>&1 || true
rm -f $L/STOP
nohup bash $L/run_live.sh > /dev/null 2>&1 &
echo "live started; selected model: ${CKPT:-$(cat $L/CKPT_OVERRIDE 2>/dev/null || echo 'MISSING - live_play will refuse to run')}"
echo "hand-reader model input: $HAND_READER_EFFECTIVE"
echo "watch:  tail -f $L/overnight.out      stop:  bash $L/stop_live.sh"
