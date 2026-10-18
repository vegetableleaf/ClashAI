#!/bin/bash
# one poll: journal result count + newest file times on laptop r7* and pods
J="/c/Users/benpe/.claude/projects/C--Users-benpe-ClashBot/f4e7cd66-2122-4134-a1d2-d45291b5bc2a/subagents/workflows/wf_21fd22dc-130/journal.jsonl"
D=/c/Users/benpe/ClashBot/scratchpad/gauntlet/L74/parity/diag_night
echo "now $(date -u '+%F %T') UTC"
echo "journal lines $(wc -l < "$J") results $(grep -c '"type":"result"' "$J") mtime $(date -u -r "$J" '+%T')"
echo "laptop newest: $(find $D/r7a $D/r7b $D/r7c $D/r7d $D/v7_* -type f -printf '%TY-%Tm-%Td %TT %p\n' | sort | tail -1)"
for hp in "216.81.151.5 15617" "64.247.206.76 19899"; do set -- $hp
  echo "pod $1: $(ssh -o ConnectTimeout=20 -i ~/.ssh/runpod_clashbot root@$1 -p $2 'echo $(find /workspace/w_r7* /workspace/w_v7* /workspace/results/r7* /workspace/results/v7_* -type f -printf "%TY-%Tm-%Td %TT %p\n" 2>/dev/null | sort | tail -1); echo " procs=$(pgrep -fc "fights.py|cargo|rustc")"; for f in /workspace/results/v7_*/run.log; do echo " $f: $(ls /workspace/results/$(basename $(dirname $f))/matches 2>/dev/null | wc -l) $(ls $(dirname $f) | grep -E "^(DONE|FAILED)$")"; done')"
done
