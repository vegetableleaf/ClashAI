#!/bin/bash
# Laptop checker for the CAL re-run (no Claude usage).  cd /c/Users/benpe/ClashBot && nohup bash <this file> > /c/Users/benpe/pod_backup_weekend/xl2_checker.log 2>&1 &
# Every 10 min: a new DONE in CAL / S9XL2b / S10XL2b on pod 1 -> post that stage's SUMMARY.txt to Discord (post.py reads the webhook, never printed).  Exits after ICEBOW_DONE.
cd /c/Users/benpe/ClashBot || exit 1
OUT=/c/Users/benpe/pod_backup_weekend; touch $OUT/posted_xl2b.txt
SSH="ssh -o BatchMode=yes -o ConnectTimeout=20 -i $HOME/.ssh/runpod_clashbot -p 17497 root@64.247.206.76"
PY=icebow/.venv/Scripts/python.exe
while true; do
  for s in CAL S9XL2b S10XL2b; do
    grep -q "^$s\$" $OUT/posted_xl2b.txt && continue
    sum=$($SSH "test -e /workspace/results/wk/$s/DONE && cat /workspace/results/wk/$s/SUMMARY.txt" 2>/dev/null | tr -d '\r')
    [ -z "$sum" ] && continue
    printf '%s\n' "[$s done] $sum" > $OUT/_msg_xl2b.txt
    $PY scratchpad/gauntlet/L69/discord/post.py $OUT/_msg_xl2b.txt > /dev/null 2>&1 && echo $s >> $OUT/posted_xl2b.txt
  done
  $SSH 'test -e /workspace/results/wk/ICEBOW_DONE' 2>/dev/null && grep -q '^S10XL2b$' $OUT/posted_xl2b.txt && exit 0
  sleep 600
done
