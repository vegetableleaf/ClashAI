#!/usr/bin/env bash
# killtree.sh PID ... -- kill each given PID and all its descendants, by exact PID (no pattern kill)
desc() { local c; for c in $(ps -o pid= --ppid "$1"); do desc "$c"; echo "$c"; done; }
all=""
for p in "$@"; do all="$all $(desc "$p") $p"; done
echo "killing:" $all
kill $all 2>/dev/null
sleep 2
for p in $all; do kill -0 "$p" 2>/dev/null && echo "still alive: $p"; done
true
