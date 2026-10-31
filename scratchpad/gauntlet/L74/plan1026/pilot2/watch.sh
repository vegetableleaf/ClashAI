#!/bin/bash
# watch.sh ARM RUN PORT POD_ID [HOST] -- PILOT2 laptop watcher, one per arm (owner 10-31: stop each pod IMMEDIATELY when its
# training concludes; copy back first -- a stopped pod loses /workspace). Launch via WMI with C:\Program Files\Git\bin\bash.exe.
# Every 5 min: mirror each new u%20 checkpoint (sha-checked) to C:/Users/benpe/pod_backup_weekend/pilot2/ARM/; Discord every
# 20th update and on a 45-min stall. End states:
#   FINAL (loop.rc 0, FINAL written, no "[rl] CRASH") -> copy FINAL + every u%20 + logs, sha-checked -> stop THIS pod from inside
#     (runpodctl, key from /proc/1/environ; refused unless RUNPOD_POD_ID == POD_ID) -> Discord.
#   CRASH ("[rl] CRASH", or the loop gone without a clean FINAL) -> copy the same + _latest / crash saves -> Discord alert ->
#     the pod is stopped 30 min later unless the lead creates KEEP_ARM in the backup dir (then it stays up, watcher exits).
# A failed copy never stops the pod (Discord alert instead). Stop the watcher: touch STOP_ARM in the backup dir.
# Test knobs: DRY=1 (no pod stop, no Discord: watch.log only), POLL (s, 300), KEEP_WAIT (min, 30), BACKUP (dir).
ARM=$1; RUN=$2; PORT=$3; POD_ID=$4; HOST=${5:-root@81.27.69.177}
cd /c/Users/benpe/ClashBot || exit 1
B=${BACKUP:-C:/Users/benpe/pod_backup_weekend/pilot2/$ARM}; mkdir -p $B; POLL=${POLL:-300}
S="ssh -o BatchMode=yes -o ConnectTimeout=30 -o ServerAliveInterval=30 -i $HOME/.ssh/runpod_clashbot -p $PORT $HOST"
O=/workspace/loop/p2/$RUN; CK=/workspace/loop/cb/icebow/data/bench/rl_royale/$RUN
PY=icebow/.venv/Scripts/python.exe; MSG=$B/.msg.txt
log() { echo "$(date -u +%FT%TZ) $*" >> $B/watch.log; }
post() { printf '%s\n' "$1" > "$MSG"; [ -n "${DRY:-}" ] || $PY scratchpad/gauntlet/L69/discord/post.py "$MSG" > /dev/null 2>&1; log "POST $1"; }
fetch() {   # pod path -> $B/basename, sha-checked; 0 = ok
  local f=$1 n want got; n=$(basename "$f")
  want=$($S "sha256sum < '$f' | cut -c1-64") || return 1
  [ ${#want} = 64 ] || return 1
  [ -f "$B/$n" ] && [ "$(sha256sum < "$B/$n" | cut -c1-64)" = "$want" ] && return 0
  $S "cat '$f'" > "$B/$n.part" && got=$(sha256sum < "$B/$n.part" | cut -c1-64) && [ "$got" = "$want" ] \
    && mv "$B/$n.part" "$B/$n" && log "copied $n ${want:0:16}" && return 0
  log "COPY FAILED $n (want ${want:0:16} got ${got:0:16})"; return 1
}
mirror20() {   # every u%20 checkpoint on the pod -> laptop
  local f ok=0
  for f in $($S "ls $CK/${RUN}_u[0-9]*.pt 2> /dev/null"); do
    [[ $f =~ _u([0-9]{4})\.pt$ ]] && [ $((10#${BASH_REMATCH[1]} % 20)) = 0 ] || continue
    [ -f "$B/$(basename $f)" ] && continue                 # present = sha-checked when it was copied
    fetch $f || ok=1
  done
  return $ok
}
collect() {   # end of run: logs + FINAL / latest / crash saves + every u%20; 0 = everything copied
  local ok=0 f fin
  for f in loop.log loop.rc pids throughput.jsonl FINAL auto_stop.log auto_stop.out pin.log gpu.log STOP; do
    $S "test -f $O/$f" && { fetch $O/$f || ok=1; }
  done
  fin=$($S "head -1 $O/FINAL 2> /dev/null")
  [ -n "$fin" ] && [ "$fin" != none ] && { $S "test -f '$fin'" || fin=$CK/$(basename "$fin"); fetch "$fin" || ok=1; }
  for f in $($S "ls $CK/${RUN}_latest.pt $CK/${RUN}_crash*.pt 2> /dev/null"); do fetch $f || ok=1; done
  mirror20 || ok=1
  return $ok
}
stop_pod() {
  local out
  [ -n "${DRY:-}" ] && { post "PILOT2 $ARM DRY: would stop pod $POD_ID now"; return 0; }
  out=$($S 'export $(tr "\0" "\n" < /proc/1/environ | grep -E "^RUNPOD_(API_KEY|POD_ID)="); [ "$RUNPOD_POD_ID" = '$POD_ID' ] || { echo "WRONG POD $RUNPOD_POD_ID"; exit 3; }; runpodctl config --apiKey "$RUNPOD_API_KEY" > /dev/null 2>&1; runpodctl stop pod "$RUNPOD_POD_ID" 2>&1' 2>&1)
  log "stop: $out"
  sleep 60
  if $S true 2> /dev/null; then post ":rotating_light: PILOT2 $ARM: pod $POD_ID still answers ssh after the stop ($out) -- STOP IT BY HAND"; return 1; fi
  post "PILOT2 $ARM: pod $POD_ID STOPPED ($out)"; return 0
}
log "watch $ARM $RUN $PORT $POD_ID start"
last=""; since=$(date +%s); stalled=0; fails=0
while [ ! -f $B/STOP_$ARM ]; do
  st=$($S "m=\$(sed -n 's/.*main \([0-9]*\).*/\1/p' $O/pids 2> /dev/null); kill -0 \$m 2> /dev/null && echo alive || echo gone
           cat $O/loop.rc 2> /dev/null || echo none; head -1 $O/FINAL 2> /dev/null || echo none
           echo \"C:\$(grep -m1 '^\[rl\] CRASH' $O/loop.log | cut -c1-200)\"; echo \"U:\$(grep '^\[rl\] u[0-9]' $O/loop.log | tail -n 1 | cut -c1-160)\"") || st=""
  if [ -z "$st" ]; then fails=$((fails + 1)); [ $fails = 3 ] && post ":rotating_light: PILOT2 $ARM watcher: ssh to $PORT failed 3x"; sleep $POLL; continue; fi
  fails=0
  alive=$(sed -n 1p <<< "$st"); rc=$(sed -n 2p <<< "$st"); fin=$(sed -n 3p <<< "$st"); crash=$(sed -n 's/^C://p' <<< "$st"); line=$(sed -n 's/^U://p' <<< "$st")
  u=$(grep -oE '^\[rl\] u[0-9]{4}' <<< "$line" | grep -oE '[0-9]{4}')
  if [ "$alive" = gone ] || [ -n "$crash" ]; then
    sleep 20; [ -n "$crash" ] || rc=$($S "cat $O/loop.rc 2> /dev/null || echo none")
    if [ -z "$crash" ] && [ "$rc" = 0 ] && [ "$fin" != none ]; then
      if collect; then post "PILOT2 $ARM ($RUN) FINAL $fin | $line | copied to $B (sha-checked); stopping pod $POD_ID"; stop_pod; exit 0; fi
      post ":rotating_light: PILOT2 $ARM FINAL but a copy failed (see $B/watch.log) -- pod $POD_ID NOT stopped"; exit 1
    fi
    collect; c=$?
    post ":rotating_light: PILOT2 $ARM ($RUN) CRASHED/EXITED rc=$rc on $PORT: ${crash:-process gone without a clean FINAL} | last $line | copy $([ $c = 0 ] && echo ok || echo INCOMPLETE) -> $B. Pod stops in 30 min unless $B/KEEP_$ARM exists."
    for i in $(seq 1 ${KEEP_WAIT:-30}); do [ -f $B/KEEP_$ARM ] && { post "PILOT2 $ARM: KEEP_$ARM found -- pod $POD_ID left running"; exit 1; }; sleep 60; done
    [ $c = 0 ] || { collect && c=0; }
    [ $c = 0 ] && stop_pod || post ":rotating_light: PILOT2 $ARM: copy still incomplete after 30 min -- pod $POD_ID NOT stopped"
    exit 1
  fi
  mirror20
  if [ -n "$u" ] && [ "$u" != "$last" ]; then
    [ -n "$last" ] && [ $((10#$u / 20)) != $((10#$last / 20)) ] && post "PILOT2 $ARM $line"
    last=$u; since=$(date +%s); stalled=0
  elif [ $(( $(date +%s) - since )) -gt 2700 ] && [ $stalled = 0 ]; then
    post ":rotating_light: PILOT2 $ARM no new update for 45 min (last ${last:-none})"; stalled=1
  fi
  sleep $POLL
done
log "STOP_$ARM found; watcher exits"
