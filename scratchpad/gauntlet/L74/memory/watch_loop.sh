#!/bin/bash
# watch_loop.sh KEY SINCE ROUNDS -- laptop: every 45 min, live_watch.py on KEY's live matches since SINCE (habits, Rockets,
# mid-match X-Bow adaptation) -> promote/watch_KEY.log + a Discord summary; ALERT when the leak is back (> 20 s at full per
# match over >= 5 matches) or no new match landed in the round (live stopped?). Owner 10-26: "keep watch of its habits, its
# rocket use, and changes in strategy mid-match".
cd /c/Users/benpe/ClashBot || exit 1
KEY=$1; SINCE=$2; N=${3:-16}; D=scratchpad/gauntlet/L74/memory/promote; OUT=$D/watch_$KEY.log; PY=icebow/.venv/Scripts/python.exe
prev=0
for i in $(seq 1 $N); do
  sleep 2700
  R=$($PY scratchpad/gauntlet/L74/memory/live_watch.py $KEY --since $SINCE 2>/dev/null)
  { echo "=== $(date '+%F %T')"; echo "$R"; } >> $OUT
  n=$(echo "$R" | grep -oE "^## $KEY: [0-9]+" | grep -oE "[0-9]+$"); n=${n:-0}
  leak=$(echo "$R" | grep "seconds at full" | awk '{print $5}')
  alert=""
  [ "$n" -ge 5 ] && awk "BEGIN{exit !(${leak:-0} > 20)}" && alert=":rotating_light: LEAK back: ${leak} s at full / match. "
  [ "$n" = "$prev" ] && alert="${alert}:rotating_light: no new $KEY match in 45 min (live stopped?). "
  prev=$n
  msg=$(echo "$R" | grep -E "matches|win rate|seconds at full|first play|Rockets / match|tower Rockets|lock rate|ADAPT" | sed 's/  */ /g' | tr '\n' ';' | cut -c1-1500)
  printf '%s\n' "[ClashAI] live watch ${KEY}: ${alert}${msg}" > $D/watch.msg
  $PY scratchpad/gauntlet/L69/discord/post.py $D/watch.msg > /dev/null 2>&1
done
