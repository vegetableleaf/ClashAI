#!/bin/bash
# Laptop checker for S11 (Log Bait specialist), no Claude usage.  Separate from wk_checker.sh (which may stop at CHAIN_DONE).
#   cd /c/Users/benpe/ClashBot && nohup bash <this file> > /c/Users/benpe/pod_backup_weekend/bait/checker.log 2>&1 &
# Every 10 min: S11_bait/DONE on the pod -> post S11_bait/SUMMARY.txt to Discord (post.py), copy the bait checkpoints + summary + stage log
# to $OUT (verified by size), post once, exit.
cd /c/Users/benpe/ClashBot || exit 1
OUT=/c/Users/benpe/pod_backup_weekend/bait; mkdir -p $OUT
SSH="ssh -o BatchMode=yes -o ConnectTimeout=20 -i $HOME/.ssh/runpod_clashbot -p 17497 root@64.247.206.76"
SCP="scp -q -o BatchMode=yes -i $HOME/.ssh/runpod_clashbot -P 17497"
PY=icebow/.venv/Scripts/python.exe
P=/workspace/results/wk/S11_bait
log() { echo "$(date '+%F %T') $*"; }
while true; do
  if $SSH "test -e $P/DONE" 2>/dev/null; then
    log "S11 DONE on the pod -- copying"
    $SCP "root@64.247.206.76:$P/SUMMARY.txt" "root@64.247.206.76:$P/stage.log" "root@64.247.206.76:$P/train.out" $OUT/ 2>/dev/null
    $SCP -r "root@64.247.206.76:$P/ckpt" $OUT/ 2>/dev/null
    $SSH "cd $P && ls -l ckpt | awk '{print \$5, \$9}'" 2>/dev/null | tr -d '\r' | sort -k2 > $OUT/remote_ckpt_sizes.txt
    ( cd $OUT/ckpt 2>/dev/null && for f in *.pt; do echo "$(stat -c %s "$f") $f"; done ) | sort -k2 > $OUT/local_ckpt_sizes.txt
    if [ -s $OUT/SUMMARY.txt ] && cmp -s <(grep -v ' total' $OUT/remote_ckpt_sizes.txt | grep -v '^ *$') $OUT/local_ckpt_sizes.txt; then
      { cat $OUT/SUMMARY.txt; echo "checkpoints + summary copied to $OUT (sizes verified)"; } > $OUT/_msg.txt
      $PY scratchpad/gauntlet/L69/discord/post.py $OUT/_msg.txt > /dev/null 2>&1 || log "post failed"
      touch $OUT/COPIED_OK; log "done"; exit 0
    fi
    log "copy not verified; retry in 10 min"
  else
    log "S11 not done yet / ssh failed"
  fi
  sleep 600
done
