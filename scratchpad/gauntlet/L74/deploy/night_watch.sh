#!/bin/bash
# Overnight 10-16 watcher: every 10 min list the *DONE* markers on every pod; exit (printing them) as soon as a new one
# appears, so the lead wakes only on events. SEEN = file of already-handled "port:path" lines.
#   night_watch.sh SEEN
SEEN=$1; touch $SEEN
K="-o BatchMode=yes -o ConnectTimeout=20 -i $HOME/.ssh/runpod_clashbot"
PODS="216.81.245.71:37184 64.247.206.76:18881 64.247.206.76:10530 81.27.69.179:37671 81.27.69.177:23419 81.27.69.177:23450 64.247.206.80:18869 64.247.206.120:12331"
while :; do
  new=""
  for hp in $PODS; do
    H=${hp%:*}; P=${hp#*:}
    for f in $(timeout 60 ssh -n $K -p $P root@$H 'find /workspace/results /workspace -maxdepth 3 -name "*DONE*" 2>/dev/null' 2>/dev/null); do
      grep -qxF "$P:$f" $SEEN || new="$new $P:$f"
    done
  done
  [ -n "$new" ] && { for x in $new; do echo "$x"; echo "$x" >> $SEEN; done; exit 0; }
  sleep 600
done
