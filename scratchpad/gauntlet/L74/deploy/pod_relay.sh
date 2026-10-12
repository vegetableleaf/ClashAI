#!/bin/bash
# Generic pod relay (2026-10-12), no Claude usage. One per pod:
#   cd /c/Users/benpe/ClashBot && nohup bash scratchpad/gauntlet/L74/deploy/pod_relay.sh NAME HOST PORT STAGE RESDIR >> /c/Users/benpe/pod_backup_weekend/NAME/relay.log 2>&1 &
# Every 10 min: once $RESDIR/DONE exists on the pod, copy $RESDIR (tar over ssh -> gzip -t -> sha256 of every member, remote vs
# laptop; the laptop list is normalised because Git-Bash prints "hash *path"), then post "[weekend STAGE done]" + SUMMARY.txt.
# After that: stop the pod via runpodctl once no job process has run for 12 checks (2 h, owner's idle-pod rule), unless the
# file $OUT/KEEP exists (the lead queued more work). NEVER touches any other pod.
cd /c/Users/benpe/ClashBot || exit 1
NAME=$1 HOST=$2 PORT=$3 STAGE=$4 RESDIR=$5
OUT=/c/Users/benpe/pod_backup_weekend/$NAME; mkdir -p $OUT
K="-o BatchMode=yes -o ConnectTimeout=20 -o ServerAliveInterval=30 -i $HOME/.ssh/runpod_clashbot"
S="ssh $K -p $PORT root@$HOST"
PY=icebow/.venv/Scripts/python.exe
BUSY='[s]earch_s0|[e]1_eval|[l]ivecal|[r]l_royale|[d]river.py|[r]un_adapt|[f]lock /workspace'
log() { echo "$(date '+%F %T') $*"; }
post() { printf '%s\n' "$1" > $OUT/_msg.txt; $PY scratchpad/gauntlet/L69/discord/post.py $OUT/_msg.txt > /dev/null 2>&1 || log "post failed"; }
copy_stage() {
  local p=${RESDIR#/workspace/}
  $S "cd /workspace && tar czf - $p 2>/dev/null; true" > $OUT/$STAGE.tgz || return 1
  gzip -t $OUT/$STAGE.tgz && rm -rf $OUT/x_$STAGE && mkdir -p $OUT/x_$STAGE && tar xzf $OUT/$STAGE.tgz -C $OUT/x_$STAGE || return 1
  tar tzf $OUT/$STAGE.tgz | grep -v '/$' > $OUT/$STAGE.members && grep -q 'SUMMARY.txt$' $OUT/$STAGE.members || return 1
  $S "cd /workspace && while read f; do sha256sum \"\$f\"; done" < $OUT/$STAGE.members | sort -k2 > $OUT/$STAGE.sha.remote || return 1
  (cd $OUT/x_$STAGE && while read f; do sha256sum "$f"; done < $OUT/$STAGE.members | sed 's/ \*/  /' | sort -k2) > $OUT/$STAGE.sha.local || return 1
  cmp -s $OUT/$STAGE.sha.remote $OUT/$STAGE.sha.local && [ -s $OUT/$STAGE.sha.local ]
}
stop_pod() {
  if $S 'export HOME=/dev/shm; export $(tr "\0" "\n" < /proc/1/environ | grep -E "^RUNPOD_(API_KEY|POD_ID)="); runpodctl config --apiKey "$RUNPOD_API_KEY" > /dev/null 2>&1; runpodctl stop pod "$RUNPOD_POD_ID"'; then
    log "pod $NAME stop requested ($1)"; post "pod $NAME stopped ($1)"
  else log "pod $NAME stop FAILED"; post "pod $NAME stop FAILED: please stop it on the RunPod page"; fi
  exit 0
}
quiet=0
while true; do
  if [ ! -e $OUT/COPIED_$STAGE ]; then
    if $S "test -e $RESDIR/DONE" 2>/dev/null; then
      if copy_stage; then
        touch $OUT/COPIED_$STAGE; log "$STAGE copied + verified ($(du -h $OUT/$STAGE.tgz | cut -f1))"
        post "[weekend $STAGE done] $(find $OUT/x_$STAGE -name SUMMARY.txt | head -1 | xargs cat 2>/dev/null)"
      else log "$STAGE copy/verify failed; retry in 10 min"; fi
    else log "$STAGE not done yet / ssh failed"; fi
  fi
  n=$($S "pgrep -fc '$BUSY' || true" 2>/dev/null | tr -d '\r')
  if [ -z "$n" ]; then log "ssh failed"
  else
    if [ "$n" = 0 ]; then quiet=$((quiet+1)); else quiet=0; fi
    log "busy $n, idle checks $quiet/12, keep=$([ -e $OUT/KEEP ] && echo yes || echo no)"
    if [ -e $OUT/COPIED_$STAGE ] && [ $quiet -ge 12 ] && [ ! -e $OUT/KEEP ]; then stop_pod "results copied, idle 2 h"; fi
  fi
  sleep 600
done
