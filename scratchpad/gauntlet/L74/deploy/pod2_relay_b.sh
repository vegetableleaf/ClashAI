#!/bin/bash
# Pod-2 relay for the CAL re-run (S9XL2b; 2026-10-11), no Claude usage.  Also copies pod 1 CAL/PICK.env to pod 2.  cd /c/Users/benpe/ClashBot && nohup bash <this file> > /c/Users/benpe/pod_backup_weekend/pod2b/relay.log 2>&1 &
# Every 10 min:
#  1. pod 2 S9XL2/DONE (the D5,D6 half of the XL2 drills) -> stream the result files to $OUT, verify, push them into pod 1's
#     /workspace/results/wk/S9XL2, touch POD2_DONE there (releases S10XL2 on pod 1), post "pod 2 drills copied".
#  2. then STOP POD 2 only when: drills copied; S11_bait/DONE on pod 2 AND the S11 checker's bait copy finished (bait/COPIED_OK + ckpts);
#     no [s]earch_s0|[r]l_royale|[f]lock /workspace|[x]l2 process on pod 2 for two checks 10 min apart.  NEVER touches pod 1's power.
cd /c/Users/benpe/ClashBot || exit 1
OUT=/c/Users/benpe/pod_backup_weekend/pod2b; BAIT=/c/Users/benpe/pod_backup_weekend/bait; mkdir -p $OUT
K="-o BatchMode=yes -o ConnectTimeout=20 -o ServerAliveInterval=30 -i $HOME/.ssh/runpod_clashbot"
S1="ssh $K -p 17497 root@64.247.206.76"; S2="ssh $K -p 23358 root@81.27.69.177"
PY=icebow/.venv/Scripts/python.exe
R=/workspace/results/wk; DRILLS="D5 D6"
BUSY='[s]earch_s0|[r]l_royale|[f]lock /workspace|[x]l2'
log() { echo "$(date '+%F %T') $*"; }
post() { printf '%s\n' "$1" > $OUT/_msg.txt; $PY scratchpad/gauntlet/L69/discord/post.py $OUT/_msg.txt > /dev/null 2>&1 || log "post failed"; }

copy_drills() {
  # transform renames the pod-2 copies of files that pod 1 also writes; only D5/D6 trees are taken (pod 1's dump/census/p1 untouched)
  $S2 "cd $R/S9XL2b && tar czf - --transform 's,^SUMMARY.txt,SUMMARY.pod2.txt,;s,^stage.log,stage.pod2.log,;s,^workload.json,workload.pod2.json,' \
       manifest.pod2.json verdicts.pod2.json SUMMARY.txt stage.log workload.json \$(for d in $DRILLS; do ls -d \${d}_search.json {dev,test}/{evo,lad}/\$d 2>/dev/null; done) 2>/dev/null; true" > $OUT/pod2_s9xl2.tgz || return 1
  gzip -t $OUT/pod2_s9xl2.tgz && tar tzf $OUT/pod2_s9xl2.tgz | grep -v '/$' > $OUT/members.txt && [ -s $OUT/members.txt ] || return 1
  $S1 "mkdir -p $R/S9XL2b && tar xzf - -C $R/S9XL2b" < $OUT/pod2_s9xl2.tgz || return 1
  $S1 "cd $R/S9XL2b && while read f; do [ -e \"\$f\" ] || { echo MISSING \$f; exit 1; }; done" < $OUT/members.txt || return 1
  $S1 "touch $R/S9XL2b/POD2_DONE"
}

copied=0; idle=0; [ -e $OUT/COPIED_OK ] && copied=1
while true; do
  # CAL pick (pod 1 CAL/PICK.env, written before CAL/DONE) -> pod 2, where the D5/D6 launcher waits for it
  if ! $S2 "test -s $R/CAL/PICK.env" 2>/dev/null && $S1 "test -e $R/CAL/DONE && test -s $R/CAL/PICK.env" 2>/dev/null; then
    $S1 "cat $R/CAL/PICK.env" | $S2 "mkdir -p $R/CAL && cat > $R/CAL/PICK.env.tmp && mv $R/CAL/PICK.env.tmp $R/CAL/PICK.env" && log "CAL pick copied to pod 2"
  fi
  if [ $copied = 0 ]; then
    if $S2 "test -e $R/S9XL2b/DONE" 2>/dev/null; then
      ok=$($S2 "test -e $R/S9XL2b/SUCCESS && echo SUCCESS || echo FAILED" 2>/dev/null | tr -d '\r')
      if copy_drills; then
        touch $OUT/COPIED_OK; copied=1; log "drills copied ($ok)"
        post "pod 2 drills copied (D5, D6 half of the XL2 drills, stage $ok; $(du -h $OUT/pod2_s9xl2.tgz | cut -f1), verified on the laptop and in pod 1's wk/S9XL2; POD2_DONE set, S10XL2 on pod 1 now waits only for its own half)"
      else log "copy failed; retry in 10 min"; fi
    else log "pod 2 drills not done yet / ssh failed"; fi
  fi
  if [ $copied = 1 ]; then
    if $S2 "test -e $R/S11_bait/DONE" 2>/dev/null && [ -e $BAIT/COPIED_OK ] && ls $BAIT/ckpt/*.pt > /dev/null 2>&1; then
      n=$($S2 "pgrep -fc '$BUSY' || true" 2>/dev/null | tr -d '\r')
      if [ -z "$n" ]; then log "ssh failed"
      else
        if [ "$n" = 0 ]; then idle=$((idle+1)); else idle=0; fi
        log "pod 2 busy processes: $n (quiet checks $idle/2)"
        if [ $idle -ge 2 ]; then
          if $S2 'export $(tr "\0" "\n" < /proc/1/environ | grep -E "^RUNPOD_(API_KEY|POD_ID)="); runpodctl config --apiKey "$RUNPOD_API_KEY" > /dev/null; runpodctl stop pod "$RUNPOD_POD_ID"'; then
            log "pod 2 stop requested"; post "pod 2 stopped (drills copied, S11 copied, idle for two checks)"
          else
            log "pod 2 stop FAILED"; post "pod 2 stop FAILED: please stop it on the RunPod page"
          fi
          exit 0
        fi
      fi
    else log "waiting for S11 DONE + bait copy"; idle=0; fi
  fi
  sleep 600
done
