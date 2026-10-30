#!/bin/bash
# pilot_watch.sh RUN [PORT] -- laptop watcher for a fast-loop pilot (account 3, 10-30). Posts to Discord when the pilot
# process is gone without FINAL, when updates stall > 75 min, every 10th update, and on FINAL (then exits).
# Launch via WMI so it survives the Claude session (memory windows-background-jobs-orphan). Stop: touch STOP_PILOT_WATCH here.
RUN=${1:-pilot_box3}; P=${2:-33308}; cd /c/Users/benpe/ClashBot || exit 1
S="ssh -o BatchMode=yes -o ConnectTimeout=30 -i $HOME/.ssh/runpod_clashbot root@157.157.221.29 -p $P"
PY=icebow/.venv/Scripts/python.exe; STOP=$(dirname "$0")/STOP_PILOT_WATCH; MSG=$(dirname "$0")/.pilot_watch_msg.txt
post() { printf '%s\n' "$1" > "$MSG"; $PY scratchpad/gauntlet/L69/discord/post.py "$MSG" >/dev/null 2>&1; echo "$(date -u +%FT%TZ) $1"; }
last=""; since=$(date +%s); fails=0; stalled=0
while [ ! -f "$STOP" ]; do
  out=$($S "ps -eo args | grep -c '[f]astloop.py.*$RUN'; cat /workspace/loop/pilot/$RUN/FINAL 2>/dev/null || echo none; grep '^\[rl\] u' /workspace/loop/logs/$RUN.log | tail -n 1 | cut -c1-120") || out=""
  if [ -z "$out" ]; then fails=$((fails+1)); [ $fails = 3 ] && post ":rotating_light: $RUN watcher: ssh to $P failed 3x"; sleep 600; continue; fi
  fails=0; n=$(sed -n 1p <<<"$out"); fin=$(sed -n 2p <<<"$out"); line=$(sed -n 3p <<<"$out"); u=$(grep -oE 'u[0-9]{4}' <<<"$line" | head -1)
  if [ "$fin" != none ]; then post "$RUN FINAL: $fin | $line"; exit 0; fi
  if [ "$n" = 0 ]; then                       # 2 misses in a row: run.sh compiles Java before fastloop starts (10-30 false alarm)
    gone=$((${gone:-0}+1)); [ $gone -ge 2 ] && { post ":rotating_light: $RUN process GONE on $P with no FINAL (OOM? check oom_kill). Last: $line"; exit 1; }
    sleep 600; continue
  fi; gone=0
  if [ "$u" != "$last" ]; then
    [ -n "$last" ] && [ $((10#${u#u} % 10)) = 0 ] && post "$RUN $line"
    last=$u; since=$(date +%s); stalled=0
  elif [ $(( $(date +%s) - since )) -gt 4500 ] && [ $stalled = 0 ]; then post ":rotating_light: $RUN no new update for 75 min (last $u)"; stalled=1; fi
  sleep 600
done
