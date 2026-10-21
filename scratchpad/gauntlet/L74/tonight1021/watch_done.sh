#!/bin/bash
# watch_done.sh -- tonight 10-21 (lead): poll the 9 successor runs every 10 min; exit (printing "DONE host port run") as soon
# as a run has /workspace/stepd/out/<run>.tgz.sha that is not yet listed in scored.txt. Also exits "DEAD ..." if a run's
# chain is gone without ALL_DONE (crash), so the lead is woken either way.
HERE=$(cd "$(dirname "$0")" && pwd); touch "$HERE/scored.txt"
K="-n -o StrictHostKeyChecking=no -o ConnectTimeout=20 -i $HOME/.ssh/runpod_clashbot"
RUNS="64.247.206.76:13396:tn_otstart_s74 64.247.206.76:14009:tn_otstart_s75 64.247.206.76:19899:tn_w14_s74
157.157.221.29:32621:tn_w14_s75 157.157.221.29:32621:tn_bait_s74 157.157.221.29:32525:tn_w14_s76
157.157.221.29:32525:tn_bait_s75 213.192.2.125:40144:tn_otstart_s76 64.247.206.120:22539:tn_bait_s76"
while true; do
  for x in $RUNS; do
    IFS=: read -r h p r <<< "$x"; grep -qx "$r" "$HERE/scored.txt" && continue
    # RUN = some process names the run (rl_royale --run rlarm_<r>, gap.py --out .../rl_<r>/...); checked twice 30 s apart
    s=$(timeout 90 ssh $K -p $p root@$h "if [ -f /workspace/stepd/out/$r.tgz.sha ]; then echo DONE;
      elif ps -eo args | grep -v grep | grep -q '$r'; then echo RUN;
      else sleep 30; ps -eo args | grep -v grep | grep -q '$r' && echo RUN || echo DEAD; fi" 2>/dev/null)
    case "$s" in DONE|DEAD) echo "$s $h $p $r"; exit 0;; esac
  done
  sleep 600
done
