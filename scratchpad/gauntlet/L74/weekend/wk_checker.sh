#!/bin/bash
# Laptop checker for the weekend pod chain (no Claude usage).  Modeled on deploy/pod_drain.sh minus the pod stop.
#   cd /c/Users/benpe/ClashBot && nohup bash <this file> > /c/Users/benpe/pod_backup_weekend/checker.log 2>&1 &
# Every 10 min: new <stage>/DONE on the pod -> post that stage's SUMMARY.txt to Discord.  When CHAIN_DONE appears: stream results (+ the weekend
# checkpoints) back to $OUT, verify, post "weekend queue done".  The webhook is only read by post.py, never printed.
# OWNER-AUTHORISED LIVE ACTION (via the lead, 2026-10-10: "if the recommended path is to revert the model, you may revert. otherwise, nothing changes."):
#   if S2's SUMMARY says "VERDICT: worse: recommend owner revert" AND live still points at the E4 checkpoint (CKPT_OVERRIDE names rdef_e4),
#   copy CKPT_OVERRIDE.pre_e4_backup over CKPT_OVERRIDE and run restart_live.py (stops between matches, restarts, posts).  Nothing else touches live.
cd /c/Users/benpe/ClashBot || exit 1
OUT=/c/Users/benpe/pod_backup_weekend; mkdir -p $OUT; touch $OUT/posted.txt
SSH="ssh -o BatchMode=yes -o ConnectTimeout=20 -i $HOME/.ssh/runpod_clashbot -p 17497 root@64.247.206.76"
PY=icebow/.venv/Scripts/python.exe
LIVE=scratchpad/gauntlet/L70/live
log() { echo "$(date '+%F %T') $*"; }
post() { printf '%s\n' "$1" > $OUT/_msg.txt; $PY scratchpad/gauntlet/L69/discord/post.py $OUT/_msg.txt > /dev/null 2>&1 || log "post failed"; }

if ! grep -q '^start$' $OUT/posted.txt; then
  post "Weekend pod queue started (S2 S4 S3 S8 S7 S9 S10 S5 S6). Live archetype history (result inferred from last-decision towers):
$(cat $OUT/live_archetypes.txt 2>/dev/null | head -c 1500)"
  echo start >> $OUT/posted.txt
fi

revert_if_worse() {   # $1 = S2 summary text
  grep -q 'VERDICT: worse: recommend owner revert' <<< "$1" || return 0
  grep -q '^reverted$' $OUT/posted.txt && return 0
  if grep -q rdef_e4 $LIVE/CKPT_OVERRIDE; then
    cp $LIVE/CKPT_OVERRIDE.pre_e4_backup $LIVE/CKPT_OVERRIDE
    why="S2 (pod SIM, 960 paired): E4 graft worse than the previous live model, 95% CI upper < 0: $(grep -m1 ' - live_old' <<< "$1" | head -c 200)"
    nohup $PY scratchpad/gauntlet/L74/deploy/restart_live.py "revert to the previous model: $why" > $OUT/restart_live.out 2>&1 &
    echo reverted >> $OUT/posted.txt; log "REVERTED live (S2 worse)"
  else
    log "S2 worse but CKPT_OVERRIDE does not name rdef_e4: live left alone"
  fi
}

while true; do
  list=$($SSH 'cd /workspace/results/wk 2>/dev/null && ls -d */DONE CHAIN_DONE 2>/dev/null' 2>/dev/null | tr -d '\r')
  if [ -z "$list" ]; then log "no DONE yet / ssh failed"; fi
  for f in $list; do
    s=${f%%/*}; [ "$s" = CHAIN_DONE ] && continue
    grep -q "^$s\$" $OUT/posted.txt && continue
    sum=$($SSH "cat /workspace/results/wk/$s/SUMMARY.txt" 2>/dev/null | tr -d '\r')
    [ -z "$sum" ] && continue
    post "[weekend $s done] $sum"
    echo $s >> $OUT/posted.txt; log "posted $s"
    [ "$s" = S2 ] && revert_if_worse "$sum"
  done
  if grep -q '^CHAIN_DONE$' <<< "$list"; then
    log "chain done -- streaming results"
    $SSH 'cd /workspace && tar czf - results $(cd clashbot/icebow/data/bench/rl_royale 2>/dev/null && ls -d wk_* | sed "s#^#clashbot/icebow/data/bench/rl_royale/#")' > $OUT/results_weekend.tgz 2>/dev/null
    if tar tzf $OUT/results_weekend.tgz > /dev/null 2>&1; then
      touch $OUT/COPIED_OK; sz=$(du -h $OUT/results_weekend.tgz | cut -f1)
      post "weekend queue done. All results copied and verified ($sz) to $OUT. Pod left running."
      log "done ($sz)"; exit 0
    else
      post "weekend queue done but the copy-back did not verify; retrying in 10 min"; log "tar not verified"
    fi
  fi
  sleep 600
done
