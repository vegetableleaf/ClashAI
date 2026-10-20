#!/bin/bash
# Owner 10-20 night: wake the lead when the live run gets stuck. Exits (printing why) when, in overnight.out,
#   - the navigator logged >= 6 'unknown' / tap_through lines among its last 12 lines (stuck on an unknown screen), or
#   - a '[nav] run stopped' / 'live run stopped' line appeared since the start, or
#   - no live_play process has run for 10 min while no STOP file exists.
# Takes a screenshot to L70/live/stuck_<time>.png for the diagnosis. Read-only otherwise.
cd /c/Users/benpe/ClashBot
L=scratchpad/gauntlet/L70/live; O=$L/overnight.out
A="/c/Program Files/Netease/MuMuPlayer/nx_device/15.0/shell/adb.exe"
n0=$(wc -l < $O); gone=0
while :; do
  sleep 120
  new=$(tail -n +$((n0 + 1)) $O)
  why=""
  [ "$(tail -12 $O | grep -cE '\] unknown:|tap_through:')" -ge 6 ] && why="stuck on an unknown screen"
  echo "$new" | grep -qE '\[nav\] run stopped|live run stopped' && why="${why:+$why; }run stopped: $(echo "$new" | grep -E '\[nav\] run stopped|live run stopped' | tail -1 | cut -c1-160)"
  if [ "$(powershell -NoProfile -Command "@(Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | Where-Object {\$_.CommandLine -like '*live_play.py*'}).Count")" = 0 ] && [ ! -e $L/STOP ]; then
    gone=$((gone + 1)); [ $gone -ge 5 ] && why="${why:+$why; }no live_play for 10 min"
  else gone=0; fi
  if [ -n "$why" ]; then
    png=$L/stuck_$(date +%H%M).png
    MSYS_NO_PATHCONV=1 timeout 20 "$A" -s 127.0.0.1:16384 exec-out screencap -p > $png 2>/dev/null
    echo "$(date +%H:%M) STUCK: $why  screenshot $png"; tail -6 $O | cut -c1-160; exit 0
  fi
done
